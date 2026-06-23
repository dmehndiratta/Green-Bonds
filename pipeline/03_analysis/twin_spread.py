"""Headline estimator: identical-twin matched-pair greenium.

For each German twin pair and day, greenium_bp = (conventional yield - green
yield) * 100. This is the cleanest, near-model-free estimate (issuer, coupon,
maturity and tax are held identical by construction). We summarise:
  * pooled level with a block-bootstrap CI and a Newey-West (HAC) mean SE,
  * by pair (level, CI, sign) -> sign-stability check,
  * by maturity bucket (short / medium / long, on CURRENT years-to-maturity),
  * a weekly pooled time series with a dispersion band (for the dashboard),
  * a term-structure snapshot (recent greenium vs current maturity),
  * with- and without-stress-window variants.

Writes data/processed/results_twin.json.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
from common import PROCESSED, data_mode, load_config, write_json  # noqa: E402
from stats import block_bootstrap_ci, newey_west_mean  # noqa: E402

BUCKETS = [("short_0_5y", 0, 5), ("medium_5_12y", 5, 12), ("long_12y_plus", 12, 100)]


def _bucket(m: float) -> str:
    for name, lo, hi in BUCKETS:
        if lo <= m < hi:
            return name
    return "long_12y_plus"


def _level_summary(g: pd.Series, cfg, seed) -> dict:
    g = g.dropna()
    if g.empty:
        return {"mean_bp": None, "n": 0}
    boot = block_bootstrap_ci(g.values, np.mean, cfg["bootstrap"]["n_boot"],
                              cfg["bootstrap"]["block_len"], seed)
    nw = newey_west_mean(g.values)
    return {"mean_bp": float(g.mean()), "median_bp": float(g.median()),
            "ci_lo_bp": boot["lo"], "ci_hi_bp": boot["hi"],
            "hac_se_bp": nw["se"], "hac_t": nw["t"], "hac_p": nw.get("p_value"),
            "n": int(g.shape[0]), "share_positive": float((g > 0).mean())}


def _weekly_pooled(df: pd.DataFrame) -> list[dict]:
    """Weekly pooled greenium mean + within-week dispersion band (mean ± 1.96 SE)."""
    s = df.set_index("date")
    wk = s["greenium_bp"].resample("W-FRI")
    mean = wk.mean()
    cnt = wk.count()
    sd = wk.std()
    se = sd / np.sqrt(cnt.clip(lower=1))
    out = []
    for d in mean.index:
        if cnt.get(d, 0) == 0 or not np.isfinite(mean[d]):
            continue
        m = float(mean[d]); s_ = float(se[d]) if np.isfinite(se[d]) else 0.0
        out.append({"date": d.strftime("%Y-%m-%d"), "greenium_bp": m,
                    "lo": m - 1.96 * s_, "hi": m + 1.96 * s_,
                    "n": int(cnt[d])})
    return out


def _per_pair_weekly(df: pd.DataFrame) -> dict:
    out = {}
    for pid, sub in df.groupby("pair_id"):
        w = sub.set_index("date")["greenium_bp"].resample("W-FRI").mean().dropna()
        out[pid] = [{"date": d.strftime("%Y-%m-%d"), "greenium_bp": float(v)}
                    for d, v in w.items()]
    return out


def main(offline: bool = False) -> None:
    cfg = load_config()
    seed = cfg["seed"]
    df = pd.read_parquet(PROCESSED / "twin_spread_daily.parquet")
    df["date"] = pd.to_datetime(df["date"])

    headline = _level_summary(df["greenium_bp"], cfg, seed)

    by_pair = []
    for pid, sub in df.groupby("pair_id"):
        s = _level_summary(sub["greenium_bp"], cfg, seed)
        s["pair_id"] = pid
        s["tenor_label"] = sub["tenor_label"].iloc[0]
        s["current_maturity_years"] = float(sub.sort_values("date")["maturity_years"].iloc[-1])
        by_pair.append(s)
    by_pair.sort(key=lambda r: r["current_maturity_years"])

    df["bucket"] = df["maturity_years"].apply(_bucket)
    by_bucket = []
    for name, _, _ in BUCKETS:
        sub = df[df["bucket"] == name]
        if sub.empty:
            continue
        s = _level_summary(sub["greenium_bp"], cfg, seed)
        s["bucket"] = name
        by_bucket.append(s)

    # term-structure snapshot: last 60 trading days, mean greenium vs current maturity
    last_day = df["date"].max()
    recent = df[df["date"] > last_day - pd.Timedelta(days=90)]
    term = []
    for pid, sub in recent.groupby("pair_id"):
        if sub.empty:
            continue
        term.append({"pair_id": pid,
                     "tenor_label": sub["tenor_label"].iloc[0],
                     "maturity_years": float(sub["maturity_years"].mean()),
                     "greenium_bp": float(sub["greenium_bp"].mean()),
                     "se_bp": float(sub["greenium_bp"].std()
                                    / np.sqrt(max(len(sub), 1)))})
    term.sort(key=lambda r: r["maturity_years"])

    stress = {
        "with_stress": _level_summary(df["greenium_bp"], cfg, seed),
        "ex_stress": _level_summary(df.loc[~df["in_stress"], "greenium_bp"], cfg, seed),
    }

    out = {
        "data_mode": data_mode().get("data_mode", "live"),
        "seed": seed,
        "estimand": "greenium_bp = (conventional_yield - green_yield) * 100, "
                    "identical-twin matched pair",
        "date_span": [df["date"].min().strftime("%Y-%m-%d"),
                      df["date"].max().strftime("%Y-%m-%d")],
        "headline": headline,
        "by_pair": by_pair,
        "by_maturity_bucket": by_bucket,
        "term_structure": term,
        "stress": stress,
        "series_weekly_pooled": _weekly_pooled(df),
        "series_weekly_by_pair": _per_pair_weekly(df),
        "n_signs_positive": int(sum(1 for r in by_pair if (r.get("mean_bp") or 0) > 0)),
        "n_pairs": len(by_pair),
    }
    write_json(PROCESSED / "results_twin.json", out)
    print(f"  twin greenium pooled {headline['mean_bp']:.2f} bp "
          f"[{headline['ci_lo_bp']:.2f}, {headline['ci_hi_bp']:.2f}]; "
          f"{out['n_signs_positive']}/{out['n_pairs']} pairs positive")


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
