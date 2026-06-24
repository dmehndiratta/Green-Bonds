# Green-Bond-Greenium

Does sustainability-labelled **sovereign** debt trade at a lower yield than
otherwise-identical conventional debt — a **"greenium"** — and how large, how
stable, and how does it move across the maturity curve and over time?

> **Identification.** Germany issues green Federal securities **each paired with a
> conventional twin of identical coupon and maturity**. Within a twin pair the only
> difference is the green label (and the smaller, less-liquid green leg), so the
> greenium is just `(conventional yield − green yield)` — no curve-fitting, no
> convention mismatch. It is falsified if the twin spread is statistically
> indistinguishable from zero, or if it is entirely a liquidity premium. (France was
> scoped as a second issuer but dropped — it has no twin, so it needs a fitted curve,
> and there is no free per-ISIN green-OAT yield feed. German twins only.)

## What's here

| Piece | Where |
|---|---|
| Green↔conventional **twin ISIN pairs** (rebuilt from Bundesbank labels at fetch time) | `data/manual/twin_pairs.csv` |
| Fetcher: Bundesbank monthly workbooks → twin yields + issue volumes, **demo fallback** | `pipeline/01_fetch/` |
| Panel build: align twins, **harmonise conventions**, liquidity vars, entry dates | `pipeline/02_clean/build_pairs_panel.py` |
| **Headline matched-pair greenium** (level, term structure, CI) | `pipeline/03_analysis/twin_spread.py` |
| **FE panel** (pair×date FE + liquidity controls) → raw vs adjusted | `pipeline/03_analysis/panel_greenium.py` |
| Dynamics (compression trend, issuance) | `pipeline/03_analysis/dynamics.py` |
| **Refutation**: placebo pairs, liquidity-only, sign stability | `pipeline/03_analysis/refutation.py` |
| Inference: block bootstrap, Newey–West HAC, cluster-robust OLS | `pipeline/stats.py` |
| Live **dashboard** + long-form **report** | `site/dashboard.html`, `site/report.html` |

## Quickstart

```bash
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# full pipeline (fetch -> clean -> analysis -> export)
.venv\Scripts\python run_pipeline.py

# force the synthetic panel (no network) / rebuild from committed artefacts
.venv\Scripts\python run_pipeline.py --demo
.venv\Scripts\python run_pipeline.py --offline

# a single stage (1 fetch, 2 clean, 3 analysis, 4 export)
.venv\Scripts\python run_pipeline.py --stage 3
```

Open `site/dashboard.html` over http (`python -m http.server` then browse to
`site/`) — it reads `site/data/*.json`.

## Data mode

Every artefact is stamped with a `data_mode` and the dashboard/report show a banner:

- **`live`** (default) — real daily yields and issue volumes from the **Deutsche
  Bundesbank** "prices and yields of listed Federal securities" monthly Excel
  workbooks (keyless; the per-ISIN SDMX API does not carry these). The fetcher crawls
  the archive, parses each daily sheet, and rebuilds the twin set from the workbook's
  green/conventional labels.
- **`demo-synthetic`** — a deterministic synthetic panel (real twin ISIN pairs +
  real coupons/maturities/first-issue dates + an embedded greenium signal) used
  **only** when the live Bundesbank archive is unreachable, so the full method is
  runnable and testable anywhere. Synthetic numbers are illustrative; never quote
  them as empirical.

## Method (lead with the twins)

1. **Identical-twin matched-pair spread (headline).** `greenium_bp = (conv − green)
   × 100`, summarised as a level (block-bootstrap CI + Newey–West HAC), by pair, by
   maturity bucket, and as a weekly time series with a band.
2. **FE panel.** `yield ~ green + liquidity | pair×date FE`, cluster-robust by pair.
   Within a twin-day cell only **issue size** varies, so the green dummy is adjusted
   for log amount outstanding; **raw vs liquidity-adjusted** is the liquidity story.
3. **Refutation.** Placebo (conventional-leg deviation from a fitted conventional
   curve ≈ 0), liquidity-only model, and sign stability across pairs.

## Honesty notes

- The greenium is a **few basis points** — near microstructure noise; all levels
  carry block-bootstrap CIs and HAC SEs and we aggregate to weekly for the headline.
- **Sovereign-specific**: the clean twin identification does **not** transfer to
  corporate green bonds. **Not investment advice.**

See [`CLAUDE.md`](CLAUDE.md) for conventions and [`SOURCES.md`](SOURCES.md) for the
primary data sources. Full execution spec and acceptance criteria in [`plan.md`](plan.md).
