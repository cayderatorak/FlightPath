import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
from supabase import create_client

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------

st.set_page_config(
    page_title="FlightPath",
    page_icon="✈️",
    layout="wide"
)

st.title("✈️ FlightPath")
st.caption("Smart training tracker for student pilots")

# --------------------------------------------------
# STYLING
# --------------------------------------------------

st.markdown("""
<style>
[data-testid="stMetric"] {
    background-color:#111;
    border:1px solid #333;
    padding:15px;
    border-radius:10px;
}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# SUPABASE CONNECTION
# --------------------------------------------------

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --------------------------------------------------
# FAA REQUIREMENTS (PPL)
# --------------------------------------------------

FAA_TOTAL = 40
FAA_DUAL = 20
FAA_SOLO = 10
FAA_XC = 5
FAA_NIGHT = 3

# --------------------------------------------------
# COST SETTINGS
# --------------------------------------------------

COST_DUAL = 180
COST_SOLO = 120
XC_SURCHARGE = 20
NIGHT_SURCHARGE = 15

# --------------------------------------------------
# SIDEBAR NAV
# --------------------------------------------------

st.sidebar.title("✈️ FlightPath")

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Log Flight",
        "Flight Log",
        "Reports"
    ]
)

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

def load_flights():

    response = supabase.table("flights").select("*").execute()

    data = response.data if response.data else []

    return pd.DataFrame(data)

df = load_flights()

# --------------------------------------------------
# CALCULATIONS
# --------------------------------------------------

if not df.empty:

    total_hours = df["duration"].sum()

    dual_hours = df[df["flight_type"] == "Dual"]["duration"].sum()

    solo_hours = df[df["flight_type"] == "Solo"]["duration"].sum()

    xc_hours = df[df["is_xc"] == True]["duration"].sum()

    night_hours = df[df["is_night"] == True]["duration"].sum()

    df["flight_cost"] = df["duration"] * df["cost_per_hour"]

    total_cost = df["flight_cost"].sum()

else:

    total_hours = dual_hours = solo_hours = xc_hours = night_hours = 0
    total_cost = 0

readiness = min((total_hours / FAA_TOTAL) * 100, 100)

# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

if page == "Dashboard":

    st.header("Dashboard")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total Flight Hours",
        f"{round(total_hours,1)} hrs"
    )

    col2.metric(
        "Checkride Readiness",
        f"{int(readiness)}%"
    )

    col3.metric(
        "Training Cost",
        f"${int(total_cost)}"
    )

    st.divider()

    colA, colB = st.columns(2)

    with colA:

        st.subheader("Checkride Readiness")

        gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=readiness,
            title={"text": "FAA Readiness"},
            gauge={
                "axis": {"range":[0,100]},
                "bar":{"color":"green"},
                "steps":[
                    {"range":[0,40],"color":"red"},
                    {"range":[40,70],"color":"orange"},
                    {"range":[70,100],"color":"green"}
                ]
            }
        ))

        st.plotly_chart(gauge, use_container_width=True)

    with colB:

        st.subheader("Training Distribution")

        chart_data = pd.DataFrame({
            "Type":["Dual","Solo","Cross Country","Night"],
            "Hours":[dual_hours, solo_hours, xc_hours, night_hours]
        })

        fig = px.bar(
            chart_data,
            x="Type",
            y="Hours",
            color="Type"
        )

        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("FAA Requirement Progress")

    st.write("Total Hours")
    st.progress(min(total_hours/FAA_TOTAL,1.0))

    st.write("Dual Instruction")
    st.progress(min(dual_hours/FAA_DUAL,1.0))

    st.write("Solo Hours")
    st.progress(min(solo_hours/FAA_SOLO,1.0))

    st.write("Night Hours")
    st.progress(min(night_hours/FAA_NIGHT,1.0))

    st.write("Cross Country")
    st.progress(min(xc_hours/FAA_XC,1.0))

    st.divider()

    st.subheader("Training Insight")

    if night_hours < FAA_NIGHT:

        st.warning(f"You still need {round(FAA_NIGHT-night_hours,1)} night hours")

    elif xc_hours < FAA_XC:

        st.warning(f"You still need {round(FAA_XC-xc_hours,1)} cross country hours")

    elif total_hours < FAA_TOTAL:

        st.info(f"You need {round(FAA_TOTAL-total_hours,1)} more hours")

    else:

        st.success("You're close to meeting FAA training minimums!")

    st.divider()

    st.subheader("Recent Flights")

    if not df.empty:

        recent = df.sort_values("date", ascending=False).head(5)

        st.dataframe(recent, use_container_width=True)

    else:

        st.info("No flights logged yet.")

# --------------------------------------------------
# LOG FLIGHT
# --------------------------------------------------

if page == "Log Flight":

    st.header("Log New Flight")

    with st.form("flight_form"):

        col1, col2 = st.columns(2)

        with col1:

            flight_date = st.date_input("Date", date.today())

            flight_type = st.selectbox(
                "Flight Type",
                ["Dual","Solo"]
            )

            duration = st.number_input(
                "Flight Duration (hours)",
                min_value=0.1,
                step=0.1
            )

        with col2:

            instructor = st.text_input("Instructor")

            is_xc = st.checkbox("Cross Country")

            is_night = st.checkbox("Night")

        submitted = st.form_submit_button("Add Flight")

        if submitted:

            base_cost = COST_DUAL if flight_type=="Dual" else COST_SOLO

            if is_xc:
                base_cost += XC_SURCHARGE

            if is_night:
                base_cost += NIGHT_SURCHARGE

            supabase.table("flights").insert({

                "date":str(flight_date),
                "flight_type":flight_type,
                "duration":float(duration),
                "instructor":instructor,
                "is_xc":is_xc,
                "is_night":is_night,
                "cost_per_hour":base_cost

            }).execute()

            st.success("Flight logged!")

            st.rerun()

# --------------------------------------------------
# EDITABLE FLIGHT LOG
# --------------------------------------------------

if page == "Flight Log":

    st.header("Flight Log")

    if not df.empty:

        for index, row in df.iterrows():

            with st.expander(
                f"{row['date']} | {row['flight_type']} | {row['duration']} hrs"
            ):

                new_duration = st.number_input(
                    "Duration",
                    value=float(row["duration"]),
                    key=f"dur{index}"
                )

                new_type = st.selectbox(
                    "Flight Type",
                    ["Dual","Solo"],
                    index=0 if row["flight_type"]=="Dual" else 1,
                    key=f"type{index}"
                )

                new_xc = st.checkbox(
                    "Cross Country",
                    value=row["is_xc"],
                    key=f"xc{index}"
                )

                new_night = st.checkbox(
                    "Night",
                    value=row["is_night"],
                    key=f"night{index}"
                )

                col1, col2 = st.columns(2)

                if col1.button("Update", key=f"update{index}"):

                    supabase.table("flights").update({

                        "duration":new_duration,
                        "flight_type":new_type,
                        "is_xc":new_xc,
                        "is_night":new_night

                    }).eq("id", row["id"]).execute()

                    st.success("Flight updated")

                    st.rerun()

                if col2.button("Delete", key=f"delete{index}"):

                    supabase.table("flights").delete().eq("id", row["id"]).execute()

                    st.warning("Flight deleted")

                    st.rerun()

    else:

        st.info("No flights logged yet.")

# --------------------------------------------------
# REPORTS
# --------------------------------------------------

if page == "Reports":

    st.header("Reports")

    if not df.empty:

        csv = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download Flight Log CSV",
            csv,
            "flight_log.csv",
            "text/csv"
        )

        st.success("Export your logbook for instructors or checkrides.")

    else:

        st.info("No data available yet.")