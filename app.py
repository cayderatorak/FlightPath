# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client

# -----------------------
# Streamlit Page Config
# -----------------------
st.set_page_config(page_title="FlightPath", layout="wide")
st.title("FlightPath")

# -----------------------
# Supabase Setup
# -----------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------
# Helper Functions (Safe)
# -----------------------
def add_flight(date, flight_type, duration, instructor, is_xc, is_night, cost_per_hour):
    try:
        duration = float(duration) if duration is not None else 0.0
        cost_per_hour = float(cost_per_hour) if cost_per_hour is not None else 0.0
        is_xc = bool(is_xc)
        is_night = bool(is_night)
        instructor = instructor if instructor else ""

        st.write(f"Adding flight: {date}, {flight_type}, {duration}h, {instructor}, XC={is_xc}, Night={is_night}, ${cost_per_hour}/hr")

        response = supabase.table("flights").insert({
            "date": date,
            "flight_type": flight_type,
            "duration": duration,
            "instructor": instructor,
            "is_xc": is_xc,
            "is_night": is_night,
            "cost_per_hour": cost_per_hour
        }).execute()

        if hasattr(response, "error") and response.error:
            st.error(f"Supabase insert error: {response.error}")
        else:
            st.success("Flight added successfully!")

    except Exception as e:
        st.error(f"Error adding flight: {e}")

def update_flight(flight_id, date, flight_type, duration, instructor, is_xc, is_night, cost_per_hour):
    try:
        duration = float(duration) if duration is not None else 0.0
        cost_per_hour = float(cost_per_hour) if cost_per_hour is not None else 0.0
        is_xc = bool(is_xc)
        is_night = bool(is_night)
        instructor = instructor if instructor else ""

        st.write(f"Updating flight {flight_id}: {date}, {flight_type}, {duration}h")

        response = supabase.table("flights").update({
            "date": date,
            "flight_type": flight_type,
            "duration": duration,
            "instructor": instructor,
            "is_xc": is_xc,
            "is_night": is_night,
            "cost_per_hour": cost_per_hour
        }).eq("id", flight_id).execute()

        if hasattr(response, "error") and response.error:
            st.error(f"Supabase update error: {response.error}")
        else:
            st.success("Flight updated successfully!")

    except Exception as e:
        st.error(f"Error updating flight: {e}")

def delete_flight(flight_id):
    try:
        response = supabase.table("flights").delete().eq("id", flight_id).execute()
        if hasattr(response, "error") and response.error:
            st.error(f"Supabase delete error: {response.error}")
        else:
            st.success("Flight deleted successfully!")
    except Exception as e:
        st.error(f"Error deleting flight: {e}")

def get_flights():
    try:
        response = supabase.table("flights").select("*").order("date", desc=False).execute()
        data = response.data if response.data else []
        df = pd.DataFrame(data)
        # Ensure expected columns exist
        for col in ["id","student_id","date","flight_type","duration","instructor","is_xc","is_night","cost_per_hour","created_at"]:
            if col not in df.columns:
                df[col] = None if col in ["id","student_id","date","flight_type","instructor","created_at"] else 0
        df["is_xc"] = df["is_xc"].fillna(False).astype(bool)
        df["is_night"] = df["is_night"].fillna(False).astype(bool)
        df["duration"] = df["duration"].fillna(0).astype(float)
        df["cost_per_hour"] = df["cost_per_hour"].fillna(0).astype(float)
        return df
    except Exception as e:
        st.error(f"Error fetching flights: {e}")
        return pd.DataFrame()

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
    return remaining,status

def estimate_checkride_date(totals,targets,planned_hours_per_week):
    remaining_hours = max(targets["Total"]-totals.get("Total",0),0)
    if planned_hours_per_week<=0:
        return "Enter weekly hours to estimate"
    est_date = datetime.today() + timedelta(weeks=remaining_hours/planned_hours_per_week)
    return est_date.strftime("%b %d, %Y")

def estimate_remaining_cost(totals, targets, avg_cost_per_hour):
    remaining_hours = max(targets["Total"]-totals.get("Total",0),0)
    return remaining_hours*avg_cost_per_hour

# -----------------------
# Sidebar: Cost & Proficiency
# -----------------------
st.sidebar.header("Default Cost per Hour ($/hr)")
cost_dual = st.sidebar.number_input("Dual", value=180.0, step=1.0)
cost_solo = st.sidebar.number_input("Solo", value=120.0, step=1.0)
xc_surcharge = st.sidebar.number_input("XC Surcharge", value=20.0, step=1.0)
night_surcharge = st.sidebar.number_input("Night Surcharge", value=30.0, step=1.0)
cost_defaults = {"Dual":cost_dual,"Solo":cost_solo}

st.sidebar.markdown("---")
st.sidebar.header("Proficiency Targets")
proficiency_multiplier = st.sidebar.number_input("Proficiency Factor (1.0=FAA min, 1.25=25% extra)", value=1.25, step=0.05)
faa_min = {"Dual":20,"Solo":10,"XC":5,"Night":3,"Total":40}
targets = {cat:int(faa_min[cat]*proficiency_multiplier) for cat in faa_min}
targets["Dual"] = st.sidebar.number_input("Target Dual Hours", value=targets["Dual"], min_value=0)
targets["Solo"] = st.sidebar.number_input("Target Solo Hours", value=targets["Solo"], min_value=0)
targets["XC"] = st.sidebar.number_input("Target XC Hours", value=targets["XC"], min_value=0)
targets["Night"] = st.sidebar.number_input("Target Night Hours", value=targets["Night"], min_value=0)
targets["Total"] = int(faa_min["Total"] * proficiency_multiplier)

