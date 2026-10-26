"""Flood Prediction Engine (Python).
Analyze rainfall & location -> check drainage conditions -> calculate flood risk level."""
import native


def level_for(score):
    if score < 25:
        return "Low"
    if score < 50:
        return "Moderate"
    if score < 75:
        return "High"
    return "Severe"


def effective_capacity(zone):
    """Drainage condition: design capacity reduced by blockage."""
    return zone["drain_capacity_mm_hr"] * (1 - zone["blockage_pct"] / 100.0)


def predict(zone, w, report_count):
    cap = effective_capacity(zone)
    score = native.risk_score(w["rain_1h"], w["rain_24h"], w["forecast_3h"], cap,
                              w["soil_saturation"], zone["elevation_m"], report_count)
    ponding = native.ponding_cm(w["rain_24h"], w["forecast_3h"], zone["curve_number"],
                                cap, zone["elevation_m"])
    score = round(score, 1)
    return {"risk_score": score, "risk_level": level_for(score), "ponding_cm": round(ponding, 1)}


def alert_message(zone, p, w):
    return (f"{p['risk_level']} flood risk at {zone['name']}: "
            f"{w['rain_1h']:.1f} mm in the last hour, {w['forecast_3h']:.1f} mm expected in 3 h. "
            f"Possible water depth {p['ponding_cm']:.0f} cm. Avoid low-lying roads and subways.")
