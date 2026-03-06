# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# -----------------------
# Supabase setup
# -----------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -----------------------
# Tracks and FAA targets
# -----------------------
TRACKS = {
    "PPL": {"Dual": 20, "Solo": 10, "XC": 5, "Night": 3, "Total": 40},
    "Instrument": {"Dual": 15, "Solo": 5, "XC": 5, "Night": 5, "Total": 30},
    "CPL": {"Dual": 30, "Solo": 10, "XC": 10, "Night": 5, "Total": 50},
    "ATP": {"Dual": 20, "Solo": 10, "XC": 5, "Night": 5, "Total": 40}
}

# -----------------------
# Session state defaults
# -----------------------
if 'dual_cost' not in st.session_state: st.session_state['dual_cost'] = 180.0
if 'solo_cost' not in st.session_state: st.session_state['solo_cost'] = 120.0
if 'user' not in st.session_state: st.session_state['user'] = None
if 'remember_me' not in st.session_state: st.session_state['remember_me'] = False

# -----------------------
# Authentication
# -----------------------
def handle_login():
    if st.session_state['user']:
        return st.session_state['user']

    st.title("✈️ FlightPath Login / Signup")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    remember_me = st.checkbox("Remember Me", value=st.session_state['remember_me'])
    st.session_state['remember_me'] = remember_me

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login"):
            try:
                resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if resp.user:
                    st.session_state['user'] = resp.user
                    if remember_me:
                        st.session_state['remember_token'] = resp.session.access_token
                    st.success("Logged in successfully!")
                    st.experimental_rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")
    with col2:
        if st.button("Signup"):
            try:
                supabase.auth.sign_up({"email": email, "password": password})
                st.success("Account created! Check your email to confirm your account before logging in.")
            except Exception as e:
                st.error(f"Signup failed: {e}")

    st.stop()

# -----------------------
# Persistent login check
# -----------------------
if 'remember_token' in st.session_state:
    try:
        user_resp = supabase.auth.get_user(st.session_state['remember_token'])
        if user_resp and user_resp.user:
            st.session_state['user'] = user_resp.user
    except:
        st.session_state['user'] = None

user = handle_login()

# -----------------------
# Helper functions
# -----------------------
def get_user_flights(track, user_id):
    resp = supabase.table("flights").select("*").eq("track", track).eq("user_id", user_id).order("date", desc=False).execute()
    data = resp.data if resp.data else []
    df = pd.DataFrame(data)
    if df.empty:
        for col in ["date","flight_type","duration","instructor","is_xc","is_night","cost_per_hour"]:
            df[col] = []
    df["is_xc"] = df.get("is_xc", False).fillna(False).astype(bool)
    df["is_night"] = df.get("is_night", False).fillna(False).astype(bool)
    df["duration"] = df.get("duration", 0).fillna(0).astype(float)
    df["cost_per_hour"] = df.get("cost_per_hour", 0).fillna(0).astype(float)
    return df

def calculate_totals(df):
    totals = {cat: df[df['flight_type']==cat]['duration'].sum() for cat in ["Dual","Solo"]}
    totals["XC"] = df[df['is_xc']==True]['duration'].sum()
    totals["Night"] = df[df['is_night']==True]['duration'].sum()
    totals["Total"] = df['duration'].sum()
    costs = {cat: (df[df['flight_type']==cat]['duration']*df[df['flight_type']==cat]['cost_per_hour']).sum() for cat in ["Dual","Solo"]}
    costs["XC"] = (df[df['is_xc']==True]['duration']*df[df['is_xc']==True]['cost_per_hour']).sum()
    costs["Night"] = (df[df['is_night']==True]['duration']*df[df['is_night']==True]['cost_per_hour']).sum()
    costs["Total"] = (df['duration']*df['cost_per_hour']).sum()
    return totals, costs

def calculate_remaining(totals, targets):
    remaining, status = {}, {}
    for cat in targets:
        remaining[cat] = max(targets[cat]-totals.get(cat,0),0)
        if totals.get(cat,0) >= targets[cat]:
            status[cat] = "green"
        elif totals.get(cat,0) >= targets[cat]*0.5:
            status[cat] = "yellow"
        else:
            status[cat] = "red"
    return remaining, status

def estimate_checkride_date(totals, targets, planned_hours_per_week):
    remaining_hours = max(targets["Total"]-totals.get("Total",0),0)
    if planned_hours_per_week <= 0:
        return "Enter weekly hours to estimate"
    est_date = datetime.today() + timedelta(weeks=remaining_hours/planned_hours_per_week)
    return est_date.strftime("%b %d, %Y")

def estimate_remaining_cost(totals, targets, avg_cost_per_hour):
    remaining_hours = max(targets["Total"]-totals.get("Total",0),0)
    return remaining_hours*avg_cost_per_hour

# -----------------------
# Streamlit UI
# -----------------------
st.set_page_config(layout="wide", page_title="FlightPath")
st.sidebar.markdown(f"**Logged in as:** {user.email}")
if st.sidebar.button("Logout"):
    supabase.auth.sign_out()
    st.session_state['user'] = None
    if 'remember_token' in st.session_state: del st.session_state['remember_token']
    st.experimental_rerun()

