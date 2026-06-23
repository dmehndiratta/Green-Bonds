"""Fetch the French green-OAT list + green-OAT yields and a conventional OAT
curve to fit (Agence France Tresor + ECB SDW fallback for conventional yields).

AFT publishes the green-OAT list and allocation/performance reports
(https://www.aft.gouv.fr/en/green-oat). There is no identical-twin construct, so
the greenium is estimated against a fitted conventional OAT curve (NSS) — see
pipeline/03_analysis/nss_curve.py. Conventional OAT yields come from ECB SDW.

Best-effort + last-good fallback; on total failure writes no `_latest` file and
the orchestrator falls back to the synthetic demo data.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
from common import (MANUAL, RAW, http_session, load_config,  # noqa: E402
                    snapshot_dir)


def main(offline: bool = False) -> None:
    cfg = load_config()
    _ = http_session()
    snap = snapshot_dir("aft")
    oats = pd.read_csv(MANUAL / "green_oats.csv")
    print(f"  AFT green-OAT list: {len(oats)} securities "
          f"({', '.join(oats['oat_id'])}).")
    # A live per-ISIN OAT yield feed is not keyless/stable enough to hard-code a
    # series key here; conventional OAT yields would be assembled from ECB SDW
    # (fetch_ecb_curve.py) and green-OAT yields from a market data feed at run
    # time. In this environment those are unreachable, so we leave no `_latest`
    # file and let run_pipeline fall back to demo-synthetic. The CI environment
    # (or the user's network) is expected to populate these.
    if not (RAW / "aft" / "oat_green_yields_latest.csv").exists():
        print("  [warn] no live green-OAT yields available; "
              "orchestrator will fall back to demo-synthetic.")


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
