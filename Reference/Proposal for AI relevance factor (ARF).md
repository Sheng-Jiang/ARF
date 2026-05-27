# AI Relevance Factor (ARF): A Single-Figure Bubble Thermometer & Stock-Ranking Score for the 5-Layer AI Stack

## TL;DR
- **Build the ARF as a geometric blend of two normalized z-scored sub-scores — an "AI Exposure" sub-score (qualitative-to-quantitative supply-chain weight) times a "Valuation Stretch" sub-score (reverse-DCF implied growth vs. delivered growth, plus PEG/P-S richness, with a profitability-quality penalty)** — so that a single number ranks AI-levered picks *and* lights up red at the tails where stretch dominates exposure. The extreme tails ARE the bubble warning, by design.
- **For a free-data POC, use yfinance + stockanalysis.com + SEC EDGAR for US names; AkShare (free, broad China coverage via Eastmoney/Sina scrapes) plus Tushare free tier for China A/H names; HKEX filings for HK; and last-round VC valuations from press releases for pre-IPO names.** This covers every anchor company in the brief at zero cost, with unofficial-API fragility being the main caveat. Migrate to Wind / Bloomberg / Capital IQ / 同花顺 iFinD pro for licensed feeds when validated.
- **The "good pick AND froth gauge" duality is not a contradiction — it is the design.** Today's ARF cross-section already separates the universe cleanly: NVIDIA (fwd P/E 21–25, ROE 114%, FY26 revenue $215.9B +65% YoY) is *very* AI-relevant but not bubbly on multiples; meanwhile Palantir (P/S 67–100, fwd P/E 82–97), 天孚通信 (dynamic P/E ~115×), Cambricon (TTM P/E 273×), and Lumentum (fwd P/E 117×) sit in dot-com-comparable extreme percentiles. The S&P 500 Shiller CAPE was 40.75 on May 1, 2026 and 42.32 by May 27 (multpl.com, Shiller's Yale series running from 1881) — the only higher reading in 145 years was the precise 44.19 December-1999 dot-com peak.

---

## Key Findings

1. **Methodology consensus.** The academic and practitioner literature converges on three orthogonal building blocks for the kind of factor you want: (a) **reverse-DCF / implied-growth** to back out the growth rate the market is already paying for ("priced for perfection" framing); (b) **justified P/E and justified P/B from residual income** (CFA Level II canonical), where Justified P/B = 1 + (ROE − r)/(r − g) makes the link between *future* ROE and *current* multiple explicit — the exact "tolerance for low current earnings betting on high future ROE" mechanic in your brief; and (c) **Damodaran's narrative-to-numbers framework** that explicitly bridges story-driven valuations (Uber 2013, Anthropic 2026) to quantitative ranges. The dot-com archetype — Cisco March 2000: market cap >$500B on $19B revenue, P/E 201×, EV/Sales 31×, P/FCF 176×, then –88% drawdown despite revenue growing roughly 4× over the next 21 years — is the canonical "narrative correct, multiple wrong" case and the right historical anchor for the bubble side of the factor.

2. **Existing AI thematic scoring (sell-side / index providers).** Morningstar's Global Next Gen AI methodology (used in the iShares filing) explicitly scores companies on a 4-point thematic exposure scale considering "role in the AI subtheme value chain, expected net profit increase from exposure, and the portion of revenue expected to be derived from each AI subtheme over the next five years," then tiers them (Tier 1 = generative-AI score ≥2). Nasdaq CTA AI (tracked by WisdomTree WTAI) uses a tripartite Enablers/Enhancers/Engagers taxonomy that maps cleanly to your 5-layer cake (Enablers ≈ Layers 1–3, Enhancers ≈ Layer 4, Engagers ≈ Layer 5). Themes ETF Trust uses Solactive's "ARTIS" NLP algorithm against filings and news. The common DNA: **a hand-curated thematic ladder + a quantitative exposure weight from revenue mix or expected revenue mix.** Your ARF should adopt this proven template for the exposure side.

