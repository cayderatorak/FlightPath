import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
from supabase import create_client

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="FlightPath", page_icon="✈️", layout="wide")
st.title("✈️ FlightPath")

# -------------------------
# Session state for rerun and cost persistence
# -------------------------
if 'rerun_trigger' not in st.session_state:
    st.session_state['rerun_trigger'] = 0

# Initialize cost values if not already in session_state
if "cost_dual" not in st.session_state:
    st.session_state["cost_dual"] = 180.0
if "cost_solo" not in st.session_state:
    st.session_state["cost_solo"] = 120.0
if "xc_surcharge" not in st.session_state:
    st.session_state["xc_surcharge"] = 20.0
if "night_surcharge" not in st.session_state:
    st.session_state["night_surcharge"] = 15.0
if "planned_hours_per_week" not in st.session_state:
    st.session_state["planned_hours_per_week"] = 5.0

# -------------------------
# Supabase
# -------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------
# FAA minimums
# -------------------------
FAA_TOTAL = 40
FAA_DUAL = 20
FAA_SOLO = 10
FAA_XC = 5
FAA_NIGHT = 3

# -------------------------
# Sidebar: Navigation & Inputs
# -------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Dashboard", "Log Flight", "Flight Log", "Reports"])

st.sidebar.header("Default Cost per Hour ($/hr)")
st.sidebar.number_input("Dual", min_value=0.0, step=1.0, key="cost_dual")
st.sidebar.number_input("Solo", min_value=0.0, step=1.0, key="cost_solo")
st.sidebar.number_input("XC Surcharge", min_value=0.0, step=1.0, key="xc_surcharge")
st.sidebar.number_input("Night Surcharge", min_value=0.0, step=1.0, key="night_surcharge")
st.sidebar.number_input(
    "Planned Flight Hours / Week",
    min_value=0.0,
    step=1.0,
    key="planned_hours_per_week"
)

# -------------------------
# Load flights
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

remaining_hours = max(FAA_TOTAL - total_hours,0)
est_checkride_date = "N/A"
if st.session_state["planned_hours_per_week"] > 0:
    est_checkride_date = (date.today() + timedelta(weeks=remaining_hours/st.session_state["planned_hours_per_week"])).strftime("%b %d, %Y")
avg_cost_per_hour = total_cost / max(total_hours,1)
est_remaining_cost = remaining_hours * avg_cost_per_hour

# -------------------------
# Dashboard
# -------------------------
if page=="Dashboard":
    st.header("📊 Dashboard")
    # Cards
    st.markdown(f"""
    <div style="display:flex; gap:20px; flex-wrap:wrap;">
        <div style="flex:1; background:#1f77b4; color:white; padding:20px; border-radius:10px; text-align:center;">
            <h4>Total Hours</h4><h2>{round(total_hours,1)} hrs</h2>
        </div>
        <div style="flex:1; background:#ff7f0e; color:white; padding:20px; border-radius:10px; text-align:center;">
            <h4>Total Cost</h4><h2>${int(total_cost)}</h2>
        </div>
        <div style="flex:1; background:#2ca02c; color:white; padding:20px; border-radius:10px; text-align:center;">
            <h4>Estimated Checkride</h4><h2>{est_checkride_date}</h2>
        </div>
        <div style="flex:1; background:#d62728; color:white; padding:20px; border-radius:10px; text-align:center;">
            <h4>Est. Remaining Cost</h4><h2>${int(est_remaining_cost)}</h2>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # FAA Progress with circular gauges
    st.subheader("FAA Requirement Progress")
    progress_data = {
        "Category":["Dual","Solo","XC","Night","Total"],
        "Completed":[dual_hours, solo_hours, xc_hours, night_hours, total_hours],
        "Target":[FAA_DUAL, FAA_SOLO, FAA_XC, FAA_NIGHT, FAA_TOTAL]
    }
    progress_df = pd.DataFrame(progress_data)
    for idx,row in progress_df.iterrows():
        fig = px.pie(
            names=["Completed","Remaining"],
            values=[row["Completed"], max(row["Target"]-row["Completed"],0)],
            hole=0.6,
            title=f"{row['Category']} ({row['Completed']}/{row['Target']} hrs)"
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Flight type distribution chart
    if not df.empty:
        fig1 = px.pie(df, names="flight_type", values="duration", title="Flight Type Distribution")
        st.plotly_chart(fig1, use_container_width=True)

        df_sorted = df.sort_values("date")
        df_cum = df_sorted.groupby("date")["duration"].sum().cumsum().reset_index()
        fig2 = px.line(df_cum, x="date", y="duration", title="Cumulative Hours Over Time")
        st.plotly_chart(fig2, use_container_width=True)

# -------------------------
# Log Flight
# -------------------------
if page=="Log Flight":
    st.header("📝 Log New Flight")
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
            base_cost = st.session_state["cost_dual"] if flight_type=="Dual" else st.session_state["cost_solo"]
            if is_xc: base_cost += st.session_state["xc_surcharge"]
            if is_night: base_cost += st.session_state["night_surcharge"]
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
            st.session_state['rerun_trigger'] += 1

# -------------------------
# Editable Flight Log
# -------------------------
if page=="Flight Log":
    st.header("📋 Flight Log")
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
    st.header("📄 Reports")
    if not df.empty:
        csv = df.drop(columns=["id"]).to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, "flight_log.csv", "text/csv")
    else:
        st.info("No data available yet.")