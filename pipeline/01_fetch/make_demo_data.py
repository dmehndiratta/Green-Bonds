"""Deterministic SYNTHETIC data (used only when live endpoints are unreachable).

This is NOT real market data. It exists so the full method — twin matched-pair
spreads, the FE liquidity-adjusted panel, dynamics, the placebo/refutation suite,
the dashboard band — runs and is testable when the live Bundesbank workbook archive
is unreachable. It uses the *real* twin ISIN pairs and *real* coupons/maturities/
first-issue dates from data/manual/twin_pairs.csv, and a realistic euro-area rate
path (negative-yield 2020-21 -> 2022 rate shock -> 2023-26 plateau), then embeds a
known greenium signal (larger at the short end, compressing over time) so the
estimators have something genuine to recover.

Every artefact it feeds is stamped data_mode="demo-synthetic"; the dashboard and
report show a prominent banner. The default path is live Bundesbank data (see
fetch_bundesbank.py); this fallback only triggers if that archive cannot be reached.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
from common import MANUAL, RAW, load_config, snapshot_dir, write_json  # noqa: E402

# Euro-area rate-level anchors (yield on a ~1y point, in %); piecewise-linear.
LEVEL_ANCHORS = {
    "2020-09-02": -0.65, "2021-06-30": -0.55, "2021-12-31": -0.30,
    "2022-06-30": 0.90, "2022-12-31": 2.30, "2023-12-31": 2.55,
    "2024-12-31": 2.20, "2026-06-15": 2.55,
}
# Curve slope (long-minus-short add-on at the very long end, in %); inverts in 2022-23.
SLOPE_ANCHORS = {
    "2020-09-02": 1.10, "2021-12-31": 1.40, "2022-09-30": -0.20,
    "2023-06-30": -0.55, "2024-12-31": 0.10, "2026-06-15": 0.70,
}


def _interp(anchors: dict, idx: pd.DatetimeIndex) -> np.ndarray:
    xs = pd.to_datetime(list(anchors.keys())).map(pd.Timestamp.toordinal).to_numpy(float)
    ys = np.array(list(anchors.values()), float)
    xo = idx.map(pd.Timestamp.toordinal).to_numpy(float)
    return np.interp(xo, xs, ys)


def _ar1(n, rho, sd, rng):
    e = rng.standard_normal(n) * sd
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = rho * x[t - 1] + e[t]
    return x


def base_curve(level, slope, m_years):
    """Conventional yield (%) at maturity m for a day with (level, slope)."""
    shape = 1.0 - np.exp(-np.asarray(m_years, float) / 6.0)  # 0 at 0y -> ~1 at long end
    return level + slope * shape


def greenium_bp(m_years, frac_time):
    """Embedded greenium (bp): ~6 bp at the 3y point, ~2-3 bp at the long end,
    compressing by ~40% from start to end of sample."""
    m = np.asarray(m_years, float)
    level = 2.0 + 7.3 * np.exp(-m / 5.0)        # ~6 bp @3y, ~2 bp @30y
    decay = 1.0 - 0.40 * np.clip(frac_time, 0, 1)
    return level * decay


def build(seed: int, cfg: dict):
    rng = np.random.default_rng(seed)
    start = pd.Timestamp(cfg["sample"]["start"])
    end = pd.Timestamp(cfg["sample"]["end"])
    days = pd.bdate_range(start, end)
    n = len(days)
    span = (end.toordinal() - start.toordinal())
    frac = (days.map(pd.Timestamp.toordinal).to_numpy(float) - start.toordinal()) / span

    level = _interp(LEVEL_ANCHORS, days) + _ar1(n, 0.96, 0.015, rng)  # common factor
    slope = _interp(SLOPE_ANCHORS, days)

    pairs = pd.read_csv(MANUAL / "twin_pairs.csv")

    yld_rows, amt_rows = [], []
    for _, p in pairs.iterrows():
        first = pd.Timestamp(p["first_issue"])
        mat = pd.Timestamp(p["maturity"])
        alive = (days >= first) & (days <= min(mat, end))
        if alive.sum() < 30:
            continue
        d_alive = days[alive]
        m_years = (mat - d_alive).days.to_numpy(float) / 365.25
        lv = level[alive]
        sl = slope[alive]
        fr = frac[alive]

        conv_idio = _ar1(int(alive.sum()), 0.9, 0.004, rng)   # ~0.4bp daily
        conv_y = base_curve(lv, sl, m_years) + conv_idio
        g_bp = greenium_bp(m_years, fr)
        green_noise = _ar1(int(alive.sum()), 0.5, 0.005, rng)  # ~0.5bp
        green_y = conv_y - g_bp / 100.0 + green_noise          # bp -> percentage pts

        for leg, isin, yv in (("green", p["green_isin"], green_y),
                              ("conv", p["conv_isin"], conv_y)):
            yld_rows.append(pd.DataFrame({
                "date": d_alive, "isin": isin, "leg": leg,
                "pair_id": p["pair_id"], "yield_pct": yv}))

        # liquidity: green smaller, grows via taps; conv 3-4x larger.
        age_years = (d_alive - first).days.to_numpy(float) / 365.25
        g_amt = float(p["initial_green_amount_eur_bn"]) * (1.0 + 0.45 * np.minimum(age_years, 3.0))
        c_amt = g_amt * 3.5
        on_run = (age_years < 1.0).astype(int)
        amt_rows.append(pd.DataFrame({"date": d_alive, "isin": p["green_isin"],
                                      "leg": "green", "pair_id": p["pair_id"],
                                      "amount_out_eur_bn": g_amt, "on_the_run": on_run}))
        amt_rows.append(pd.DataFrame({"date": d_alive, "isin": p["conv_isin"],
                                      "leg": "conv", "pair_id": p["pair_id"],
                                      "amount_out_eur_bn": c_amt, "on_the_run": on_run}))

    de_yields = pd.concat(yld_rows, ignore_index=True)
    de_amounts = pd.concat(amt_rows, ignore_index=True)
    return de_yields, de_amounts


def main(seed: int | None = None) -> None:
    cfg = load_config()
    seed = seed or cfg["seed"]
    de_y, de_a = build(seed, cfg)

    snap = snapshot_dir("bundesbank")
    de_y.to_csv(snap / "bundesbank_yields.csv", index=False)
    de_a.to_csv(snap / "bundesbank_amounts.csv", index=False)
    de_y.to_csv(RAW / "bundesbank" / "bundesbank_yields_latest.csv", index=False)
    de_a.to_csv(RAW / "bundesbank" / "bundesbank_amounts_latest.csv", index=False)

    write_json(PIPE.parent / "data" / "facts" / "data_mode.json",
               {"data_mode": "demo-synthetic",
                "reason": "Live Bundesbank archive unreachable in this run; synthetic "
                          "panel with real twin ISIN pairs, real coupons/maturities and "
                          "an embedded greenium signal so the method is runnable and "
                          "testable.",
                "seed": seed,
                "n_days": int(de_y['date'].nunique()),
                "n_de_pairs": int(de_y['pair_id'].nunique())})
    print(f"  SYNTHETIC demo data: {de_y['pair_id'].nunique()} DE twin pairs, "
          f"{de_y['date'].nunique()} trading days; data_mode=demo-synthetic")


if __name__ == "__main__":
    main()
