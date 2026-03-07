# milestones.py

def next_milestone(totals: dict):
    milestones = [10, 20, 30, 40, 50]
    total = totals.get("Total",0)
    for m in milestones:
        if total < m:
            return f"{m} Hours"
    return "All milestones reached"