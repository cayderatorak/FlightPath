import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from supabase import create_client, Client
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# -----------------------
# Page config
# -----------------------

st.set_page_config(
    layout="wide",
    page_title="ClimbPath",
    page_icon="✈️"
)

# -----------------------
# Custom Styling
# -----------------------

st.markdown("""
<style>

.stApp {
    background-color:#F8FAFC;
}

section[data-testid="stSidebar"] {
    background-color:#0B1F3B;
}

section[data-testid="stSidebar"] * {
    color:white !important;
}

.main-title {
    font-size:42px;
    font-weight:700;
    color:#0B1F3B;
}

.section-header {
    font-size:24px;
    font-weight:600;
    color:#0B1F3B;
}

[data-testid="stMetric"] {
    background-color:white;
    border-radius:12px;
    padding:10px;
    border:1px solid #E5E7EB;
}

.stButton>button {
    background-color:#3FA7F5;
    color:white;
    border-radius:8px;
    border:none;
}

.stButton>button:hover {
    background-color:#1d8de3;
}

</style>
""", unsafe_allow_html=True)

# -----------------------
# Supabase setup
# -----------------------

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -----------------------
# FAA Tracks
# -----------------------

TRACKS = {
"PPL":{"Dual":20,"Solo":10,"XC":5,"Night":3,"Total":40},
"Instrument":{"Dual":15,"Solo":5,"XC":5,"Night":5,"Total":30},
"CPL":{"Dual":30,"Solo":10,"XC":10,"Night":5,"Total":50},
"ATP":{"Dual":20,"Solo":10,"XC":5,"Night":5,"Total":40}
}

# -----------------------
# Session
# -----------------------

if "user" not in st.session_state:
    st.session_state.user=None

if "dual_cost" not in st.session_state:
    st.session_state.dual_cost=180

if "solo_cost" not in st.session_state:
    st.session_state.solo_cost=120

# -----------------------
# Authentication
# -----------------------

def handle_login():

    if st.session_state.user:
        return st.session_state.user

    st.title("✈️ ClimbPath Login")

    email=st.text_input("Email")
    password=st.text_input("Password",type="password")

    col1,col2=st.columns(2)

    with col1:
        if st.button("Login"):
            try:
                resp=supabase.auth.sign_in_with_password({
                    "email":email,
                    "password":password
                })

                st.session_state.user=resp.user
                st.success("Logged in!")
                st.rerun()

            except Exception as e:
                st.error(e)

    with col2:
        if st.button("Signup"):
            try:
                supabase.auth.sign_up({
                    "email":email,
                    "password":password
                })

                st.success("Check your email to confirm.")
            except Exception as e:
                st.error(e)

    st.stop()

user=handle_login()

# -----------------------
# Database
# -----------------------

def get_user_flights(track,user_id):

    resp=supabase.table("flights")\
        .select("*")\
        .eq("track",track)\
        .eq("user_id",user_id)\
        .order("date",desc=False)\
        .execute()

    data=resp.data if resp.data else []

    df=pd.DataFrame(data)

    if df.empty:
        df=pd.DataFrame(columns=[
            "date","flight_type","duration",
            "instructor","is_xc","is_night",
            "cost_per_hour"
        ])

    df["duration"]=pd.to_numeric(df["duration"],errors="coerce").fillna(0)

    return df

# -----------------------
# Calculations
# -----------------------

def calculate_totals(df):

    totals={}

    totals["Dual"]=df[df.flight_type=="Dual"].duration.sum()
    totals["Solo"]=df[df.flight_type=="Solo"].duration.sum()
    totals["XC"]=df[df.is_xc==True].duration.sum()
    totals["Night"]=df[df.is_night==True].duration.sum()
    totals["Total"]=df.duration.sum()

    total_cost=(df.duration*df.cost_per_hour).sum()

    return totals,total_cost

def readiness_score(totals,targets):

    score=(totals["Total"]/targets["Total"])*100
    return min(round(score),100)

def estimate_checkride(totals,targets,hours_per_week):

    remaining=max(targets["Total"]-totals["Total"],0)

    if hours_per_week==0:
        return "Enter weekly hours"

    weeks=remaining/hours_per_week

    date=datetime.today()+timedelta(weeks=weeks)

    return date.strftime("%b %d %Y")

# -----------------------
# Sidebar
# -----------------------

st.sidebar.markdown(f"Logged in as: {user.email}")

if st.sidebar.button("Logout"):
    st.session_state.user=None
    supabase.auth.sign_out()
    st.rerun()

with st.sidebar.expander("Training Track"):
    track_selected=st.selectbox("Track",list(TRACKS.keys()))

