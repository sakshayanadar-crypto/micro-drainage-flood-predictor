"""Report generation: uses the optional Java module, falls back to Python."""
import csv
import os
import shutil
import subprocess
import tempfile

BUILD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "modules", "build"))
FIELDS = ["name", "risk_level", "risk_score", "ponding_cm", "rain_1h", "rain_24h", "forecast_3h"]


def _python_report(rows):
    rows = sorted(rows, key=lambda r: -float(r["risk_score"]))
    lines = ["MICRO-DRAINAGE & LOCALIZED FLOOD REPORT", f"Zones monitored: {len(rows)}", ""]
    lines.append(f"{'Zone':<28} {'Level':<9} {'Score':>6} {'Water cm':>9}")
    for r in rows:
        lines.append(f"{r['name']:<28} {r['risk_level']:<9} {r['risk_score']:>6} {r['ponding_cm']:>9}")
    return "\n".join(lines)


def build_report(rows):
    rows = [r for r in rows if r.get("risk_level")]
    if not rows:
        return "No predictions yet. Press Refresh live data first."
    java_ready = shutil.which("java") and os.path.exists(os.path.join(BUILD, "ReportGenerator.class"))
    if not java_ready:
        return _python_report(rows)
    with tempfile.TemporaryDirectory() as d:
        src, out = os.path.join(d, "in.csv"), os.path.join(d, "out.txt")
        with open(src, "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(FIELDS)
            for r in rows:
                wr.writerow([str(r[k]).replace(",", " ") for k in FIELDS])
        try:
            subprocess.run(["java", "-cp", BUILD, "ReportGenerator", src, out], check=True, timeout=20)
            with open(out, encoding="utf-8") as f:
                return f.read()
        except Exception:
            return _python_report(rows)
