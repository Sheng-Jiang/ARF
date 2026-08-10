# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ARF (AI Relevance Factor) is a Python data pipeline that computes a single 0–100 score per stock measuring how much a company's valuation is bent by the AI narrative. It covers 73 scored companies (36 in the US leg and 37 in the China leg — the China leg includes 0100.HK MiniMax) of Jensen Huang's "5-layer cake" AI stack, produces weekly ranked reports, and generates a bubble-thermometer chart over time.

The full spec is in `ARF_PRD.md`. The reference research is in `Reference/`.

## Target Repo Layout (from PRD §7)

```
arf/          # Python package (fetchers, scoring, reporting)
config/       # universe.yaml — seed universe, layer map, pure-play %
data/         # gitignored — arf.db (DuckDB), raw cache
reports/      # gitignored — .md reports and thermometer.html
tests/
```

## Key Commands (once implemented)

```bash
# Full pipeline for a given date
python -m arf.run --as-of 2026-05-28

# Run tests
pytest tests/

# Lint
ruff check arf/
```

## Architecture

### Pipeline stages
1. **Fetch** — pull market data, fundamentals, forward estimates per ticker; store raw in DuckDB (`data/arf.db`)
2. **Score** — compute `E_score` and `V_score`; combine as `ARF = sqrt(E_score × V_score)`
3. **Snapshot** — write one row per ticker per `as_of_date` to DuckDB (idempotent: overwrite same date)
4. **Render** — emit `data/snapshots/arf_<date>.parquet`, `reports/arf_<date>.md`, and `reports/thermometer.html`

### Scoring formula (`arf/scoring.py` — primary test target)
- **E_score** (AI Exposure): weighted sum of layer (30%), pure-play % (40%), supply-chain criticality (20%), forward AI revenue growth capped at 200% (10%) → percentile-rank 0–100 within leg. (`z_score`/`winsorize` helpers exist and are unit-tested, but are not applied — percentile ranking is invariant to monotone transforms, so the PRD's z-score/winsorize step is a no-op for rankings.)
- **V_score** (Valuation Stretch): equal-weighted sum of reverse-DCF implied growth (local-currency basis), PEG-like ratio, EV/Sales 5yr percentile → subtract ROE quality adjustment (±20 pts) → percentile-rank 0–100 within leg
- **ARF**: `sqrt(E_score × V_score)` → percentile-rank within leg → `decile = 10 − floor(ARF/10)` (ARF ≥ 90 → D1; note this differs from `ceil(ARF/10)` at exact boundaries)
- **Implied growth**: `implied_growth` (g*) and `implied_growth_gap` (g* − eps_2yr_cagr consensus proxy) are computed per row in `compute_arf` on a local-currency basis and written to `snapshots`; the thermometer's "growth gap" line reads them via `MEDIAN(implied_growth_gap)`
- **Froth flag**: `ARF in D1 AND ROE < cost_of_equity AND P/S > 25`

### Universe legs — scored separately, never pooled
- **US leg (36 names)**: NVDA, AMD, INTC, MSFT, CRM, EQIX, DLR, ANET, CSCO, NEE, WMB, COHR, LITE, AVGO, MRVL, PLTR, TSM, MU, QCOM, KLAC, LRCX, AMAT, GOOGL, META, AAPL, TSLA, ORCL, NOW, DELL, VRT, CEG, VST, SMCI, ADBE, PANW, SNPS
- **China leg (37 names)**: 300308.SZ, 300502.SZ, 300394.SZ, 688498.SH, 002281.SZ, 688256.SH, 688981.SH, 000977.SZ, GDS, VNET, 300750.SZ, BIDU, BABA, 0700.HK, 9868.HK, 2513.HK, 0100.HK, 601138.SH, 002463.SZ, 300496.SZ, 002230.SZ, 688111.SH, 1810.HK, 3690.HK, 002415.SZ, 300033.SZ, 688787.SH, 603501.SH, 603986.SH, 688012.SH, 0981.HK, 1347.HK, 600584.SH, 000063.SZ, 300017.SZ, 300151.SZ, 600268.SH
- **Pre-IPO**: Anthropic, OpenAI, ByteDance, Moonshot AI, Huawei — manual tier only, no numeric ARF
- **Europe chokepoint**: ASML, ARM, Siemens Energy, Schneider Electric, STMicro, Infineon, SAP, ABB — display-only reference

### Data sources
- **US**: `yfinance` (primary) + `stockanalysis.com` scrape (EV/S history) + SEC EDGAR (segment revenue)
- **China A/HK**: `AkShare` (primary, scrapes Eastmoney/Sina) + `tushare` free tier (cross-check)
- **5-year EV/S history**: Macrotrends scrape for US
- **Pre-IPO**: manual table from press releases

All `yfinance` and scraper calls must use retry + exponential backoff. A single failed ticker logs a warning and produces a partial output — it must never crash the pipeline. Mark missing fields `null`; exclude that ticker from percentile calculations for that snapshot.

### Config
`config/universe.yaml` is the source of truth for the seed universe: layer assignment, pure-play %, leg, and policy-premium flag. Editing it must trigger recomputation on the next run without code changes.

## Critical Implementation Notes

1. **Cambricon (688256) revenue growth** hits +2386% YoY off a tiny base — cap forward growth at 200% in E_score input.
2. **Chinese names use 扣非 (after non-recurring items) net profit** for ROE — not reported net income. AkShare exposes this as a separate field.
3. **FX**: compute all valuation multiples in local currency (CNY/HKD); convert market cap to USD only for cross-leg display. Innolight/Eoptolink had ~¥2.7B FX losses in 2025 that distort GAAP net income. The reverse-DCF (V_score C1 and `implied_growth`) uses the market cap converted into the **reporting currency** (`market_cap_usd × financial_fx_usd`, falling back to `fx_rate_usd`) so it matches the FCF — mixing USD market cap with CNY/HKD FCF biases g* by the FX rate. The reporting currency is not always the trading one: BABA/BIDU/PDD/GDS/VNET trade in USD but report in CNY, and TSM trades in USD but reports in TWD, so keying off `fx_rate_usd` alone leaves those (the largest China-leg names) with a ~7x inflated FCF yield.
4. **SMIC dual-listing** (0981.HK + 688981.SH): prefer A-share (688981.SH) for the China leg's valuation; HK for liquidity reference. Document in `universe.yaml`.
5. **Policy-premium flag**: Cambricon and SMIC get `policy_premium = True` in output — informational only, not used in the formula.
6. **WACC**: 10% for US, 12% for China in the reverse-DCF calculation.

## Calibration Sanity Checks (§7 of PRD)

Before declaring v1 done, verify:
- **NVDA** lands in D2–D4 (high exposure, not bubbly given 114% ROE and fwd P/E 21–25)
- **PLTR, LITE, 300394, 688256** land in D1 (froth-flagged)
- **CSCO, NEE, BIDU, BABA, 0700** land in D6–D10

Reference calibration figures (May 2026): NVDA fwd P/E ~21–25, P/S ~21, ROE ~114%; PLTR P/S ~67–100, fwd P/E ~82–97; Cambricon TTM P/E ~273, market cap ¥800B+.

## Python Requirements

Python ≥ 3.11, type hints throughout, `ruff` clean. Unit test coverage >80% for `arf/scoring.py` (z-scoring, winsorization, percentile ranking, geometric mean, reverse-DCF solver).
