# Product Requirements Document: AI Relevance Factor (ARF) — POC v1

**Owner:** [User]
**Status:** Draft for engineering handoff (Claude Code)
**Last updated:** May 28, 2026
**Target completion (v1):** 2 weeks from kickoff

---

## 1. Background and Problem Statement

We want a **single scalar per stock — the AI Relevance Factor (ARF) — that measures how much a public or pre-IPO company's valuation is being bent by the AI narrative.** "Bent" here can mean valuation multiples 10× a normal sector baseline, or the market tolerating negative / low current earnings on the bet that growth will eventually convert into high ROE.

The factor must satisfy two simultaneous use cases:

1. **Stock-picking:** Rank an investable universe so that high-ARF names are concrete candidates worth deeper diligence.
2. **Bubble thermometer:** When applied cross-sectionally and over time, the *distribution* of ARF should make it obvious in hindsight how stretched the market was — i.e., counting the names sitting at extreme ARF levels should serve as a regime indicator analogous to the count of S&P names trading at P/S > 10 in early 2000.

The reference framework is Jensen Huang's "5-layer cake" model of AI infrastructure (Energy → Chips → Infrastructure → Models → Applications/Physical AI). The factor must follow **two parallel supply-chain narratives — US and China** — and produce rankings separately for each leg before any pooled view, because their accounting, sanctions exposure, and policy-premium dynamics are not directly comparable.

The two reference documents in the project (`The_Global_Architecture_of_Artificial_Intelligence...md` and `AI光通信_护城河与估值逻辑.md`) define the seed universe and the narrative.

## 2. Goals and Non-Goals

### Goals (v1)

- Produce **one number per stock** (range 0–100) that is interpretable, stable week-over-week, and comparable within a universe leg (US or China).
- Cover the seed universe of ~30 named anchor companies across US and China legs of the 5-layer cake, plus a handful of pre-IPO names handled as a separate sub-universe.
- Use **only free / publicly accessible data sources** for the POC. No paid feeds.
- Output a CSV/Parquet table plus a simple ranked HTML or Markdown report. No web app required for v1.
- Make the calculation **fully reproducible** from raw inputs to final score with a single command.
- Cache fundamentals locally so the system can recompute the factor over time and chart the bubble-thermometer view.

### Non-Goals (v1)

- No live trading signals, no backtesting framework, no portfolio construction.
- No NLP / LLM-based filing parsing (Stage 3 future work).
- No UI beyond a rendered report file.
- No coverage of names outside the seed universe (expand later).
- No European chokepoint names (ASML, ARM, Siemens Energy, Schneider Electric, etc.) — surface them in v1 outputs but exclude from the primary US/China leg rankings. Treat as a third "Europe chokepoint" reference bucket.

## 3. Users and Use Cases

**Primary user:** Solo investor/researcher (the PRD author).
- Open the weekly ranked report; scan top-decile names in each leg; identify which deserve deeper fundamental work.
- Open the rolling-thermometer chart; check whether the count of "froth-flagged" names is rising, falling, or stable vs. recent history.
- Manually update the pre-IPO sub-universe table when a new private round is announced.

**Secondary (later):** Sharing the output with peers as a discussion artifact. The number must be interpretable without a 30-minute methodology lecture — a single 0–100 score with a decile bucket is the bar.

## 4. Methodology Specification

The ARF is the **geometric mean of two normalized 0–100 sub-scores**:

```
ARF = sqrt(E_score × V_score)
```

Geometric (not arithmetic) so that a near-zero in either sub-score zeros the composite — a name with no AI exposure or no valuation stretch cannot dominate the ranking.

### 4.1 E_score — AI Exposure (0–100)

Four components, weighted, then percentile-ranked within the universe leg.

| Component | Weight | Source / Method |
|---|---|---|
| **Layer in 5-layer cake** | 30% | Manual map (see §5.1). Numeric scale: L5 Apps = 5, L4 Models = 5, L2 Chips = 4, L3 Infra = 3, L1 Energy = 2. Higher scale = more "AI-pure" layer in this cycle. |
| **Pure-play %** | 40% | Disclosed or estimated share of revenue tied to AI workloads. From 10-K segments where available; otherwise sell-side estimate or rule-of-thumb (see §5.2). 0–100% scale. |
| **Supply-chain criticality** | 20% | Proxy = gross margin of the AI segment OR top-3 customer concentration (whichever is higher / more available). Higher GM and higher hyperscaler-customer concentration = more critical. Normalize to 0–100. |
| **Forward AI revenue growth** | 10% | Consensus next-12-month YoY revenue growth from yfinance / 同花顺 scrape. Cap at 200% to avoid Cambricon-style off-tiny-base distortions blowing out the scale. |

