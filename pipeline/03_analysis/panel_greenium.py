"""Liquidity-adjusted greenium via a fixed-effects panel.

Model (German twins, long panel of yields):

    yield_{i,t} = a_{pair x date} + b * GREEN_i + g' * liquidity_i,t + e_{i,t}

with **pair x date fixed effects**, so each green bond is compared only to its own
conventional twin on the same day. The green-dummy coefficient b is the
within-cell green-minus-conventional yield gap; the greenium is -b (in bp). Adding
liquidity controls turns the *raw* greenium into the *liquidity-adjusted* greenium
- the gap between the two IS the liquidity story (plan §4).

Identification note: within a twin-day cell, both legs share the same security age
and on/off-the-run status (identical maturity & coupon by construction), so the
only liquidity dimension that varies *within* the FE is **issue size**
(log amount outstanding) - and that is exactly the confound the twin design cannot
remove mechanically. We therefore adjust the green dummy for log-amount; controls
that are invariant within a cell are reported but cannot move the estimate.

SEs are cluster-robust (clustered by pair). Writes results_panel.json.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
from common import PROCESSED, data_mode, load_config, write_json  # noqa: E402
from stats import cluster_robust_ols  # noqa: E402

Z = 1.959963985


def _within(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Within (pair x date) transform: subtract cell means."""
    cell = df["pair_id"].astype(str) + "|" + df["date"].astype(str)
    out = df.copy()
    out["_cell"] = cell
    for c in cols:
        out[c + "_dm"] = out[c] - out.groupby("_cell")[c].transform("mean")
    return out


def _fit(dm: pd.DataFrame, regressors: list[str], cluster: np.ndarray) -> dict:
    X = dm[[r + "_dm" for r in regressors]].to_numpy(float)
    y = dm["yield_pct_dm"].to_numpy(float)
    res = cluster_robust_ols(X, y, cluster)
    rows = {}
    for j, r in enumerate(regressors):
        b, se = float(res["beta"][j]), float(res["se"][j])
        rows[r] = {"coef": b, "se": se, "t": float(res["t"][j]),
                   "p_value": float(res["p_value"][j]),
                   "lo": b - Z * se, "hi": b + Z * se}
    rows["_n"] = res["n"]
    rows["_n_clusters"] = res["n_clusters"]
    return rows


def _greenium_from_green_coef(row: dict) -> dict:
    """greenium_bp = -100 * b_green; flip CI bounds accordingly."""
    return {"greenium_bp": -100.0 * row["coef"],
            "ci_lo_bp": -100.0 * row["hi"], "ci_hi_bp": -100.0 * row["lo"],
            "se_bp": 100.0 * row["se"], "p_value": row["p_value"]}


def main(offline: bool = False) -> None:
    cfg = load_config()
    g = pd.read_parquet(PROCESSED / "panel_germany.parquet")
    g["date"] = pd.to_datetime(g["date"])
    g["green"] = (g["leg"] == "green").astype(float)

    candidate_controls = cfg["panel"]["liquidity_controls"]  # log_amount_out, age_years, on_the_run
    cols = ["yield_pct", "green"] + candidate_controls
    dm = _within(g, cols)

    # keep only cells with both legs present (within transform meaningful)
    cell_sizes = dm.groupby("_cell")["green"].transform("size")
    dm = dm[cell_sizes >= 2].copy()
    cluster = dm["pair_id"].to_numpy()

    # which controls actually vary within a cell?
    varying = [c for c in candidate_controls
               if float(np.nanstd(dm[c + "_dm"].to_numpy())) > 1e-9]
    invariant = [c for c in candidate_controls if c not in varying]

    raw = _fit(dm, ["green"], cluster)
    adj = _fit(dm, ["green"] + varying, cluster)

    raw_g = _greenium_from_green_coef(raw["green"])
    adj_g = _greenium_from_green_coef(adj["green"])

    coef_table = [{"term": "green dummy (raw, pair×date FE)", **raw["green"]},
                  {"term": "green dummy (liquidity-adjusted)", **adj["green"]}]
    for c in varying:
        coef_table.append({"term": f"control: {c}", **adj[c]})

    out = {
        "data_mode": data_mode().get("data_mode", "live"),
        "seed": cfg["seed"],
        "spec": "yield ~ green + liquidity | pair×date FE; cluster-robust by pair",
        "controls_varying_within_cell": varying,
        "controls_invariant_within_cell": invariant,
        "controls_invariant_note": "Identical maturity/coupon -> age & on/off-the-run "
                                   "are equal across the two twin legs on a given day, "
                                   "so they cannot vary within the pair×date cell; "
                                   "issue size (log amount) is the operative control.",
        "n_obs": raw["_n"], "n_clusters": raw["_n_clusters"],
        "greenium_raw": raw_g,
        "greenium_adjusted": adj_g,
        "liquidity_gap_bp": raw_g["greenium_bp"] - adj_g["greenium_bp"],
        "coef_table": coef_table,
    }
    write_json(PROCESSED / "results_panel.json", out)
    print(f"  panel greenium raw {raw_g['greenium_bp']:.2f} bp -> "
          f"liquidity-adjusted {adj_g['greenium_bp']:.2f} bp "
          f"(liquidity gap {out['liquidity_gap_bp']:.2f} bp)")


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
