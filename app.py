import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# ------------------ CUSTOM MODULES ------------------
from database import supabase, load_flights
from calculations import calculate_totals, estimate_checkride
from milestones import next_milestone
from achievements import calculate_achievements
from config import TRACKS
from solo import calculate_solo_readiness, predict_solo
from progress import school_averages, student_rankings

# ------------------ PAGE CONFIG ------------------
st.set_page_config(
    page_title="ClimbPath",
    page_icon="✈️",
    layout="wide"
)

# ------------------ CSS (Light + Dark Mode) ------------------
st.markdown("""
<style>
/* LIGHT MODE */
[data-theme="light"] {
    section[data-testid="stSidebar"] { background: #F8FAFC; }
    section[data-testid="stSidebar"] * { color: #0B1F3B !important; }
    .main-title, .section-title { color: #0B1F3B; }
    [data-testid="stMetric"] {
        background: white; border-radius:12px; padding:10px; border:1px solid #E5E7EB; color: #0B1F3B;
    }
}

/* DARK MODE */
[data-theme="dark"] {
    section[data-testid="stSidebar"] { background: #0B1F3B; }
    section[data-testid="stSidebar"] * { color: #F8FAFC !important; }
    .main-title, .section-title { color: #F8FAFC; }
    [data-testid="stMetric"] {
        background: #1f2937; border-radius:12px; padding:10px; border:1px solid #374151; color: #F8FAFC;
    }
}

/* COMMON */
.stApp { background: #F8FAFC; }
.main-title { font-size:42px; font-weight:700; }
.section-title { font-size:24px; font-weight:600; margin-top:30px; }
</style>
""", unsafe_allow_html=True)

# ------------------ SESSION STATE ------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "dual_cost" not in st.session_state:
    st.session_state.dual_cost = 180.0
if "solo_cost" not in st.session_state:
    st.session_state.solo_cost = 120.0

# ------------------ AUTH ------------------
def login():
    if st.session_state.user:
        return st.session_state.user

    st.title("✈️ ClimbPath Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Login"):
            try:
                resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = resp.user
                st.rerun()
            except:
                st.error("Invalid login")

    with col2:
        if st.button("Signup"):
            try:
                supabase.auth.sign_up({"email": email, "password": password})
                st.success("Account created!")
            except:
                st.error("Signup failed")
    st.stop()

user = login()

# ------------------ SIDEBAR ------------------
st.sidebar.markdown(f"**Logged in:** {user.email}")
if st.sidebar.button("Logout"):
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

track = st.sidebar.selectbox("Training Track", list(TRACKS.keys()))
hours_week = st.sidebar.number_input("Hours / Week", 0.0, 20.0, 3.0)
st.session_state.dual_cost = st.sidebar.number_input("Dual Cost", value=st.session_state.dual_cost)
st.session_state.solo_cost = st.sidebar.number_input("Solo Cost", value=st.session_state.solo_cost)

# ------------------ ADD FLIGHT ------------------
st.sidebar.markdown("### Add Flight")
date = st.sidebar.date_input("Date", datetime.today())
flight_type = st.sidebar.selectbox("Flight Type", ["Dual","Solo"])
duration = st.sidebar.number_input("Duration", 0.0, 10.0, 1.0)
aircraft = st.sidebar.text_input("Aircraft")
instructor = st.sidebar.text_input("Instructor")
is_xc = st.sidebar.checkbox("XC")
is_night = st.sidebar.checkbox("Night")
feedback = st.sidebar.text_area("Instructor Feedback")
cost = st.session_state.dual_cost if flight_type=="Dual" else st.session_state.solo_cost

if st.sidebar.button("Add Flight"):
    supabase.table("flights").insert({
        "user_id": user.id,
        "date": str(date),
        "flight_type": flight_type,
        "duration": duration,
        "aircraft": aircraft,
        "instructor": instructor,
        "is_xc": is_xc,
        "is_night": is_night,
        "cost_per_hour": cost,
        "track": track,
        "feedback": feedback
    }).execute()
    st.rerun()

