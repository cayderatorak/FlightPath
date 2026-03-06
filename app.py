# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client

# -----------------------
# Supabase setup
# -----------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -----------------------
# Tracks and targets
# -----------------------
TRACKS = {
    "PPL": {"Dual": 20, "Solo": 10, "XC": 5, "Night": 3, "Total": 40},
    "Instrument": {"Dual": 15, "Solo": 5, "XC": 5, "Night": 5, "Total": 30},
    "CPL": {"Dual": 30, "Solo": 10, "XC": 10, "Night": 5, "Total": 50},
    "ATP": {"Dual": 20, "Solo": 10, "XC": 5, "Night": 5, "Total": 40}
}

# -----------------------
# Helper functions
# -----------------------
def get_flights(track):
    resp = supabase.table("flights").select("*").eq("track", track).order("date", desc=False).execute()
    data = resp.data if resp.data else []
    df = pd.DataFrame(data)
    if df.empty:
        for col in ["date","flight_type","duration","instructor","is_xc","is_night","cost_per_hour"]:
            df[col] = []
    df["is_xc"] = df.get("is_xc", False).fillna(False).astype(bool)
    df["is_night"] = df.get("is_night", False).fillna(False).astype(bool)
    df["duration"] = df.get("duration", 0).fillna(0).astype(float)
    df["cost_per_hour"] = df.get("cost_per_hour", 0).fillna(0).astype(float)
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
    return remaining, status

def estimate_checkride_date(totals, targets, planned_hours_per_week):
    remaining_hours = max(targets["Total"]-totals.get("Total",0),0)
    if planned_hours_per_week <= 0:
        return "Enter weekly hours to estimate"
    est_date = datetime.today() + timedelta(weeks=remaining_hours/planned_hours_per_week)
    return est_date.strftime("%b %d, %Y")

def estimate_remaining_cost(totals, targets, avg_cost_per_hour):
    remaining_hours = max(targets["Total"]-totals.get("Total",0),0)
    return remaining_hours*avg_cost_per_hour

# -----------------------
# Streamlit UI
# -----------------------
st.set_page_config(layout="wide", page_title="FlightPath")
st.title("FlightPath")

# -----------------------
# Sidebar: login
# -----------------------
st.sidebar.header("Login / Magic Link")
email = st.sidebar.text_input("Email")
if st.sidebar.button("Send Magic Link"):
    try:
        supabase.auth.sign_in_with_otp({"email": email})
        st.sidebar.success("Magic link sent! Check your email.")
    except Exception as e:
        err_msg = str(e)
        if "rate limit" in err_msg.lower():
            st.sidebar.error("You are sending too many requests. Wait a minute before retrying.")
        else:
            st.sidebar.error(f"Error sending link: {err_msg}")

# -----------------------
# Track selection
# -----------------------
track_selected = st.sidebar.selectbox("Select Track", list(TRACKS.keys()))

# -----------------------
# Persistent sidebar costs
# -----------------------
if 'dual_cost' not in st.session_state:
    st.session_state['dual_cost'] = 180.0
if 'solo_cost' not in st.session_state:
    st.session_state['solo_cost'] = 120.0

st.sidebar.header("Cost per Hour ($)")
st.session_state['dual_cost'] = st.sidebar.number_input(
    "Dual", value=st.session_state['dual_cost'], step=1.0, format="%.2f"
)
st.session_state['solo_cost'] = st.sidebar.number_input(
    "Solo", value=st.session_state['solo_cost'], step=1.0, format="%.2f"
)

# -----------------------
# Planned weekly hours
# -----------------------
planned_hours_per_week = st.sidebar.number_input(
    "Planned Flight Hours / Week", min_value=0.0, step=1.0, format="%.1f"
)

# -----------------------
# Add flight entry
# -----------------------
st.sidebar.header("Add Flight Entry")
date = st.sidebar.date_input("Flight Date", datetime.today())
flight_type = st.sidebar.selectbox("Flight Type", ["Dual","Solo"])
duration = st.sidebar.number_input("Duration (hours)", min_value=0.0, step=0.1, format="%.1f")
instructor = st.sidebar.text_input("Instructor (optional)")
is_xc = st.sidebar.checkbox("XC Flight")
is_night = st.sidebar.checkbox("Night Flight")

# Dynamic cost per hour
cost_per_hour = float(st.session_state['dual_cost'] if flight_type=="Dual" else st.session_state['solo_cost'])
cost_per_hour += 20.0 if is_xc else 0.0
cost_per_hour += 30.0 if is_night else 0.0

