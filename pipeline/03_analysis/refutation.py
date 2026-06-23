"""Refutation suite — the honest stress tests (plan §4).

(a) PLACEBO via the conventional Bund curve. Each day we fit an NSS curve to the
    *conventional* twin legs only, then take each bond's deviation from that
    conventional curve:
      * conventional legs' residuals = a placebo pseudo-greenium -> should centre
        on ~0 (a conventional bond does not deviate from the conventional curve
        beyond noise); if it were large, an apparent greenium could be a mechanical
        maturity/curve artefact.
      * green legs' residuals from the SAME conventional curve -> should be
        negative (~ -greenium), i.e. green bonds sit below the conventional curve.
    Also a simpler placebo: pseudo-spreads between similar- (not identical-)
    maturity conventional legs, which should be ~0.

(b) LIQUIDITY-ONLY model. Regress the within-twin yield gap (green - conv) on the
    within-twin log-amount gap. The intercept is the greenium at equal liquidity:
    if it collapses to ~0, the "greenium" is largely a liquidity premium (a
    falsifying outcome, reported honestly); if it survives, the green label is
    priced beyond liquidity.

(c) SIGN STABILITY. A real greenium should be consistently signed across pairs;
    we report the share of pairs with a positive mean greenium and a sign test.

Writes results_refutation.json.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
from common import PROCESSED, data_mode, load_config, write_json  # noqa: E402
from nss import curve_value, fit_nss  # noqa: E402
from stats import block_bootstrap_ci, cluster_robust_ols  # noqa: E402


def _level(g, cfg) -> dict:
    g = np.asarray(g, float)
    g = g[np.isfinite(g)]
    if g.size == 0:
        return {"mean_bp": None, "n": 0}
    boot = block_bootstrap_ci(g, np.mean, cfg["bootstrap"]["n_boot"],
                              cfg["bootstrap"]["block_len"], cfg["seed"])
    return {"mean_bp": float(g.mean()), "ci_lo_bp": boot["lo"], "ci_hi_bp": boot["hi"],
            "n": int(g.size), "ci_spans_zero": bool(boot["lo"] < 0 < boot["hi"])}


def _placebo(g: pd.DataFrame, cfg) -> dict:
    conv_resid, green_resid, sim_spread = [], [], []
    for d, sub in g.groupby("date"):
        conv = sub[sub["leg"] == "conv"]
        if len(conv) < 4:
            continue
        fit = fit_nss(conv["maturity_years"].values, conv["yield_pct"].values,
                      cfg["nss"]["tau1_init"], cfg["nss"]["tau2_init"])
        if fit is None:
            continue
        for _, r in conv.iterrows():
            conv_resid.append((r["yield_pct"] - curve_value(fit, r["maturity_years"])) * 100)
        for _, r in sub[sub["leg"] == "green"].iterrows():
            green_resid.append((r["yield_pct"] - curve_value(fit, r["maturity_years"])) * 100)
        # similar-maturity conventional pseudo-pairs (|dmat| < 3y)
        cc = conv.sort_values("maturity_years").reset_index(drop=True)
        for i in range(len(cc) - 1):
            if abs(cc.loc[i + 1, "maturity_years"] - cc.loc[i, "maturity_years"]) < 3:
                sim_spread.append((cc.loc[i, "yield_pct"] - cc.loc[i + 1, "yield_pct"]) * 100)
    return {
        "conventional_curve_residual": _level(conv_resid, cfg),     # expect ~0
        "green_curve_residual": _level(green_resid, cfg),           # expect < 0
        "similar_maturity_conv_pseudo_spread": _level(sim_spread, cfg),  # expect ~0
        "interpretation": "Conventional-leg residuals and similar-maturity "
                          "pseudo-spreads centred on ~0 (CI spans 0) show the "
                          "greenium is not a mechanical curve/maturity artefact; "
                          "green-leg residuals sit below the conventional curve.",
    }


def _liquidity_only(g: pd.DataFrame, cfg) -> dict:
    """Per-cell green-minus-conv yield gap regressed on the log-amount gap."""
    piv_y = g.pivot_table(index=["date", "pair_id"], columns="leg", values="yield_pct")
    piv_a = g.pivot_table(index=["date", "pair_id"], columns="leg", values="log_amount_out")
    d = pd.DataFrame({
        "gap_yield": (piv_y["green"] - piv_y["conv"]),
        "gap_logamt": (piv_a["green"] - piv_a["conv"])}).dropna().reset_index()
    if len(d) < 20:
        return {"available": False}
    X = np.column_stack([np.ones(len(d)), d["gap_logamt"].to_numpy(float)])
    y = d["gap_yield"].to_numpy(float)
    res = cluster_robust_ols(X, y, d["pair_id"].to_numpy())
    b0, b1 = float(res["beta"][0]), float(res["beta"][1])
    se0 = float(res["se"][0])
    # greenium at equal liquidity = -(intercept) in bp
    return {
        "available": True,
        "spec": "(green_yield - conv_yield) ~ 1 + (log_amt_green - log_amt_conv)",
        "intercept_pct": b0, "slope_on_logamt_gap": b1,
        "greenium_at_equal_liquidity_bp": -100.0 * b0,
        "ci_lo_bp": -100.0 * (b0 + 1.96 * se0),
        "ci_hi_bp": -100.0 * (b0 - 1.96 * se0),
        "intercept_p": float(res["p_value"][0]),
        "survives_liquidity": bool(res["p_value"][0] < 0.05 and -100.0 * b0 > 0),
    }


def _sign_stability(g: pd.DataFrame) -> dict:
    spread = g.pivot_table(index=["date", "pair_id"], columns="leg", values="yield_pct")
    spread["greenium_bp"] = (spread["conv"] - spread["green"]) * 100
    per_pair = spread.reset_index().groupby("pair_id")["greenium_bp"].mean()
    n = int(per_pair.size)
    n_pos = int((per_pair > 0).sum())
    # two-sided sign test under H0: p=0.5
    p_value = float(sps.binomtest(n_pos, n, 0.5).pvalue) if n else None
    return {"n_pairs": n, "n_positive": n_pos,
            "share_positive": (n_pos / n) if n else None,
            "sign_test_p": p_value,
            "by_pair_mean_bp": {k: float(v) for k, v in per_pair.items()}}


def main(offline: bool = False) -> None:
    cfg = load_config()
    g = pd.read_parquet(PROCESSED / "panel_germany.parquet")
    g["date"] = pd.to_datetime(g["date"])

    out = {
        "data_mode": data_mode().get("data_mode", "live"),
        "seed": cfg["seed"],
        "placebo": _placebo(g, cfg),
        "liquidity_only": _liquidity_only(g, cfg),
        "sign_stability": _sign_stability(g),
    }
    write_json(PROCESSED / "results_refutation.json", out)
    pl = out["placebo"]["conventional_curve_residual"].get("mean_bp")
    print(f"  placebo conv-curve residual {pl:.2f} bp (expect ~0); "
          f"sign stability {out['sign_stability']['n_positive']}/"
          f"{out['sign_stability']['n_pairs']} pairs positive")


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
