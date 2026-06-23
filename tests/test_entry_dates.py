"""No pre-twin comparisons: a bond never appears before its first_issue, and the
greenium is the like-for-like (conv - green) difference on the shared quote basis.
"""
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data" / "processed" / "panel_germany.parquet"
SPREAD = ROOT / "data" / "processed" / "twin_spread_daily.parquet"
PAIRS = pd.read_csv(ROOT / "data" / "manual" / "twin_pairs.csv")


@pytest.mark.skipif(not PANEL.exists(), reason="run the pipeline first")
def test_no_obs_before_first_issue():
    g = pd.read_parquet(PANEL)
    g["date"] = pd.to_datetime(g["date"])
    fi = PAIRS.set_index("pair_id")["first_issue"].apply(pd.Timestamp)
    mat = PAIRS.set_index("pair_id")["maturity"].apply(pd.Timestamp)
    for pid, sub in g.groupby("pair_id"):
        assert sub["date"].min() >= fi[pid], f"{pid} has obs before first issue"
        assert sub["date"].max() <= mat[pid], f"{pid} has obs after maturity"


@pytest.mark.skipif(not SPREAD.exists(), reason="run the pipeline first")
def test_greenium_is_conv_minus_green():
    """greenium_bp must equal (conv - green) * 100 exactly (convention-harmonised)."""
    df = pd.read_parquet(SPREAD)
    recomputed = (df["conv"] - df["green"]) * 100.0
    assert (df["greenium_bp"] - recomputed).abs().max() < 1e-9


@pytest.mark.skipif(not SPREAD.exists(), reason="run the pipeline first")
def test_maturity_is_positive():
    df = pd.read_parquet(SPREAD)
    assert (df["maturity_years"] > 0).all(), "years-to-maturity must be positive"
