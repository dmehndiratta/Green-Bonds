"""Assemble site/data/*.json — the only thing the dashboard/report read.

Pulls the committed processed results (twin, panel, dynamics, refutation,
panel meta, data mode) into a small set of browser-parseable JSON files. Numbers
in report.html / dashboard.html must trace back to these.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
from common import (FACTS, PROCESSED, SITE_DATA, data_mode,  # noqa: E402
                    load_config, read_json, write_json)


def _maybe(name: str):
    p = PROCESSED / name
    return read_json(p) if p.exists() else None


def main(offline: bool = False) -> None:
    cfg = load_config()
    dm = data_mode()

    twin = _maybe("results_twin.json")
    panel = _maybe("results_panel.json")
    dyn = _maybe("results_dynamics.json")
    refu = _maybe("results_refutation.json")
    pmeta = _maybe("panel_meta.json")

    for obj, fn in [(twin, "twin.json"), (panel, "panel.json"),
                    (dyn, "dynamics.json"), (refu, "refutation.json")]:
        if obj is not None:
            write_json(SITE_DATA / fn, obj)

    head = (twin or {}).get("headline", {})
    facts = {
        "title": "Green-Bond Greenium",
        "subtitle": "How much less does sustainability-labelled sovereign debt yield "
                    "than its identical conventional twin?",
        "last_updated": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_mode": dm.get("data_mode", "live"),
        "data_mode_reason": dm.get("reason", ""),
        "seed": cfg["seed"],
        "sample": cfg["sample"],
        "stress_windows": cfg["stress_windows"],
        "headline_greenium_bp": head.get("mean_bp"),
        "headline_ci_bp": [head.get("ci_lo_bp"), head.get("ci_hi_bp")],
        "headline_n_obs": head.get("n"),
        "n_pairs": (twin or {}).get("n_pairs"),
        "n_pairs_positive": (twin or {}).get("n_signs_positive"),
        "panel_raw_bp": (panel or {}).get("greenium_raw", {}).get("greenium_bp"),
        "panel_adjusted_bp": (panel or {}).get("greenium_adjusted", {}).get("greenium_bp"),
        "liquidity_gap_bp": (panel or {}).get("liquidity_gap_bp"),
        "compression_bp_per_yr": (dyn or {}).get("compression_trend", {}).get("point"),
        "placebo_conv_residual_bp": (refu or {}).get("placebo", {})
                                    .get("conventional_curve_residual", {}).get("mean_bp"),
        "panel_meta": pmeta,
    }
    write_json(SITE_DATA / "facts.json", facts)
    print(f"  exported site/data: facts, twin, panel, dynamics, refutation "
          f"(data_mode={facts['data_mode']}, headline={facts['headline_greenium_bp']})")


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