Within each universe leg, the four weighted components are summed, z-scored, winsorized at ±3σ, and percentile-ranked to 0–100.

### 4.2 V_score — Valuation Stretch (0–100)

Three orthogonal pressures, equal-weighted (33⅓% each), then a profitability-quality adjustment.

| Component | Free-data formula | Why |
|---|---|---|
| **Reverse-DCF implied growth gap** | Solve Gordon-growth for `g*` given current price, TTM FCF, and `r = WACC = 10%` (US) / `12%` (China). Then `gap = g* − 3yr_revenue_CAGR_consensus`. Higher gap = market paying for more growth than analysts forecast. | Captures "priced for perfection" directly. |
| **PEG-like** | `forward_PE / forward_EPS_CAGR_2yr`. Use 2-year forward EPS CAGR from consensus. Cap at 5.0; floor at 0. | Quick, robust, sector-comparable. |
| **EV/Sales percentile vs own 5-year history** | Macrotrends / stockanalysis scrape for US, AkShare / Eastmoney for China. Output as 0–100 percentile of current EV/S vs the company's own trailing 5-year distribution. | Self-referential richness; flags multiple expansion. |

**Profitability-quality adjustment:** subtract `(ROE − cost_of_equity)` normalized to ±20 points. Names already delivering high ROE (e.g., NVIDIA at 114%) get a credit that reduces V_score (less stretched given fundamentals). Pure narrative names with ROE below cost of equity pay the full stretch penalty.

The three components are equal-weighted and summed, then the adjustment is applied, then z-scored, winsorized at ±3σ, and percentile-ranked to 0–100 within the universe leg.

### 4.3 Combination and Bucketing

```
ARF_raw = sqrt(E_score × V_score)
ARF = percentile_rank(ARF_raw within universe leg) × 100
decile = ceil(ARF / 10)        # D1 = top, D10 = bottom
```

**Froth flag (binary):** True if `ARF in top decile (D1) AND ROE < cost_of_equity AND P/S > 25`. This is the dot-com-style "narrative-only" tag.

### 4.4 Universe Legs

Three separate computations:

1. **US leg** — public US-listed names. ARF percentile is within this leg only.
2. **China leg** — A-share (Shanghai / Shenzhen) + HK-listed + China ADRs. ARF percentile is within this leg only. Compute multiples in local currency (CNY / HKD); convert market cap to USD for cross-leg display only.
3. **Pre-IPO sub-universe** — bucketed (not percentile-ranked). Each name receives a manual qualitative tier ("D1 froth flag" / "high" / "mid") based on last-round post-money valuation vs. last-known ARR. No numeric ARF; flag only.

**Europe chokepoint names** are tracked as a reference bucket but not scored in v1.

### 4.5 Bubble-Thermometer View

For the regime indicator, compute weekly:

- Count of names with ARF ≥ 90 in each leg.
- Count of names with `froth_flag = True` in each leg.
- Median ARF across each leg.

Plot all three series over time (from earliest data available, typically 2022). A rising count of froth-flagged names = the bubble signal.

## 5. Universe and Manual Maps

### 5.1 Seed Universe (~30 names)

**US leg (16 names):**
NVDA, AMD, INTC, MSFT, CRM, EQIX, DLR, ANET, CSCO, NEE, WMB, COHR, LITE, AVGO, MRVL, PLTR.

**China leg (16 names):**
300308.SZ (中际旭创 InnoLight), 300502.SZ (新易盛 Eoptolink), 300394.SZ (天孚通信 TFC), 688498.SH (源杰科技), 002281.SZ (光迅科技 Accelink), 688256.SH (寒武纪 Cambricon), 0981.HK / 688981.SH (SMIC 中芯国际), 000977.SZ (浪潮 Inspur), GDS, VNET, 300750.SZ (CATL 宁德时代), BIDU, BABA, 0700.HK (Tencent), 9868.HK (XPeng), 2513.HK (Zhipu / Knowledge Atlas).

