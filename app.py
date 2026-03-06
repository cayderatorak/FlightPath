import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client

# -----------------------
# Supabase
# -----------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -----------------------
# Initialize session_state
# -----------------------
if "cost_dual" not in st.session_state:
    st.session_state.cost_dual = 180.0
if "cost_solo" not in st.session_state:
    st.session_state.cost_solo = 120.0

# -----------------------
# Sidebar: Default costs & proficiency
# -----------------------
st.sidebar.header("Default Cost per Hour ($/hr)")
st.session_state.cost_dual = st.sidebar.number_input("Dual", value=st.session_state.cost_dual, step=1.0)
st.session_state.cost_solo = st.sidebar.number_input("Solo", value=st.session_state.cost_solo, step=1.0)

st.sidebar.markdown("---")
st.sidebar.header("Proficiency Targets")
proficiency_factor = st.sidebar.number_input("Proficiency Multiplier (1.0 = FAA Min)", value=1.25, step=0.05)

faa_min = {"Dual":20,"Solo":10,"XC":5,"Night":3,"Total":40}
targets = {cat:int(faa_min[cat]*proficiency_factor) for cat in faa_min}

# -----------------------
# Add Flight Entry
# -----------------------
st.sidebar.header("Add Flight")
date = st.sidebar.date_input("Date", datetime.today())
flight_type = st.sidebar.selectbox("Flight Type", ["Dual","Solo"])
duration = st.sidebar.number_input("Duration (hours)", min_value=0.0, step=0.1)
instructor = st.sidebar.text_input("Instructor")
is_xc = st.sidebar.checkbox("XC Flight")
is_night = st.sidebar.checkbox("Night Flight")

cost_per_hour = (st.session_state.cost_dual if flight_type=="Dual" else st.session_state.cost_solo) + \
                (20 if is_xc else 0) + (30 if is_night else 0)

if st.sidebar.button("Add Flight"):
    supabase.table("flights").insert({
        "date": date.strftime("%Y-%m-%d"),
        "flight_type": flight_type,
        "duration": float(duration),
        "instructor": instructor,
        "is_xc": bool(is_xc),
        "is_night": bool(is_night),
        "cost_per_hour": float(cost_per_hour)
    }).execute()
    st.sidebar.success(f"Flight Added! ${cost_per_hour}/hr")

# -----------------------
# Get Flights
# -----------------------
def get_flights():
    resp = supabase.table("flights").select("*").order("date", desc=False).execute()
    data = resp.data if resp.data else []
    df = pd.DataFrame(data)
    for col in ["id","student_id","date","flight_type","duration","instructor","is_xc","is_night","cost_per_hour","created_at"]:
        if col not in df.columns:
            df[col] = None if col in ["id","student_id","date","flight_type","instructor","created_at"] else 0
    df["is_xc"] = df["is_xc"].fillna(False).astype(bool)
    df["is_night"] = df["is_night"].fillna(False).astype(bool)
    df["duration"] = df["duration"].fillna(0).astype(float)
    df["cost_per_hour"] = df["cost_per_hour"].fillna(0).astype(float)
    return df

df = get_flights()

# -----------------------
# Calculate Totals
# -----------------------
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

# -----------------------
# Remaining & Status
# -----------------------
remaining = {}
status = {}
for cat in targets:
    remaining[cat] = max(targets[cat]-totals.get(cat,0),0)
    if totals.get(cat,0) >= targets[cat]:
        status[cat] = "🟢"
    elif totals.get(cat,0) >= targets[cat]*0.5:
        status[cat] = "🟡"
    else:
        status[cat] = "🔴"

# -----------------------
# Estimated Checkride & Remaining Cost
# -----------------------
planned_hours_per_week = st.sidebar.number_input("Planned Hours / Week", min_value=0.0, step=1.0)
remaining_hours = max(targets["Total"]-totals.get("Total",0),0)
if planned_hours_per_week > 0:
    est_checkride = datetime.today() + timedelta(weeks=remaining_hours/planned_hours_per_week)
    est_checkride = est_checkride.strftime("%b %d, %Y")
else:
    est_checkride = "Enter weekly hours"

avg_cost_per_hour = costs["Total"]/max(totals["Total"],1)
est_remaining_cost = remaining_hours*avg_cost_per_hour

# -----------------------
# Dashboard Cards
# -----------------------
st.title("FlightPath")

col1, col2, col3, col4 = st.columns(4)
col1.metric("✅ Total Hours", f"{totals['Total']:.1f}")
col2.metric("📅 Est. Checkride", est_checkride)
col3.metric("💰 Total Spent", f"${costs['Total']:.2f}")
col4.metric("💸 Remaining Cost", f"${est_remaining_cost:.2f}")

# -----------------------
# Colored Progress Bars
# -----------------------
st.subheader("Flight Progress")
for cat in ["Dual","Solo","XC","Night"]:
    percent = min(totals[cat]/targets[cat],1.0)
    color_desc = {"🟢":"green","🟡":"yellow","🔴":"red"}[status[cat]]
    st.write(f"**{cat}**: {totals[cat]:.1f}/{targets[cat]} hours")
    st.progress(percent)

# -----------------------
# Flight Log Table
# -----------------------
st.subheader("Logged Flights")
if not df.empty:
    display_df = df.drop(columns=[c for c in ["id","created_at"] if c in df.columns])
    st.dataframe(display_df.sort_values("date", ascending=True))
else:
    st.write("No flights logged yet.")

# -----------------------
# Export CSV
# -----------------------
csv = df.to_csv(index=False).encode("utf-8")
st.download_button(label="Export Flight Log CSV", data=csv, file_name="flight_log.csv", mime="text/csv")