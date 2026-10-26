// runoff.cpp - C++ module: SCS Curve-Number runoff and street ponding depth estimate.
#include <algorithm>
#include <cmath>

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

extern "C" EXPORT double ponding_depth_cm(double rain_24h, double forecast_3h,
                                          double curve_number, double eff_capacity,
                                          double elevation_m)
{
    const double P = rain_24h + forecast_3h;                 // mm of rain
    const double S = 25400.0 / curve_number - 254.0;         // potential retention (mm)
    const double Ia = 0.2 * S;                               // initial abstraction
    const double Q = P > Ia ? std::pow(P - Ia, 2) / (P - Ia + S) : 0.0;   // runoff (mm)
    const double excess = std::max(0.0, Q - eff_capacity * 4.0);          // what drains can't clear in ~4 h
    const double lowLying = 1.0 + std::max(0.0, 5.0 - elevation_m) / 5.0; // water collects in low areas
    return (excess / 10.0) * lowLying;                       // cm
}
