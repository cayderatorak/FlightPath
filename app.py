import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client
from supabase_auth.errors import AuthApiError
import io

# -----------------------
# Supabase Setup
# -----------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -----------------------
# Session State Setup
# -----------------------
if "login_message" not in st.session_state:
    st.session_state["login_message"] = ""
if "user_email" not in st.session_state:
    st.session_state["user_email"] = ""
if "cost_dual" not in st.session_state:
    st.session_state["cost_dual"] = 180.0
if "cost_solo" not in st.session_state:
    st.session_state["cost_solo"] = 120.0
if "rerun_trigger" not in st.session_state:
    st.session_state["rerun_trigger"] = 0

# -----------------------
# Login Section
# -----------------------
if "user_session" not in st.session_state or st.session_state["user_session"] is None:
    st.title("FlightPath Login")
    email = st.text_input("Enter your email for a magic link", value=st.session_state["user_email"])
    if st.button("Send Magic Link"):
        st.session_state["user_email"] = email
        try:
            supabase.auth.sign_in_with_otp({"email": email})
            st.session_state["login_message"] = f"✅ Magic link sent! Check {email} (including spam folder)."
        except AuthApiError as e:
            msg = str(e)
            if "rate limit" in msg.lower():
                st.session_state["login_message"] = "⚠️ Rate limit exceeded. Wait a few minutes."
            else:
                st.session_state["login_message"] = f"⚠️ Login error: {msg}"
    if st.session_state["login_message"]:
        st.info(st.session_state["login_message"])
    st.stop()

# -----------------------
# Fetch Session After Login
# -----------------------
session_resp = supabase.auth.get_session()
st.session_state["user_session"] = session_resp.data.get("session") if session_resp.data else None
if not st.session_state["user_session"]:
    st.warning("Please complete login via your magic link.")
    st.stop()

# -----------------------
# Helper Functions
# -----------------------
def add_flight(date, flight_type, duration, instructor, is_xc, is_night, cost_per_hour):
    supabase.table("flights").insert({
        "date": date,
        "flight_type": flight_type,
        "duration": float(duration),
        "instructor": instructor,
        "is_xc": bool(is_xc),
        "is_night": bool(is_night),
        "cost_per_hour": float(cost_per_hour)
    }).execute()
    st.session_state["rerun_trigger"] += 1

def update_flight(flight_id, **kwargs):
    supabase.table("flights").update(kwargs).eq("id", flight_id).execute()
    st.session_state["rerun_trigger"] += 1

def delete_flight(flight_id):
    supabase.table("flights").delete().eq("id", flight_id).execute()
    st.session_state["rerun_trigger"] += 1

def get_flights():
    resp = supabase.table("flights").select("*").order("date", desc=False).execute()
    data = resp.data if resp.data else []
    df = pd.DataFrame(data)
    for col in ["id","date","flight_type","duration","instructor","is_xc","is_night","cost_per_hour"]:
        if col not in df.columns:
            df[col] = None if col in ["id","date","flight_type","instructor"] else 0
    df["is_xc"] = df["is_xc"].fillna(False).astype(bool)
    df["is_night"] = df["is_night"].fillna(False).astype(bool)
    df["duration"] = df["duration"].fillna(0).astype(float)
    df["cost_per_hour"] = df["cost_per_hour"].fillna(0).astype(float)
    return df

def calculate_totals(df):
    totals = {
        "Dual": df[df['flight_type']=="Dual"]['duration'].sum(),
        "Solo": df[df['flight_type']=="Solo"]['duration'].sum(),
        "XC": df[df['is_xc']==True]['duration'].sum(),
        "Night": df[df['is_night']==True]['duration'].sum(),
        "Total": df['duration'].sum()
    }
    costs = {
        "Dual": (df[df['flight_type']=="Dual"]['duration']*df[df['flight_type']=="Dual"]['cost_per_hour']).sum(),
        "Solo": (df[df['flight_type']=="Solo"]['duration']*df[df['flight_type']=="Solo"]['cost_per_hour']).sum(),
        "XC": (df[df['is_xc']==True]['duration']*df[df['is_xc']==True]['cost_per_hour']).sum(),
        "Night": (df[df['is_night']==True]['duration']*df[df['is_night']==True]['cost_per_hour']).sum(),
        "Total": (df['duration']*df['cost_per_hour']).sum()
    }
    return totals, costs

def estimate_checkride_date(totals, planned_hours_per_week):
    remaining = max(40 - totals.get("Total",0), 0)
    if planned_hours_per_week <= 0:
        return "Enter weekly hours to estimate"
    est_date = datetime.today() + timedelta(weeks=remaining/planned_hours_per_week)
    return est_date.strftime("%b %d, %Y")