**Pre-IPO sub-universe (manual table, no numeric ARF):**
Anthropic, OpenAI, ByteDance (字节跳动), Moonshot AI (月之暗面), Huawei (华为, also state-aligned).

**Europe chokepoint reference (display only):**
ASML, ARM (Nasdaq-listed but UK-domiciled — treat as Europe reference), Siemens Energy, Schneider Electric, STMicroelectronics, Infineon, SAP, ABB.

### 5.2 Layer Map and Pure-Play Estimates (initial values)

Engineering should implement this as a single editable YAML or JSON config file (`universe.yaml`). Values below are starting points; researcher can edit without code changes.

| Ticker | Leg | Layer | Pure-play % (initial) | Notes |
|---|---|---|---|---|
| NVDA | US | L2 | 90 | Data Center segment dominant |
| AMD | US | L2 | 50 | MI series scaling; non-AI client/embedded still material |
| INTC | US | L2 | 25 | AI relatively small share |
| AVGO | US | L2 | 55 | AI ASICs growing fast; legacy semis half |
| MRVL | US | L2 | 70 | Datacenter optical/custom silicon |
| ARM | Europe-ref | L2 | 40 | IP licensing; AI compute share rising |
| ASML | Europe-ref | L2 | 70 | EUV chokepoint, but tools serve non-AI too |
| MSFT | US | L5 | 35 | Azure AI growing; majority still classical SaaS |
| CRM | US | L5 | 30 | Agentforce push |
| PLTR | US | L5 | 80 | AIP-driven growth narrative |
| EQIX | US | L3 | 30 | AI portion of colo growing |
| DLR | US | L3 | 35 | Hyperscale AI mix higher |
| ANET | US | L3 | 70 | AI back-end ethernet |
| CSCO | US | L3 | 20 | AI a small part of revenue |
| NEE | US | L1 | 25 | Data-center load tailwind |
| WMB | US | L1 | 30 | Gas pipelines feeding DC clusters |
| COHR | US | L3 | 60 | Datacom optics |
| LITE | US | L3 | 80 | AI optics + OCS pure play |
| 300308 | China | L3 | 95 | Pure-play optical modules |
| 300502 | China | L3 | 95 | Pure-play optical modules |
| 300394 | China | L3 | 90 | Optical components for AI clusters |
| 688498 | China | L2 | 90 | Optical chips (laser diodes) |
| 002281 | China | L3 | 60 | Telecom + datacom |
| 688256 | China | L2 | 95 | AI accelerators, national-champion premium |
| 0981 / 688981 | China | L2 | 50 | Foundry; AI part of mix |
| 000977 | China | L3 | 60 | AI servers |
| GDS | China | L3 | 50 | Hyperscale IDC |
| VNET | China | L3 | 40 | IDC |
| 300750 | China | L1 | 20 | BESS into DC power; small share |
| BIDU | China | L5 | 35 | AI cloud + ERNIE |
| BABA | China | L5 | 30 | Cloud Intelligence including AI |
| 0700 | China | L5 | 20 | Hunyuan + WeChat AI |
| 9868 | China | L5 | 60 | Physical AI / autonomous driving |
| 2513 | China | L4 | 95 | Pure-play foundation model |

### 5.3 Pre-IPO Manual Table (snapshot fields)

For each pre-IPO name, record:
- Last-round post-money valuation (USD)
- Last-known revenue or ARR (USD)
- Implied multiple (post-money / ARR)
- Date of last round
- Tier classification (manual: `D1 froth` / `high` / `mid`)

## 6. Data Sources and Implementation

### 6.1 Free Data Stack (POC)

| Source | Use | Coverage | Caveats |
|---|---|---|---|
| **yfinance (Python)** | US tickers, ADRs, HK tickers (`.HK`), some China A (`.SS` / `.SZ`) | Prices, market cap, fwd P/E, P/S, EPS estimates, revenue growth | Unofficial; rate-limited; can break |
| **SEC EDGAR** | US 10-K, 10-Q, 20-F for ADRs | Definitive segment revenue, geographic breakdowns | XBRL parsing required |
| **stockanalysis.com** | US backstop for ratios + 5-year EV/S history | Full statistics pages | Scrape only |
| **AkShare (Python)** | China A-share + HK primary | Full financial statements, ratios, concept tags, 扣非 net profit | Scrapes Eastmoney/Sina; can break when sites redesign |
| **Tushare free tier** | China A-share cross-check | Core fundamentals | Points-limited |
| **HKEX disclosure portal** | HK filings | Definitive PDFs | Manual |
| **Macrotrends** | US 20-year multiple history | EV/S, P/E history | Scrape only |
| **Press / Crunchbase / news** | Pre-IPO valuations | Last-round only | Manual update |