# ------------------ HEADER ------------------
st.markdown('<div class="main-title">✈️ ClimbPath</div>', unsafe_allow_html=True)
st.caption("Track training • Predict checkrides • Control costs")

# ------------------ LOAD DATA ------------------
df = load_flights(track, user.id)
if df.empty:
    df = pd.DataFrame(columns=[
        "id","date","flight_type","duration",
        "aircraft","instructor",
        "is_xc","is_night","cost_per_hour","track","feedback"
    ])

# ------------------ CALCULATIONS ------------------
totals, total_cost = calculate_totals(df)
targets = TRACKS[track]
milestone = next_milestone(totals)
avg_cost = total_cost / max(totals["Total"],1)
remaining_cost = (targets["Total"] - totals["Total"]) * avg_cost
solo_score = calculate_solo_readiness(df)
predicted_solo = predict_solo(df, hours_week, targets)
achievements_list = calculate_achievements(totals)
school_avg = school_averages(track)
rank, percentile = student_rankings(user.id, track)

# ------------------ METRICS ------------------
c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Total Hours", round(totals["Total"],1))
c2.metric("Next Milestone", milestone)
c3.metric("Solo Readiness", f"{solo_score}%")
c4.metric("Predicted Solo", predicted_solo)
c5.metric("Total Spent", f"${total_cost:,.0f}")
c6.metric("Remaining Cost", f"${remaining_cost:,.0f}")

# ------------------ FAA PROGRESS ------------------
st.markdown('<div class="section-title">FAA Progress</div>', unsafe_allow_html=True)
for cat in ["Dual","Solo","XC","Night"]:
    percent = min(totals.get(cat,0)/targets[cat]*100, 100)
    st.write(f"{cat}: {totals.get(cat,0):.1f}/{targets[cat]}")
    st.progress(percent/100)

# ------------------ ACHIEVEMENTS ------------------
st.markdown('<div class="section-title">Achievements</div>', unsafe_allow_html=True)
for badge in achievements_list:
    st.write("🏅", badge)

# ------------------ PROGRESS VS SCHOOL AVERAGES ------------------
st.markdown('<div class="section-title">Progress vs School Averages</div>', unsafe_allow_html=True)
if school_avg:
    for key, val in school_avg.items():
        st.write(f"{key}: You: {totals.get(key,0)} hrs • School Avg: {val} hrs")

# ------------------ STUDENT RANKING ------------------
st.markdown('<div class="section-title">Student Ranking</div>', unsafe_allow_html=True)
st.write(f"You are ranked #{rank} ({percentile} percentile) in your school for {track} track")

# ------------------ TRAINING VELOCITY ------------------
st.markdown('<div class="section-title">Training Velocity</div>', unsafe_allow_html=True)
if not df.empty:
    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.to_period("W").astype(str)
    weekly = df.groupby("week").duration.sum().reset_index()
    chart = alt.Chart(weekly).mark_bar().encode(x="week",y="duration")
    st.altair_chart(chart, use_container_width=True)

# ------------------ FLIGHT LOGBOOK ------------------
st.markdown('<div class="section-title">Flight Logbook</div>', unsafe_allow_html=True)
display_df = df.drop(columns=["id","user_id"], errors="ignore")
gb = GridOptionsBuilder.from_dataframe(display_df)
gb.configure_columns(display_df.columns, editable=True)
gb.configure_selection("single")
grid = AgGrid(display_df, gridOptions=gb.build(), update_mode=GridUpdateMode.MODEL_CHANGED, height=400)
updated = pd.DataFrame(grid["data"])

# ------------------ DELETE / EDIT FLIGHTS ------------------
selected = grid["selected_rows"]
if selected:
    flight_id = selected[0]["id"]
    col1,col2 = st.columns(2)
    with col1:
        if st.button("Delete Flight"):
            supabase.table("flights").delete().eq("id", flight_id).execute()
            st.success("Flight deleted!")
            st.rerun()

# ------------------ CSV EXPORT ------------------
csv = updated.to_csv(index=False).encode()
st.download_button("Download CSV", csv, "climbpath_logbook.csv")