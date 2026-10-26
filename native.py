"""Bridge to the optional native modules (C and C++) via ctypes.
If the shared libraries have not been compiled, pure-Python fallbacks
with identical maths are used, so the website always works."""
import ctypes
import os
import platform

BUILD = os.path.join(os.path.dirname(__file__), "..", "modules", "build")
EXT = {"Windows": ".dll", "Darwin": ".dylib"}.get(platform.system(), ".so")


def _load(name):
    path = os.path.abspath(os.path.join(BUILD, name + EXT))
    try:
        return ctypes.CDLL(path)
    except OSError:
        return None


_c = _load("risk_core")      # C module
_cpp = _load("runoff")       # C++ module
D = ctypes.c_double

if _c:
    _c.flood_risk_score.restype = D
    _c.flood_risk_score.argtypes = [D, D, D, D, D, D, ctypes.c_int]
if _cpp:
    _cpp.ponding_depth_cm.restype = D
    _cpp.ponding_depth_cm.argtypes = [D, D, D, D, D]


def status():
    return {"c_module": bool(_c), "cpp_module": bool(_cpp)}


def risk_score(rain_1h, rain_24h, forecast_3h, eff_capacity, soil_sat, elevation, reports):
    if _c:
        return _c.flood_risk_score(rain_1h, rain_24h, forecast_3h, eff_capacity,
                                   soil_sat, elevation, int(reports))
    intensity = rain_1h + forecast_3h / 3.0
    ratio = intensity / eff_capacity if eff_capacity > 0 else 1.5
    s = 45 * min(max(ratio, 0), 1.5) / 1.5
    s += 25 * min(rain_24h / 150.0, 1)
    s += 10 * min(max(soil_sat, 0), 1)
    s += 10 * min(max((10 - elevation) / 10.0, 0), 1)
    s += 2 * min(reports, 5)
    return min(s, 100.0)


def ponding_cm(rain_24h, forecast_3h, curve_number, eff_capacity, elevation):
    if _cpp:
        return _cpp.ponding_depth_cm(rain_24h, forecast_3h, curve_number, eff_capacity, elevation)
    p = rain_24h + forecast_3h
    s = 25400.0 / curve_number - 254.0
    ia = 0.2 * s
    q = ((p - ia) ** 2) / (p - ia + s) if p > ia else 0.0
    excess = max(0.0, q - eff_capacity * 4.0)
    return (excess / 10.0) * (1.0 + max(0.0, 5.0 - elevation) / 5.0)
