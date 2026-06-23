"""French green-OAT greenium via a fitted conventional OAT curve (corroboration).

France has no identical-twin construct, so each day we fit a Nelson-Siegel-
Svensson conventional OAT curve to the available conventional yields, then:

    greenium_bp = (fitted_conventional_yield(at green OAT maturity) - green yield) * 100

This is a noisier, independent check on the German twin result (different issuer,
different method). We report the curve-fit RMSE, the pooled French greenium with a
block-bootstrap CI, a per-OAT breakdown, and an NS-vs-NSS robustness comparison.

Writes results_nss.json. Degrades gracefully if the French data are unavailable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
from common import PROCESSED, data_mode, load_config, write_json  # noqa: E402
from nss import curve_value, fit_ns, fit_nss  # noqa: E402
from stats import block_bootstrap_ci  # noqa: E402


def _greenium_panel(green: pd.DataFrame, conv: pd.DataFrame, cfg, kind: str) -> pd.DataFrame:
    """For each green-OAT obs, fit a curve on the nearest conventional-curve date
    and evaluate the fitted conventional yield at the OAT's current maturity."""
    fitter = fit_nss if kind == "nss" else fit_ns
    fits = {}
    diag = []
    for d, sub in conv.groupby("date"):
        f = (fit_nss(sub["maturity_years"].values, sub["yield_pct"].values,
                     cfg["nss"]["tau1_init"], cfg["nss"]["tau2_init"]) if kind == "nss"
             else fit_ns(sub["maturity_years"].values, sub["yield_pct"].values))
        if f:
            fits[pd.Timestamp(d)] = f
            diag.append({"date": pd.Timestamp(d).strftime("%Y-%m-%d"),
                         "rmse_bp": f["rmse"] * 100, "n": f["n"], "kind": f["kind"]})
    if not fits:
        return pd.DataFrame(), diag
    curve_dates = pd.DatetimeIndex(sorted(fits.keys()))
    rows = []
    for _, r in green.iterrows():
        d = pd.Timestamp(r["date"])
        # nearest curve date on/before d (curves are weekly)
        pos = curve_dates.searchsorted(d, side="right") - 1
        if pos < 0:
            continue
        cd = curve_dates[pos]
        conv_fit = curve_value(fits[cd], float(r["maturity_years"]))
        rows.append({"date": d, "oat_id": r["oat_id"],
                     "maturity_years": float(r["maturity_years"]),
                     "greenium_bp": (conv_fit - float(r["yield_pct"])) * 100.0})
    return pd.DataFrame(rows), diag


def _level(g: pd.Series, cfg) -> dict:
    g = g.dropna()
    if g.empty:
        return {"mean_bp": None, "n": 0}
    boot = block_bootstrap_ci(g.values, np.mean, cfg["bootstrap"]["n_boot"],
                              cfg["bootstrap"]["block_len"], cfg["seed"])
    return {"mean_bp": float(g.mean()), "ci_lo_bp": boot["lo"], "ci_hi_bp": boot["hi"],
            "n": int(g.shape[0]), "share_positive": float((g > 0).mean())}


def main(offline: bool = False) -> None:
    cfg = load_config()
    fp_green = PROCESSED / "panel_france.parquet"
    fp_conv = PROCESSED / "conv_curve_fr.parquet"
    if not (fp_green.exists() and fp_conv.exists()):
        write_json(PROCESSED / "results_nss.json",
                   {"data_mode": data_mode().get("data_mode", "live"),
                    "available": False,
                    "note": "French OAT data unavailable in this run."})
        print("  France unavailable; wrote stub results_nss.json")
        return

    green = pd.read_parquet(fp_green)
    conv = pd.read_parquet(fp_conv)
    green["date"] = pd.to_datetime(green["date"])
    conv["date"] = pd.to_datetime(conv["date"])

    nss_panel, nss_diag = _greenium_panel(green, conv, cfg, "nss")
    ns_panel, _ = _greenium_panel(green, conv, cfg, "ns")

    by_oat = []
    if not nss_panel.empty:
        for oid, sub in nss_panel.groupby("oat_id"):
            s = _level(sub["greenium_bp"], cfg)
            s["oat_id"] = oid
            s["maturity_years"] = float(sub["maturity_years"].mean())
            by_oat.append(s)
        by_oat.sort(key=lambda r: r["maturity_years"])

    series = []
    if not nss_panel.empty:
        wk = nss_panel.set_index("date")["greenium_bp"].resample("W-FRI").mean().dropna()
        series = [{"date": d.strftime("%Y-%m-%d"), "greenium_bp": float(v)}
                  for d, v in wk.items()]

    rmse_vals = [d["rmse_bp"] for d in nss_diag]
    out = {
        "data_mode": data_mode().get("data_mode", "live"),
        "seed": cfg["seed"],
        "available": True,
        "method": "NSS conventional OAT curve fit per day; greenium = "
                  "fitted_conv(maturity) - green yield",
        "fit_diagnostics": {
            "mean_rmse_bp": float(np.mean(rmse_vals)) if rmse_vals else None,
            "median_rmse_bp": float(np.median(rmse_vals)) if rmse_vals else None,
            "n_days_fit": len(nss_diag)},
        "greenium_nss": _level(nss_panel["greenium_bp"] if not nss_panel.empty
                               else pd.Series(dtype=float), cfg),
        "greenium_ns_robustness": _level(ns_panel["greenium_bp"] if not ns_panel.empty
                                         else pd.Series(dtype=float), cfg),
        "by_oat": by_oat,
        "series_weekly": series,
    }
    write_json(PROCESSED / "results_nss.json", out)
    gm = out["greenium_nss"].get("mean_bp")
    print(f"  French NSS greenium {gm:.2f} bp (mean fit RMSE "
          f"{out['fit_diagnostics']['mean_rmse_bp']:.2f} bp)"
          if gm is not None else "  French greenium: no fit")


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
