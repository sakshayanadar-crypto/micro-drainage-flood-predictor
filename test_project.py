"""Run:  python -m unittest discover tests   (from the project root)"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import collector, config, db, engine  # noqa: E402

ZONE = dict(drain_capacity_mm_hr=25, blockage_pct=30, elevation_m=3, curve_number=92)


class Tests(unittest.TestCase):
    def test_preprocess_cleans_bad_values(self):
        times = [f"2026-10-{21 + h // 24:02d}T{h % 24:02d}:00" for h in range(48)]
        raw = {"current": {"time": "2026-10-22T14:15", "temperature_2m": 28},
               "hourly": {"time": times, "precipitation": [None, -5, "x"] + [1.0] * 45,
                          "soil_moisture_0_to_1cm": [0.3] * 48}}
        w = collector.preprocess(raw)
        self.assertGreaterEqual(w["rain_24h"], 0)
        self.assertLessEqual(w["soil_saturation"], 1)

    def test_empty_payload_rejected(self):
        with self.assertRaises(ValueError):
            collector.preprocess({})

    def test_dry_weather_is_low(self):
        w = dict(rain_1h=0, rain_24h=0, forecast_3h=0, soil_saturation=0.2)
        self.assertEqual(engine.predict(ZONE, w, 0)["risk_level"], "Low")

    def test_storm_is_high_or_severe(self):
        w = collector.simulate(40)
        self.assertIn(engine.predict(ZONE, w, 0)["risk_level"], ("High", "Severe"))

    def test_blockage_raises_risk(self):
        w = collector.simulate(15)
        clear = engine.predict(dict(ZONE, blockage_pct=0), w, 0)["risk_score"]
        blocked = engine.predict(dict(ZONE, blockage_pct=60), w, 0)["risk_score"]
        self.assertGreater(blocked, clear)

    def test_database_seeds_zones(self):
        config.SQLITE_PATH = os.path.join(tempfile.mkdtemp(), "t.db")
        db.MYSQL = False
        db.init_db()
        self.assertEqual(len(db.query("SELECT * FROM zones")), 8)


if __name__ == "__main__":
    unittest.main()