### 6.2 Required Fields per Stock

Engineering must collect and store the following for every name in the universe:

**Identity:** ticker, exchange, name (English + Chinese where applicable), currency, sector, layer assignment, leg (US / China / Europe-ref / Pre-IPO).

**Market data (point-in-time, refreshed weekly):** price, market_cap_local, market_cap_usd, ev_local, ev_usd, shares_outstanding.

**Trailing fundamentals (TTM):** revenue, revenue_yoy_growth, gross_profit, gross_margin, operating_income, net_income (and net_income_excl_nonrecurring for China names — 扣非 net profit), free_cash_flow, total_equity, roe, roic.

**Forward estimates:** forward_pe, eps_2yr_cagr_consensus, revenue_3yr_cagr_consensus, revenue_ntm.

**Valuation ratios:** trailing_pe, forward_pe, ps_ratio, ev_sales, ev_sales_5yr_percentile, peg.

**Computed:** reverse_dcf_implied_growth, implied_growth_gap (= implied − consensus), e_score, v_score, arf, decile, froth_flag.

**Metadata:** as_of_date, data_source_used_per_field, currency, fx_rate_used.

### 6.3 Storage and Pipeline

- **Local cache:** SQLite or DuckDB at `data/arf.db`. One row per ticker per as_of_date snapshot. Engineer chooses; DuckDB preferred for analytical queries on the time series.
- **Config:** `config/universe.yaml` (the table in §5.2) is the source of truth for the seed universe. Editing this file should trigger recomputation on next run.
- **Pipeline command:** `python -m arf.run --as-of 2026-05-28` runs the full pipeline: fetch → compute → snapshot to DB → render report.
- **Idempotency:** Re-running for the same as-of date should overwrite that snapshot only.
- **Failure handling:** A failed fetch for a single ticker should log a warning and produce a partial output, not crash the run. Mark missing fields as `null` in the DB and exclude that name from percentile calculations for that snapshot (but keep the row).

### 6.4 Output Artifacts

Per pipeline run:

1. **`data/snapshots/arf_<as_of_date>.parquet`** — full table, all fields.
2. **`reports/arf_<as_of_date>.md`** — Markdown report:
   - Header: as-of date, leg counts, Shiller CAPE for context (scrape multpl.com).
   - Section per leg (US, China): ranked table with ticker, name, layer, ARF, decile, E_score, V_score, froth_flag, fwd P/E, P/S, revenue growth, ROE.
   - Pre-IPO sub-universe table.
   - Europe chokepoint reference table.
   - Bubble-thermometer summary: count of D1 names, count of froth-flagged names, median ARF per leg, deltas vs. last week.
3. **`reports/thermometer.html`** — Single Plotly chart of the three thermometer series over time. Static HTML, no server.

## 7. Acceptance Criteria

### Functional

- [ ] One command (`python -m arf.run --as-of <date>`) runs the full pipeline end-to-end.
- [ ] All 32+ named anchor companies in §5.1 produce a non-null ARF value for the most recent run, OR a documented reason if data is unavailable.
- [ ] US and China legs each produce a ranked Markdown table with 0–100 ARF, decile, and froth flag.
- [ ] Pre-IPO sub-universe table renders with the five named companies, last-round valuation, implied multiple, and tier.
- [ ] Bubble thermometer chart renders with at least 12 weeks of history once the pipeline has been run for that many weeks (acceptable to backfill from cached snapshots).
- [ ] Re-running the pipeline produces the same output for the same input data (deterministic given the cache).
- [ ] The `universe.yaml` config file is editable without code changes.

### Quality

