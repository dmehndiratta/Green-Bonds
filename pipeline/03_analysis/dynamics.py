"""Greenium dynamics: compression trend over 2020->2026 and an issuance view.

Tests whether the pooled twin greenium has trended (compressed) over the sample.
We regress the weekly pooled greenium on time (years since sample start) and put a
block-bootstrap CI on the slope, so a noisy downward drift is not over-read. We
also report greenium in annual buckets and the number of live twins over time
(market maturation), and a simple pre/post view around each new green issuance.

Writes results_dynamics.json.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
from common import MANUAL, PROCESSED, data_mode, load_config, write_json  # noqa: E402
from stats import block_bootstrap_trend  # noqa: E402


def main(offline: bool = False) -> None:
    cfg = load_config()
    df = pd.read_parquet(PROCESSED / "twin_spread_daily.parquet")
    df["date"] = pd.to_datetime(df["date"])
    start = pd.Timestamp(cfg["sample"]["start"])

    # weekly pooled greenium
    wk = df.set_index("date")["greenium_bp"].resample("W-FRI").mean().dropna()
    t_years = (wk.index - start).days / 365.25
    trend = block_bootstrap_trend(t_years, wk.values, cfg["bootstrap"]["n_boot"],
                                  max(cfg["bootstrap"]["block_len"] // 5, 4),
                                  cfg["seed"])
    trend["units"] = "bp per year"
    trend["compressing"] = bool((trend.get("point") or 0) < 0)
    trend["significant"] = bool(np.isfinite(trend.get("lo", np.nan))
                                and np.isfinite(trend.get("hi", np.nan))
                                and (trend["lo"] < 0 < trend["hi"]) is False)

    # annual buckets
    df["year"] = df["date"].dt.year
    by_year = []
    for y, sub in df.groupby("year"):
        by_year.append({"year": int(y), "greenium_bp": float(sub["greenium_bp"].mean()),
                        "n": int(len(sub)),
                        "n_pairs": int(sub["pair_id"].nunique())})

    # number of live twins over time (monthly count of pairs with obs)
    live = (df.set_index("date").groupby(pd.Grouper(freq="MS"))["pair_id"]
            .nunique())
    live_series = [{"date": d.strftime("%Y-%m-%d"), "n_live_pairs": int(v)}
                   for d, v in live.items() if v > 0]

    # issuance event view: greenium in the 60 trading days before vs after each
    # pair's first appearance (proxy for its issuance), pooled across pairs.
    pairs = pd.read_csv(MANUAL / "twin_pairs.csv")
    events = []
    for _, p in pairs.iterrows():
        sub = df[df["pair_id"] == p["pair_id"]].sort_values("date")
        if len(sub) < 40:
            continue
        first = sub["date"].min()
        post = sub[sub["date"] <= first + pd.Timedelta(days=120)]["greenium_bp"]
        later = sub[sub["date"] > first + pd.Timedelta(days=120)]["greenium_bp"]
        events.append({"pair_id": p["pair_id"], "tenor_label": p["tenor_label"],
                       "greenium_first_120d_bp": float(post.mean()) if len(post) else None,
                       "greenium_after_bp": float(later.mean()) if len(later) else None})

    out = {
        "data_mode": data_mode().get("data_mode", "live"),
        "seed": cfg["seed"],
        "compression_trend": trend,
        "by_year": by_year,
        "live_pairs_series": live_series,
        "issuance_events": events,
        "interpretation": "A negative slope with a CI excluding zero indicates "
                          "compression; otherwise the apparent drift is not "
                          "distinguishable from noise.",
    }
    write_json(PROCESSED / "results_dynamics.json", out)
    print(f"  compression trend {trend.get('point'):.2f} bp/yr "
          f"[{trend.get('lo'):.2f}, {trend.get('hi'):.2f}]")


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
