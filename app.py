import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from supabase import create_client
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# --------------------------------------------------
# LOAD SECRETS
# --------------------------------------------------
SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase keys not found! Add them to secrets.toml (Streamlit) or .env (local).")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(page_title="ClimbPath", page_icon="✈️", layout="wide")

# --------------------------------------------------
# UI STYLE
# --------------------------------------------------
st.markdown("""
<style>
.stApp{background:#F8FAFC;}
section[data-testid="stSidebar"]{background:#0B1F3B;}
section[data-testid="stSidebar"] *{color:white !important;}
.main-title{font-size:42px;font-weight:700;color:#0B1F3B;}
.section-title{font-size:24px;font-weight:600;margin-top:30px;color:#0B1F3B;}
[data-testid="stMetric"]{background:white;border-radius:12px;padding:10px;border:1px solid #E5E7EB;}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# FAA TRACKS
# --------------------------------------------------
TRACKS = {
    "PPL":{"Dual":20,"Solo":10,"XC":5,"Night":3,"Total":40},
    "Instrument":{"Dual":15,"Solo":5,"XC":5,"Night":5,"Total":30},
    "CPL":{"Dual":30,"Solo":10,"XC":10,"Night":5,"Total":50},
    "ATP":{"Dual":20,"Solo":10,"XC":5,"Night":5,"Total":40}
}

# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------
if "user" not in st.session_state: st.session_state.user = None
if "dual_cost" not in st.session_state: st.session_state.dual_cost = 180.0
if "solo_cost" not in st.session_state: st.session_state.solo_cost = 120.0

# --------------------------------------------------
# AUTH
# --------------------------------------------------
def login():
    if st.session_state.user: return st.session_state.user

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

# --------------------------------------------------
# DATABASE
# --------------------------------------------------
def load_flights(track, user_id):
    """
    Load flights for the given user.
    - Ensures only the current user's flights are loaded.
    - Shows old flights with placeholder track 'Yes (optional)'.
    """
    resp = supabase.table("flights")\
        .select("*")\
        .eq("user_id", user_id)\
        .order("date")\
        .execute()

    data = resp.data if resp.data else []
    df = pd.DataFrame(data)

    if df.empty:
        df = pd.DataFrame(columns=[
            "id", "date", "flight_type", "duration",
            "aircraft", "instructor", "is_xc", "is_night",
            "cost_per_hour", "track"
        ])
    else:
        # Show flights matching the current track OR old placeholder flights
        df = df[(df["track"] == track) | (df["track"] == "Yes (optional)")]

    return df

# --------------------------------------------------
# CALCULATIONS
# --------------------------------------------------
def calculate_totals(df):
    totals = {}
    totals["Dual"] = df[df.flight_type=="Dual"].duration.sum()
    totals["Solo"] = df[df.flight_type=="Solo"].duration.sum()
    totals["XC"] = df[df.is_xc==True].duration.sum()
    totals["Night"] = df[df.is_night==True].duration.sum()
    totals["Total"] = df.duration.sum()
    total_cost = (df.duration * df.cost_per_hour).sum()
    return totals, total_cost

def estimate_checkride(totals, targets, hours_week):
    remaining = max(targets["Total"] - totals["Total"], 0)
    if hours_week==0: return "Enter hours/week"
    weeks = remaining / hours_week
    date = datetime.today() + timedelta(weeks=weeks)
    return date.strftime("%b %d %Y")

# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------
st.sidebar.markdown(f"**Logged in:** {user.email}")

if st.sidebar.button("Logout"):
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

track = st.sidebar.selectbox("Training Track", list(TRACKS.keys()))
hours_week = st.sidebar.number_input("Hours / Week", 0.0, 20.0, 3.0)
st.session_state.dual_cost = st.sidebar.number_input("Dual Cost", value=st.session_state.dual_cost)
st.session_state.solo_cost = st.sidebar.number_input("Solo Cost", value=st.session_state.solo_cost)

# --------------------------------------------------
# ADD FLIGHT FORM
# --------------------------------------------------
st.sidebar.markdown("### Add Flight")
date = st.sidebar.date_input("Date", datetime.today())
flight_type = st.sidebar.selectbox("Flight Type", ["Dual","Solo"])
duration = st.sidebar.number_input("Duration", 0.0, 10.0, 1.0)
aircraft = st.sidebar.text_input("Aircraft")
instructor = st.sidebar.text_input("Instructor")
is_xc = st.sidebar.checkbox("XC")
is_night = st.sidebar.checkbox("Night")
cost = st.session_state.dual_cost if flight_type=="Dual" else st.session_state.solo_cost

st.sidebar.markdown("### Upload Flights CSV")
csv_file = st.sidebar.file_uploader("Choose CSV", type=["csv"])

if csv_file is not None:
    df_csv = pd.read_csv(csv_file)

    # Optional: preview first few rows
    st.sidebar.write(df_csv.head())

    if st.sidebar.button("Upload CSV"):
        for _, row in df_csv.iterrows():
            # Determine cost per hour based on flight type
            cost = st.session_state.dual_cost if row["flight_type"] == "Dual" else st.session_state.solo_cost

            # Insert flight into Supabase
            supabase.table("flights").insert({
                "user_id": user.id,
                "date": str(row["date"]),
                "flight_type": row["flight_type"],
                "duration": float(row["duration"]),
                "aircraft": row.get("aircraft", ""),
                "instructor": row.get("instructor", ""),
                "is_xc": bool(row.get("is_xc", False)),
                "is_night": bool(row.get("is_night", False)),
                "cost_per_hour": cost,
                "track": row.get("track", track)  # fallback to current sidebar track
            }).execute()
        st.success("CSV uploaded successfully!")
        st.rerun()

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
        "track": track
    }).execute()
    st.rerun()

# --------------------------------------------------
# HEADER
# --------------------------------------------------
st.markdown('<div class="main-title">✈️ ClimbPath</div>', unsafe_allow_html=True)
st.caption("Track training • Predict checkrides • Control costs")

# --------------------------------------------------
# DATA
# --------------------------------------------------
df = load_flights(track, user.id)
totals, total_cost = calculate_totals(df)
targets = TRACKS[track]
avg_cost = total_cost/max(totals["Total"],1)
remaining_cost = (targets["Total"]-totals["Total"])*avg_cost
checkride = estimate_checkride(totals, targets, hours_week)

# --------------------------------------------------
# METRICS
# --------------------------------------------------
c1,c2,c3,c4 = st.columns(4)
c1.metric("Total Hours", round(totals["Total"],1))
c2.metric("Est Checkride", checkride)
c3.metric("Total Spent", f"${total_cost:,.0f}")
c4.metric("Remaining Cost", f"${remaining_cost:,.0f}")

# --------------------------------------------------
# FAA PROGRESS
# --------------------------------------------------
st.markdown('<div class="section-title">FAA Progress</div>', unsafe_allow_html=True)
for cat in ["Dual","Solo","XC","Night"]:
    percent = min(totals.get(cat,0)/targets[cat]*100, 100)
    st.write(f"{cat}: {totals.get(cat,0):.1f}/{targets[cat]}")
    st.progress(percent/100)

# --------------------------------------------------
# WEEKLY TRAINING VELOCITY
# --------------------------------------------------
st.markdown('<div class="section-title">Training Velocity</div>', unsafe_allow_html=True)
if not df.empty:
    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.to_period("W").astype(str)
    weekly = df.groupby("week").duration.sum().reset_index()
    chart = alt.Chart(weekly).mark_bar().encode(x="week", y="duration")
    st.altair_chart(chart, use_container_width=True)

# --------------------------------------------------
# COST PROJECTION
# --------------------------------------------------
st.markdown('<div class="section-title">Cost Projection</div>', unsafe_allow_html=True)
if totals["Total"] > 0:
    hours = list(range(int(totals["Total"]), targets["Total"]+1))
    costs = [h*avg_cost for h in hours]
    chart_df = pd.DataFrame({"Hours": hours, "Cost": costs})
    chart = alt.Chart(chart_df).mark_line().encode(x="Hours", y="Cost")
    st.altair_chart(chart, use_container_width=True)

# --------------------------------------------------
# INSTRUCTOR ANALYTICS
# --------------------------------------------------
st.markdown('<div class="section-title">Instructor Analytics</div>', unsafe_allow_html=True)
if not df.empty:
    inst = df.groupby("instructor").duration.sum().reset_index()
    chart = alt.Chart(inst).mark_bar().encode(x="duration", y="instructor")
    st.altair_chart(chart, use_container_width=True)

# --------------------------------------------------
# AIRCRAFT ANALYTICS
# --------------------------------------------------
st.markdown('<div class="section-title">Aircraft Analytics</div>', unsafe_allow_html=True)
if not df.empty:
    ac = df.groupby("aircraft").duration.sum().reset_index()
    chart = alt.Chart(ac).mark_bar().encode(x="duration", y="aircraft")
    st.altair_chart(chart, use_container_width=True)

# --------------------------------------------------
# FLIGHT LOGBOOK
# --------------------------------------------------
st.markdown('<div class="section-title">Flight Logbook</div>', unsafe_allow_html=True)
gb = GridOptionsBuilder.from_dataframe(df)
gb.configure_columns(["date","flight_type","duration","aircraft","instructor","is_xc","is_night","cost_per_hour"], editable=True)
gb.configure_selection("single")
grid = AgGrid(df, gridOptions=gb.build(), update_mode=GridUpdateMode.MODEL_CHANGED, height=400)
updated = pd.DataFrame(grid["data"])

# --------------------------------------------------
# DELETE FLIGHT
# --------------------------------------------------
selected = grid["selected_rows"]
if selected:
    flight_id = selected[0]["id"]
    if st.button("Delete Flight"):
        supabase.table("flights").delete().eq("id", flight_id).execute()
        st.rerun()

# --------------------------------------------------
# CSV EXPORT
# --------------------------------------------------
csv = updated.to_csv(index=False).encode()
st.download_button("Download CSV", csv, "climbpath_logbook.csv")