"""The twin pairs are the identification spine — they must be well-formed.

Acceptance criterion (plan §8): >=8 pairs, identical coupon + maturity within each
pair (true by construction since the CSV stores one coupon/maturity per pair), a
distinct green vs conventional ISIN, and a source URL per row.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_at_least_eight_pairs():
    pairs = pd.read_csv(ROOT / "data" / "manual" / "twin_pairs.csv")
    assert len(pairs) >= 8


def test_pair_fields_well_formed():
    pairs = pd.read_csv(ROOT / "data" / "manual" / "twin_pairs.csv")
    for _, p in pairs.iterrows():
        assert p["green_isin"] != p["conv_isin"], "green and conv ISIN must differ"
        assert str(p["green_isin"]).startswith("DE"), "German ISINs start DE"
        assert str(p["conv_isin"]).startswith("DE")
        assert pd.notna(p["coupon"]) and pd.notna(p["maturity"])
        assert pd.notna(p["first_issue"])
        assert str(p["source_url"]).startswith("http")
        # first issue precedes maturity
        assert pd.Timestamp(p["first_issue"]) < pd.Timestamp(p["maturity"])


def test_isins_unique():
    pairs = pd.read_csv(ROOT / "data" / "manual" / "twin_pairs.csv")
    all_isins = list(pairs["green_isin"]) + list(pairs["conv_isin"])
    assert len(all_isins) == len(set(all_isins)), "ISINs must be unique across legs"