# -----------------------
# Streamlit Layout
# -----------------------
st.set_page_config(layout="wide", page_title="FlightPath")
st.title("FlightPath")

# -----------------------
# Sidebar: Settings & Add Flight
# -----------------------
st.sidebar.header("Flight Costs")
st.session_state["cost_dual"] = st.sidebar.number_input("Dual $/hr", value=st.session_state["cost_dual"])
st.session_state["cost_solo"] = st.sidebar.number_input("Solo $/hr", value=st.session_state["cost_solo"])

st.sidebar.header("Add Flight Entry")
date = st.sidebar.date_input("Date", datetime.today())
flight_type = st.sidebar.selectbox("Type", ["Dual","Solo"])
duration = st.sidebar.number_input("Duration (hours)", min_value=0.0, step=0.1)
instructor = st.sidebar.text_input("Instructor (optional)")
is_xc = st.sidebar.checkbox("XC Flight")
is_night = st.sidebar.checkbox("Night Flight")

cost_per_hour = st.session_state["cost_dual"] if flight_type=="Dual" else st.session_state["cost_solo"]
cost_per_hour += 20 if is_xc else 0
cost_per_hour += 30 if is_night else 0

if st.sidebar.button("Add Flight"):
    add_flight(date.strftime("%Y-%m-%d"), flight_type, duration, instructor, is_xc, is_night, cost_per_hour)
    st.success(f"Flight added at ${cost_per_hour}/hr")
    st.experimental_rerun()

# -----------------------
# Main Dashboard
# -----------------------
df = get_flights()
totals, costs = calculate_totals(df)
planned_hours = st.sidebar.number_input("Planned Hours / Week", min_value=0.0, step=1.0)
est_checkride = estimate_checkride_date(totals, planned_hours)

st.subheader("🛫 Flight Progress")
cols = st.columns(4)
categories = ["Dual","Solo","XC","Night"]
for i, cat in enumerate(categories):
    percent = min(totals[cat]/(5 if cat=="XC" else 3 if cat=="Night" else 20),1.0)
    color = "green" if percent>=1 else "yellow" if percent>=0.5 else "red"
    cols[i].metric(f"{cat}", f"{totals[cat]:.1f} hrs", delta=f"{int(percent*100)}%")
    cols[i].markdown(f"<div style='background-color:{color};height:10px;width:{percent*100}%;'></div>", unsafe_allow_html=True)

st.subheader("💰 Cost & Checkride")
st.write(f"Total Cost: ${costs['Total']:.2f}")
st.write(f"Estimated Remaining Cost: ${max(0, (40-totals['Total'])*((costs['Total']/max(1,totals['Total'])) if totals['Total']>0 else st.session_state['cost_dual'])):.2f}")
st.write(f"Estimated Checkride Date: {est_checkride}")

# -----------------------
# Flight Log Table & Export
# -----------------------
st.subheader("✈️ Flight Log")
if not df.empty:
    display_df = df.copy()
    display_df = display_df.drop(columns=["id"])  # remove ID for clarity
    st.dataframe(display_df)
    
    csv = display_df.to_csv(index=False).encode("utf-8")
    st.download_button("Export CSV", data=csv, file_name="flight_log.csv", mime="text/csv")
    
    # Edit/Delete
    st.sidebar.header("Edit/Delete Flight")
    flight_options = [f"{row['date']} | {row['flight_type']} | {row['duration']}h | {row['instructor']}" for _, row in df.iterrows()]
    selected = st.sidebar.selectbox("Select a flight to edit/delete", [""]+flight_options)
    if selected:
        idx = flight_options.index(selected)
        row = df.iloc[idx]
        new_date = st.sidebar.date_input("Date", datetime.strptime(row['date'],"%Y-%m-%d"))
        new_type = st.sidebar.selectbox("Type", ["Dual","Solo"], index=["Dual","Solo"].index(row['flight_type']))
        new_duration = st.sidebar.number_input("Duration", min_value=0.0, step=0.1, value=row['duration'])
        new_instructor = st.sidebar.text_input("Instructor", value=row['instructor'])
        new_is_xc = st.sidebar.checkbox("XC", value=row['is_xc'])
        new_is_night = st.sidebar.checkbox("Night", value=row['is_night'])
        
        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("Update Flight"):
                update_flight(row['id'], date=new_date.strftime("%Y-%m-%d"), flight_type=new_type, 
                              duration=new_duration, instructor=new_instructor, is_xc=new_is_xc, is_night=new_is_night,
                              cost_per_hour=new_duration*(st.session_state["cost_dual"] if new_type=="Dual" else st.session_state["cost_solo"]))
                st.experimental_rerun()
        with col2:
            if st.button("Delete Flight"):
                delete_flight(row['id'])
                st.experimental_rerun()
else:
    st.write("No flights recorded yet.")