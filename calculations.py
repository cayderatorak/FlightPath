# calculations.py
import pandas as pd
from datetime import datetime, timedelta

def calculate_totals(df):
    """
    Calculate total hours and costs for a given dataframe of flights.
    Returns exactly 2 items to match app.py:
    totals dict and total_cost.
    """
    totals = {}
    totals["Dual"] = df[df.flight_type == "Dual"].duration.sum()
    totals["Solo"] = df[df.flight_type == "Solo"].duration.sum()
    totals["XC"] = df[df.is_xc == True].duration.sum()
    totals["Night"] = df[df.is_night == True].duration.sum()
    totals["Total"] = df.duration.sum()

    total_cost = (df.duration * df.cost_per_hour).sum()

    return totals, total_cost

def estimate_checkride(totals, targets, hours_week):
    """
    Predict checkride date based on remaining hours and weekly schedule.
    """
    remaining = max(targets["Total"] - totals["Total"], 0)
    if hours_week == 0:
        return "Enter hours/week"
    weeks = remaining / hours_week
    date = datetime.today() + timedelta(weeks=weeks)
    return date.strftime("%b %d %Y")