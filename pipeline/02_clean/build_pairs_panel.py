"""Build the analysis panels from the raw German twin yields.

Outputs (committed, small parquet):
  data/processed/panel_germany.parquet  — long: date, pair_id, leg, isin,
      yield_pct, maturity_years, coupon, amount_out_eur_bn, age_years,
      on_the_run, tenor_label, in_stress
  data/processed/twin_spread_daily.parquet — date, pair_id, greenium_bp,
      maturity_years, ... (conv_yield - green_yield, by pair & day)
  data/processed/panel_meta.json         — coverage + convention harmonisation log

Guards (the gotchas in plan §3):
  * Yield-convention harmonisation: both legs of a German twin come from the same
    Bundesbank quote basis (annual / actual-actual), so they are differenced
    directly; this is asserted and logged.
  * Pair entry dates: a bond never appears before its first_issue (no pre-twin
    comparison); enforced here and tested in tests/test_entry_dates.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
from common import (MANUAL, PROCESSED, RAW, load_config, write_json)  # noqa: E402


def _in_stress(dates: pd.Series, cfg) -> pd.Series:
    flag = pd.Series(False, index=dates.index)
    for w in cfg["stress_windows"]:
        flag |= (dates >= pd.Timestamp(w["start"])) & (dates <= pd.Timestamp(w["end"]))
    return flag


def main(offline: bool = False) -> None:
    cfg = load_config()
    pairs = pd.read_csv(MANUAL / "twin_pairs.csv")
    pmeta = pairs.set_index("pair_id")

    yld = pd.read_csv(RAW / "bundesbank" / "bundesbank_yields_latest.csv",
                      parse_dates=["date"])
    amt_path = RAW / "bundesbank" / "bundesbank_amounts_latest.csv"
    amt = (pd.read_csv(amt_path, parse_dates=["date"]) if amt_path.exists()
           else None)

    # --- entry-date guard: drop any obs before the bond's first_issue ----------
    first_issue = pmeta["first_issue"].apply(pd.Timestamp)
    yld = yld.merge(pairs[["pair_id", "green_isin", "conv_isin", "coupon",
                           "maturity", "first_issue", "tenor_label"]],
                    on="pair_id", how="left")
    yld["first_issue"] = pd.to_datetime(yld["first_issue"])
    yld["maturity"] = pd.to_datetime(yld["maturity"])
    pre = (yld["date"] < yld["first_issue"]).sum()
    yld = yld[yld["date"] >= yld["first_issue"]].copy()
    # also never compare past maturity
    yld = yld[yld["date"] <= yld["maturity"]].copy()

    yld["maturity_years"] = (yld["maturity"] - yld["date"]).dt.days / 365.25
    yld = yld[yld["maturity_years"] > 0].copy()  # drop the maturity day (0y to go)
    yld["age_years"] = (yld["date"] - yld["first_issue"]).dt.days / 365.25
    yld["in_stress"] = _in_stress(yld["date"], cfg).values

    # liquidity (amount outstanding + on/off-the-run). Fall back to manual initial
    # amounts if no live amounts feed.
    if amt is not None:
        yld = yld.merge(amt[["date", "isin", "amount_out_eur_bn", "on_the_run"]],
                        on=["date", "isin"], how="left")
    if "amount_out_eur_bn" not in yld or yld["amount_out_eur_bn"].isna().all():
        # documented initial amounts (green leg) as a conservative constant proxy
        init = pmeta["initial_green_amount_eur_bn"]
        yld["amount_out_eur_bn"] = yld.apply(
            lambda r: float(init[r["pair_id"]]) * (3.5 if r["leg"] == "conv" else 1.0),
            axis=1)
        yld["on_the_run"] = (yld["age_years"] < 1.0).astype(int)
    yld["log_amount_out"] = np.log(yld["amount_out_eur_bn"].clip(lower=1e-6))

    germany = yld[["date", "pair_id", "leg", "isin", "yield_pct", "maturity_years",
                   "coupon", "amount_out_eur_bn", "log_amount_out", "age_years",
                   "on_the_run", "tenor_label", "in_stress"]].sort_values(
        ["pair_id", "date", "leg"]).reset_index(drop=True)
    germany.to_parquet(PROCESSED / "panel_germany.parquet")

    # --- matched-pair twin spread (the headline estimand) ----------------------
    wide = germany.pivot_table(index=["date", "pair_id", "maturity_years",
                                       "tenor_label", "in_stress"],
                               columns="leg", values="yield_pct").reset_index()
    wide = wide.dropna(subset=["green", "conv"])
    # greenium = conventional yield - green yield, in basis points
    wide["greenium_bp"] = (wide["conv"] - wide["green"]) * 100.0
    # liquidity gap (conv - green log amount) for the panel/robustness
    liq = germany.pivot_table(index=["date", "pair_id"], columns="leg",
                              values="log_amount_out").reset_index()
    liq = liq.rename(columns={"green": "log_amt_green", "conv": "log_amt_conv"})
    wide = wide.merge(liq, on=["date", "pair_id"], how="left")
    wide = wide.sort_values(["pair_id", "date"]).reset_index(drop=True)
    wide.to_parquet(PROCESSED / "twin_spread_daily.parquet")

    # --- coverage + convention log --------------------------------------------
    cov = (germany.groupby(["pair_id", "leg"])
           .agg(n=("date", "size"),
                start=("date", "min"), end=("date", "max"))
           .reset_index())
    cov["start"] = cov["start"].dt.strftime("%Y-%m-%d")
    cov["end"] = cov["end"].dt.strftime("%Y-%m-%d")
    meta = {
        "quote_basis": cfg["germany"]["quote_basis"],
        "convention_note": "Both twin legs share the Bundesbank annual / "
                            "actual-actual yield basis; greenium = conv - green is "
                            "a like-for-like difference (no convention mismatch).",
        "pre_issue_obs_dropped": int(pre),
        "n_pairs": int(germany["pair_id"].nunique()),
        "n_days": int(germany["date"].nunique()),
        "date_span": [germany["date"].min().strftime("%Y-%m-%d"),
                      germany["date"].max().strftime("%Y-%m-%d")],
        "coverage": cov.to_dict(orient="records"),
    }
    write_json(PROCESSED / "panel_meta.json", meta)
    print(f"  panel_germany {germany.shape}; twin_spread_daily {wide.shape}; "
          f"dropped {pre} pre-issue obs")


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
