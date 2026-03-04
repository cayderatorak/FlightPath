# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client

# -----------------------
# Page Config
# -----------------------
st.set_page_config(page_title="FlightPath", layout="wide")
st.title("FlightPath")

# -----------------------
# Supabase Setup
# -----------------------
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase credentials missing. Check your secrets.toml!")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------
# Helper Functions
# -----------------------
def safe_float(val, default=0.0):
    try:
        return float(val)
    except:
        return default

def safe_bool(val):
    try:
        return bool(val)
    except:
        return False

def add_flight(date, flight_type, duration, instructor, is_xc, is_night, cost_per_hour):
    try:
        duration = safe_float(duration)
        cost_per_hour = safe_float(cost_per_hour)
        is_xc = safe_bool(is_xc)
        is_night = safe_bool(is_night)
        instructor = instructor if instructor else ""
        response = supabase.table("flights").insert({
            "date": date,
            "flight_type": flight_type,
            "duration": duration,
            "instructor": instructor,
            "is_xc": is_xc,
            "is_night": is_night,
            "cost_per_hour": cost_per_hour
        }).execute()
        if getattr(response, "error", None):
            st.error(f"Insert error: {response.error}")
        else:
            st.success(f"Flight added: {flight_type} on {date} ({duration}h)")
    except Exception as e:
        st.error(f"Add flight error: {e}")

def update_flight(flight_id, date, flight_type, duration, instructor, is_xc, is_night, cost_per_hour):
    try:
        duration = safe_float(duration)
        cost_per_hour = safe_float(cost_per_hour)
        is_xc = safe_bool(is_xc)
        is_night = safe_bool(is_night)
        instructor = instructor if instructor else ""
        response = supabase.table("flights").update({
            "date": date,
            "flight_type": flight_type,
            "duration": duration,
            "instructor": instructor,
            "is_xc": is_xc,
            "is_night": is_night,
            "cost_per_hour": cost_per_hour
        }).eq("id", flight_id).execute()
        if getattr(response, "error", None):
            st.error(f"Update error: {response.error}")
        else:
            st.success(f"Flight updated: {flight_type} on {date} ({duration}h)")
    except Exception as e:
        st.error(f"Update flight error: {e}")

def delete_flight(flight_id):
    try:
        response = supabase.table("flights").delete().eq("id", flight_id).execute()
        if getattr(response, "error", None):
            st.error(f"Delete error: {response.error}")
        else:
            st.success(f"Flight deleted")
    except Exception as e:
        st.error(f"Delete flight error: {e}")

def get_flights():
    try:
        resp = supabase.table("flights").select("*").order("date", desc=False).execute()
        data = resp.data if getattr(resp, "data", None) else []
        df = pd.DataFrame(data)
        for col in ["id","student_id","date","flight_type","duration","instructor","is_xc","is_night","cost_per_hour","created_at"]:
            if col not in df.columns:
                df[col] = None if col in ["id","student_id","date","flight_type","instructor","created_at"] else 0
        df["duration"] = df["duration"].fillna(0).astype(float)
        df["cost_per_hour"] = df["cost_per_hour"].fillna(0).astype(float)
        df["is_xc"] = df["is_xc"].fillna(False).astype(bool)
        df["is_night"] = df["is_night"].fillna(False).astype(bool)
        return df
    except Exception as e:
        st.error(f"Error fetching flights: {e}")
        return pd.DataFrame()

def calculate_totals(df):
    totals = {cat: df[df['flight_type']==cat]['duration'].sum() for cat in ["Dual","Solo"]}
    totals["XC"] = df[df['is_xc']].duration.sum() if not df.empty else 0
    totals["Night"] = df[df['is_night']].duration.sum() if not df.empty else 0
    totals["Total"] = df["duration"].sum() if not df.empty else 0
    costs = {cat: (df[df['flight_type']==cat]['duration']*df[df['flight_type']==cat]['cost_per_hour']).sum() for cat in ["Dual","Solo"]}
    costs["XC"] = (df[df['is_xc']]['duration']*df[df['is_xc']]['cost_per_hour']).sum() if not df.empty else 0
    costs["Night"] = (df[df['is_night']]['duration']*df[df['is_night']]['cost_per_hour']).sum() if not df.empty else 0
    costs["Total"] = (df["duration"]*df["cost_per_hour"]).sum() if not df.empty else 0
    return totals, costs

