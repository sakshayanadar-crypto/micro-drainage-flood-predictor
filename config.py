"""Reads config.ini (standard library only)."""
import configparser
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_cp = configparser.ConfigParser()
_cp.read(os.path.join(ROOT, "config.ini"))

PORT = _cp.getint("server", "port", fallback=8000)
REFRESH_SECONDS = _cp.getint("server", "refresh_seconds", fallback=900)
ENGINE = os.environ.get("DB_ENGINE", _cp.get("database", "engine", fallback="sqlite")).lower()
SQLITE_PATH = os.path.join(ROOT, "database", "flood.db")
MYSQL = dict(
    host=_cp.get("mysql", "host", fallback="localhost"),
    port=_cp.getint("mysql", "port", fallback=3306),
    user=_cp.get("mysql", "user", fallback="root"),
    password=_cp.get("mysql", "password", fallback=""),
    database=_cp.get("mysql", "database", fallback="flood_predictor"),
)
REPORT_WINDOW_HOURS = 6      # public reports counted toward risk
ALERT_COOLDOWN_HOURS = 3     # don't repeat the same-level alert for a zone
