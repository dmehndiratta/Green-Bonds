# SOURCES.md — primary data sources & traceability

Every headline figure traces to the primary source below and to a value in
`site/data/*.json`. Source verified live 2026-06-24.

## Germany — the identification spine (identical twins)

| Source | What | Access | Notes |
|---|---|---|---|
| **Deutsche Bundesbank — Prices and yields of listed Federal securities** | Daily reference price, **yield and issue volume per ISIN** for every listed Federal security, one sheet per trading day, published as a monthly Excel workbook. Green bonds are labelled ("… Green") in the description column. | Archive: `https://www.bundesbank.de/dynamic/action/en/service/federal-securities/prices-and-yields/810710/prices-and-yields-of-listed-federal-securities` (monthly `*-excel-data.xlsx`) | This, not the SDMX API, is the per-ISIN yield source (the API does not carry per-bond yields). `fetch_bundesbank.py` crawls the archive, parses each daily sheet, and **rebuilds `data/manual/twin_pairs.csv`** by matching each green bond to its conventional twin on identical coupon+maturity (real, Luhn-valid ISINs). Annual / actual-actual yield basis shared by both legs → differenced directly. |

The twin-bond design itself is the Deutsche Finanzagentur's: each green Bund is
issued with a conventional twin of identical coupon and maturity, differing only in
the green label and issue size. The Bundesbank workbook is where the daily yields and
volumes for both legs are published.

## France — dropped

France was scoped as cross-issuer corroboration via a fitted Nelson–Siegel–Svensson
curve (French green OATs have no identical twin). It was removed: a curve-fitted
estimate carries exactly the model risk the German twin design exists to avoid, and
there is no free, machine-readable per-ISIN green-OAT yield series (the Agence France
Trésor site blocks automated access; daily yields are published only via commercial
terminals). The project is German-twins only.

## Liquidity control

- **Amount outstanding** per ISIN comes straight from the Bundesbank workbook's issue
  volume column (real data, not a proxy), for both the green and conventional leg, and
  varies over time as each bond is reopened. This is the operative within-twin
  liquidity control. On/off-the-run is derived from bond age.
- Absent paid feeds (Bloomberg/Refinitiv), intraday bid-ask and turnover are not
  available, so the liquidity control is issue size rather than microstructure depth.

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