def calculate_remaining(totals, targets):
    remaining = {}
    status = {}
    for cat in targets:
        remaining[cat] = max(targets[cat]-totals.get(cat,0),0)
        if totals.get(cat,0) >= targets[cat]:
            status[cat]="🟢"
        elif totals.get(cat,0) >= targets[cat]*0.5:
            status[cat]="🟡"
        else:
            status[cat]="🔴"
    return remaining,status

def estimate_checkride_date(totals, targets, planned_hours_per_week):
    remaining_hours = max(targets["Total"]-totals.get("Total",0),0)
    if planned_hours_per_week <= 0:
        return "Enter weekly hours"
    return (datetime.today() + timedelta(weeks=remaining_hours/planned_hours_per_week)).strftime("%b %d, %Y")

def estimate_remaining_cost(totals, targets, avg_cost_per_hour):
    remaining_hours = max(targets["Total"]-totals.get("Total",0),0)
    return remaining_hours*avg_cost_per_hour

# -----------------------
# Sidebar Inputs
# -----------------------
st.sidebar.header("Default Cost per Hour ($/hr)")
cost_dual = st.sidebar.number_input("Dual", value=180.0)
cost_solo = st.sidebar.number_input("Solo", value=120.0)
xc_surcharge = st.sidebar.number_input("XC Surcharge", value=20.0)
night_surcharge = st.sidebar.number_input("Night Surcharge", value=30.0)
cost_defaults = {"Dual": cost_dual, "Solo": cost_solo}

st.sidebar.markdown("---")
st.sidebar.header("Proficiency Targets")
multiplier = st.sidebar.number_input("Proficiency Factor", value=1.25, step=0.05)
faa_min = {"Dual":20,"Solo":10,"XC":5,"Night":3,"Total":40}
targets = {cat:int(faa_min[cat]*multiplier) for cat in faa_min}

# Flight Entry
st.sidebar.header("Add Flight Entry")
date = st.sidebar.date_input("Flight Date", datetime.today())
flight_type = st.sidebar.selectbox("Flight Type", ["Dual","Solo"])
duration = st.sidebar.number_input("Duration (hours)", min_value=0.0, step=0.1)
instructor = st.sidebar.text_input("Instructor")
is_xc = st.sidebar.checkbox("XC Flight")
is_night = st.sidebar.checkbox("Night Flight")
try:
    cost_per_hour = cost_defaults.get(flight_type, 0) + (xc_surcharge if is_xc else 0) + (night_surcharge if is_night else 0)
except Exception as e:
    st.error(f"Error calculating cost: {e}")
    cost_per_hour = 0

if st.sidebar.button("Add Flight"):
    add_flight(date.strftime("%Y-%m-%d"), flight_type, duration, instructor, is_xc, is_night, cost_per_hour)

# CSV Upload
st.sidebar.header("Bulk Import Flights (CSV)")
csv_file = st.sidebar.file_uploader("Upload CSV", type=["csv"])
if csv_file:
    try:
        df_csv = pd.read_csv(csv_file)
        for _, row in df_csv.iterrows():
            add_flight(
                str(row['date']),
                row['flight_type'],
                safe_float(row['duration']),
                row.get('instructor',''),
                safe_bool(row.get('is_xc',0)),
                safe_bool(row.get('is_night',0)),
                safe_float(row.get('cost_per_hour',0))
            )
        st.success(f"Imported {len(df_csv)} flights")
    except Exception as e:
        st.error(f"CSV import error: {e}")

