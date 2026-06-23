# plan-green-bond-greenium.md

> Execution plan for Claude Code. Self-contained. See SETUP.md for the shared
> website mechanism and house conventions.
>
> **Repo:** `dmehndiratta/Green-Bond-Greenium` (new, public, independent)
> **Local path:** `D:\Python Projects\Green-Bond-Greenium`
> **Site slug:** `green-bond-greenium` → `Website/public/green-bond-greenium/`,
> page `/research/green-bond-greenium`. **Living** (weekly cron; greenium moves daily).

---

## 1. Thesis

**Question:** Does sustainability-labelled sovereign debt trade at a lower yield than
otherwise-identical conventional debt — a "greenium" — and how large, how stable, and
how does it move over time and across the maturity curve?

**Hypothesis:** Using Germany's **green "twin" bonds** (each green Bund issued with a
conventional twin of identical coupon and maturity) — the cleanest possible matched
pair — the green bond yields a few basis points *below* its conventional twin
(greenium > 0), larger at the short end and compressing over 2020→2026, with French
green OATs corroborating directionally.

**What would falsify it:** If the green-minus-conventional yield spread on the
identical-twin pairs is statistically indistinguishable from zero (CI spans 0) across
the sample, the greenium claim is falsified for sovereigns. If the spread is positive
(green yields *above* conventional) outside crisis windows, that contradicts the
hypothesis. If apparent greenium is an artefact of liquidity differences (the green
leg is smaller/less liquid) rather than the green label, the *causal* "investors pay
for green" interpretation fails — which is why liquidity controls and the twin design
are central, and a liquidity-driven null must be reported honestly.

---

## 2. Why it is in the portfolio

**Audience:** sustainable-finance / ESG fixed-income desks, fixed-income research, and
asset-management ESG teams.

**Skill demonstrated:** fixed-income analytics (yield curves, matched-pair spreads,
Nelson–Siegel–Svensson fitting), a credible **identification strategy via identical
twins** (holding issuer, coupon, maturity, and tax treatment fixed so the only
difference is the green label), liquidity-confound awareness, and time-series/panel
estimation of a small, noisy spread with honest uncertainty. It's a finance-native
project that still foregrounds clean identification.

---

## 3. Data

### Primary — German green "twin" bonds (the identification spine)
- **What:** since 2020 the German Finance Agency issues **green Federal securities
  each paired with a conventional twin of identical coupon and maturity**, expressly
  so the market can read the **greenium** as the yield difference. As of Dec 2025,
  **~€79.25bn outstanding across 9 green securities**, a green curve out to 30y;
  greenium reported around **2–3 bp (long end) to ~6 bp (3y)**. **Verified 2026-06-15.**
- **Concept & pair list:** Deutsche Finanzagentur "Twin Bond Concept" page and
  green-securities pages give the ISIN pairs and issuance details
  (`https://www.deutsche-finanzagentur.de/en/federal-securities/types-of-federal-
  securities/green-federal-securities`). Encode the green↔conventional ISIN pairs
  (coupon, maturity, first issue date) into `data/manual/twin_pairs.csv` with URLs.
- **Yields/prices (the time series):** **Deutsche Bundesbank** publishes daily
  **prices and yields of listed Federal securities by ISIN**
  (`.../prices-and-yields-of-listed-federal-securities/...793580`) and a **Green Bond
  Monitor / green finance dashboard**. The greenium is reconstructed as
  green_yield(ISIN) − twin_yield(ISIN) per day. Bundesbank time-series are downloadable
  (CSV/SDMX). This makes the headline fully **reproducible from public data**.

### Corroboration — French green OATs (Agence France Trésor)
- AFT green OATs (first 2017 OAT 2039; further 2021, 2022, 2024; ~€83bn green debt).
  No identical-twin construct, so greenium is estimated **against a fitted conventional
  OAT curve** (matched by maturity), a noisier but independent check. AFT publishes the
  green OAT list and allocation/performance reports
  (`https://www.aft.gouv.fr/en/green-oat`). Conventional OAT yields from public
  sources (Banque de France / ECB / FRED).

