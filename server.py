"""Web server + REST API using only Python's standard library (http.server)."""
import json
import math
import mimetypes
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import collector
import config
import db
import engine
import native
import reports

FRONTEND = os.path.join(config.ROOT, "frontend")
CYCLE_LOCK = threading.Lock()

LATEST_SQL = """
SELECT z.id, z.name, z.lat, z.lng, z.elevation_m, z.drain_capacity_mm_hr, z.blockage_pct,
       p.risk_score, p.risk_level, p.ponding_cm, p.created_at AS predicted_at, p.source,
       l.rain_1h, l.rain_24h, l.forecast_3h, l.temperature, l.humidity, l.soil_saturation
FROM zones z
LEFT JOIN predictions p ON p.id = (SELECT MAX(id) FROM predictions WHERE zone_id = z.id)
LEFT JOIN live_data   l ON l.id = (SELECT MAX(id) FROM live_data   WHERE zone_id = z.id)
ORDER BY z.name
"""


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# ------------------------------------------------------------------ pipeline
def run_cycle(simulate_mm=None):
    """Collect -> pre-process -> predict -> store -> alert, for every zone."""
    source = "live" if simulate_mm is None else "simulated"
    result = {"updated": 0, "failed": [], "source": source}
    with CYCLE_LOCK:
        for zone in db.query("SELECT * FROM zones"):
            try:
                if simulate_mm is None:
                    w = collector.preprocess(collector.fetch_weather(zone["lat"], zone["lng"]))
                else:
                    w = collector.simulate(simulate_mm)
                n = db.query("SELECT COUNT(*) AS n FROM public_reports WHERE zone_id=? AND created_at>?",
                             (zone["id"], db.now_utc(config.REPORT_WINDOW_HOURS)))[0]["n"]
                p = engine.predict(zone, w, n)
                now = db.now_utc()
                db.execute("INSERT INTO live_data (zone_id,recorded_at,rain_1h,rain_24h,forecast_3h,temperature,"
                           "humidity,soil_saturation,source) VALUES (?,?,?,?,?,?,?,?,?)",
                           (zone["id"], now, w["rain_1h"], w["rain_24h"], w["forecast_3h"], w["temperature"],
                            w["humidity"], w["soil_saturation"], source))
                db.execute("INSERT INTO predictions (zone_id,created_at,risk_score,risk_level,ponding_cm,rain_1h,source)"
                           " VALUES (?,?,?,?,?,?,?)",
                           (zone["id"], now, p["risk_score"], p["risk_level"], p["ponding_cm"], w["rain_1h"], source))
                if p["risk_level"] != "Low":
                    recent = db.query("SELECT id FROM alerts WHERE zone_id=? AND level=? AND created_at>?",
                                      (zone["id"], p["risk_level"], db.now_utc(config.ALERT_COOLDOWN_HOURS)))
                    if not recent:
                        msg = engine.alert_message(zone, p, w)
                        if source == "simulated":
                            msg = "[Simulation] " + msg
                        db.execute("INSERT INTO alerts (zone_id,created_at,level,message) VALUES (?,?,?,?)",
                                   (zone["id"], now, p["risk_level"], msg[:300]))
                result["updated"] += 1
            except Exception as e:          # one failing zone must not stop the others
                result["failed"].append({"zone": zone["name"], "error": str(e)})
    return result


def worker():
    while True:
        try:
            r = run_cycle()
            if r["failed"]:
                print("Live refresh problem:", r["failed"][0]["error"])
        except Exception as e:
            print("Cycle error:", e)
        time.sleep(config.REFRESH_SECONDS)


