# achievements.py

def calculate_achievements(totals: dict):
    """
    Returns a list of badges based on flight totals.
    Example logic: Dual, Solo, XC, Night milestones
    """
    badges = []
    if totals.get("Dual",0) >= 10:
        badges.append("Dual Flight Milestone Achieved")
    if totals.get("Solo",0) >= 5:
        badges.append("Solo Flight Milestone Achieved")
    if totals.get("XC",0) >= 5:
        badges.append("Cross-Country Milestone Achieved")
    if totals.get("Night",0) >= 3:
        badges.append("Night Flight Milestone Achieved")
    if totals.get("Total",0) >= 40:
        badges.append("Total Flight Hours Completed")
    return badges