### Supporting
- **Risk-free / curve inputs** for the fitted-curve approach: ECB euro-area AAA and
  all-bonds yield curves (ECB Statistical Data Warehouse, public) for Nelson–Siegel–
  Svensson references.
- **Liquidity proxies:** outstanding amount per ISIN (Finanzagentur), and, where
  public, bid-ask/turnover indicators; at minimum control for issue size and
  on-the-run/off-the-run status.

### Access, cadence, size
- Bundesbank time-series (SDMX/CSV, keyless), Finanzagentur factsheets/ISIN pages,
  AFT pages, ECB SDW (keyless). All MB-scale. Cadence: daily yields; weekly refresh is
  ample for a living dashboard.

### Gotchas to guard against
1. **Liquidity confound (the central threat):** the green leg is typically smaller and
   less liquid than the conventional benchmark; part of any yield gap can be a
   liquidity premium, not a green preference. The **identical-twin** design fixes
   issuer/coupon/maturity/tax, isolating label+liquidity; then **control for liquidity**
   (issue size, age, on/off-the-run) and discuss the residual. Do not claim a pure
   "green preference" without addressing this.
2. **Matching quality:** only the German twins are *identical*; French/other greenium
   needs curve-fitting (Nelson–Siegel–Svensson) and is sensitive to the curve spec —
   report curve-fit diagnostics and alternative specs.
3. **Small magnitudes / noise:** greenium is a few bp — within bid-ask noise on some
   days. Use robust time-series inference (HAC/Newey–West), report CIs, and avoid
   over-reading daily wiggles; aggregate to weekly/monthly for the headline.
4. **Day-count / yield conventions:** ensure green and conventional yields use the same
   convention and quote basis before differencing (Bundesbank yields are consistent;
   cross-source French data may not be — harmonise).
5. **Survivorship / issuance timing:** new twins enter over time; the panel is
   unbalanced; handle entry dates and avoid comparing a bond before its twin existed.
6. **Crisis/illiquidity windows:** 2022 rate shock and stress periods distort spreads;
   show results with/without stress windows.
7. **Tax/regulatory parity:** twins share tax treatment (sovereign), so this is clean;
   note that the result is sovereign-specific and may not extend to corporates (where
   credit and covenants differ).

---

## 4. Method

**Estimand:** the greenium = (conventional yield − green yield) for matched pairs,
in basis points, as a level, a curve (by maturity), and a time series.

**Estimators:**
1. **Identical-twin matched-pair spread (headline):** for each German twin pair and
   day, greenium_t = y_conventional_t − y_green_t; summarise level + CI, by pair and by
   maturity bucket; plot the time series. This is the cleanest estimate — minimal
   modelling.
2. **Panel regression:** pooled/fixed-effects panel of yields on a `green` dummy with
   **pair × date fixed effects** (so each green bond is compared only to its own twin on
   the same day) and **liquidity controls** (issue size, age, on/off-the-run) → the
   green-dummy coefficient is the liquidity-adjusted greenium; cluster SEs by pair/date.
