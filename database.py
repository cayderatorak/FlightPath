# database.py
from supabase import create_client
import streamlit as st
import pandas as pd

# Connect to Supabase using Streamlit secrets
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Function to load flights for a user and track
def load_flights(track, user_id):
    resp = supabase.table("flights") \
        .select("*") \
        .eq("track", track) \
        .eq("user_id", user_id) \
        .order("date") \
        .execute()
    
    data = resp.data if resp.data else []
    df = pd.DataFrame(data)
    
    if df.empty:
        df = pd.DataFrame(columns=[
            "id","date","flight_type","duration",
            "aircraft","instructor",
            "is_xc","is_night","cost_per_hour","track"
        ])
    return df