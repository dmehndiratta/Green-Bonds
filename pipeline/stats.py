"""Inference helpers: stationary block bootstrap, HAC/Newey-West SEs, and a
small cluster-robust OLS used by the FE panel.

The greenium is a few basis points and the daily series is strongly serially
dependent, so naive iid SEs would be badly understated. Everything here respects
that dependence (block bootstrap on the level/trend; Newey-West on regression
coefficients).
"""
from __future__ import annotations

import numpy as np
from scipy import stats

EPS = 1e-12


# --- stationary block bootstrap (Politis-Romano) ---------------------------
def stationary_bootstrap_indices(n: int, mean_block: int, rng) -> np.ndarray:
    """Vectorised stationary bootstrap index draw (geometric block lengths)."""
    p = 1.0 / max(mean_block, 1)
    restarts = rng.random(n) < p
    restarts[0] = True
    starts = rng.integers(0, n, size=n)
    block_id = np.cumsum(restarts) - 1
    block_start_pos = np.flatnonzero(restarts)
    pos = np.arange(n)
    start_pos = block_start_pos[block_id]
    offset = pos - start_pos
    base = starts[start_pos]
    return (base + offset) % n


def block_bootstrap_ci(x, stat_fn, n_boot: int, block_len: int, seed: int,
                       alpha: float = 0.05) -> dict:
    """Block-bootstrap CI for a scalar statistic of a 1-D series `x`."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    rng = np.random.default_rng(seed)
    n = len(x)
    if n < 3:
        pt = float(stat_fn(x)) if n else float("nan")
        return {"point": pt, "lo": float("nan"), "hi": float("nan"), "n": n}
    vals = []
    for _ in range(n_boot):
        idx = stationary_bootstrap_indices(n, block_len, rng)
        v = stat_fn(x[idx])
        if np.isfinite(v):
            vals.append(v)
    vals = np.asarray(vals)
    return {
        "point": float(stat_fn(x)),
        "lo": float(np.quantile(vals, alpha / 2)),
        "hi": float(np.quantile(vals, 1 - alpha / 2)),
        "se": float(np.std(vals, ddof=1)),
        "n": int(n),
    }


def block_bootstrap_trend(t, y, n_boot: int, block_len: int, seed: int,
                          alpha: float = 0.05) -> dict:
    """Block-bootstrap CI for an OLS slope of y on t (the compression trend).

    Resamples contiguous blocks of the (t, y) pairs to preserve serial structure.
    """
    t = np.asarray(t, float)
    y = np.asarray(y, float)
    ok = np.isfinite(t) & np.isfinite(y)
    t, y = t[ok], y[ok]
    n = len(t)

    def slope(tt, yy):
        tt = tt - tt.mean()
        denom = float(np.dot(tt, tt))
        return float(np.dot(tt, yy - yy.mean()) / denom) if denom > EPS else float("nan")

    if n < 5:
        return {"point": slope(t, y), "lo": float("nan"), "hi": float("nan"), "n": n}
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        idx = stationary_bootstrap_indices(n, block_len, rng)
        v = slope(t[idx], y[idx])
        if np.isfinite(v):
            vals.append(v)
    vals = np.asarray(vals)
    return {
        "point": slope(t, y),
        "lo": float(np.quantile(vals, alpha / 2)),
        "hi": float(np.quantile(vals, 1 - alpha / 2)),
        "n": int(n),
    }


# --- HAC / Newey-West long-run variance of a mean ---------------------------
def newey_west_mean(x, bandwidth: int | None = None) -> dict:
    """Mean of x with a Newey-West (Bartlett-kernel) HAC standard error."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 2:
        return {"mean": float(x.mean()) if n else float("nan"),
                "se": float("nan"), "t": float("nan"), "n": n}
    if bandwidth is None:
        bandwidth = int(np.floor(4 * (n / 100.0) ** (2.0 / 9.0)))  # Newey-West rule
    xc = x - x.mean()
    gamma0 = float(np.mean(xc * xc))
    lrv = gamma0
    for lag in range(1, bandwidth + 1):
        w = 1.0 - lag / (bandwidth + 1.0)
        cov = float(np.mean(xc[lag:] * xc[:-lag]))
        lrv += 2.0 * w * cov
    se = float(np.sqrt(max(lrv, EPS) / n))
    mean = float(x.mean())
    t = mean / se if se > 0 else float("nan")
    p = float(2 * (1 - stats.norm.cdf(abs(t)))) if np.isfinite(t) else float("nan")
    return {"mean": mean, "se": se, "t": t, "p_value": p, "n": int(n),
            "bandwidth": int(bandwidth)}


# --- cluster-robust OLS (for the FE panel) ---------------------------------
def cluster_robust_ols(X: np.ndarray, y: np.ndarray, clusters: np.ndarray) -> dict:
    """OLS with cluster-robust (sandwich) covariance.

    X already includes any intercept/columns the caller wants. Returns betas, a
    cluster-robust covariance, SEs and two-sided p-values.
    """
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    n, k = X.shape
    XtX = X.T @ X
    XtX_inv = np.linalg.pinv(XtX)
    beta = XtX_inv @ (X.T @ y)
    resid = y - X @ beta
    uniq = np.unique(clusters)
    G = len(uniq)
    meat = np.zeros((k, k))
    for g in uniq:
        m = clusters == g
        Xg = X[m]
        ug = resid[m]
        sg = Xg.T @ ug
        meat += np.outer(sg, sg)
    dof = (G / max(G - 1, 1)) * ((n - 1) / max(n - k, 1))  # small-sample adj.
    cov = dof * (XtX_inv @ meat @ XtX_inv)
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    with np.errstate(divide="ignore", invalid="ignore"):
        tvals = np.where(se > 0, beta / se, np.nan)
    pvals = 2 * (1 - stats.t.cdf(np.abs(tvals), df=max(G - 1, 1)))
    return {"beta": beta, "se": se, "t": tvals, "p_value": pvals,
            "cov": cov, "n": int(n), "n_clusters": int(G)}