# ------------------------------------------------------------------ helpers
def haversine(lat1, lng1, lat2, lng2):
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2 + math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) * math.sin(math.radians(lng2 - lng1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def need_float(d, key):
    try:
        return float(d[key])
    except (KeyError, TypeError, ValueError):
        raise ApiError(f"'{key}' is required and must be a number")


# ------------------------------------------------------------------ routes
def route(method, path, q, body):
    if method == "GET":
        if path == "/api/health":
            return {"status": "ok", "database": config.ENGINE, "native_modules": native.status()}
        if path == "/api/zones":
            return db.query(LATEST_SQL)
        if path == "/api/check":
            lat, lng = need_float(q, "lat"), need_float(q, "lng")
            rows = [z for z in db.query(LATEST_SQL) if z["risk_level"]]
            if not rows:
                raise ApiError("No predictions yet. Press Refresh live data.", 404)
            for z in rows:
                z["distance_km"] = round(haversine(lat, lng, z["lat"], z["lng"]), 2)
            return min(rows, key=lambda z: z["distance_km"])
        m = re.fullmatch(r"/api/zones/(\d+)/history", path)
        if m:
            hours = min(int(q.get("hours", 48)), 24 * 14)
            return db.query("SELECT created_at, risk_score, risk_level, ponding_cm, rain_1h, source FROM predictions "
                            "WHERE zone_id=? AND created_at>? ORDER BY created_at", (int(m.group(1)), db.now_utc(hours)))
        if path == "/api/alerts":
            return db.query("SELECT a.id, a.zone_id, z.name AS zone, a.level, a.message, a.created_at FROM alerts a "
                            "JOIN zones z ON z.id=a.zone_id ORDER BY a.id DESC LIMIT 30")
        if path == "/api/reports":
            return db.query("SELECT r.id, r.lat, r.lng, r.water_level_cm, r.description, r.created_at, z.name AS zone "
                            "FROM public_reports r LEFT JOIN zones z ON z.id=r.zone_id WHERE r.created_at>? "
                            "ORDER BY r.id DESC LIMIT 100", (db.now_utc(24),))
        if path == "/api/report":
            return {"text": reports.build_report(db.query(LATEST_SQL))}
    if method == "POST":
        if path == "/api/refresh":
            return run_cycle()
        if path == "/api/simulate":
            return run_cycle(simulate_mm=need_float(body, "mm_per_hour"))
        if path == "/api/reports":
            lat, lng = need_float(body, "lat"), need_float(body, "lng")
            level = int(need_float(body, "water_level_cm"))
            if not (-90 <= lat <= 90 and -180 <= lng <= 180 and 0 <= level <= 300):
                raise ApiError("Values are out of range")
            zones = db.query("SELECT id, lat, lng FROM zones")
            nearest = min(zones, key=lambda z: haversine(lat, lng, z["lat"], z["lng"]))
            zone_id = nearest["id"] if haversine(lat, lng, nearest["lat"], nearest["lng"]) <= 3 else None
            rid = db.execute("INSERT INTO public_reports (zone_id,lat,lng,water_level_cm,description,created_at) "
                             "VALUES (?,?,?,?,?,?)",
                             (zone_id, lat, lng, level, str(body.get("description", ""))[:300], db.now_utc()))
            return {"id": rid, "zone_id": zone_id}
    raise ApiError("Not found", 404)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):      # keep the terminal quiet
        pass

    def _send(self, status, body, ctype):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _api(self, method, u, body=None):
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            status, data = 200, route(method, u.path, q, body or {})
        except ApiError as e:
            status, data = e.status, {"error": str(e)}
        except Exception as e:
            status, data = 500, {"error": f"Server error: {e}"}
        self._send(status, json.dumps(data).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith("/api/"):
            return self._api("GET", u)
        rel = "index.html" if u.path in ("", "/") else u.path.lstrip("/")
        full = os.path.abspath(os.path.join(FRONTEND, rel))
        if not full.startswith(FRONTEND + os.sep) or not os.path.isfile(full):
            return self._send(404, b"Not found", "text/plain")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)

    def do_POST(self):
        u = urlparse(self.path)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            body = {}
        self._api("POST", u, body if isinstance(body, dict) else {})


def main():
    db.init_db()
    threading.Thread(target=worker, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", config.PORT), Handler)
    print(f"Flood Predictor running at http://localhost:{config.PORT}  (database: {config.ENGINE})")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