# -----------------------
# Add Flight Entry
# -----------------------
st.sidebar.header("Add Flight Entry")
date = st.sidebar.date_input("Flight Date", datetime.today())
flight_type = st.sidebar.selectbox("Flight Type", ["Dual","Solo"])
duration = st.sidebar.number_input("Duration (hours)", min_value=0.0, step=0.1)
instructor = st.sidebar.text_input("Instructor (optional)")
is_xc = st.sidebar.checkbox("XC Flight")
is_night = st.sidebar.checkbox("Night Flight")
cost_per_hour = cost_defaults[flight_type] + (xc_surcharge if is_xc else 0) + (night_surcharge if is_night else 0)

if st.sidebar.button("Add Flight"):
    add_flight(date.strftime("%Y-%m-%d"), flight_type, duration, instructor, is_xc, is_night, cost_per_hour)

# -----------------------
# CSV Import
# -----------------------
st.sidebar.header("Bulk Import Flights (CSV)")
csv_file = st.sidebar.file_uploader("Upload CSV (date,flight_type,duration,instructor,is_xc,is_night,cost_per_hour)", type=["csv"])
if csv_file:
    imported_df = pd.read_csv(csv_file)
    for _, row in imported_df.iterrows():
        add_flight(
            str(row['date']),
            row['flight_type'],
            float(row['duration']),
            row.get('instructor',''),
            int(row.get('is_xc',0)),
            int(row.get('is_night',0)),
            float(row.get('cost_per_hour', cost_defaults.get(row['flight_type'],0)))
        )
    st.sidebar.success(f"Imported {len(imported_df)} flights!")

planned_hours_per_week = st.sidebar.number_input("Planned Flight Hours / Week", min_value=0.0, step=1.0)

# -----------------------
# Main Dashboard
# -----------------------
df = get_flights()
totals,costs = calculate_totals(df)
remaining,status = calculate_remaining(totals,targets)
est_checkride = estimate_checkride_date(totals,targets,planned_hours_per_week)
avg_cost_per_hour = costs["Total"]/max(totals["Total"],1)
est_remaining_cost = estimate_remaining_cost(totals,targets,avg_cost_per_hour)

st.subheader("🛫 Flight Progress by Category")
progress_df = pd.DataFrame({
    'Category': ["Dual", "Solo", "XC", "Night"],
    'Completed': [totals["Dual"], totals["Solo"], totals["XC"], totals["Night"]],
    'Target': [targets["Dual"], targets["Solo"], targets["XC"], targets["Night"]]
})
progress_df["Percent"] = (progress_df["Completed"] / progress_df["Target"]).clip(upper=1.0) * 100

for _, row in progress_df.iterrows():
    bar_color = "green" if row["Percent"] >= 100 else "yellow" if row["Percent"] >= 50 else "red"
    st.write(f"**{row['Category']}**: {row['Completed']:.1f}/{row['Target']} hours")
    st.progress(row["Percent"]/100)
    st.markdown(f"<span style='color:{bar_color};'>Status: {status[row['Category']]}</span>", unsafe_allow_html=True)

st.markdown("### Estimated Checkride & Cost")
col1, col2, col3 = st.columns(3)
col1.metric("✅ Total Hours", f"{totals['Total']:.1f}")
col2.metric("📅 Est. Checkride", est_checkride)
col3.metric("💰 Total Spent", f"${costs['Total']:.2f}")
st.write(f"Estimated Remaining Cost to Target: **${est_remaining_cost:.2f}**")
st.write(f"Projected Total Cost: **${costs['Total'] + est_remaining_cost:.2f}**")

# -----------------------
# Edit/Delete Flights
# -----------------------
st.subheader("Edit or Delete Existing Flights")
if not df.empty:
    flight_options = df.apply(lambda x: f"{x['id']}: {x['date']} | {x['flight_type']} | {x['duration']}h | ${x['cost_per_hour']}/hr | XC:{x['is_xc']} | Night:{x['is_night']} | {x['instructor']}", axis=1).tolist()
    selected = st.selectbox("Select a flight to edit/delete", [""] + flight_options)
    if selected:
        flight_id = selected.split(":")[0]
        row = df[df['id']==flight_id].iloc[0]

        new_date = st.date_input("Flight Date", datetime.strptime(row['date'],"%Y-%m-%d"))
        new_type = st.selectbox("Flight Type", ["Dual","Solo"], index=["Dual","Solo"].index(row['flight_type']))
        new_duration = st.number_input("Duration (hours)", min_value=0.0, step=0.1, value=float(row['duration']))
        new_instructor = st.text_input("Instructor", value=row['instructor'] if row['instructor'] else "")
        new_is_xc = st.checkbox("XC Flight", value=bool(row['is_xc']))
        new_is_night = st.checkbox("Night Flight", value=bool(row['is_night']))
        new_cost = st.number_input("Cost per Hour ($)", min_value=0.0, step=1.0, value=float(row['cost_per_hour']))

        col1,col2 = st.columns(2)
        with col1:
            if st.button("Update Flight"):
                update_flight(flight_id,new_date.strftime("%Y-%m-%d"),new_type,new_duration,new_instructor,new_is_xc,new_is_night,new_cost)
        with col2:
            if st.button("Delete Flight"):
                delete_flight(flight_id)
else:
    st.write("No flights yet.")