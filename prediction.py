def predict_solo(flights):

    total_hours = sum(float(f["duration"]) for f in flights)

    pattern_flights = sum(
        1 for f in flights if "pattern" in f["flight_type"].lower()
    )

    score = 0

    if total_hours >= 10:
        score += 40

    if pattern_flights >= 5:
        score += 30

    if total_hours >= 15:
        score += 30

    probability = min(score, 100)

    flights_remaining = max(0, int((15 - total_hours) / 1.2))

    return probability, flights_remaining