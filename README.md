# ARF — AI Relevance Factor

A weekly stock-scoring tool that ranks 73 AI supply-chain companies (36 US and 37 China) by how much their valuation is driven by the AI narrative. Produces a ranked Markdown report and a Plotly bubble-thermometer chart.

## What it does

Each run computes one score per stock:

```
ARF = sqrt(E_score × V_score)   →  percentile-ranked 0–100 within leg
```

- **E_score** (AI Exposure): how deep is this company in the AI stack?  
- **V_score** (Valuation Stretch): how much is the market pricing in AI-perpetual growth?  
- **ARF**: geometric mean — a stock must score high on *both* to land in D1.  
- **Decile**: D1 (top, most stretched) → D10 (bottom, least stretched).  
- **Froth flag** ★: D1 + ROE < cost-of-equity + P/S > 25 — all three required.

US and China legs are scored separately and never pooled.

## Requirements

- Python 3.11 or later
- Internet access for market data (see [Known Limitations](#known-limitations))

## Installation

```bash
git clone <repo>
cd ARF
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running the pipeline

```bash
python -m arf.run --as-of 2026-05-28
```

Output written to:

| Path | Contents |
|---|---|
| `reports/arf_<date>.md` | Ranked table per leg, bubble thermometer summary |
| `reports/thermometer.html` | Interactive Plotly chart (open in browser) |
| `data/snapshots/arf_<date>.parquet` | Full scored DataFrame |
| `data/arf.db` | DuckDB database, cumulative across runs |

Re-running the same date is idempotent — the database row and parquet file are overwritten.

### Options

```bash
python -m arf.run --as-of 2026-05-28 \
    --data-dir   data/     \   # where to write arf.db and parquet
    --report-dir reports/  \   # where to write .md and .html
    --universe   config/universe.yaml
```

## Understanding the output

### Calibration targets (May 2026 reference)

| Ticker | Expected | Rationale |
|---|---|---|
| PLTR | D1–D2 | P/S ~60, high AI exposure |
| LITE / MRVL | D1 | Very low FCF yield, high AI narrative |
| NVDA | D3–D7 | High exposure but strong FCF and 100%+ ROE keep V_score moderate |
| CSCO | D7–D10 | Low AI exposure, high FCF, mature |
| NEE / WMB | D8–D10 | Minimal AI revenue |

The froth flag fires only when *all three* conditions are met: D1 + ROE < WACC + P/S > 25. A stock with high ROE (e.g., NVDA at 114%) will not be froth-flagged even at D1.

### Reading the Markdown report

```
## US Leg
Ticker | Name | Layer | ARF | D | E | V | Froth | Fwd P/E | P/S | Rev YoY | ROE
...
PLTR   | Palantir | L5 | 85.7 | 2 | 100.0 | 42.9 | False | 63.9 | 60.8 | 68.0% | 32.6%
```

- **D**: decile 1–10 (1 = most AI-narrative-stretched)
- **E / V**: sub-scores, 0–100
- **Froth**: `**True** ★` when froth flag fires

## Editing the universe

All configuration is in `config/universe.yaml`. Changes take effect on the next run — no code changes needed.

### Changing a pure-play estimate

```yaml
- ticker: MSFT
  pure_play_pct: 40    # was 35 — raise if Azure AI revenue share grows
```

### Adding a new stock

```yaml
- ticker: ARM
  name: Arm Holdings
  leg: US
  layer: L2
  pure_play_pct: 85
  primary_exchange: NASDAQ
  policy_premium: false
  notes: "CPU IP licensor; near-100% AI-linked demand now"
```

Valid `layer` values: `L1` (Energy) · `L2` (Chips) · `L3` (Infra) · `L4` (Models) · `L5` (Apps)  
Valid `leg` values: `US` · `China` · `Europe-ref` · `Pre-IPO`

`Europe-ref` and `Pre-IPO` entries are displayed in the report but not scored (no ARF computed).

### Removing a stock

Delete the corresponding block from `universe.yaml`. Past snapshots in `data/arf.db` are unaffected.

## Running tests

```bash
# Unit tests (no network required, ~2 s)
pytest tests/test_config.py tests/test_scoring.py tests/test_db.py tests/test_reporting.py

# Integration tests — hit real yfinance / AkShare APIs (~5 min, requires internet)
pytest tests/integration/ -m integration -v

# Lint
ruff check arf/ tests/
```

## Known Limitations

### China A-share data (partial)

AkShare (the primary source for SSE/SZSE-listed stocks) connects to EastMoney servers, which are geo-restricted and require either running from mainland China or routing through a proxy.

**Affected tickers**: all `.SH` and `.SZ` suffixed tickers (e.g., `688256.SH`, `300308.SZ`).  
**Working**: HK-listed (`.HK`) and US ADR names (BIDU, BABA, GDS, VNET) via yfinance.

When AkShare fails, the ticker appears in the report with no ARF score.

### EV/Sales 5-year percentile (missing)

The V_score C3 component (EV/Sales relative to its own 5-year history) requires historical EV/Sales data. The stockanalysis.com scrape is blocked by Cloudflare. When C3 is unavailable, V_score falls back to the average of the two remaining components (reverse-DCF g* and PEG ratio).

### Some US stocks score null (INTC, COHR)

Stocks with negative free cash flow return `None` from the reverse-DCF (C1 undefined), and if `eps_2yr_cagr` is also unavailable from yfinance, all three V_score components become NaN → null ARF. These stocks appear at the bottom of the report with no decile.

## Scoring formula reference

```
E_score = percentile_rank(
    0.30 × layer_score          # L5=100, L4=100, L2=80, L3=60, L1=40
  + 0.40 × pure_play_pct        # 0–100, from universe.yaml
  + 0.20 × gross_margin × 100   # supply-chain criticality proxy
  + 0.10 × min(rev_growth, 2.0) × 50  # forward growth, capped 200%
)

V_score = percentile_rank(
    mean(
        percentile_rank(g*)          # C1: reverse-DCF implied perpetual growth
        percentile_rank(PEG)         # C2: forward P/E ÷ (eps_2yr_cagr × 100)
        percentile_rank(EV/S pct)    # C3: 5yr EV/Sales percentile (when available)
    )
  − ROE_adjustment                   # −20 to +20 pts based on ROE vs WACC
)

ARF = percentile_rank(sqrt(E_score × V_score))   # within leg
```

WACC: 10% for US, 12% for China.