3. **Macro backdrop is dot-com-comparable.** The Shiller CAPE was 40.75 on May 1, 2026 (GuruFocus, citing Shiller's Yale series) and 42.32 by May 27, 2026 (multpl.com); only the December 1999 peak of exactly 44.19 was higher in the 145-year series. Invesco's March 2025 Global Market Strategy paper applying Shiller's methodology at CAPE ~37–38 implied annualised capital returns over the next 10 years of around 0.5% (total return ~2.3%); at today's CAPE the implied return is lower still. Whatever single-name ARF reading you get must be read against a market that is, system-wide, near a once-in-a-generation valuation extreme.

4. **The numbers around your anchor universe make the duality concrete** (May 2026 snapshot):
   - **NVIDIA**: mkt cap **$5.2T**, trailing P/E 32–45, fwd P/E **~21–25**, P/S ~21, FY26 revenue **$215.9B (+65% YoY)** per the Q4 FY2026 8-K, gross margin **74%**, ROE **114%**. By Cisco-2000 standards, NVDA's *multiples* are not bubbly — but its absolute size and concentration risk are.
   - **Palantir (PLTR)**: trailing P/E **~146–217**, fwd P/E **~82–97**, **P/S ~67–100**, ROE 33%, FCF $2.7B on $5.2B revenue. The cleanest US AI app-layer narrative-priced name.
   - **Lumentum (LITE)**: mkt cap **$62.24B**, fwd P/E **117**, Q3 FY26 revenue **+90% YoY to $808M**, backlog >$400M in optical-circuit-switches.
   - **Coherent (COHR)**: Q3 FY26 revenue **$1.81B (+21% YoY; +27% pro-forma)**, GAAP gross margin 37.7%, non-GAAP EPS $1.41.
   - **AMD**: P/E TTM 168, fwd P/E **58–68**, P/S 22, gross margin 53%; recent revenue growth ~+35% YoY.
   - **Broadcom (AVGO)**: mkt cap **$1.96T**, fwd P/E **31–37**, P/S 28, gross margin 77%.
   - **Marvell (MRVL)**: fwd P/E 47–51, P/S ~21, Q3 FY26 revenue growth **+45% YoY**.
   - **Arm Holdings (ARM)**: fwd P/E **141–146**, P/S ~70, Q2 FY26 revenue $1.14B (+35% YoY), gross margin 97%.
   - **ASML**: fwd P/E 41–45, P/S 16, revenue €32.67B (~+31% YoY), gross margin 53%.
   - **Equinix / Digital Realty**: fwd P/E ~61 / 98; FY26 revenue guides $10.14–10.24B / >$6.5B (+10–14% YoY).
   - **Arista (ANET)**: fwd P/E **40.7**, P/S 22, Q1 26 revenue $2.71B (+30.6% YoY), gross margin 64%.
   - **Cisco (CSCO)**: fwd P/E **18**, P/S 5, FY26 guide $62.8–63.0B (+6–7%) — the "former bubble king" now trades at deeply normal multiples.
   - **NextEra (NEE)** / **Williams (WMB)**: fwd P/E **24 / 33**, both Layer-1 names trading much closer to utility multiples despite the AI-power narrative.
   - **China line — InnoLight 中际旭创 (300308.SZ)**: 2025 revenue **¥38.24B (+60.25% YoY)** and net profit **¥10.797B (+108.78% YoY)** per the company's 2025 annual report (Futunn, May 2026); trailing P/E ~62.5, FY26E P/E 28–30× on consensus.
   - **天孚通信 TFC (300394.SZ)**: 2025 net profit guided **+40–60% YoY to ¥18.81–21.5B**; dynamic P/E ~115×; sell-side models show FY25/26/27 P/E of 57×/39×/31× — analyst commentary explicitly says "PEG significantly >2, no margin of safety."
   - **新易盛 Eoptolink (300502.SZ)**: 2025 revenue **+220–283% YoY** to ~¥22.5B; 2025 net profit guidance **¥9.4–9.9B (+231–249% YoY)**; net margin 33–38%.
   - **Cambricon 寒武纪 (688256.SH)**: market cap **¥807B+**, trailing P/E **~273**, FY25 H1 revenue **+4348% YoY** (off a tiny base), gross margin 55%, but TTM net margin still modest because R&D dominates. Pure narrative + national-champion-premium name.
   - **SMIC**: FY2025 revenue **$9.33B (+16.2%)**, Q1 2026 $2.5B (+0.7% sequential), gross margin 20.1% — strategic-importance name with policy-supported multiples.
   - **CATL (300750.SZ)**: ~$283B market cap, trailing P/E ~25 — Layer-1-adjacent (grid-scale storage).
   - **GDS** (~$7–8B), **VNET** (~$2.5B, +20% revenue YoY) — China hyperscale-IDC peers to EQIX/DLR but at much lower multiples (VNET P/S ~1.8).
   - **Baidu / Alibaba / Tencent**: fwd P/E ~21 / ~22 / ~12.6, all materially cheaper than US peers despite real AI revenue (Baidu's "AI-powered business" crossed 50% of Baidu Core in Q1 2026; Alibaba Cloud Intelligence grew ~40% YoY, with AI products ~30% of external cloud revenue).
   - **Pre-IPO**: **Anthropic** in talks at **$900B** valuation at ~$45B annualized run-rate (~20× ARR; CNBC confirms it generated "roughly $10 billion in revenue last year" — i.e., 2025 — vs. >$30B annualized by April 2026 and a $1B-ish run-rate at end-2024); **OpenAI** $852B (March 2026 round, S-1 filed confidentially May 22, 2026). **Zhipu / Knowledge Atlas (2513.HK)** IPO'd Jan 8, 2026 at HK$57B / **~$7.1B**, raised $558M, H1 2025 net loss **¥2.36B** on R&D 8× revenue — a pure narrative-priced public-market AI model name.

5. **Free data sources that realistically cover the universe.** For a free POC:
   - **US equities + ADRs**: `yfinance` (Python; free; rate-limited and unofficial) + `stockanalysis.com` scraping + **SEC EDGAR** (10-K/Q, definitive) + FMP free tier (500MB/30-day trailing bandwidth — enough for ~50 names refreshed weekly).
   - **China A-shares (Shanghai + Shenzhen)**: **AkShare** is the right primary (free, scrapes Eastmoney 东方财富, Sina Finance 新浪财经, 金十数据 — covers prices, valuation ratios, full financial statements, industry/concept tags); **Tushare** free tier is points-based and increasingly limited but useful as a cross-check; **Baostock** is an additional free fallback for deeper history.
   - **Hong Kong-listed**: AkShare and yfinance both cover HKEX tickers (`xxxx.HK`); HKEX filings via the exchange's official disclosure portal are free PDFs.
   - **Pre-IPO**: latest funding round and last-round valuation from press releases (CNBC, Bloomberg, TechCrunch, Caixin); secondary-market implied valuations (Forge Global, Hiive, Caplight) when reported. Don't try to be precise on private names — bucket them.
   - **Analyst forward estimates** are the big gap on free tier. yfinance exposes consensus EPS and revenue forecasts that are usable for a POC; Futu and 同花顺 expose sell-side forecasts in Chinese for A-shares (scrapeable). Plan to layer in Capital IQ / FactSet later.

6. **Currency, accounting, sanctions premium, state subsidies.** Three structural differences require *separate* sub-rankings on the US and China legs before any merged universe ranking:
   - **Accounting**: A-share filings use CAS (largely converged with IFRS, but R&D capitalization, government grants, and "non-recurring P&L" classifications differ materially from US GAAP). Most A-share research reports use "扣非" (after non-recurring items) net profit — the ARF should standardize on this for Chinese names.
   - **Currency**: report market caps in USD using same-day FX (CNY ~7.20, HKD ~7.78), but compute valuation multiples in the *local* reporting currency to avoid FX noise (Innolight recorded ~¥2.7B in FX losses in 2025 from USD weakness on its North-America revenue).
   - **Sanctions / national-champion premium**: Cambricon's P/E of 273 and SMIC's chronic policy-supported valuation are not "market-driven" in the Western sense. The factor should either (a) flag these names with a binary "policy premium" indicator that shifts where in the distribution the score is read, or (b) compare them only against other Chinese-listed peers.

---

## Details

### 1. Recommended ARF Construction (Simple v1)

The single figure should be the **geometric mean** of two normalized sub-scores (geometric, not arithmetic, so a zero in either sub-score zeros the composite — a name with no AI exposure or no valuation stretch cannot dominate):

> **ARF = √(E_score × V_score)**

Each sub-score is mapped to a 0–100 scale via cross-sectional percentile within the defined universe (separately for US and China legs, then optionally pooled).

**E_score — AI Exposure (qualitative-to-quantitative).** A 4-point scale per the Morningstar/iShares template, refined with a Layer weight and Pure-play weight:

| Component | Weight | Source |
|---|---|---|
| Layer in 5-layer cake (Layer 5 Apps ≥ Layer 4 Models ≥ Layer 2 Chips ≥ Layer 3 Infra ≥ Layer 1 Energy) | 30% | Manual map |
| Pure-play %: disclosed or estimated share of revenue tied to AI workloads | 40% | 10-K segments, earnings calls, sell-side estimates |
| Supply-chain criticality (proxy: gross margin in the AI segment, hyperscaler customer concentration) | 20% | Filings |
| Forward AI revenue growth (next-12-month consensus YoY) | 10% | yfinance / 同花顺 / scrape |

The layer weights reflect the empirical truth from this cycle: **P/S has scaled most aggressively at the Application layer (PLTR P/S 67–100) and at the Model layer (Anthropic ~20× annualized revenue, Zhipu raised at very high multiples on tiny revenue), and at very pure-play picks-and-shovels names** (InnoLight, Eoptolink, Lumentum, TFC). Deeper-infrastructure names (NEE fwd P/E 24, CSCO fwd P/E 18) remain at "normal" utility/networking multiples.

**V_score — Valuation Stretch.** Three orthogonal pressures, equal-weighted:

| Component | Free-data formula | Why |
|---|---|---|
| **Reverse-DCF implied growth − consensus growth** | Solve the Gordon-growth equation for g* given current price, FCF, and WACC=10% (US) / 12% (China); subtract the 3-year consensus revenue CAGR | Captures "priced for perfection" gap directly |
| **Forward P/E ÷ forward EPS growth (PEG-like)** | yfinance `forwardPE` ÷ consensus 2-yr EPS CAGR | Quick, robust, comparable across sectors |
| **EV/Sales percentile vs own 5-year history** | Macrotrends or stockanalysis.com | Self-referential richness; picks up multiple expansion |

Then **subtract a profitability-quality term** that captures the brief's "tolerance for negative or low earnings betting on future high ROE": (current ROE − cost of equity), normalized. A name with ROE 114% (NVDA) gets a *credit*; a name with ROE −20% gets a *penalty*. This is the residual-income justified-P/B logic: companies already *delivering* the high-ROE promise get a lower V_score (less stretched given fundamentals); pure narrative names pay the full stretch penalty.

**Combining.** Z-score each component within the universe, winsorize at ±3σ, percentile-rank to 0–100, then ARF = √(E × V). Display also as a deciled bucket (D1 = "deep AI froth", D10 = "AI-relevant, fundamentals-supported"). For the bubble-thermometer use case, **publish the cross-sectional top-decile cutoff value and how many names sit above it** — when that count balloons, the regime is froth-like, analogous to how the count of S&P names trading at P/S > 10 ballooned into 2000.

### 2. Why the Dual Use Is Not in Tension

A high ARF means the market is paying a stretched price for strong AI exposure. **In a normal regime**, that combination is your pick-list. **In a froth regime**, the same number — applied across the universe — shows you the *count* and *magnitude* of names whose stretched prices are no longer compensated by exposure-quality. The pick-side use is name-by-name in the top decile; the bubble-side use is the *distribution* across the universe. They are the same number used at different cross-sectional moments. Practical UI:

- **D1 (top 10%) — "AI Crown"**: highest ARF — buy candidates *if* you believe the regime continues.
- **D1 with ROE < cost of equity and revenue < $1B**: explicit froth flag.
- **Universe median ARF crosses a rolling threshold**: regime-level bubble alarm.

### 3. The Anchor Table (Free-Data POC, May 2026)

| Ticker | Layer | Mkt Cap | Fwd P/E | P/S | Rev growth YoY | Gross Margin | ROE | Likely ARF Decile |
|---|---|---|---|---|---|---|---|---|
| NVDA | L2 Chips | $5.2T | 21–25 | 21 | +65% | 74% | 114% | High-mid (extreme exposure, multiples NOT bubbly relative to delivery) |
| PLTR | L5 Apps | $326B | 82–97 | 67 | +68% | 84% | 33% | **D1 — Bubble flag** |
| LITE | L3 Infra | $62B | 117 | high | +69% | n/a | n/a | **D1 — Bubble flag** |
| COHR | L3 Infra | n/a | high | n/a | +21% | 38% | n/a | High |
| AMD | L2 Chips | $822B | 58–68 | 22 | +35% | 53% | mid | High |
| AVGO | L2/L3 | $1.96T | 31–37 | 28 | +24% | 77% | high | Top quartile |
| MRVL | L2 Chips | $156–182B | 47–51 | 21 | +45% | 51% | n/a | High |
| ARM | L2 IP | $326B | 141–146 | ~70 | +35% | 97% | n/a | **D1 — Bubble flag** |
| ASML | L2 Equipment | $629B | 41–45 | 16 | +31% | 53% | high | Mid-high |
| EQIX | L3 Infra | ~$95B | ~61 | high | +11% | 49% | mid | Mid |
| DLR | L3 Infra | ~$68B | 98 | 10.7 | +14% | n/a | low | Mid-high |
| ANET | L3 Infra | ~$200B | 40.7 | 22 | +31% | 64% | high | High |
| CSCO | L3 Infra | $312B | 18 | 5 | +6% | 65% | mid | Low |
| NEE | L1 Energy | ~$201B | 24 | 7 | +12% | 61% | mid | Low |
| WMB | L1 Energy | ~$96B | 33 | 8 | mid-teens | n/a | n/a | Low |
| 300308 InnoLight | L3/L2 China | n/a | 28–30 fwd | n/a | +60% rev / +109% NP | mid | high | Top quartile (de-rating as earnings catch up) |
| 300502 Eoptolink | L3 China | ~$80B | 19–24 fwd | n/a | +220–283% rev / +231–249% NP | mid-40s% | high | High |
| 300394 TFC | L3 China | ~$240B+ | 39–48 fwd (115 dynamic) | n/a | +50–75% | 52% | high | **D1 — Bubble flag** |
| 688256 Cambricon | L2 China | ~$112B | TTM 273; fwd 197 | very high | +2386% (low base) | 55% | low | **D1 — Bubble + national-champion flag** |
| 688981 SMIC | L2 China | n/a | n/a | n/a | +16% | 20% | low | Mid (policy-supported) |
| GDS | L3 China | ~$7–8B | high | 4.2 | mid-teens | n/a | n/a | Mid |
| VNET | L3 China | ~$2.5B | n/m | 1.8 | +20% | n/a | n/a | Mid |
| BIDU | L4/L5 China | ~$43B | 21 | 2.3 | +AI cloud strong | n/a | n/a | Low |
| BABA | L4/L5 China | ~$320B | 22 | 2.4 | +cloud +40% AI | 41% | mid | Low |
| TCEHY | L4/L5 China | ~$507B | 12.6 | 4.7 | +mid teens | high | high | Low |
| 300750 CATL | L1 China | ~$283B | n/a | n/a | n/a | n/a | high | Low |
| Anthropic (private) | L4 Models | $900B (talks) | n/a | ~20× ARR | revenue ~3× YoY | n/a | negative | **D1 — Bubble flag** |
| OpenAI (private) | L4 Models | $852B (Mar 26) | n/a | high | high | n/a | negative | **D1 — Bubble flag** |
| 2513 Zhipu | L4 Models China | $7.1B IPO | n/a | very high | n/a | net loss ¥2.36B H1 | negative | **D1 — Bubble flag** |

### 4. Free Data Source Recommendation Matrix

| Source | US | China A | HK | Pre-IPO | Fundamentals | Forecasts | API | Caveats |
|---|---|---|---|---|---|---|---|---|
| **yfinance** | ✓ | partial (xxx.SS / xxx.SZ) | ✓ (.HK) | ✗ | rev, margins, P/E, fwd P/E, EPS est. | yes (consensus) | unofficial Python | Rate-limited; Yahoo no longer officially supports |
| **stockanalysis.com** | ✓ | partial | partial | ✗ | full statistics, valuations | partial | scrape only | High data quality, no API |
| **FMP free** | ✓ | limited | limited | ✗ | full | yes | REST | 500MB/30-day bandwidth |
| **Alpha Vantage free** | ✓ | weak | weak | ✗ | OK | partial | REST | 25 calls/day |
| **SEC EDGAR** | ✓ | F-filer subset | ADRs only | ✗ | filings primary | ✗ | XBRL | Definitive, free, no rate limit |
| **AkShare** | partial | ✓✓✓ | ✓ | ✗ | full Chinese statements, ratios, concept tags | partial | Python | Web-scrapes Eastmoney/Sina — breaks when sites change |
| **Tushare free** | ✗ | ✓ | partial | ✗ | core | limited | Python | Points-based; better paid |
| **Eastmoney 东方财富** | ✗ | ✓ | ✓ | ✗ | full | ✓ | scrape | De-facto default for retail Chinese fundamentals |
| **同花顺 iFinD basic** | ✗ | ✓ | ✓ | ✗ | full | ✓ | scrape/paid | Best Chinese forecast feed |
| **Sina Finance** | ✗ | ✓ | ✓ | ✗ | full | partial | scrape | Older but reliable |
| **HKEX** | ✗ | ✗ | ✓ | ✗ | filings | ✗ | PDF | Definitive |
| **Macrotrends** | ✓ | ✗ | ✗ | ✗ | 20-yr P/E, P/S history | ✗ | scrape | Time-series gold |
| **Finviz** | ✓ | ✗ | ✗ | ✗ | snapshot screen | ✗ | scrape/paid | OK for screening |
| **SimplyWall.st** | ✓ | partial | ✓ | ✗ | nice viz | yes | paid | Limited free |
| **Press / Crunchbase / TechCrunch** | n/a | n/a | n/a | ✓ | last round only | ✗ | manual | Only viable free option for OpenAI/Anthropic/ByteDance/Moonshot |

**POC stack recommendation**: yfinance + SEC EDGAR + AkShare + manual private-round table. Cache locally (SQLite or DuckDB) on a weekly cron — rate limits become irrelevant if you only refresh weekly. Budget 1–2 days to write robust scrapers with retry/backoff for stockanalysis.com and Eastmoney as fallbacks. Migrate to Wind / Bloomberg / Capital IQ / 同花顺 iFinD pro once the methodology is validated.

### 5. Pitfalls and How to Handle Them

- **"AI revenue" is not consistently disclosed.** NVIDIA breaks out Data Center; Broadcom blends AI ASIC into Semiconductor Solutions; most Chinese names disclose by product (光模块, 服务器) not by end-use. **Solution**: use sell-side estimates of "AI revenue share" where available; otherwise apply a layer-and-customer-concentration heuristic (if >50% of revenue goes to hyperscalers and Nvidia, treat as >80% AI-attributable).
- **Pre-IPO names**: use last-round post-money valuation as the "market cap"; use disclosed ARR or last-known revenue as denominator. **Bucket** them as a separate sub-universe; do not pretend the V_score is comparable to public-market percentiles.
- **Survivorship and look-ahead in back-tests**: when checking the ARF as a *bubble* indicator historically, you must use point-in-time financials and point-in-time index constituents — Cisco-2000-like exercises systematically over-state predictive power if you back-fit using current survivor lists.
- **China policy-driven multiples**: Cambricon's 273× P/E and SMIC's structurally subsidized capex make these names "uninvestable" by Western valuation discipline but tradeable by flow/policy logic. Flag them with a binary "national-champion / sanctions-resilience premium" indicator and compare them only against other A-share peers.
- **US dollar dominance + AI capex circularity**: NVDA → OAI → MSFT → NVDA. The Anthropic ~$50B raise (~$45B run-rate revenue at $900B post-money), paired with Anthropic committing 5 GW of compute to Google/Broadcom, is the vivid 2026 example. The factor cannot directly model this, but the bubble thermometer should account for it qualitatively when ARF goes extreme: vendor-financed demand inflates the exposure side without delivering ROE.
- **Currency mismatches**: Innolight and Eoptolink recorded ¥2.7B-class FX losses in 2025 from USD weakness on their North-America revenue. Compute multiples in CNY/HKD locally; convert to USD only at the market-cap layer for cross-comparison.

### 6. Bubble-Thermometer Threshold Calibration

Anchor the "froth tier" against the dot-com benchmark using known datapoints:
- **Cisco March 2000**: P/E 201, EV/Sales 31, P/FCF 176. Set EV/Sales >25 + fwd P/E >80 + ROE < cost of equity = automatic D1.
- **Sun Microsystems 2000** (Scott McNealy's "what were you thinking" 10× revenue speech): P/S >10 is the historical "you've lost your mind" threshold. Any pure-play AI name above P/S 30 should trip a flag.
- **Today's "above Cisco-2000" candidates in the universe**: Palantir (P/S 67–100), Arm (P/S ~70), 天孚通信 (dynamic P/E 115), Cambricon (P/E 273), Lumentum (fwd P/E 117). These names already exceed Cisco-2000 multiples on their respective dominant metric.
- **Today's "still below Cisco-2000" giants**: NVIDIA (P/E 32, EV/Sales 21, ROE 114%), Broadcom (fwd P/E 31), CSCO itself today (fwd P/E 18). The decisive difference vs. 2000 is that NVDA actually delivers the cash flow — Cisco didn't have profit growth anywhere near its multiple.

---

## Recommendations

**Stage 1 (Week 1–2, free POC).** Implement E_score manually (one-row-per-anchor-company spreadsheet with layer weight and pure-play estimate). Implement V_score from yfinance/AkShare with the three components. Compute geometric ARF. Output a ranked list across US + China legs separately. Threshold: top decile = candidate; top decile + ROE < r and P/S > 25 = froth flag.

**Stage 2 (Week 3–4).** Add a rolling time series — compute ARF weekly back to 2022 for the anchor universe. Plot the count of names in the "froth flag" bucket over time. **This curve is your bubble thermometer.** Compare its current level to Q3 2024 (pre-DeepSeek), Q1 2025 (Trump-tariff dip), and today; rising count = froth accumulating.

**Stage 3 (later, with paid data).** Replace yfinance with Capital IQ or FactSet; replace AkShare with Wind or 同花顺 iFinD pro; layer in sell-side AI-revenue estimates as the E_score input rather than your manual map. Add an LLM-based filings parser to extract "AI" mention density from 10-Ks / 年报 as a Layer 5 narrative-intensity proxy (Damodaran-style numbers-to-story bridge).

**Stage 4 (research).** Decompose the V_score residual (delivered ROE vs implied ROE from reverse residual-income) name-by-name to identify the "Cisco of 2026" — the company where the gap between justified-P/B and observed P/B is widest. As of May 2026, the screen flags TFC, Cambricon, Lumentum, Palantir, Arm, and the two private model-layer names.

**Triggers that would change these recommendations:**
- If the Shiller CAPE drops below 30, lower the V_score weight and rely more on E_score (less froth, more thematic conviction).
- If a major model-layer name (OpenAI / Anthropic / ByteDance) IPOs and starts trading publicly, fold its post-IPO valuation into the public-leg ranking and re-calibrate the bubble threshold accordingly.
- If sanctions on China A-share AI names tighten further (Cambricon export ban, additional SMIC restrictions), increase the national-champion-premium weight rather than scoring these names against US peers.

---

## Caveats

- **The factor is descriptive, not predictive.** Cisco's multiple was "obviously wrong" in March 2000 *with hindsight*, but the stock kept going up for months after every traditional valuation alarm. ARF in extreme territory tells you *price-implied expectations* are extreme; it does not tell you when the regime will change. Use it for *position-sizing discipline*, not timing.
- **Free-data limitations are real.** yfinance breaks without warning; AkShare scrapes can fail when Eastmoney redesigns its pages; FMP's 500MB/30-day bandwidth limit will bite at scale. Cache aggressively and write defensive code.
- **Chinese and Western accounting do not perfectly compare.** Government grants, R&D capitalization, and consolidation differences between CAS and GAAP can swing reported ROE meaningfully. Use 扣非 (after-non-recurring-items) net profit for Chinese names.
- **Pre-IPO valuations are stale and structural.** Last-round post-money is a snapshot with preferences, ratchets, and information asymmetry baked in. The $900B Anthropic talks valuation is what investors *say* they would pay; secondary-market implied valuations (reportedly trending toward $1T for Anthropic in May 2026) are closer to a market-clearing price but still illiquid and skewed toward optimistic shareholders.
- **The "AI Relevance" concept itself will erode.** Within 2–3 years, "AI exposure" will be as diffuse as "internet exposure" became by 2005 — every company will claim it. Plan for the E_score component to become less discriminating over time and for the V_score component to bear more of the weight.
- **Source-quality note on macro figures.** The Shiller CAPE figures cited come from Robert Shiller's Yale data series via multpl.com and GuruFocus. Some news aggregators (e.g., Jinse Finance) reproduce these numbers second-hand; always anchor to the primary Shiller series. Forward-return implications from CAPE (e.g., Invesco's ~0.5% annualised capital return projection at CAPE 37–38) are model-based projections, not facts.