# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client
import io

# -----------------------
# Streamlit Secrets
# -----------------------
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
except KeyError:
    st.error("Supabase credentials not found in st.secrets. Please add SUPABASE_URL and SUPABASE_ANON_KEY.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -----------------------
# Session State Defaults
# -----------------------
if "cost_dual" not in st.session_state:
    st.session_state["cost_dual"] = 180.0
if "cost_solo" not in st.session_state:
    st.session_state["cost_solo"] = 120.0

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

def get_flights():
    response = supabase.table("flights").select("*").order("date", desc=False).execute()
    data = response.data if response.data else []
    df = pd.DataFrame(data)

    for col in ["id","date","flight_type","duration","instructor","is_xc","is_night","cost_per_hour","created_at"]:
        if col not in df.columns:
            df[col] = None if col in ["id","date","flight_type","instructor","created_at"] else 0

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

def calculate_remaining(totals, targets):
    remaining = {}
    status = {}
    for cat in targets:
        remaining[cat] = max(targets[cat]-totals.get(cat,0),0)
        if totals.get(cat,0)>=targets[cat]:
            status[cat]="🟢"
        elif totals.get(cat,0)>=targets[cat]*0.5:
            status[cat]="🟡"
        else:
            status[cat]="🔴"
    return remaining,status

def estimate_checkride_date(totals,targets,planned_hours_per_week):
    remaining_hours = max(targets["Total"]-totals.get("Total",0),0)
    if planned_hours_per_week<=0:
        return "Enter weekly hours to estimate"
    est_date = datetime.today() + timedelta(weeks=remaining_hours/planned_hours_per_week)
    return est_date.strftime("%b %d, %Y")

def estimate_remaining_cost(totals, targets, avg_cost_per_hour):
    remaining_hours = max(targets["Total"]-totals.get("Total",0),0)
    return remaining_hours*avg_cost_per_hour

# -----------------------
# Streamlit Layout
# -----------------------
st.set_page_config(layout="wide")
st.title("FlightPath Tracker")

# -----------------------
# Sidebar: Cost & Proficiency
# -----------------------
st.sidebar.header("Default Cost per Hour ($/hr)")
st.session_state["cost_dual"] = st.sidebar.number_input("Dual", value=st.session_state["cost_dual"], step=1.0)
st.session_state["cost_solo"] = st.sidebar.number_input("Solo", value=st.session_state["cost_solo"], step=1.0)
cost_defaults = {"Dual": st.session_state["cost_dual"], "Solo": st.session_state["cost_solo"]}

st.sidebar.markdown("---")
st.sidebar.header("Proficiency Targets")
proficiency_multiplier = st.sidebar.number_input("Proficiency Factor (1.0=FAA min, 1.25=25% extra)", value=1.25, step=0.05)
faa_min = {"Dual":20,"Solo":10,"XC":5,"Night":3,"Total":40}
targets = {cat:int(faa_min[cat]*proficiency_multiplier) for cat in faa_min}

# -----------------------
# Sidebar: Add Flight
# -----------------------
st.sidebar.markdown("---")
st.sidebar.header("Add Flight Entry")
date = st.sidebar.date_input("Flight Date", datetime.today())
flight_type = st.sidebar.selectbox("Flight Type", ["Dual","Solo"])
duration = st.sidebar.number_input("Duration (hours)", min_value=0.0, step=0.1)
instructor = st.sidebar.text_input("Instructor (optional)")
is_xc = st.sidebar.checkbox("XC Flight")
is_night = st.sidebar.checkbox("Night Flight")

cost_per_hour = cost_defaults[flight_type]
cost_per_hour += 20.0 if is_xc else 0
cost_per_hour += 30.0 if is_night else 0

if st.sidebar.button("Add Flight"):
    add_flight(date.strftime("%Y-%m-%d"), flight_type, duration, instructor, is_xc, is_night, cost_per_hour)
    st.sidebar.success(f"Flight Added! ${cost_per_hour}/hr")

# -----------------------
# Main Dashboard
# -----------------------
df = get_flights()
totals,costs = calculate_totals(df)
remaining,status = calculate_remaining(totals,targets)
avg_cost_per_hour = costs["Total"]/max(totals["Total"],1)
est_checkride = estimate_checkride_date(totals,targets,planned_hours_per_week=5)  # default 5 h/week
est_remaining_cost = estimate_remaining_cost(totals,targets,avg_cost_per_hour)

# Colored Progress Cards
st.subheader("🛫 Flight Progress & Dashboard")
col1,col2,col3,col4,col5 = st.columns(5)
col1.metric("✅ Total Hours", f"{totals['Total']:.1f}")
col2.metric("💰 Total Cost", f"${costs['Total']:.2f}")
col3.metric("📅 Est. Checkride", est_checkride)
col4.metric("🕒 Remaining Hours", f"{remaining['Total']:.1f}")
col5.metric("💵 Remaining Cost", f"${est_remaining_cost:.2f}")

# Flight Progress Bars
st.subheader("Flight Progress by Category")
for cat in ["Dual","Solo","XC","Night"]:
    percent = min(totals[cat]/targets[cat],1.0)
    color = "green" if status[cat]=="🟢" else "yellow" if status[cat]=="🟡" else "red"
    st.write(f"**{cat}**: {totals[cat]:.1f}/{targets[cat]} hours")
    st.progress(percent)

# -----------------------
# Export Flight Log
# -----------------------
st.subheader("Export Flight Log")
if not df.empty:
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    st.download_button("Download CSV", csv_buffer.getvalue(), file_name="flight_log.csv", mime="text/csv")
else:
    st.write("No flights yet.")