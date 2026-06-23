# SOURCES.md — primary data sources & traceability

Every headline figure traces to a primary source below and to a value in
`site/data/*.json`. Sources verified live 2026-06-15/16 (per the project plan).

## Germany — the identification spine (identical twins)

| Source | What | Access | Notes |
|---|---|---|---|
| **Deutsche Finanzagentur — Twin Bond Concept** | Definition of green Federal securities issued with a conventional twin of **identical coupon and maturity**; green/conventional ISIN pairing scheme | `https://www.deutsche-finanzagentur.de/en/federal-securities/types-of-federal-securities/green-federal-securities/twin-bond-concept` | The twin shares all features except instrument class & issue size; each gets its own ISIN. |
| **Deutsche Finanzagentur — Green securities / Issuance** | The list of green securities + issue dates/volumes; the green curve (2027–2053 by end-2025, plus a 15y 2041 issued 2026-03-03) | `.../green-federal-securities/issuance` | ISIN pairs encoded in `data/manual/twin_pairs.csv`. **Verify exact ISINs at fetch** (`isin_verified` flag; the 10y green 2030 `DE0001030757` is confirmed). |
| **Deutsche Bundesbank** | Daily **prices and yields of listed Federal securities by ISIN** (the greenium time series); green-finance / Green Bond Monitor dashboard | `https://api.statistiken.bundesbank.de/rest/data` (SDMX/CSV); web portal "prices-and-yields-of-listed-federal-securities" | Annual / actual-actual yield basis shared by both twin legs → differenced directly. Per-ISIN series keys can change. |

## France — corroboration (fitted curve, no identical twin)

| Source | What | Access | Notes |
|---|---|---|---|
| **Agence France Trésor — Green OAT** | The green-OAT list (2017 OAT 2039; 2021, 2022, 2024 issues) + allocation/performance reports | `https://www.aft.gouv.fr/en/green-oat` | Encoded in `data/manual/green_oats.csv`, source URL per row. |
| **ECB Statistical Data Warehouse** | Euro-area AAA / all-government **yield curves** (NSS reference) and FR government yields used to fit the conventional OAT curve | `https://data-api.ecb.europa.eu/service/data/YC/...` | Keyless SDMX-CSV. |

## Liquidity proxies

- **Amount outstanding** per ISIN (Finanzagentur factsheets) — the green leg is
  materially smaller than its conventional twin; encoded as `initial_green_amount`
  in `twin_pairs.csv` and grown over time. On/off-the-run derived from bond age.
- Absent paid feeds (Bloomberg/Refinitiv), intraday bid-ask and turnover are not
  available; liquidity controls are proxies (issue size, age, on/off-the-run).

## Labels / estimand

- **Greenium (bp)** = `(conventional yield − green yield) × 100` for matched twins.
- Reported as a level, a curve (by maturity), and a time series, each with a
  block-bootstrap 95% CI and a Newey–West HAC SE.

## Reproducibility

- `SEED = 20260615` (`config.yaml`), recorded in every results JSON.
- Raw snapshots cached under `data/raw/<source>/<YYYY-MM-DD>/` (gitignored);
  committed artefacts under `data/processed/`, `data/facts/`, `data/manual/`.
- `data_mode` (`live` / `demo-synthetic`) is stamped on all outputs; synthetic runs
  are clearly banner-labelled and never quoted as empirical.