# Sidebar: Track / Costs / Add Flight
with st.sidebar.expander("Track & Weekly Plan"):
    track_selected = st.selectbox("Select Track", list(TRACKS.keys()))
    planned_hours_per_week = st.number_input("Planned Flight Hours / Week", min_value=0.0, step=1.0, format="%.1f")

with st.sidebar.expander("Flight Costs"):
    st.session_state['dual_cost'] = st.number_input("Dual", value=st.session_state['dual_cost'], step=1.0, format="%.2f")
    st.session_state['solo_cost'] = st.number_input("Solo", value=st.session_state['solo_cost'], step=1.0, format="%.2f")

with st.sidebar.expander("Add Flight"):
    date = st.date_input("Flight Date", datetime.today())
    flight_type = st.selectbox("Flight Type", ["Dual","Solo"])
    duration = st.number_input("Duration (hours)", min_value=0.0, step=0.1, format="%.1f")
    instructor = st.text_input("Instructor (optional)")
    is_xc = st.checkbox("XC Flight")
    is_night = st.checkbox("Night Flight")
    cost_per_hour = st.session_state['dual_cost'] if flight_type=="Dual" else st.session_state['solo_cost']
    cost_per_hour += 20 if is_xc else 0
    cost_per_hour += 30 if is_night else 0
    if st.button("Add Flight"):
        supabase.table("flights").insert({
            "date": date.strftime("%Y-%m-%d"),
            "flight_type": flight_type,
            "duration": float(duration),
            "instructor": instructor,
            "is_xc": bool(is_xc),
            "is_night": bool(is_night),
            "cost_per_hour": float(cost_per_hour),
            "track": track_selected,
            "user_id": user.id
        }).execute()
        st.success(f"Flight Added! ${cost_per_hour:.2f}/hr")
        st.experimental_rerun()

# -----------------------
# Fetch flights & calculations
df = get_user_flights(track_selected, user.id)
totals, costs = calculate_totals(df)
remaining, status = calculate_remaining(totals, TRACKS[track_selected])
avg_cost_per_hour = costs["Total"]/max(totals["Total"],1)
est_checkride = estimate_checkride_date(totals, TRACKS[track_selected], planned_hours_per_week)
est_remaining_cost = estimate_remaining_cost(totals, TRACKS[track_selected], avg_cost_per_hour)

# Dashboard metrics
st.subheader("🛫 Flight Progress & Costs")
col1, col2, col3, col4 = st.columns(4)
col1.metric("✅ Total Hours", f"{totals['Total']:.1f}")
col2.metric("📅 Est. Checkride", est_checkride)
col3.metric("💰 Total Spent", f"${costs['Total']:.2f}")
col4.metric("💰 Remaining Cost", f"${est_remaining_cost:.2f}")

# Colored progress bars
st.subheader("Progress by Category")
for cat in ["Dual","Solo","XC","Night"]:
    percent = min(totals[cat]/TRACKS[track_selected][cat]*100, 100)
    color = status[cat]
    st.markdown(f"**{cat}**: {totals[cat]:.1f}/{TRACKS[track_selected][cat]} hours")
    st.markdown(f"""
        <div style="background-color:#e0e0e0;border-radius:5px;width:100%;height:24px;">
            <div style="width:{percent}%;background-color:{color};height:100%;border-radius:5px;text-align:right;padding-right:5px;font-weight:bold;color:black;">
                {percent:.0f}%
            </div>
        </div>
    """, unsafe_allow_html=True)

# Flight log table with inline edit/delete
st.subheader("✈️ Flight Log")
if not df.empty:
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_selection("single", use_checkbox=True)
    gb.configure_columns(["date","flight_type","duration","instructor","is_xc","is_night","cost_per_hour"], editable=True)
    gb.configure_grid_options(domLayout='normal', suppressRowClickSelection=False)
    gridOptions = gb.build()

    grid_response = AgGrid(
        df,
        gridOptions=gridOptions,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        height=400,
        fit_columns_on_grid_load=True
    )

    updated_df = pd.DataFrame(grid_response['data'])

    # Update backend on edits
    for _, row in updated_df.iterrows():
        supabase.table("flights").update({
            "date": row['date'],
            "flight_type": row['flight_type'],
            "duration": float(row['duration']),
            "instructor": row['instructor'],
            "is_xc": bool(row['is_xc']),
            "is_night": bool(row['is_night']),
            "cost_per_hour": float(row['cost_per_hour'])
        }).eq("user_id", user.id).eq("date", row['date']).eq("flight_type", row['flight_type']).execute()

    # Delete selected row
    selected = grid_response['selected_rows']
    if selected:
        sel = selected[0]
        if st.button(f"Delete selected flight ({sel['date']}, {sel['flight_type']})"):
            supabase.table("flights").delete().eq("user_id", user.id).eq("date", sel['date']).eq("flight_type", sel['flight_type']).execute()
            st.success("Flight deleted!")
            st.experimental_rerun()

    csv = updated_df.to_csv(index=False).encode('utf-8')
    st.download_button("Download Flight Log CSV", data=csv, file_name=f"{track_selected}_flights.csv", mime="text/csv")
else:
    st.write("No flights logged yet.")