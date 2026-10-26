"""Database layer. SQLite (built into Python) by default; MySQL if config.ini says so.
All SQL uses '?' placeholders; they are converted to '%s' for MySQL."""
import datetime
import decimal
import json
import os
import sqlite3

import config

MYSQL = config.ENGINE == "mysql"


def now_utc(hours_ago=0):
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours_ago)
    return t.strftime("%Y-%m-%d %H:%M:%S")


def _iso(v):
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(v).replace(" ", "T")[:19] + "Z"


def connect(with_database=True):
    if MYSQL:
        import mysql.connector            # the only non-standard package, and only for MySQL
        cfg = dict(config.MYSQL)
        if not with_database:
            cfg.pop("database")
        return mysql.connector.connect(**cfg)
    conn = sqlite3.connect(config.SQLITE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _run(sql, params, fetch):
    conn = connect()
    try:
        if MYSQL:
            cur = conn.cursor(dictionary=True)
            sql = sql.replace("?", "%s")
        else:
            cur = conn.cursor()
        cur.execute(sql, tuple(params or ()))
        if fetch:
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                for k, v in d.items():
                    if isinstance(v, decimal.Decimal):
                        d[k] = float(v)
                    elif k.endswith("_at") and v is not None:
                        d[k] = _iso(v)
                rows.append(d)
            return rows
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def query(sql, params=None):
    return _run(sql, params, True)


def execute(sql, params=None):
    return _run(sql, params, False)


def init_db():
    """Create tables (and the MySQL database) if missing, then seed the zones."""
    if MYSQL:
        c = connect(with_database=False)
        c.cursor().execute(f"CREATE DATABASE IF NOT EXISTS `{config.MYSQL['database']}` CHARACTER SET utf8mb4")
        c.close()
    pk = "INT AUTO_INCREMENT PRIMARY KEY" if MYSQL else "INTEGER PRIMARY KEY AUTOINCREMENT"
    tables = [
        f"""CREATE TABLE IF NOT EXISTS zones (id {pk}, name VARCHAR(100) NOT NULL, lat DOUBLE NOT NULL,
            lng DOUBLE NOT NULL, elevation_m DOUBLE NOT NULL, drain_capacity_mm_hr DOUBLE NOT NULL,
            blockage_pct DOUBLE NOT NULL, curve_number INT NOT NULL)""",
        f"""CREATE TABLE IF NOT EXISTS live_data (id {pk}, zone_id INT NOT NULL, recorded_at DATETIME NOT NULL,
            rain_1h DOUBLE, rain_24h DOUBLE, forecast_3h DOUBLE, temperature DOUBLE, humidity DOUBLE,
            soil_saturation DOUBLE, source VARCHAR(10) NOT NULL DEFAULT 'live',
            FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE)""",
        f"""CREATE TABLE IF NOT EXISTS predictions (id {pk}, zone_id INT NOT NULL, created_at DATETIME NOT NULL,
            risk_score DOUBLE NOT NULL, risk_level VARCHAR(10) NOT NULL, ponding_cm DOUBLE NOT NULL,
            rain_1h DOUBLE, source VARCHAR(10) NOT NULL DEFAULT 'live',
            FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE)""",
        f"""CREATE TABLE IF NOT EXISTS alerts (id {pk}, zone_id INT NOT NULL, created_at DATETIME NOT NULL,
            level VARCHAR(10) NOT NULL, message VARCHAR(300) NOT NULL,
            FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE)""",
        f"""CREATE TABLE IF NOT EXISTS public_reports (id {pk}, zone_id INT NULL, lat DOUBLE NOT NULL,
            lng DOUBLE NOT NULL, water_level_cm INT NOT NULL, description VARCHAR(300),
            created_at DATETIME NOT NULL,
            FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL)""",
    ]
    for t in tables:
        execute(t)
    if query("SELECT COUNT(*) AS n FROM zones")[0]["n"] == 0:
        seed = os.path.join(config.ROOT, "database", "zones_seed.json")
        with open(seed, encoding="utf-8") as f:
            for z in json.load(f):
                execute("INSERT INTO zones (name,lat,lng,elevation_m,drain_capacity_mm_hr,blockage_pct,curve_number)"
                        " VALUES (?,?,?,?,?,?,?)",
                        (z["name"], z["lat"], z["lng"], z["elevation_m"], z["drain_capacity_mm_hr"],
                         z["blockage_pct"], z["curve_number"]))