3. **Fitted-curve approach (French + cross-check):** estimate a Nelson–Siegel–Svensson
   conventional curve per day; greenium = fitted-conventional-yield(at green's maturity)
   − green yield; corroborates the twin result on a different issuer.
4. **Dynamics:** track greenium over 2020→2026; test for a **trend (compression)** and
   relate to issuance volume / market maturation; optional event study around new green
   issuance dates.

**Validation, robustness, refutation — "done right":**
- **Twin design first:** lead with the model-free identical-twin spread; the panel and
  curve methods are corroboration, not the headline.
- **Liquidity-adjusted vs raw:** report greenium with and without liquidity controls;
  the gap between them *is* the liquidity story — show it explicitly.
- **Uncertainty (mandatory):** HAC/Newey–West SEs and **block-bootstrap** CIs on the
  greenium level and trend; the dashboard shows the spread with a confidence band.
- **Robustness:** by maturity bucket; with/without the 2022 stress window; daily vs
  weekly vs monthly aggregation; German twins vs French OATs; alternative NSS curve
  specs; excluding the most recently issued (least seasoned) bonds.
- **Refutation:** (a) **placebo pairs** — match two *conventional* Bunds of similar
  (not identical) maturity and compute a pseudo-spread; it should be near zero/noise,
  showing the greenium isn't a mechanical maturity artefact; (b) liquidity-only model —
  if the green dummy dies once liquidity is controlled, report that the "greenium" is
  largely a liquidity premium (an honest, falsifying outcome); (c) test sign stability
  across pairs (a real greenium should be consistently signed).

**What "not credible" looks like:** quoting a single bp number with no CI; ignoring
liquidity; mixing yield conventions across sources; over-fitting a curve and reading
sub-bp greenium off it; treating noisy daily spreads as signal; claiming corporate or
universal greenium from sovereign twins.

---

## 5. Architecture

```
Green-Bond-Greenium/
├── README.md
├── CLAUDE.md
├── plan.md
├── requirements.txt              # pinned
├── run_pipeline.py               # --offline --export-only --stage N
├── sync_to_website.py
├── .gitignore
├── SOURCES.md                    # Finanzagentur twin pages, Bundesbank series, AFT, ECB SDW
├── config.yaml                   # ISIN pairs, stress windows, NSS settings, seed
├── data/
│   ├── manual/twin_pairs.csv            # green↔conventional ISIN pairs + coupon/maturity + URLs (committed)
│   ├── raw/bundesbank/<YYYY-MM-DD>/      # daily yields by ISIN (gitignored)
│   ├── raw/aft/<YYYY-MM-DD>/
│   ├── raw/ecb/<YYYY-MM-DD>/
│   ├── interim/
│   └── processed/                        # greenium series + results (committed small)
├── pipeline/
│   ├── 01_fetch/fetch_bundesbank.py      # SDMX/CSV daily yields for twin ISINs + issue sizes
│   ├── 01_fetch/fetch_aft_oat.py         # green OAT list + conventional OAT yields
│   ├── 01_fetch/fetch_ecb_curve.py       # euro-area reference curves
│   ├── 02_clean/build_pairs_panel.py     # align by date/ISIN; harmonise yield conventions; liquidity vars
│   ├── 03_analysis/twin_spread.py        # matched-pair greenium + CIs → results_twin.json
│   ├── 03_analysis/panel_greenium.py     # FE panel w/ liquidity controls → results_panel.json
│   ├── 03_analysis/nss_curve.py          # Nelson–Siegel–Svensson fit; French greenium → results_nss.json
│   ├── 03_analysis/dynamics.py           # trend/compression, issuance events → results_dynamics.json
│   ├── 03_analysis/refutation.py         # placebo pairs, liquidity-only, sign stability
│   └── 04_export/export_json.py
├── site/{report.html,dashboard.html,data/*.json}
├── tests/                        # convention harmonisation, pair-entry dates, JSON schema
└── .github/workflows/green-greenium-update.yml
```

- **Environment:** **Python 3.11**. Pin: `pandas==2.2.*`, `numpy==1.26.*`,
  `statsmodels==0.14.*` (HAC, panel), `linearmodels==6.*` (FE panel), `scipy==1.13.*`
  (NSS optimisation), `arch==7.*` or custom block bootstrap, `requests`,
  `pandasdmx==1.*` (Bundesbank/ECB SDMX) or direct CSV, `matplotlib`, `pyyaml`, `tqdm`.
- **Seeds:** `SEED=20260615` for bootstrap; recorded in JSON.
- Reuse SETUP.md §7 conventions; validate-then-promote with last-good fallback so the
  weekly CI never publishes on a failed fetch; raw gitignored; processed committed.

---

## 6. Deliverables

- **Repo** as above; `python run_pipeline.py` reproduces the greenium from public
  data; `--offline` rebuilds JSON.
- **Report** `site/report.html`: greenium concept → why twins identify it → data →
  matched-pair headline → liquidity-adjusted panel → French corroboration & NSS →
  dynamics/compression → robustness & refutation (placebo pairs, liquidity-only) →
  limitations (sovereign-specific, small magnitudes).
- **Interactive dashboard** `site/dashboard.html` (living; static; Plotly/D3 from CDN;
  JSON): (a) **greenium time series** per twin pair with a confidence band and a
  pair/maturity selector; (b) **greenium term structure** (bp by maturity) snapshot;
  (c) raw vs liquidity-adjusted greenium comparison; (d) Germany vs France panel;
  (e) "last updated" stamp. No backend.
- **Figures/tables:** greenium time series, term-structure curve, panel coefficient
  table with CIs, placebo-pair distribution, compression-trend estimate.
- **Project CLAUDE.md:** ISIN pair list, yield-convention harmonisation rule,
  liquidity-control requirement, "lead with twins, not the fitted curve," seed.

---

## 7. Website integration (Pattern A; see SETUP.md §3–§8)

**Secret in this repo:** `WEBSITE_REPO_TOKEN` (required). Data sources are keyless
(Bundesbank/ECB SDMX, AFT) — no data API key needed.

**Workflow:** `.github/workflows/green-greenium-update.yml` — two-job shape from
plan-credit-default-pd.md §7, **plus a weekly schedule** (`cron: '0 7 * * 1'`) and
`workflow_dispatch` (living analysis). `update` runs the **full** pipeline
(fetch→analysis→export) with validate-then-promote, runs the JSON guard, commits
refreshed `site/data/` + `data/processed/`. `sync-website` copies the full payload
into `website/public/green-bond-greenium/{data/,dashboard.html,report.html}` via the
PAT and pushes (Cloudflare Pages redeploys).

**Human action items (Dhruv):** create repo `Green-Bond-Greenium`; add
`WEBSITE_REPO_TOKEN`; one-time Website edit — `/research` card +
`src/pages/research/green-bond-greenium.mdx` (status `LIVE`, tags
`SUSTAINABLE FINANCE`, `FIXED INCOME`, `ESG`, `TIME SERIES`) embedding
`/green-bond-greenium/dashboard.html`.

**Verify the deploy:** trigger `workflow_dispatch`; both jobs green; open
`https://dhruv-mehndiratta.com/green-bond-greenium/dashboard.html` and
`/research/green-bond-greenium`; confirm JSON parses, the band renders, and a
scheduled run updates the "last updated" stamp.

---

## 8. Acceptance criteria

- [ ] German green↔conventional twin ISIN pairs encoded with coupon/maturity/first-
      issue + source URLs.
- [ ] Bundesbank daily yields by ISIN (and issue sizes) fetched idempotently; AFT +
      ECB curves fetched; vintages logged.
- [ ] Yield conventions harmonised before differencing (tested).
- [ ] **Matched-pair twin greenium** (headline) computed with CIs, by pair & maturity.
- [ ] **FE panel with pair×date effects + liquidity controls**; raw vs adjusted
      greenium both reported.
- [ ] NSS fitted-curve greenium for French OATs as corroboration with fit diagnostics.
- [ ] Dynamics: compression trend tested; issuance-event view.
- [ ] Robustness (maturity buckets, stress-window in/out, aggregation frequency,
      Germany vs France, NSS specs) + refutation (**placebo conventional pairs**,
      liquidity-only model, sign stability) run and reported.
- [ ] HAC + block-bootstrap CIs; dashboard band shown; "last updated" stamp.
- [ ] JSON guard passes; numbers trace to JSON; limitations present.

---

## 9. Task sequence

1. Scaffold repo, `config.yaml` (ISIN pairs, stress windows, NSS settings, SEED),
   pinned `requirements.txt`, README/CLAUDE, `SOURCES.md`. **Verify:** imports; links.
2. `data/manual/twin_pairs.csv` from Finanzagentur (green↔conventional ISINs, coupon,
   maturity, first issue). **Verify:** ≥8 pairs; identical coupon+maturity within pair.
3. `fetch_bundesbank.py`: daily yields per ISIN (SDMX/CSV) + issue sizes; cache.
   **Verify:** both legs of ≥1 pair return aligned daily yields; idempotent.
4. `fetch_aft_oat.py` + `fetch_ecb_curve.py`. **Verify:** green OAT list + conventional
   yields + ECB reference curve load.
5. `build_pairs_panel.py`: align by date/ISIN, harmonise conventions, build liquidity
   vars, handle pair entry dates. **Verify:** convention test; no pre-twin comparisons.
6. `twin_spread.py` → `results_twin.json` (greenium level/series/term structure + CIs).
   **Verify:** greenium small (single-digit bp), consistently signed, near published
   2–3/6 bp figures.
7. `panel_greenium.py` → `results_panel.json` (FE + liquidity-adjusted green dummy).
   **Verify:** raw vs adjusted both reported; clustered SEs.
8. `nss_curve.py` → `results_nss.json` (French greenium, fit diagnostics). **Verify:**
   curve fit RMSE small; greenium estimate with CI.
9. `dynamics.py` → `results_dynamics.json` (compression trend, issuance events).
   **Verify:** trend sign/CI; not over-read.
10. `refutation.py`: placebo conventional pairs (≈0), liquidity-only model, sign
    stability → `results_refutation.json`. **Verify:** placebo near zero.
11. `export_json.py` → `site/data/*.json` (+ last-updated). **Verify:** JSON guard passes.
12. Build `report.html` + living `dashboard.html` (greenium series + band + selector,
    term structure, raw-vs-adjusted, DE-vs-FR). **Verify:** `file://` load; numbers
    match JSON.
13. `tests/` green; reproducibility.
14. Add weekly workflow (§7); commit processed artefacts. **Verify:** `workflow_dispatch`
    both jobs green.
15. (Dhruv) secret + one-time Website page/card; **verify deploy**.

---

## 10. Limitations and caveats

- **Sovereign-specific:** the clean twin identification exists for German Bunds (and
  partially French OATs); results do **not** transfer to corporate green bonds, where
  credit risk, covenants, and use-of-proceeds verification differ materially. State
  this prominently.
- **Small, noisy magnitudes:** a few basis points is near market microstructure noise;
  conclusions are about averages with bands, not precise daily values.
- **Liquidity vs preference:** even with twins, the residual greenium blends a genuine
  green-investor preference with a liquidity premium; we bound but cannot fully
  separate them without proprietary order-flow/liquidity data.
- **Public-data granularity:** without paid feeds (Bloomberg/Refinitiv) we lack
  intraday bid-ask and some turnover measures; liquidity controls are proxies.
- **Not investment advice:** the greenium is a research quantity, not a trade
  recommendation.

---

## 11. Open questions and risks

1. **Scope of issuers:** Germany (twins) + France (curve) proposed. Add a second twin
   issuer if available, or keep it tight? Default: Germany headline + France
   corroboration; tight scope.
2. **Corporate extension:** a matched corporate green/conventional panel is attractive
   but public corporate bond pricing is sparse/unreliable for clean matches. Default:
   exclude corporates this round; note as v2 with the data caveat.
3. **Bundesbank access path:** SDMX vs direct CSV download for per-ISIN yields —
   builder should confirm the exact series keys at fetch time (IDs can change); the
   Green Bond Monitor may expose a ready greenium series to cross-check against.
4. **Refresh cadence:** weekly Monday cron proposed (greenium moves daily but weekly is
   ample for a portfolio dashboard). Confirm weekly vs daily.
5. **Curve spec:** Nelson–Siegel–Svensson vs simpler NS for the French leg. Default:
   NSS with NS as a robustness spec.
