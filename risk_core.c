/* risk_core.c - C module: flood risk score (0-100).
 * Weights: drain overload 45, 24h rainfall 25, soil 10, low-lying 10, public reports 10. */
#include <math.h>

static double clamp(double v, double lo, double hi) { return v < lo ? lo : (v > hi ? hi : v); }

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

EXPORT double flood_risk_score(double rain_1h, double rain_24h, double forecast_3h,
                               double eff_capacity, double soil_sat, double elevation_m,
                               int reports)
{
    double intensity = rain_1h + forecast_3h / 3.0;           /* mm/hr pressure on drains */
    double ratio = eff_capacity > 0.0 ? intensity / eff_capacity : 1.5;
    double score = 45.0 * clamp(ratio, 0.0, 1.5) / 1.5;
    score += 25.0 * clamp(rain_24h / 150.0, 0.0, 1.0);
    score += 10.0 * clamp(soil_sat, 0.0, 1.0);
    score += 10.0 * clamp((10.0 - elevation_m) / 10.0, 0.0, 1.0);
    score += 2.0 * (reports > 5 ? 5 : (reports < 0 ? 0 : reports));
    return clamp(score, 0.0, 100.0);
}
