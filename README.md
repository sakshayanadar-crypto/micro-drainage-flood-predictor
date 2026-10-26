# Micro-Drainage & Localized Flood Predictor (basic libraries only)

No Flask, no pip packages, no npm. Everything uses Python's standard library and plain
HTML/CSS/JavaScript.

## Architecture (matches the system diagram)

| Diagram block | Implementation | Files |
|---|---|---|
| Live Data Sources | Open-Meteo weather API, browser location, public flood reports | `backend/collector.py`, `frontend/js/app.js` |
| Data Collection & Pre-processing (Python) | fetch (urllib), clean and validate, format | `backend/collector.py` |
| Flood Prediction Engine (Python) | rainfall + location + drain condition -> risk level | `backend/engine.py`, `backend/native.py` |
| Optional C module | risk score 0-100 | `modules/c/risk_core.c` |
| Optional C++ module | SCS runoff / water depth | `modules/cpp/runoff.cpp` |
| Optional Java module | text report generator | `modules/java/ReportGenerator.java` |
| Database | SQLite (built in) or MySQL | `backend/db.py`, `database/schema.sql` |
| Website Dashboard (HTML+CSS+JS) | map, live table, alerts, reports | `frontend/` |
| Users | view live data, check flood risk, receive alerts | dashboard |

Libraries used, all built into Python: `http.server`, `urllib`, `json`, `sqlite3`, `configparser`,
`threading`, `ctypes`, `csv`, `subprocess`, `tempfile`, `math`, `re`, `os`, `datetime`, `unittest`.

## Run in VS Code

1. Install Python 3.10+ (tick "Add Python to PATH") and the VS Code **Python** extension.
2. Extract the zip, then File > Open Folder > `flood-predictor-basic`.
3. Open the terminal (Terminal > New Terminal) and run:
   ```
   python backend/server.py
   ```
   (or press F5 and choose "Run Flood Predictor").
4. Open http://localhost:8000 and press **Refresh live data**.
   The database file is created automatically on first start.
5. Stop with Ctrl+C.

If `python` is not found, try `py backend/server.py` on Windows or `python3` on Mac/Linux.

No rain today? Use the **Storm simulator** panel to test the whole system with a made-up storm.
Simulated rows are labelled "simulated" in the database and in the dashboard.

## Optional: use MySQL (as in the diagram)

Python has no built-in MySQL driver, so this one step needs a package:
```
pip install mysql-connector-python
```
Then edit `config.ini`: set `engine = mysql` and put your password in `[mysql]`.
Start the server; it creates the database and tables itself (`database/schema.sql` is the same
schema if you prefer to create it by hand). Everything else is unchanged.

## Optional: C, C++ and Java modules

Install gcc, g++ and a JDK, then in Git Bash (Windows) or a terminal: `sh modules/build.sh`.
Restart the server and open http://localhost:8000/api/health to confirm `c_module` and `cpp_module`
are true. Without them, Python code with identical maths runs instead.

## Tests

```
python -m unittest discover tests
```

## How the prediction works

1. Effective drain capacity = design capacity x (1 - blockage%).
2. Risk score 0-100: drain overload (45) + 24 h rain (25) + soil saturation (10) + low elevation (10)
   + public reports in last 6 h (10). Levels: Low <25, Moderate <50, High <75, Severe >=75.
3. Water depth estimate: SCS Curve Number runoff minus what drains clear in about 4 h, scaled for low ground.
4. Alerts for Moderate/High/Severe, with a 3 hour cooldown per zone and level.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/zones` | latest readings and risk per zone |
| GET | `/api/check?lat=&lng=` | risk at the nearest zone |
| GET | `/api/zones/<id>/history?hours=48` | risk trend |
| GET | `/api/alerts` | latest alerts |
| GET / POST | `/api/reports` | public flood reports |
| GET | `/api/report` | text summary (Java module if available) |
| POST | `/api/refresh` | fetch live data and predict now |
| POST | `/api/simulate` | body `{"mm_per_hour": 35}` |

## For your research write-up

- Zone settings in `database/zones_seed.json` (drain capacity, blockage, curve number, elevation) are
  **illustrative placeholders**. Replace them with municipal or field-survey data and cite the source.
  To change zones after the first run, delete `database/flood.db` and restart.
- Validate predictions against `public_reports` and known flood events; calibrate the weights in
  `risk_core.c`; compare with a rainfall-only baseline.
- Limitations: weather data is gridded (about 10 km), water depth is a heuristic, reports are unverified.
- The map uses OpenStreetMap tiles and needs internet; the rest of the dashboard works offline
  with simulated data.
