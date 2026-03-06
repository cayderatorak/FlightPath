# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# -----------------------
# Supabase setup
# -----------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -----------------------
# Tracks and FAA targets
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
def get_user_flights(track, user_id):
    resp = supabase.table("flights").select("*")\
        .eq("track", track).eq("user_id", user_id).order("date", desc=False).execute()
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
        if totals.get(cat,0) >= targets[cat]:
            status[cat] = "🟢"
        elif totals.get(cat,0) >= targets[cat]*0.5:
            status[cat] = "🟡"
        else:
            status[cat] = "🔴"
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
# Login / Signup
# -----------------------
def handle_login():
    if st.session_state.get("user"):
        return st.session_state["user"]

    params = st.query_params
    if "access_token" in params:
        try:
            supabase.auth.set_session(
                params["access_token"][0],
                params.get("refresh_token", [None])[0]
            )
            st.experimental_set_query_params()
            st.experimental_rerun()
        except Exception:
            st.error("Session restore failed.")
            st.stop()

    st.title("✈️ FlightPath Login / Signup")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    remember_me = st.checkbox("Remember Me", value=st.session_state.get("remember_me", False))
    st.session_state["remember_me"] = remember_me

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login"):
            try:
                resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if resp.user:
                    st.session_state["user"] = resp.user
                    if remember_me:
                        st.experimental_set_query_params(
                            access_token=resp.session.access_token,
                            refresh_token=resp.session.refresh_token
                        )
                    st.experimental_rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")
    with col2:
        if st.button("Signup"):
            try:
                supabase.auth.sign_up({"email": email, "password": password})
                st.success("Account created! Please login.")
            except Exception as e:
                st.error(f"Signup failed: {e}")
    st.stop()

user = handle_login()

# -----------------------
# Streamlit setup
# -----------------------
st.set_page_config(layout="wide", page_title="FlightPath")

# Session defaults
if 'dual_cost' not in st.session_state: st.session_state['dual_cost'] = 180.0
if 'solo_cost' not in st.session_state: st.session_state['solo_cost'] = 120.0

# -----------------------
# Sidebar
# -----------------------
st.sidebar.markdown(f"**Logged in as:** {user.email}")
if st.sidebar.button("Logout"):
    supabase.auth.sign_out()
    st.experimental_rerun()

with st.sidebar.expander("Track & Weekly Plan"):
    track_selected = st.selectbox("Select Track", list(TRACKS.keys()))
    planned_hours_per_week = st.number_input("Planned Flight Hours / Week", min_value=0.0, step=1.0, format="%.1f")

with st.sidebar.expander("Flight Costs"):
    st.session_state['dual_cost'] = st.number_input("Dual", value=st.session_state['dual_cost'], step=1.0, format="%.2f")
    st.session_state['solo_cost'] = st.number_input("Solo", value=st.session_state['solo_cost'], step=1.0, format="%.2f")

with st.sidebar.expander("Add Flight"):
    date = st.date_input("Flight Date", datetime.today())
    flight_type = st.selectbox("Flight Type", ["Dual","Solo"])
    duration = st.number_input("Duration (hours)", min_value=0.0, step=0.1, format="%.1f")
    instructor = st.text_input("Instructor (optional)")
    is_xc = st.checkbox("XC Flight")
    is_night = st.checkbox("Night Flight")
    cost_per_hour = float(st.session_state['dual_cost'] if flight_type=="Dual" else st.session_state['solo_cost'])
    if is_xc: cost_per_hour += 20
    if is_night: cost_per_hour += 30
    if st.button("Add Flight"):
        supabase.table("flights").insert({
            "date": date.strftime("%Y-%m-%d"),
            "flight_type": flight_type,
            "duration": float(duration),
            "instructor": instructor,
            "is_xc": bool(is_xc),
            "is_night": bool(is_night),
            "cost_per_hour": float(cost_per_hour),
            "track": track_selected,
            "user_id": user.id
        }).execute()
        st.success(f"Flight Added! ${cost_per_hour:.2f}/hr")
        st.experimental_rerun()

# -----------------------
# Fetch Flights
# -----------------------
df = get_user_flights(track_selected, user.id)
totals, costs = calculate_totals(df)
remaining, status = calculate_remaining(totals, TRACKS[track_selected])
avg_cost_per_hour = costs["Total"]/max(totals["Total"],1)
est_checkride = estimate_checkride_date(totals, TRACKS[track_selected], planned_hours_per_week)
est_remaining_cost = estimate_remaining_cost(totals, TRACKS[track_selected], avg_cost_per_hour)

# -----------------------
# Dashboard Metrics
# -----------------------
st.subheader("🛫 Flight Progress & Costs")
col1, col2, col3, col4 = st.columns(4)
col1.metric("✅ Total Hours", f"{totals['Total']:.1f}")
col2.metric("📅 Est. Checkride", est_checkride)
col3.metric("💰 Total Spent", f"${costs['Total']:.2f}")
col4.metric("💰 Remaining Cost", f"${est_remaining_cost:.2f}")

# -----------------------
# Progress Bars
# -----------------------
st.subheader("Progress by Category")
for cat in ["Dual","Solo","XC","Night"]:
    percent = min((totals[cat]/TRACKS[track_selected][cat])*100, 100)
    if percent <= 33: bar_color="red"
    elif percent <= 66: bar_color="yellow"
    else: bar_color="green"
    st.markdown(f"**{cat}**: {totals[cat]:.1f}/{TRACKS[track_selected][cat]} hours")
    st.markdown(f"""
        <div style="background-color:#e0e0e0; border-radius:5px; width:100%; height:24px;">
            <div style="width:{percent}%; background-color:{bar_color}; height:100%; border-radius:5px;
                        text-align:right; padding-right:5px; color:black; font-weight:bold;">
                {percent:.0f}%
            </div>
        </div>
    """, unsafe_allow_html=True)

# -----------------------
# Flight Log Table (AgGrid Inline Edit/Delete)
# -----------------------
st.subheader("✈️ Flight Log")
if not df.empty:
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_selection("single", use_checkbox=True)
    gb.configure_columns(df.columns, editable=True)
    gb.configure_grid_options(domLayout='normal')
    grid_options = gb.build()

    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.VALUE_CHANGED | GridUpdateMode.SELECTION_CHANGED,
        height=350,
        fit_columns_on_grid_load=True
    )

    # Handle edits
    updated_rows = grid_response['data']
    for row in updated_rows.to_dict(orient="records"):
        supabase.table("flights")\
            .update(row)\
            .eq("date", row['date'])\
            .eq("user_id", user.id)\
            .eq("track", track_selected)\
            .execute()

    # Handle delete
    selected_rows = grid_response['selected_rows']
    if selected_rows:
        if st.button("Delete Selected Flight"):
            sel = selected_rows[0]
            supabase.table("flights")\
                .delete()\
                .eq("date", sel['date'])\
                .eq("user_id", user.id)\
                .eq("track", track_selected)\
                .execute()
            st.success("Flight deleted!")
            st.experimental_rerun()

    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download Flight Log CSV", data=csv, file_name=f"{track_selected}_flights.csv", mime="text/csv")
else:
    st.write("No flights logged yet.")