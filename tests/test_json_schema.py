"""site/data/*.json must be browser-parseable (no NaN/Infinity) with key fields."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site" / "data"


def _reject(x):
    raise ValueError(f"non-finite token: {x}")


def _all_jsons():
    return sorted(SITE.glob("*.json"))


@pytest.mark.skipif(not _all_jsons(), reason="run the pipeline export first")
def test_browser_parseable():
    for p in _all_jsons():
        json.loads(p.read_text(encoding="utf-8"), parse_constant=_reject)


@pytest.mark.skipif(not (SITE / "facts.json").exists(), reason="run export first")
def test_facts_present():
    d = json.loads((SITE / "facts.json").read_text(encoding="utf-8"))
    assert d["data_mode"] in ("live", "demo-synthetic")
    assert "last_updated" in d and "headline_greenium_bp" in d
    assert len(d.get("stress_windows", [])) >= 1


@pytest.mark.skipif(not (SITE / "twin.json").exists(), reason="run export first")
def test_twin_shape():
    d = json.loads((SITE / "twin.json").read_text(encoding="utf-8"))
    for key in ("headline", "by_pair", "by_maturity_bucket", "term_structure",
                "series_weekly_pooled", "series_weekly_by_pair"):
        assert key in d, f"missing {key}"
    h = d["headline"]
    assert h["ci_lo_bp"] <= h["mean_bp"] <= h["ci_hi_bp"]
    # term structure is monotone-ish: short end >= long end greenium
    ts = sorted(d["term_structure"], key=lambda r: r["maturity_years"])
    assert ts[0]["greenium_bp"] >= ts[-1]["greenium_bp"] - 1.0


@pytest.mark.skipif(not (SITE / "panel.json").exists(), reason="run export first")
def test_panel_raw_and_adjusted():
    d = json.loads((SITE / "panel.json").read_text(encoding="utf-8"))
    assert "greenium_raw" in d and "greenium_adjusted" in d
    assert "log_amount_out" in d["controls_varying_within_cell"]
