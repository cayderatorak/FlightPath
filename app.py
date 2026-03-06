import streamlit as st
import pandas as pd
from datetime import date, timedelta
from supabase import create_client

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="FlightPath", page_icon="✈️", layout="wide")
st.title("✈️ FlightPath")

# -------------------------
# Supabase
# -------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------
# Initialize session_state for rerun
# -------------------------
if 'rerun_trigger' not in st.session_state:
    st.session_state['rerun_trigger'] = 0

# -------------------------
# FAA Requirements
# -------------------------
FAA_TOTAL = 40
FAA_DUAL = 20
FAA_SOLO = 10
FAA_XC = 5
FAA_NIGHT = 3

# -------------------------
# Sidebar: Cost Defaults & Navigation
# -------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Dashboard", "Log Flight", "Flight Log", "Reports"])

st.sidebar.header("Default Cost per Hour ($/hr)")
cost_dual = st.sidebar.number_input("Dual", value=180.0, step=1.0)
cost_solo = st.sidebar.number_input("Solo", value=120.0, step=1.0)
xc_surcharge = st.sidebar.number_input("XC Surcharge", value=20.0, step=1.0)
night_surcharge = st.sidebar.number_input("Night Surcharge", value=15.0, step=1.0)

planned_hours_per_week = st.sidebar.number_input("Planned Flight Hours / Week", min_value=0.0, step=1.0)

# -------------------------
# Load flights from Supabase
# -------------------------
def load_flights():
    resp = supabase.table("flights").select("*").execute()
    data = resp.data if resp.data else []
    return pd.DataFrame(data)

df = load_flights()

# -------------------------
# Calculations
# -------------------------
if not df.empty:
    df["flight_cost"] = df["duration"] * df["cost_per_hour"]
    total_hours = df["duration"].sum()
    dual_hours = df[df["flight_type"]=="Dual"]["duration"].sum()
    solo_hours = df[df["flight_type"]=="Solo"]["duration"].sum()
    xc_hours = df[df["is_xc"]==True]["duration"].sum()
    night_hours = df[df["is_night"]==True]["duration"].sum()
    total_cost = df["flight_cost"].sum()
else:
    total_hours = dual_hours = solo_hours = xc_hours = night_hours = total_cost = 0

readiness = min(total_hours / FAA_TOTAL * 100, 100)
remaining_hours = max(FAA_TOTAL - total_hours,0)
est_checkride_date = "N/A"
if planned_hours_per_week > 0:
    est_checkride_date = (date.today() + timedelta(weeks=remaining_hours/planned_hours_per_week)).strftime("%b %d, %Y")
avg_cost_per_hour = total_cost / max(total_hours,1)
est_remaining_cost = remaining_hours * avg_cost_per_hour

# -------------------------
# Dashboard
# -------------------------
if page=="Dashboard":
    st.header("Dashboard")

    # Cards
    st.markdown(f"""
    <div style="display:flex; gap:20px; flex-wrap:wrap;">
        <div style="flex:1; background:#111; color:white; padding:20px; border-radius:10px; text-align:center;">
            <h3>Total Hours</h3><h2>{round(total_hours,1)} hrs</h2>
        </div>
        <div style="flex:1; background:#111; color:white; padding:20px; border-radius:10px; text-align:center;">
            <h3>Readiness</h3><h2>{int(readiness)}%</h2>
        </div>
        <div style="flex:1; background:#111; color:white; padding:20px; border-radius:10px; text-align:center;">
            <h3>Total Cost</h3><h2>${int(total_cost)}</h2>
        </div>
        <div style="flex:1; background:#111; color:white; padding:20px; border-radius:10px; text-align:center;">
            <h3>Est. Checkride</h3><h2>{est_checkride_date}</h2>
        </div>
        <div style="flex:1; background:#111; color:white; padding:20px; border-radius:10px; text-align:center;">
            <h3>Est. Remaining Cost</h3><h2>${int(est_remaining_cost)}</h2>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # FAA Progress
    st.subheader("FAA Requirement Progress")
    def color_progress(value,max_value):
        percent=value/max_value
        if percent>=1: color="green"
        elif percent>=0.5: color="yellow"
        else: color="red"
        st.markdown(f"{value}/{max_value} hrs - <span style='color:{color};'>●</span>", unsafe_allow_html=True)
        st.progress(min(percent,1.0))

    color_progress(dual_hours, FAA_DUAL)
    color_progress(solo_hours, FAA_SOLO)
    color_progress(xc_hours, FAA_XC)
    color_progress(night_hours, FAA_NIGHT)
    color_progress(total_hours, FAA_TOTAL)

# -------------------------
# Log Flight
# -------------------------
if page=="Log Flight":
    st.header("Log New Flight")
    with st.form("flight_form"):
        col1,col2 = st.columns(2)
        with col1:
            flight_date = st.date_input("Date", date.today())
            flight_type = st.selectbox("Flight Type", ["Dual","Solo"])
            duration = st.number_input("Duration (hours)", min_value=0.1, step=0.1)
        with col2:
            instructor = st.text_input("Instructor")
            is_xc = st.checkbox("Cross Country")
            is_night = st.checkbox("Night")
        submitted = st.form_submit_button("Add Flight")
        if submitted:
            base_cost = cost_dual if flight_type=="Dual" else cost_solo
            if is_xc: base_cost += xc_surcharge
            if is_night: base_cost += night_surcharge
            supabase.table("flights").insert({
                "date":str(flight_date),
                "flight_type":flight_type,
                "duration":float(duration),
                "instructor":instructor,
                "is_xc":is_xc,
                "is_night":is_night,
                "cost_per_hour":base_cost
            }).execute()
            st.success(f"Flight logged! ${base_cost}/hr")
            st.session_state['rerun_trigger'] += 1  # trigger rerun

# -------------------------
# Editable Flight Log
# -------------------------
if page=="Flight Log":
    st.header("Flight Log")
    if not df.empty:
        df_sorted = df.sort_values("date", ascending=False)
        for idx,row in df_sorted.iterrows():
            label = f"{row['date']} | {row['flight_type']} | {row['duration']} hrs | Instructor: {row.get('instructor','')}"
            with st.expander(label):
                new_duration = st.number_input("Duration", value=float(row["duration"]), key=f"dur{idx}")
                new_type = st.selectbox("Flight Type", ["Dual","Solo"], index=0 if row["flight_type"]=="Dual" else 1, key=f"type{idx}")
                new_xc = st.checkbox("Cross Country", value=row["is_xc"], key=f"xc{idx}")
                new_night = st.checkbox("Night", value=row["is_night"], key=f"night{idx}")
                col1,col2 = st.columns(2)
                if col1.button("Update", key=f"update{idx}"):
                    supabase.table("flights").update({
                        "duration":new_duration,
                        "flight_type":new_type,
                        "is_xc":new_xc,
                        "is_night":new_night
                    }).eq("id", row["id"]).execute()
                    st.success("Flight updated")
                    st.session_state['rerun_trigger'] += 1
                if col2.button("Delete", key=f"delete{idx}"):
                    supabase.table("flights").delete().eq("id", row["id"]).execute()
                    st.warning("Flight deleted")
                    st.session_state['rerun_trigger'] += 1
    else:
        st.info("No flights logged yet.")

# -------------------------
# Reports
# -------------------------
if page=="Reports":
    st.header("Reports")
    if not df.empty:
        csv = df.drop(columns=["id"]).to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "flight_log.csv", "text/csv")
    else:
        st.info("No data available yet.")