with st.sidebar.expander("Training Plan"):
    planned_hours_per_week=st.number_input("Hours per week",0.0,20.0,3.0)

with st.sidebar.expander("Costs"):
    st.session_state.dual_cost=st.number_input("Dual cost",value=st.session_state.dual_cost)
    st.session_state.solo_cost=st.number_input("Solo cost",value=st.session_state.solo_cost)

# -----------------------
# Header
# -----------------------

st.markdown('<div class="main-title">✈️ ClimbPath</div>',unsafe_allow_html=True)
st.caption("Track your training • Predict your checkride • Control your costs")

# -----------------------
# Data
# -----------------------

df=get_user_flights(track_selected,user.id)
targets=TRACKS[track_selected]

totals,total_cost=calculate_totals(df)

avg_cost=total_cost/max(totals["Total"],1)
remaining_hours=max(targets["Total"]-totals["Total"],0)
remaining_cost=remaining_hours*avg_cost

checkride=estimate_checkride(
totals,
targets,
planned_hours_per_week
)

readiness=readiness_score(totals,targets)

# -----------------------
# Metrics
# -----------------------

st.markdown('<div class="section-header">Training Overview</div>',unsafe_allow_html=True)

col1,col2,col3,col4,col5=st.columns(5)

col1.metric("Total Hours",round(totals["Total"],1))
col2.metric("Checkride Est.",checkride)
col3.metric("Total Spent",f"${total_cost:,.0f}")
col4.metric("Remaining Cost",f"${remaining_cost:,.0f}")
col5.metric("Readiness",f"{readiness}%")

# -----------------------
# FAA Progress
# -----------------------

st.markdown('<div class="section-header">FAA Progress</div>',unsafe_allow_html=True)

for cat in ["Dual","Solo","XC","Night"]:

    percent=min(totals.get(cat,0)/targets[cat]*100,100)

    st.write(f"{cat}: {totals.get(cat,0):.1f}/{targets[cat]} hours")

    st.progress(percent/100)

# -----------------------
# Training Pace Analyzer
# -----------------------

st.markdown('<div class="section-header">Training Pace</div>',unsafe_allow_html=True)

pace=totals["Total"]/max((datetime.today()-datetime.strptime(str(df.date.min()),"%Y-%m-%d")).days/7,1) if not df.empty else 0

st.metric("Average hours/week",round(pace,2))

# -----------------------
# Cost Projection
# -----------------------

st.markdown('<div class="section-header">Cost Projection</div>',unsafe_allow_html=True)

if totals["Total"]>0:

    hours=list(range(int(totals["Total"]),targets["Total"]+1))
    costs=[h*avg_cost for h in hours]

    chart_df=pd.DataFrame({
    "Hours":hours,
    "Cost":costs
    })

    chart=alt.Chart(chart_df).mark_line(strokeWidth=3).encode(
    x="Hours",
    y="Cost"
    )

    st.altair_chart(chart,use_container_width=True)

# -----------------------
# Instructor Insights
# -----------------------

st.markdown('<div class="section-header">Instructor Insights</div>',unsafe_allow_html=True)

if "instructor" in df:

    instructor_hours=df.groupby("instructor").duration.sum().reset_index()

    if not instructor_hours.empty:

        chart=alt.Chart(instructor_hours).mark_bar().encode(
        x="duration",
        y="instructor"
        )

        st.altair_chart(chart,use_container_width=True)

# -----------------------
# Training Timeline
# -----------------------

st.markdown('<div class="section-header">Training Timeline</div>',unsafe_allow_html=True)

timeline=pd.DataFrame({
"Milestone":["Start","Solo","Cross Country","Checkride"],
"Hours":[0,10,25,targets["Total"]]
})

chart=alt.Chart(timeline).mark_line(point=True).encode(
x="Hours",
y="Milestone"
)

st.altair_chart(chart,use_container_width=True)

# -----------------------
# Flight Log
# -----------------------

st.markdown('<div class="section-header">Flight Log</div>',unsafe_allow_html=True)

if not df.empty:

    gb=GridOptionsBuilder.from_dataframe(df)

    gb.configure_selection("single")

    gb.configure_columns(
    ["date","flight_type","duration","instructor","is_xc","is_night","cost_per_hour"],
    editable=True
    )

    grid=AgGrid(
    df,
    gridOptions=gb.build(),
    update_mode=GridUpdateMode.MODEL_CHANGED,
    height=350
    )

    updated=pd.DataFrame(grid["data"])

    csv=updated.to_csv(index=False).encode()

    st.download_button(
    "Download CSV",
    csv,
    "climbpath_flights.csv"
    )

else:
    st.write("No flights logged yet.")