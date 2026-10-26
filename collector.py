"""Data Collection & Pre-processing (Python, standard library only).
Get live data from APIs -> clean & validate -> format for analysis."""
import json
import urllib.parse
import urllib.request

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"   # free, no API key


def fetch_weather(lat, lng):
    """Fetch live + recent + forecast rainfall for one location over HTTPS."""
    qs = urllib.parse.urlencode({
        "latitude": lat, "longitude": lng,
        "current": "temperature_2m,relative_humidity_2m,precipitation",
        "hourly": "precipitation,soil_moisture_0_to_1cm",
        "past_days": 1, "forecast_days": 1, "timezone": "auto",
    })
    with urllib.request.urlopen(f"{WEATHER_URL}?{qs}", timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def _num(v, lo, hi, default=0.0):
    """Validate a number: None / NaN / text are replaced, out-of-range values are clamped."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    if x != x:
        return default
    return max(lo, min(hi, x))


def preprocess(raw):
    """Clean + validate the raw API payload and format it for the prediction engine."""
    h = raw.get("hourly") or {}
    times = h.get("time") or []
    if not times:
        raise ValueError("Weather service returned no hourly data")
    precip = [_num(v, 0, 300) for v in h.get("precipitation", [])]
    soil = [_num(v, 0, 0.6, None) for v in h.get("soil_moisture_0_to_1cm", [])]

    cur = raw.get("current") or {}
    hour_key = str(cur.get("time", ""))[:13]
    idx = next((i for i, t in enumerate(times) if t[:13] == hour_key), min(23, len(times) - 1))
    soil_now = soil[idx] if idx < len(soil) and soil[idx] is not None else 0.25
    return {
        "rain_1h": precip[idx],
        "rain_24h": round(sum(precip[max(0, idx - 23): idx + 1]), 2),
        "forecast_3h": round(sum(precip[idx + 1: idx + 4]), 2),
        "temperature": _num(cur.get("temperature_2m"), -20, 60, None),
        "humidity": _num(cur.get("relative_humidity_2m"), 0, 100, None),
        "soil_saturation": round(min(1.0, soil_now / 0.5), 3),
    }


def simulate(mm_per_hour):
    """Synthetic storm for demos / testing when it is not raining. Not real data."""
    mm = _num(mm_per_hour, 0, 150)
    return {"rain_1h": mm, "rain_24h": round(mm * 3, 1), "forecast_3h": round(mm * 2, 1),
            "temperature": 27.0, "humidity": 95.0, "soil_saturation": 0.9}