planned_hours = st.sidebar.number_input("Planned Flight Hours / Week", min_value=0.0, step=1.0)

# -----------------------
# Main Dashboard
# -----------------------
df = get_flights()
totals, costs = calculate_totals(df)
remaining, status = calculate_remaining(totals, targets)
est_checkride = estimate_checkride_date(totals, targets, planned_hours)
avg_cost_per_hour = costs["Total"]/max(totals["Total"],1)
est_remaining_cost = estimate_remaining_cost(totals, targets, avg_cost_per_hour)

st.subheader("🛫 Flight Progress by Category")
progress_df = pd.DataFrame({
    'Category': ["Dual","Solo","XC","Night"],
    'Completed': [totals["Dual"], totals["Solo"], totals["XC"], totals["Night"]],
    'Target': [targets["Dual"], targets["Solo"], targets["XC"], targets["Night"]]
})
progress_df["Percent"] = (progress_df["Completed"]/progress_df["Target"]).clip(upper=1.0)*100
for _, row in progress_df.iterrows():
    bar_color = "green" if row["Percent"]>=100 else "yellow" if row["Percent"]>=50 else "red"
    st.write(f"**{row['Category']}**: {row['Completed']:.1f}/{row['Target']} hours")
    st.progress(row["Percent"]/100)
    st.markdown(f"<span style='color:{bar_color};'>Status: {status[row['Category']]}</span>", unsafe_allow_html=True)

st.markdown("### Estimated Checkride & Cost")
col1,col2,col3 = st.columns(3)
col1.metric("✅ Total Hours", f"{totals['Total']:.1f}")
col2.metric("📅 Est. Checkride", est_checkride)
col3.metric("💰 Total Spent", f"${costs['Total']:.2f}")
st.write(f"Estimated Remaining Cost to Target: **${est_remaining_cost:.2f}**")
st.write(f"Projected Total Cost: **${costs['Total']+est_remaining_cost:.2f}**")

# -----------------------
# Edit/Delete Flights
# -----------------------
st.subheader("Edit or Delete Existing Flights")

if not df.empty:
    # Create a mapping: readable description -> flight id
    flight_map = {
        f"{x['date']} | {x['flight_type']} | {x['duration']}h | ${x['cost_per_hour']}/hr | XC:{x['is_xc']} | Night:{x['is_night']} | {x['instructor']}": x['id']
        for _, x in df.iterrows()
    }

    # Show only readable info in dropdown
    selected_desc = st.selectbox("Select a flight to edit/delete", [""] + list(flight_map.keys()))

    if selected_desc:
        flight_id = flight_map[selected_desc]  # hidden internal ID
        row = df[df['id'] == flight_id].iloc[0]

        new_date = st.date_input("Flight Date", datetime.strptime(row['date'], "%Y-%m-%d"))
        new_type = st.selectbox("Flight Type", ["Dual", "Solo"], index=["Dual", "Solo"].index(row['flight_type']))
        new_duration = st.number_input("Duration (hours)", min_value=0.0, step=0.1, value=float(row['duration']))
        new_instructor = st.text_input("Instructor", value=row['instructor'] if row['instructor'] else "")
        new_is_xc = st.checkbox("XC Flight", value=bool(row['is_xc']))
        new_is_night = st.checkbox("Night Flight", value=bool(row['is_night']))
        new_cost = st.number_input("Cost per Hour ($)", min_value=0.0, step=1.0, value=float(row['cost_per_hour']))

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Update Flight"):
                update_flight(
                    flight_id,
                    new_date.strftime("%Y-%m-%d"),
                    new_type,
                    new_duration,
                    new_instructor,
                    new_is_xc,
                    new_is_night,
                    new_cost
                )
        with col2:
            if st.button("Delete Flight"):
                delete_flight(flight_id)
else:
    st.write("No flights yet.")