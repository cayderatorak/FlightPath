import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client
import plotly.express as px

# -------------------------
# CONFIG
# -------------------------

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="FlightPath", layout="wide")

# -------------------------
# DARK THEME
# -------------------------

st.markdown("""
<style>

.stApp {
    background-color:#0f172a;
    color:white;
}

.metric-card {
    background-color:#1e293b;
    padding:20px;
    border-radius:10px;
    text-align:center;
}

.card {
    background-color:#1e293b;
    padding:20px;
    border-radius:10px;
    margin-bottom:20px;
}

.progress-label {
    font-size:14px;
    margin-top:6px;
}

</style>
""", unsafe_allow_html=True)

# -------------------------
# LOGIN
# -------------------------

if "user" not in st.session_state:
    email = st.text_input("Email")

    if st.button("Login"):
        resp = supabase.auth.sign_in_with_otp({"email": email})
        st.success("Check your email for login link")

    st.stop()

# -------------------------
# CAREER TRACK
# -------------------------

tracks = ["PPL", "Instrument", "Commercial", "ATP"]

track_selected = st.selectbox("Training Track", tracks)

# -------------------------
# DATABASE FUNCTIONS
# -------------------------

def get_flights(track):

    resp = supabase.table("flights") \
        .select("*") \
        .eq("track", track) \
        .order("date") \
        .execute()

    return pd.DataFrame(resp.data)


df = get_flights(track_selected)

# -------------------------
# DASHBOARD METRICS
# -------------------------

total_hours = df["duration"].sum() if not df.empty else 0
total_cost = df["cost"].sum() if not df.empty else 0

remaining_hours = max(40 - total_hours, 0)
remaining_cost = remaining_hours * 180

checkride_date = "TBD"

# -------------------------
# METRIC CARDS
# -------------------------

col1,col2,col3,col4 = st.columns(4)

with col1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Total Hours", round(total_hours,1))
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Total Cost", f"${int(total_cost)}")
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Est Checkride", checkride_date)
    st.markdown('</div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric("Remaining Cost", f"${int(remaining_cost)}")
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# PROGRESS BAR FUNCTION
# -------------------------

def progress_bar(label,current,target,color):

    pct = min(current/target,1)

    colors = {
        "green":"#22c55e",
        "yellow":"#facc15",
        "red":"#ef4444"
    }

    bar_color = colors[color]

    st.markdown(f"""
    <div style="background:#374151;border-radius:6px;height:20px;">
        <div style="
        width:{pct*100}%;
        background:{bar_color};
        height:20px;
        border-radius:6px;">
        </div>
    </div>

    <div class="progress-label">
    {label} — {current:.1f}/{target} hrs
    </div>
    """, unsafe_allow_html=True)

# -------------------------
# TRAINING PROGRESS
# -------------------------

st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("Training Progress")

solo = df[df["flight_type"]=="Solo"]["duration"].sum() if not df.empty else 0
dual = df[df["flight_type"]=="Dual"]["duration"].sum() if not df.empty else 0
xc = df[df["flight_type"].str.contains("XC",na=False)]["duration"].sum() if not df.empty else 0
night = df[df["flight_type"].str.contains("Night",na=False)]["duration"].sum() if not df.empty else 0

progress_bar("Dual",dual,20,"green")
progress_bar("Solo",solo,10,"yellow")
progress_bar("XC",xc,8,"green")
progress_bar("Night",night,3,"yellow")

st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# CHECKRIDE READINESS ENGINE
# -------------------------

st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("Checkride Readiness")

def calculate_readiness(df):

    total = df["duration"].sum() if not df.empty else 0
    solo = df[df["flight_type"]=="Solo"]["duration"].sum() if not df.empty else 0
    dual = df[df["flight_type"]=="Dual"]["duration"].sum() if not df.empty else 0
    xc = df[df["flight_type"].str.contains("XC",na=False)]["duration"].sum() if not df.empty else 0
    night = df[df["flight_type"].str.contains("Night",na=False)]["duration"].sum() if not df.empty else 0

    score = 0
    max_score = 5

    if total >= 40: score+=1
    if solo >= 10: score+=1
    if dual >= 20: score+=1
    if xc >= 8: score+=1
    if night >= 3: score+=1

    pct = int((score/max_score)*100)

    return pct,total,solo,dual,xc,night


readiness,total,solo,dual,xc,night = calculate_readiness(df)

st.metric("Readiness Score",f"{readiness}%")

missing=[]

if total<40:
    missing.append(f"{40-total:.1f} hrs total")

if solo<10:
    missing.append(f"{10-solo:.1f} hrs solo")

if dual<20:
    missing.append(f"{20-dual:.1f} hrs dual")

if xc<8:
    missing.append(f"{8-xc:.1f} hrs XC")

if night<3:
    missing.append(f"{3-night:.1f} hrs night")

if missing:

    st.write("Remaining Requirements:")

    for m in missing:
        st.write("•",m)

else:
    st.success("All FAA minimums met!")

st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# TRAINING TIMELINE
# -------------------------

st.markdown('<div class="card">', unsafe_allow_html=True)

st.subheader("Training Timeline")

if not df.empty:

    timeline=df.sort_values("date",ascending=False).head(10)

    for _,row in timeline.iterrows():

        st.write(
            f"**{row['date']}** — {row['flight_type']} • {row['duration']} hrs"
        )

else:
    st.write("No flights logged yet")

st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# EXPORT FLIGHT LOG
# -------------------------

if not df.empty:

    csv=df.to_csv(index=False)

    st.download_button(
        "Export Flight Log",
        csv,
        "flight_log.csv",
        "text/csv"
    )