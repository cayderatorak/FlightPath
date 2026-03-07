# solo.py
import pandas as pd

def calculate_solo_readiness(df):
    """
    Calculate a % readiness for solo based on PPL track:
    Uses Dual, Solo, XC, and Night requirements.
    Returns 0-100%.
    """
    if df.empty:
        return 0

    # Targets for PPL
    targets = {
        "Dual": 20,
        "Solo": 10,
        "XC": 5,
        "Night": 3,
        "Total": 40
    }

    # Sum current totals
    dual = df[df.flight_type=="Dual"].duration.sum()
    solo = df[df.flight_type=="Solo"].duration.sum()
    xc = df[df.is_xc==True].duration.sum()
    night = df[df.is_night==True].duration.sum()

    # Calculate % completion for each category
    dual_pct = min(dual / targets["Dual"], 1.0)
    solo_pct = min(solo / targets["Solo"], 1.0)
    xc_pct = min(xc / targets["XC"], 1.0)
    night_pct = min(night / targets["Night"], 1.0)

    # Weighted average (example weighting)
    readiness = (dual_pct*0.3 + solo_pct*0.3 + xc_pct*0.2 + night_pct*0.2) * 100
    return round(readiness, 1)