if st.sidebar.button("Add Flight"):
    supabase.table("flights").insert({
        "date": date.strftime("%Y-%m-%d"),
        "flight_type": flight_type,
        "duration": float(duration),
        "instructor": instructor,
        "is_xc": bool(is_xc),
        "is_night": bool(is_night),
        "cost_per_hour": float(cost_per_hour),
        "track": track_selected
    }).execute()
    st.sidebar.success(f"Flight Added! ${cost_per_hour:.2f}/hr")
    st.experimental_rerun()  # Update UI immediately

# -----------------------
# CSV upload / re-import
# -----------------------
st.sidebar.header("Re-upload Flights (CSV)")
uploaded_file = st.sidebar.file_uploader("Upload CSV", type="csv")
if uploaded_file:
    df_upload = pd.read_csv(uploaded_file)
    for _, row in df_upload.iterrows():
        supabase.table("flights").insert({
            "date": row['date'],
            "flight_type": row['flight_type'],
            "duration": float(row['duration']),
            "instructor": row.get('instructor', ''),
            "is_xc": bool(row['is_xc']),
            "is_night": bool(row['is_night']),
            "cost_per_hour": float(row['cost_per_hour']),
            "track": row['track']
        }).execute()
    st.sidebar.success("All flights re-uploaded successfully!")
    st.experimental_rerun()

# -----------------------
# Fetch flights and calculate
# -----------------------
df = get_flights(track_selected)
totals, costs = calculate_totals(df)
remaining, status = calculate_remaining(totals, TRACKS[track_selected])
avg_cost_per_hour = costs["Total"]/max(totals["Total"],1)
est_checkride = estimate_checkride_date(totals, TRACKS[track_selected], planned_hours_per_week)
est_remaining_cost = estimate_remaining_cost(totals, TRACKS[track_selected], avg_cost_per_hour)

# -----------------------
# Dashboard cards
# -----------------------
st.subheader("🛫 Flight Progress & Costs")
col1, col2, col3, col4 = st.columns(4)
col1.metric("✅ Total Hours", f"{totals['Total']:.1f}")
col2.metric("📅 Est. Checkride", est_checkride)
col3.metric("💰 Total Spent", f"${costs['Total']:.2f}")
col4.metric("💰 Remaining Cost", f"${est_remaining_cost:.2f}")

# -----------------------
# Progress bars with colors
# -----------------------
st.subheader("Progress by Category")
for cat in ["Dual","Solo","XC","Night"]:
    percent = (totals[cat]/TRACKS[track_selected][cat])*100
    percent = min(percent, 100)
    bar_color = "green" if status[cat]=="🟢" else "yellow" if status[cat]=="🟡" else "red"
    st.markdown(f"**{cat}**: {totals[cat]:.1f}/{TRACKS[track_selected][cat]} hours")
    st.markdown(f"""
        <div style="background-color:#e0e0e0; border-radius:5px; width:100%; height:24px;">
            <div style="
                width:{percent}%;
                background-color:{bar_color};
                height:100%;
                border-radius:5px;
                text-align:right;
                padding-right:5px;
                color:black;
                font-weight:bold;
            ">{percent:.0f}%</div>
        </div>
        """, unsafe_allow_html=True)

# -----------------------
# Flight log table with edit/delete and CSV export
# -----------------------
st.subheader("✈️ Flight Log")

if not df.empty:
    df_display = df.copy()
    df_display.index = range(len(df_display))  # Simplify index for edit/delete buttons
    for idx, row in df_display.iterrows():
        col1, col2, col3, col4, col5 = st.columns([1,1,1,1,1])
        with col1:
            st.text(row['date'])
        with col2:
            st.text(row['flight_type'])
        with col3:
            st.text(f"{row['duration']:.1f}")
        with col4:
            st.text(f"${row['cost_per_hour']:.2f}")
        with col5:
            if st.button(f"Delete {idx}"):
                supabase.table("flights").delete().eq("date", row['date']).eq("flight_type", row['flight_type']).eq("track", track_selected).execute()
                st.experimental_rerun()
            if st.button(f"Edit {idx}"):
                st.session_state['edit_row'] = idx
                st.experimental_rerun()
    
    # CSV export
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download Flight Log CSV", data=csv, file_name=f"{track_selected}_flights.csv", mime="text/csv")
else:
    st.write("No flights logged yet.")