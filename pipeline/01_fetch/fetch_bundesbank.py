"""Fetch daily prices & yields of listed German Federal securities by ISIN from
Deutsche Bundesbank, for every green and conventional twin ISIN in twin_pairs.csv.

Bundesbank publishes per-ISIN daily yields via its statistics REST/SDMX API
(`api.statistiken.bundesbank.de/rest/data/<flow>/<key>`). The exact per-ISIN
series keys change as new securities are listed (plan §11.3), so this fetcher
logs the keys it tries and falls back to last-good cache. If nothing is
retrievable (e.g. the host blocks automated requests), it writes no `_latest`
file and the orchestrator (run_pipeline.py) switches to the synthetic demo panel.

Idempotent: cached under data/raw/bundesbank/<date>/ with last-good fallback.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
from common import (MANUAL, RAW, fetch_text, http_session, load_config,  # noqa: E402
                    snapshot_dir, write_json)

# SDMX-CSV daily yield flow for listed Federal securities. The series key per ISIN
# follows the WT3*/BBSIS structure; confirm at runtime against
# https://www.bundesbank.de/.../prices-and-yields-of-listed-federal-securities
YIELD_FLOW = "BBSIS"


def _series_url(base: str, isin: str) -> str:
    # Best-effort key; logged so a maintainer can correct it if the schema moved.
    return f"{base}/{YIELD_FLOW}/D.{isin}.YIELD?format=csv&detail=dataonly"


def main(offline: bool = False) -> None:
    cfg = load_config()
    base = cfg["germany"]["bundesbank_base"]
    pairs = pd.read_csv(MANUAL / "twin_pairs.csv")
    session = http_session()
    snap = snapshot_dir("bundesbank")

    isins = []
    for _, p in pairs.iterrows():
        isins += [(p["pair_id"], "green", p["green_isin"]),
                  (p["pair_id"], "conv", p["conv_isin"])]

    frames, meta = [], {}
    for pair_id, leg, isin in isins:
        url = _series_url(base, isin)
        dest = snap / f"{isin}.csv"
        text = fetch_text(session, url, dest, offline=offline)
        if not text:
            meta[isin] = {"status": "missing", "url": url}
            continue
        try:
            df = pd.read_csv(io.StringIO(text))
            # SDMX-CSV: expect TIME_PERIOD + OBS_VALUE columns; be tolerant.
            cols = {c.lower(): c for c in df.columns}
            tcol = cols.get("time_period") or list(df.columns)[0]
            vcol = cols.get("obs_value") or list(df.columns)[-1]
            out = pd.DataFrame({
                "date": pd.to_datetime(df[tcol], errors="coerce"),
                "isin": isin, "leg": leg, "pair_id": pair_id,
                "yield_pct": pd.to_numeric(df[vcol], errors="coerce")})
            out = out.dropna(subset=["date", "yield_pct"])
            if out.empty:
                meta[isin] = {"status": "empty", "url": url}
                continue
            frames.append(out)
            meta[isin] = {"status": "ok", "rows": int(len(out)), "url": url}
        except Exception as exc:  # noqa: BLE001
            meta[isin] = {"status": f"parse_error: {exc}", "url": url}

    write_json(RAW / "bundesbank" / "fetch_meta.json",
               {"flow": YIELD_FLOW, "series": meta})
    if not frames:
        print("  [warn] Bundesbank returned no per-ISIN yields; "
              "orchestrator will fall back to demo-synthetic.")
        return
    ally = pd.concat(frames, ignore_index=True)
    ally.to_csv(snap / "bundesbank_yields.csv", index=False)
    ally.to_csv(RAW / "bundesbank" / "bundesbank_yields_latest.csv", index=False)
    print(f"  Bundesbank: {ally['isin'].nunique()} ISINs, {len(ally)} obs")
    # NOTE: live issue-size / liquidity (amount outstanding) is fetched from the
    # Finanzagentur factsheets; absent a live amounts feed here, the cleaner falls
    # back to the initial amounts in twin_pairs.csv (documented, conservative).


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
