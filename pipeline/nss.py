"""Nelson-Siegel(-Svensson) yield-curve fitting.

Used for the French leg (no identical twin): each day a conventional OAT curve is
fitted to the available conventional yields, then greenium = fitted-conventional-
yield(at the green bond's maturity) - green yield. NSS is the default; the simpler
4-parameter Nelson-Siegel is provided as a robustness spec.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares


def _ns_factors(tau, lam):
    """Nelson-Siegel loadings at maturities `tau` for decay `lam` (>0)."""
    tau = np.maximum(np.asarray(tau, float), 1e-6)
    x = tau / lam
    slope = (1 - np.exp(-x)) / x
    curve = slope - np.exp(-x)
    return slope, curve


def ns_yield(params, tau):
    """4-param Nelson-Siegel yield: beta0 + beta1*slope + beta2*curve."""
    b0, b1, b2, lam = params
    slope, curve = _ns_factors(tau, lam)
    return b0 + b1 * slope + b2 * curve


def nss_yield(params, tau):
    """6-param Nelson-Siegel-Svensson yield (two curvature terms)."""
    b0, b1, b2, b3, lam1, lam2 = params
    s1, c1 = _ns_factors(tau, lam1)
    _, c2 = _ns_factors(tau, lam2)
    return b0 + b1 * s1 + b2 * c1 + b3 * c2


def fit_ns(tau, y, lam_init=2.0):
    tau = np.asarray(tau, float)
    y = np.asarray(y, float)
    ok = np.isfinite(tau) & np.isfinite(y)
    tau, y = tau[ok], y[ok]
    if len(tau) < 4:
        return None
    p0 = [float(y[-1]), float(y[0] - y[-1]), 0.0, lam_init]
    lb = [-20, -50, -50, 0.05]
    ub = [40, 50, 50, 30]
    res = least_squares(lambda p: ns_yield(p, tau) - y, p0, bounds=(lb, ub),
                        max_nfev=10000)
    rmse = float(np.sqrt(np.mean(res.fun ** 2)))
    return {"params": res.x.tolist(), "rmse": rmse, "kind": "ns", "n": int(len(tau))}


def fit_nss(tau, y, lam1_init=1.5, lam2_init=8.0):
    """Fit NSS; fall back to NS if the data are too sparse for 6 params."""
    tau = np.asarray(tau, float)
    y = np.asarray(y, float)
    ok = np.isfinite(tau) & np.isfinite(y)
    tau, y = tau[ok], y[ok]
    if len(tau) < 6:
        return fit_ns(tau, y, lam_init=lam1_init)
    p0 = [float(y[-1]), float(y[0] - y[-1]), 0.0, 0.0, lam1_init, lam2_init]
    lb = [-20, -50, -50, -50, 0.05, 0.05]
    ub = [40, 50, 50, 50, 30, 60]
    try:
        res = least_squares(lambda p: nss_yield(p, tau) - y, p0, bounds=(lb, ub),
                            max_nfev=20000)
        rmse = float(np.sqrt(np.mean(res.fun ** 2)))
        return {"params": res.x.tolist(), "rmse": rmse, "kind": "nss",
                "n": int(len(tau))}
    except Exception:  # noqa: BLE001
        return fit_ns(tau, y, lam_init=lam1_init)


def curve_value(fit: dict, tau_target: float) -> float:
    """Evaluate a fitted curve at a single maturity (years)."""
    if fit is None:
        return float("nan")
    p = fit["params"]
    return float(nss_yield(p, np.array([tau_target]))[0] if fit["kind"] == "nss"
                 else ns_yield(p, np.array([tau_target]))[0])
