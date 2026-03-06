import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from supabase import create_client

# -----------------------
# PAGE CONFIG
# -----------------------

st.set_page_config(
    page_title="FlightPath",
    page_icon="✈️",
    layout="wide"
)

st.title("✈️ FlightPath")
st.caption("Smart flight training tracker for student pilots")

# -----------------------
# SUPABASE CONNECTION
# -----------------------

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------
# FAA REQUIREMENTS (PPL)
# -----------------------

FAA_TOTAL = 40
FAA_DUAL = 20
FAA_SOLO = 10
FAA_XC = 5
FAA_NIGHT = 3

# -----------------------
# COST DEFAULTS
# -----------------------

COST_DUAL = 180
COST_SOLO = 120
XC_SURCHARGE = 20
NIGHT_SURCHARGE = 15

# -----------------------
# NAVIGATION
# -----------------------

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

# -----------------------
# LOAD FLIGHTS
# -----------------------

def load_flights():

    res = supabase.table("flights").select("*").execute()

    data = res.data if res.data else []

    return pd.DataFrame(data)


df = load_flights()

# -----------------------
# CALCULATIONS
# -----------------------

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

# -----------------------
# DASHBOARD
# -----------------------

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

    st.subheader("Training Progress")

    st.write("Total Hours")
    st.progress(min(total_hours / FAA_TOTAL, 1.0))

    st.write("Dual Instruction")
    st.progress(min(dual_hours / FAA_DUAL, 1.0))

    st.write("Solo Hours")
    st.progress(min(solo_hours / FAA_SOLO, 1.0))

    st.write("Night Hours")
    st.progress(min(night_hours / FAA_NIGHT, 1.0))

    st.write("Cross Country")
    st.progress(min(xc_hours / FAA_XC, 1.0))

    st.divider()

    st.subheader("Flight Hours Breakdown")

    if not df.empty:

        chart_data = pd.DataFrame({
            "Type": ["Dual", "Solo", "XC", "Night"],
            "Hours": [dual_hours, solo_hours, xc_hours, night_hours]
        })

        fig = px.bar(
            chart_data,
            x="Type",
            y="Hours",
            color="Type"
        )

        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.subheader("Training Insight")

    if night_hours < FAA_NIGHT:

        st.warning(
            f"You still need {round(FAA_NIGHT - night_hours,1)} night hours."
        )

    elif xc_hours < FAA_XC:

        st.warning(
            f"You still need {round(FAA_XC - xc_hours,1)} cross country hours."
        )

    else:

        st.success("You're close to meeting FAA training requirements!")

    st.divider()

    st.subheader("Recent Flights")

    if not df.empty:

        recent = df.sort_values("date", ascending=False).head(5)

        st.dataframe(
            recent[
                [
                    "date",
                    "flight_type",
                    "duration",
                    "cost_per_hour"
                ]
            ],
            use_container_width=True
        )

    else:

        st.info("No flights logged yet.")

# -----------------------
# LOG FLIGHT
# -----------------------

if page == "Log Flight":

    st.header("Log New Flight")

    with st.form("flight_form"):

        col1, col2 = st.columns(2)

        with col1:

            flight_date = st.date_input(
                "Date",
                date.today()
            )

            flight_type = st.selectbox(
                "Flight Type",
                ["Dual", "Solo"]
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

        submit = st.form_submit_button("Add Flight")

        if submit:

            base_cost = COST_DUAL if flight_type == "Dual" else COST_SOLO

            if is_xc:
                base_cost += XC_SURCHARGE

            if is_night:
                base_cost += NIGHT_SURCHARGE

            supabase.table("flights").insert({

                "date": str(flight_date),
                "flight_type": flight_type,
                "duration": float(duration),
                "instructor": instructor,
                "is_xc": is_xc,
                "is_night": is_night,
                "cost_per_hour": base_cost

            }).execute()

            st.success("Flight logged successfully!")

            st.rerun()

# -----------------------
# FLIGHT LOG
# -----------------------

if page == "Flight Log":

    st.header("Flight Log")

    if not df.empty:

        st.dataframe(
            df[
                [
                    "date",
                    "flight_type",
                    "duration",
                    "is_xc",
                    "is_night",
                    "cost_per_hour"
                ]
            ],
            use_container_width=True
        )

    else:

        st.info("No flights logged yet.")

# -----------------------
# REPORTS
# -----------------------

if page == "Reports":

    st.header("Export Reports")

    if not df.empty:

        csv = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download Flight Log CSV",
            csv,
            "flight_log.csv",
            "text/csv"
        )

    else:

        st.info("No data available for export.")