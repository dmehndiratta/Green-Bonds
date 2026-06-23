"""Fetch the ECB euro-area AAA-rated central-government yield curve (SDW, keyless).

Used as a euro-area reference for the NSS robustness spec and as a sanity check on
the fitted French conventional curve. ECB SDW exposes SDMX-CSV at
data-api.ecb.europa.eu/service/data/<flow>/<key>.

Best-effort + last-good fallback; on failure writes no `_latest` file and the
orchestrator falls back to the synthetic demo data.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
from common import (RAW, fetch_text, http_session, load_config,  # noqa: E402
                    snapshot_dir)

# Yield-curve flow (YC). Spot rates, AAA-rated, government bonds, for a set of
# tenors. Key per tenor: e.g. B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y.
FLOW = "YC"
TENORS = {1: "SR_1Y", 2: "SR_2Y", 3: "SR_3Y", 5: "SR_5Y", 7: "SR_7Y",
          10: "SR_10Y", 15: "SR_15Y", 20: "SR_20Y", 30: "SR_30Y"}


def _url(base: str, tenor_key: str) -> str:
    key = f"B.U2.EUR.4F.G_N_A.SV_C_YM.{tenor_key}"
    return f"{base}/{FLOW}/{key}?format=csvdata"


def main(offline: bool = False) -> None:
    cfg = load_config()
    base = cfg["ecb"]["sdw_base"]
    session = http_session()
    snap = snapshot_dir("ecb")

    frames = []
    for m, tkey in TENORS.items():
        dest = snap / f"{tkey}.csv"
        text = fetch_text(session, _url(base, tkey), dest, offline=offline)
        if not text:
            continue
        try:
            df = pd.read_csv(io.StringIO(text))
            cols = {c.lower(): c for c in df.columns}
            tcol = cols.get("time_period") or "TIME_PERIOD"
            vcol = cols.get("obs_value") or "OBS_VALUE"
            frames.append(pd.DataFrame({
                "date": pd.to_datetime(df[tcol], errors="coerce"),
                "maturity_years": float(m),
                "yield_pct": pd.to_numeric(df[vcol], errors="coerce")}).dropna())
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] ECB {tkey} parse error: {exc}")

    if not frames:
        print("  [warn] ECB curve unavailable; orchestrator may fall back to demo.")
        return
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(snap / "ecb_aaa_curve.csv", index=False)
    out.to_csv(RAW / "ecb" / "ecb_aaa_curve_latest.csv", index=False)
    print(f"  ECB AAA curve: {out['maturity_years'].nunique()} tenors, {len(out)} obs")


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
