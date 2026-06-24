"""Fetch real daily yields of German green Federal securities and their
conventional twins from Deutsche Bundesbank.

The data source (confirmed 2026-06): Bundesbank does NOT expose per-ISIN yields
through the SDMX API. "Prices and yields of listed Federal securities" is
published as one **monthly Excel workbook**, with one sheet per trading day, each
sheet listing every listed Federal security with its ISIN, coupon, maturity,
issue volume and reference yield. Green bonds are labelled in the description
column ("... Green"). See the public archive:
  https://www.bundesbank.de/dynamic/action/en/service/federal-securities/prices-and-yields/810710/prices-and-yields-of-listed-federal-securities

What this fetcher does:
  1. Crawl the monthly archive to discover the XLSX URL for every month in the
     configured sample window (the blob URLs are opaque, so they are scraped).
  2. Download + parse each workbook (closed months are cached; the current month
     is always refreshed).
  3. Identify each green bond and match it to its conventional twin by *identical
     coupon and maturity* — the Finanzagentur twin design guarantees this is a
     one-to-one match, so no curve or hand-keyed ISIN list is needed.
  4. Emit the daily per-leg yields, the per-ISIN issue volumes (the real liquidity
     control), and a freshly discovered twin_pairs.csv with verified ISINs.

If nothing is retrievable (e.g. the host is unreachable), no `_latest` file is
written and the orchestrator (run_pipeline.py) falls back to the synthetic demo.
Idempotent: monthly workbooks cached under data/raw/bundesbank/months/.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pandas as pd

PIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPE))
from common import (FACTS, MANUAL, RAW, fetch_bytes, fetch_text, http_session,  # noqa: E402
                    load_config, snapshot_dir, write_json)

ARCHIVE = ("https://www.bundesbank.de/action/en/810710/bbksearch?pageNumString={page}")
HOST = "https://www.bundesbank.de"
SOURCE_URL = (HOST + "/dynamic/action/en/service/federal-securities/prices-and-yields/"
              "810710/prices-and-yields-of-listed-federal-securities")
_XLSX_RE = re.compile(r'href="(/resource/blob/[^"]*?(\d{4})-(\d{2})-excel-data\.xlsx)"', re.I)


# --- ISIN reconstruction ----------------------------------------------------
def _mk_isin(r) -> str | None:
    """Workbook splits the ISIN across three cells: prefix 'DE000' (col 0),
    the 6-char WKN (col 1, numeric WKNs lose their leading zeros to Excel) and
    the single check digit (col 2). Reassemble and length-check."""
    a = str(r[0]).strip()
    b = r[1]
    if isinstance(b, (int, float)) and not pd.isna(b):
        b = str(int(b)).zfill(6)
    else:
        b = str(b).strip()
    if pd.isna(r[2]):
        return None
    code = f"{a}{b}{int(float(r[2]))}"
    return code if len(code) == 12 else None


def _crawl_months(session, start_ym: str, end_ym: str, snap: Path,
                  offline: bool) -> dict[str, str]:
    """Return {YYYY-MM: xlsx_url} for every month within [start_ym, end_ym]."""
    found: dict[str, str] = {}
    for page in range(60):  # 5 months/page; ~14 pages back to 2020, bounded for safety
        html = fetch_text(session, ARCHIVE.format(page=page),
                          snap / f"archive_p{page}.html", offline=offline)
        if not html:
            break
        hits = _XLSX_RE.findall(html)
        if not hits:
            break
        months_on_page = []
        for href, y, m in hits:
            ym = f"{y}-{m}"
            months_on_page.append(ym)
            if start_ym <= ym <= end_ym:
                found[ym] = HOST + href
        if min(months_on_page) < start_ym:  # walked past the window
            break
    return found


def _parse_workbook(content: bytes) -> pd.DataFrame:
    """One row per security per trading day."""
    xl = pd.ExcelFile(io.BytesIO(content))
    rows = []
    for sheet in xl.sheet_names:
        date = pd.to_datetime(sheet, format="%d.%m.%Y", errors="coerce")
        if pd.isna(date):
            continue  # non-daily sheets, if any
        df = xl.parse(sheet, header=None)
        for _, r in df.iterrows():
            if str(r[0]).strip() != "DE000":  # data rows only
                continue
            isin = _mk_isin(r)
            yld = pd.to_numeric(r[9], errors="coerce")
            mat = pd.to_datetime(r[5], format="%d.%m.%Y", errors="coerce")
            if isin is None or pd.isna(yld) or pd.isna(mat):
                continue
            desc = str(r[4]).strip()
            rows.append({
                "date": date, "isin": isin,
                "coupon": round(float(pd.to_numeric(r[3], errors="coerce")), 3),
                "desc": desc, "maturity": mat,
                "amount_out_eur_bn": pd.to_numeric(r[7], errors="coerce"),
                "yield_pct": float(yld),
                "is_green": "green" in desc.lower(),
            })
    return pd.DataFrame(rows)


def _discover_pairs(sec: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """Match each green bond to its conventional twin (identical coupon+maturity)."""
    pairs, unmatched = [], []
    for gi in sorted(sec.loc[sec["is_green"], "isin"].unique()):
        g = sec[sec["isin"] == gi]
        gc, gm, gdesc = round(float(g["coupon"].iloc[0]), 3), g["maturity"].iloc[0], g["desc"].iloc[0]
        cand = sec[(~sec["is_green"]) & (sec["maturity"] == gm)
                   & (sec["coupon"].round(3) == gc)]
        if cand.empty:
            unmatched.append({"green_isin": gi, "desc": gdesc, "reason": "no conv twin"})
            continue
        # if several, take the conventional ISIN that co-trades on the most days
        gdates = set(g["date"])
        conv_isin = max(cand.groupby("isin").groups,
                        key=lambda ci: len(gdates & set(cand[cand["isin"] == ci]["date"])))
        first_issue = g["date"].min()
        tenor = round((gm - first_issue).days / 365.25)
        kind = "Green Bobl" if gdesc.upper().startswith("BO") else "Green Bund"
        init_amt = float(g.sort_values("date")["amount_out_eur_bn"].iloc[0])
        pairs.append({
            "pair_id": f"green_{gm.year}_{tenor}y",
            "tenor_label": f"{tenor}Y {kind}",
            "green_isin": gi, "conv_isin": conv_isin,
            "coupon": gc, "maturity": gm.strftime("%Y-%m-%d"),
            "first_issue": first_issue.strftime("%Y-%m-%d"),
            "initial_green_amount_eur_bn": round(init_amt, 3),
            "isin_verified": True, "source_url": SOURCE_URL,
        })
    return pd.DataFrame(pairs), unmatched


def main(offline: bool = False) -> None:
    cfg = load_config()
    start_ym = cfg["sample"]["start"][:7]
    end_ym = cfg["sample"]["end"][:7]
    cur_ym = pd.Timestamp.today().strftime("%Y-%m")
    session = http_session()
    snap = snapshot_dir("bundesbank")
    months_dir = RAW / "bundesbank" / "months"
    months_dir.mkdir(parents=True, exist_ok=True)

    urls = _crawl_months(session, start_ym, end_ym, snap, offline)
    if not urls and not offline:
        print("  [warn] Bundesbank archive returned no monthly workbooks; "
              "orchestrator will fall back to demo-synthetic.")
        return

    frames, got = [], []
    for ym in sorted(urls) or sorted(p.stem.replace("-data", "") for p in months_dir.glob("*-data.xlsx")):
        url = urls.get(ym)
        dest = months_dir / f"{ym}-data.xlsx"
        # closed months are immutable -> reuse cache; refresh the live current month
        content = fetch_bytes(session, url, dest, offline=offline,
                              force=(ym >= cur_ym)) if url else (
            dest.read_bytes() if dest.exists() else None)
        if not content:
            continue
        try:
            frames.append(_parse_workbook(content))
            got.append(ym)
        except Exception as exc:  # noqa: BLE001
            print(f"  [warn] parse failed for {ym}: {exc}")

    if not frames:
        print("  [warn] no Bundesbank workbooks parsed; falling back to demo-synthetic.")
        return

    sec = pd.concat(frames, ignore_index=True).drop_duplicates(["date", "isin"])
    sec = sec[(sec["date"] >= cfg["sample"]["start"]) & (sec["date"] <= cfg["sample"]["end"])]
    pairs, unmatched = _discover_pairs(sec)
    if pairs.empty:
        print("  [warn] no green/conventional twins discovered; demo fallback.")
        return

    # --- twin_pairs.csv (verified, from Bundesbank's own labels) --------------
    pairs = pairs.sort_values("maturity").reset_index(drop=True)
    pairs.to_csv(MANUAL / "twin_pairs.csv", index=False)

    # --- daily per-leg yields -------------------------------------------------
    legs = []
    for _, p in pairs.iterrows():
        for leg, isin in (("green", p["green_isin"]), ("conv", p["conv_isin"])):
            s = sec[sec["isin"] == isin][["date", "yield_pct"]].copy()
            s["pair_id"], s["leg"], s["isin"] = p["pair_id"], leg, isin
            legs.append(s)
    yld = pd.concat(legs, ignore_index=True)[["date", "pair_id", "leg", "isin", "yield_pct"]]
    yld = yld.sort_values(["pair_id", "leg", "date"]).reset_index(drop=True)
    yld.to_csv(snap / "bundesbank_yields.csv", index=False)
    yld.to_csv(RAW / "bundesbank" / "bundesbank_yields_latest.csv", index=False)

    # --- per-ISIN issue volume (the real liquidity control) -------------------
    pair_isins = set(pairs["green_isin"]) | set(pairs["conv_isin"])
    amt = sec[sec["isin"].isin(pair_isins)][["date", "isin", "amount_out_eur_bn"]].copy()
    first_seen = sec.groupby("isin")["date"].min()
    age_days = (amt["date"] - amt["isin"].map(first_seen)).dt.days
    amt["on_the_run"] = (age_days < 365).astype(int)
    amt = amt.sort_values(["isin", "date"]).reset_index(drop=True)
    amt.to_csv(snap / "bundesbank_amounts.csv", index=False)
    amt.to_csv(RAW / "bundesbank" / "bundesbank_amounts_latest.csv", index=False)

    write_json(RAW / "bundesbank" / "fetch_meta.json",
               {"months_fetched": got, "n_months": len(got),
                "n_pairs": int(len(pairs)), "n_obs": int(len(yld)),
                "unmatched_green": unmatched,
                "pairs": pairs.to_dict(orient="records")})
    write_json(FACTS / "data_mode.json",
               {"data_mode": "live",
                "source": "Deutsche Bundesbank — prices and yields of listed Federal securities",
                "source_url": SOURCE_URL,
                "months": [got[0], got[-1]] if got else []})
    print(f"  Bundesbank LIVE: {len(pairs)} twin pairs, {len(got)} months "
          f"({got[0]}..{got[-1]}), {len(yld)} leg-day obs. "
          + (f"Unmatched green: {[u['green_isin'] for u in unmatched]}" if unmatched else "all green bonds twinned."))


if __name__ == "__main__":
    main(offline="--offline" in sys.argv)