- [ ] All five companies highlighted as froth flags in the research report (Palantir, Lumentum, Arm, 天孚通信, Cambricon, plus the two private model names) appear in D1 in their respective legs. If any does not, document why (this is the calibration sanity check).
- [ ] NVIDIA appears in D2–D4 (high exposure, but multiples not bubbly given delivered fundamentals), not in D1. This is the second calibration sanity check.
- [ ] Cisco (CSCO), NextEra (NEE), and the China internet majors (BIDU, BABA, 0700) appear in lower deciles (D6–D10). Third sanity check.

### Code

- [ ] Repo layout: `arf/` (package), `config/` (YAML), `data/` (gitignored cache), `reports/` (gitignored outputs), `tests/`, `README.md`.
- [ ] Python ≥ 3.11, type hints throughout, `ruff` clean.
- [ ] Unit tests for the math (z-scoring, percentile ranking, geometric mean, reverse-DCF solver). Aim for >80% line coverage of `arf/scoring.py`.
- [ ] README explains how to install, run, and edit `universe.yaml`.

## 8. Pitfalls and Explicit Decisions

Engineering should be aware of and handle:

1. **Cambricon revenue growth** of +2386% YoY (off a tiny base) will blow out the growth cap if not winsorized. Cap forward growth at 200% in the E_score input.
2. **NVIDIA's market cap (~$5T)** and weight in any pooled ranking would dominate everything. The per-leg percentile ranking already isolates this, but if/when a pooled view is added later, use rank rather than market-cap weighting.
3. **FX losses** are material for Chinese optical-module names (Innolight, Eoptolink reported ~¥2.7B FX losses in 2025). Use 扣非 (after non-recurring items) net profit for Chinese names when computing ROE.
4. **Cambricon and SMIC** have policy-driven multiples. Do not exclude them — flag them with `policy_premium = True` in the output table, but still score them. The flag is informational, not used in the formula.
5. **Pre-IPO valuations are stale** by design. Show date of last round prominently. Anthropic at $900B is "in talks" per CNBC — record as a range when sources disagree, with the source note.
6. **Macrotrends 5-year EV/S history** may not be available for recently-listed names (e.g., Zhipu IPO'd Jan 2026). If <5 years history, use the percentile vs available history with a note.
7. **HK and China A** dual-listings (e.g., SMIC has both 0981.HK and 688981.SH): pick one as primary (prefer A-share for the China leg's valuation; HK for liquidity reference). Document in `universe.yaml`.
8. **yfinance is unofficial.** Wrap all calls with retry + exponential backoff. Don't fail the pipeline on a single bad ticker.

## 9. Out of Scope for v1 (Explicit Future Work)

- LLM-based parsing of 10-K and 年报 to extract AI-mention density (Stage 3).
- Sell-side AI-revenue estimates (requires paid feeds — Wind / Capital IQ / 同花顺 iFinD pro).
- Backtest of the ARF as a return-predictive factor (requires point-in-time data).
- Automated `pure_play_%` updates (v1 uses manual config).
- Web UI / dashboard.
- Additional names beyond the seed universe.
- Sentiment / news-flow overlay.

## 10. Calibration Checks Before Sign-Off

Engineering should print these specific numbers in the v1 run output and verify they are in the right ballpark before declaring v1 done:

- **NVDA:** forward P/E ~21–25, P/S ~21, ROE ~114%, FY26 revenue ~$215.9B (+65% YoY).
- **PLTR:** forward P/E ~82–97, P/S ~67–100, ROE ~33%.
- **LITE:** forward P/E ~117, revenue growth ~+69–90% YoY.
- **天孚通信 (300394):** 2025 net profit guide +40–60% YoY, dynamic P/E ~115.
- **Cambricon (688256):** trailing P/E ~273, market cap ¥800B+.
- **InnoLight (300308):** 2025 revenue +60.25% YoY, net profit +108.78% YoY.

If the numbers from the free-data feeds diverge from the above by more than ~20%, investigate before computing the factor — likely a source-quality issue.

## 11. Definition of Done

v1 is done when:

1. The pipeline runs end-to-end on a single command with no errors for the seed universe.
2. The Markdown report renders with US leg, China leg, pre-IPO table, Europe reference table, and thermometer summary.
3. The three calibration sanity checks in §7 pass.
4. The README explains the methodology in plain language, suitable for a peer to read in 10 minutes.
5. The code is committed, type-checked, and the unit tests pass.

## 12. Open Questions for the Researcher (User)

1. Cost-of-equity assumption: 10% US / 12% China — accept or adjust?
2. Decile labels: keep numeric (D1–D10) or rename for the report (e.g., "AI Crown / Stretched / Quality / Cheap")?
3. Should the Markdown report include short manual commentary per top-decile name, or pure numbers only?
4. Refresh cadence: weekly Mondays, or on-demand only?
5. Where should snapshots be stored long-term — local DB only, or also pushed to a cloud bucket for portability?

## 13. "Ask Gemini" — Qualitative News Layer (Phase 3, added 2026-05-29)

### 13.1 Motivation
The ARF score answers *how much* a stock is bent by the AI narrative. It does not answer *why* the latest week's snapshot changed (earnings beat, geopolitics, customer concentration shift, new product). The webapp now exposes an **"Ask Gemini"** button that augments the quantitative ranking with grounded news from the last 7–14 days, so a user reading the dashboard does not need to context-switch into a search engine.

Hard rule: **the numerical factors stay the source of truth.** Gemini receives the snapshot rows as ground-truth context and is instructed never to override or restate the scores. Its job is to source and summarize the *narrative* sitting behind the numbers.

### 13.2 Surfaces
A single "Ask Gemini" button appears on:
- **Home (overview) page** — covers the top-5 by ARF in each leg (10 stocks total).
- **Thermometer page** — same top-10 set; the summary is framed as a regime/macro story explaining why the bubble counts moved.

The leg pages (US, China) do not get the button in v1 — the top-5 set on Home is the canonical "what should I read about" cohort.

### 13.3 Output
Per-stock expandable cards, one per ticker. Each card contains:
- 1–2 sentence headline summary of recent news.
- 3–5 bullet points of the most material developments (M&A, earnings, regulation, customer wins/losses, supply-chain events).
- A "how this reconciles with the ARF reading" line — e.g. *"ARF D1 + froth-flag is consistent with the recent guidance raise above consensus on tiny base revenue."*
- Citation list (publisher + URL) from Google Search grounding.

### 13.4 Model and grounding
- Model: **Gemini 2.5 Pro** (default; latest production model). No model picker exposed in v1.
- Tool: **Google Search grounding** enabled on every call. Grounding metadata (URIs + titles) is captured and rendered as citations.
- Temperature: low (0.2) — this is summarization, not creative writing.
- Per-call token budget: ~8k input (snapshot rows + methodology + prompt) and ~3k output. One call summarizes all 10 stocks in one pass to keep cost bounded.

### 13.5 Auth and secrets
- API key from Google AI Studio stored in **Secret Manager** as `gemini-api-key`.
- Cloud Run webapp mounts it as env var `GEMINI_API_KEY` via `--update-secrets`.
- Webapp service account has `roles/secretmanager.secretAccessor` on the secret only.
- Button is hidden (or shows a setup hint) when `GEMINI_API_KEY` is absent — feature degrades gracefully in local dev.

### 13.6 Caching
Responses are cached in `st.session_state` keyed by `(as_of_date, sorted ticker tuple)` for the lifetime of the browser session. This avoids burning quota when the user toggles between the Home and Thermometer pages, which share the same cohort. No server-side cache in v1 — keep it simple, refresh on session restart.

### 13.7 Non-goals (v1)
- No per-stock follow-up chat — single-shot summarize call only.
- No fine-grained source filtering (date ranges, language) — Gemini picks.
- No persistent storage of generated summaries in DuckDB. The numerical snapshot remains the only durable record.
- No streaming output — wait + render full response (keeps the cards stable).
- No multi-model fallback. Gemini fails → user sees the error and tries again.

### 13.8 Acceptance criteria
- [ ] Clicking the button on Home returns ≤30 s in normal network conditions.
- [ ] At least 80% of stocks in the cohort get ≥2 citations from credible sources (FT, Reuters, Bloomberg, 财新, 证券时报, company IR).
- [ ] Summary never contradicts the ARF score it was shown. (Spot-checked manually.)
- [ ] Webapp continues to render every other tab cleanly when `GEMINI_API_KEY` is unset — button greys out with a tooltip; no exceptions.
- [ ] Total Gemini cost per click ≤ $0.10 at 2026-05 list prices for Gemini 2.5 Pro with grounding.
