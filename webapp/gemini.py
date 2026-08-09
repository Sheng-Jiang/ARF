"""Ask Gemini — qualitative news layer on top of ARF scores.

One grounded Gemini 2.5 Pro call per stock, fanned out in parallel. The model
is given the snapshot row as ground truth and asked to summarise recent news,
with language-aware search hints (Chinese ticker → Chinese-language search).

The earlier single-call-for-N-stocks approach made the model lazy — it would
search only for stock #1 and fabricate citations for the rest. Per-stock calls
force grounding for every name in the cohort.
"""
from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

log = logging.getLogger(__name__)

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
MAX_PARALLEL = int(os.getenv("GEMINI_MAX_PARALLEL", "6"))


def is_enabled() -> bool:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return bool(key) and not key.startswith("PLACEHOLDER")


@dataclass
class Citation:
    title: str
    uri: str


@dataclass
class StockSummary:
    ticker: str
    name: str
    headline: str
    bullets: list[str] = field(default_factory=list)
    reconcile: str = ""
    citations: list[Citation] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    domain_mentions: list[str] = field(default_factory=list)


@dataclass
class GeminiReport:
    as_of: date
    cohort: list[str]
    stocks: list[StockSummary]
    citations: list[Citation]  # union of all per-stock citations
    raw_text: str
    model: str


def _factor_line(row: pd.Series) -> str:
    """One-line dump of a stock's ARF context for the prompt."""

    def f(k: str, fmt: str = "{:.1f}") -> str:
        v = row.get(k)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "?"
        try:
            return fmt.format(float(v))
        except (TypeError, ValueError):
            return str(v)

    froth = "★FROTH" if bool(row.get("froth_flag")) else ""
    decile = int(row["decile"]) if pd.notna(row.get("decile")) else "?"
    return (
        f"leg={row.get('leg')} layer={row.get('layer')} decile=D{decile} "
        f"ARF={f('arf')} E={f('e_score')} V={f('v_score')} "
        f"fwd_PE={f('forward_pe')} P/S={f('ps_ratio')} ROE={f('roe', '{:.1%}')} "
        f"rev_yoy={f('revenue_yoy_growth', '{:.1%}')} {froth}".strip()
    )


def _split_name(full_name: str) -> tuple[str, str]:
    """Split a 'Chinese English' name field into (chinese, english) halves.

    universe.yaml stores names like '中际旭创 InnoLight' or just 'NVIDIA'.
    Returns ('', english) if no Chinese characters found.
    """
    if not full_name:
        return "", ""
    # Anything in CJK Unified Ideographs range
    cjk = re.findall(r"[一-鿿]+", full_name)
    chinese = " ".join(cjk).strip()
    english = re.sub(r"[一-鿿]+", "", full_name).strip()
    return chinese, english


_SYSTEM_PROMPT = """You are a sell-side analyst writing a brief news-and-narrative
companion to a quantitative AI-relevance factor (ARF) ranking. The user has
already computed the factor — DO NOT restate or re-derive the scores. Your job is
to source recent (last 30 days) news that explains the narrative for ONE specific
stock and reconcile it with the factor reading.

Hard rules:
1. ALWAYS use Google Search. Fire at least 3 distinct queries before deciding
   whether news exists. Vary queries: include the company's English name,
   Chinese name, ticker, and the most material recent topics
   (earnings, products, customers, M&A, regulation).
2. EVERY fact in your bullets MUST come from a search result and end with the
   source domain in parentheses, e.g. "(reuters.com)" or "(caixin.com)". Do not
   include any unsourced claims.
3. If you genuinely cannot find news after exhausting reasonable queries, write
   exactly one bullet: "- No material news in the last 30 days." Do not pad with
   generic background.

Output format — exactly this, no preamble, no other sections:

### <TICKER>
HEADLINE: <one sentence, ≤25 words, plain English>
BULLETS:
- <fact (domain.com)>
- <fact (domain.com)>
- <fact (domain.com)>
RECONCILE: <one sentence linking the news to the ARF/E/V/decile shown>
"""


def _build_single_stock_prompt(row: pd.Series, as_of: date) -> str:
    chinese, english = _split_name(str(row.get("name", "") or ""))
    ticker = str(row.get("ticker", ""))
    leg = str(row.get("leg", ""))

    search_hints = [f'"{english}"' if english else None, f'"{ticker}"']
    if chinese:
        search_hints.append(f'"{chinese}"')
        search_hints.append(
            f'For this Chinese {leg}-listed name, search Chinese-language news '
            f'(query in Chinese: 「{chinese}」). Also try:'
            f' site:caixin.com, site:cls.cn, site:21jingji.com, site:stcn.com,'
            f' site:sina.com.cn.'
        )
    else:
        search_hints.append(
            'Prioritise high-credibility English outlets: site:reuters.com, '
            'site:bloomberg.com, site:ft.com, site:wsj.com, site:cnbc.com, '
            'plus the company\'s own investor-relations site.'
        )

    hints_str = "\n".join(f"- {h}" for h in search_hints if h)

    return (
        f"Snapshot date: {as_of.isoformat()}\n"
        f"Stock: {ticker} — {row.get('name', '')}\n"
        f"Factor reading: {_factor_line(row)}\n\n"
        f"Search guidance:\n{hints_str}\n\n"
        f"Now produce the section for {ticker} following the exact output format. "
        f"Search BEFORE writing. Every bullet needs a cited domain. "
        f"If genuinely no news, use the 'No material news' fallback bullet."
    )


_SECTION_RE = re.compile(r"^###\s+([A-Za-z0-9\.\-]+)\s*$", re.MULTILINE)

# Capture "(domain.tld)" or "(sub.domain.tld)" at the end of a bullet, single
# or comma-separated. Handles ".com", ".com.cn", ".cn", ".net", etc.
_DOMAIN_RE = re.compile(
    r"\(([a-z0-9][a-z0-9\-]*(?:\.[a-z0-9][a-z0-9\-]*)+(?:\s*,\s*[a-z0-9][a-z0-9\-]*(?:\.[a-z0-9][a-z0-9\-]*)+)*)\)",
    re.IGNORECASE,
)


def _extract_domain_mentions(bullets: list[str]) -> list[str]:
    """Pull '(domain.com)' tokens out of bullet text, deduped, order-preserved.

    Handles comma-separated forms like '(reuters.com, bloomberg.com)'.
    """
    seen: dict[str, None] = {}
    for line in bullets:
        for match in _DOMAIN_RE.finditer(line):
            for dom in match.group(1).split(","):
                d = dom.strip().lower()
                if "." in d and d not in seen:
                    seen[d] = None
    return list(seen)


def _parse_one_section(text: str, expected_ticker: str, name: str) -> StockSummary:
    """Parse a single per-stock response; expected_ticker is the known truth."""
    match = _SECTION_RE.search(text)
    body = text[match.end():] if match else text
    ticker = match.group(1).strip() if match else expected_ticker

    headline = ""
    reconcile = ""
    bullets: list[str] = []

    hl = re.search(r"HEADLINE:\s*(.+?)(?:\n|$)", body, re.IGNORECASE)
    if hl:
        headline = hl.group(1).strip()
    rc = re.search(r"RECONCILE:\s*(.+?)(?:\n###|\Z)", body, re.IGNORECASE | re.DOTALL)
    if rc:
        reconcile = rc.group(1).strip().rstrip("`*_").strip()

    bullets_section = re.search(
        r"BULLETS:\s*(.*?)(?:RECONCILE:|\n###|\Z)",
        body, re.IGNORECASE | re.DOTALL,
    )
    if bullets_section:
        for line in bullets_section.group(1).splitlines():
            line = line.strip()
            if line.startswith(("-", "*", "•")):
                bullets.append(line[1:].strip())

    return StockSummary(
        ticker=ticker or expected_ticker,
        name=name,
        headline=headline,
        bullets=bullets,
        reconcile=reconcile,
    )


def _extract_citations(response) -> tuple[list[Citation], list[str]]:
    """Return (citations, search_queries) from one response, deduped."""
    citations: list[Citation] = []
    queries: list[str] = []
    try:
        for cand in (getattr(response, "candidates", None) or []):
            gm = getattr(cand, "grounding_metadata", None)
            if gm is None:
                continue
            for q in (getattr(gm, "web_search_queries", None) or []):
                if q and q not in queries:
                    queries.append(q)
            for ch in (getattr(gm, "grounding_chunks", None) or []):
                web = getattr(ch, "web", None)
                if web is None:
                    continue
                citations.append(Citation(
                    title=str(getattr(web, "title", "") or ""),
                    uri=str(getattr(web, "uri", "") or ""),
                ))
    except Exception:  # noqa: BLE001
        log.exception("Failed to extract citations")

    seen, deduped = set(), []
    for c in citations:
        if c.uri and c.uri not in seen:
            seen.add(c.uri)
            deduped.append(c)
    return deduped, queries


def _summarize_one(api_key: str, row: pd.Series, as_of: date) -> StockSummary:
    """One grounded Gemini call for one stock. Never raises — returns an empty
    card with a hint in the headline on failure."""
    from google import genai
    from google.genai import types

    ticker = str(row.get("ticker", ""))
    name = str(row.get("name", "") or ticker)
    try:
        client = genai.Client(api_key=api_key.strip())
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.2,
            system_instruction=_SYSTEM_PROMPT,
        )
        response = client.models.generate_content(
            model=MODEL,
            contents=_build_single_stock_prompt(row, as_of),
            config=config,
        )
        text = response.text or ""
        summary = _parse_one_section(text, ticker, name)
        cits, queries = _extract_citations(response)
        summary.citations = cits
        summary.search_queries = queries
        summary.domain_mentions = _extract_domain_mentions(summary.bullets)
        log.info(
            "Gemini per-stock: %s chunks=%d queries=%d bullets=%d domains=%d",
            ticker, len(cits), len(queries), len(summary.bullets),
            len(summary.domain_mentions),
        )
        return summary
    except Exception as exc:  # noqa: BLE001
        log.exception("Gemini call failed for %s", ticker)
        return StockSummary(
            ticker=ticker,
            name=name,
            headline=f"[Gemini error: {type(exc).__name__}]",
        )


def summarize_stocks(
    snapshot_df: pd.DataFrame,
    tickers: list[str],
    as_of: date,
) -> GeminiReport:
    """Fan out one grounded call per ticker; aggregate into a GeminiReport.

    Raises RuntimeError if GEMINI_API_KEY is unset.
    """
    if not is_enabled():
        raise RuntimeError("GEMINI_API_KEY not set")

    cohort = snapshot_df[snapshot_df["ticker"].isin(tickers)].copy()
    cohort = cohort.sort_values("arf", ascending=False, na_position="last")
    if cohort.empty:
        return GeminiReport(
            as_of=as_of, cohort=tickers, stocks=[],
            citations=[], raw_text="", model=MODEL,
        )

    api_key = os.environ["GEMINI_API_KEY"].strip()
    rows = [r for _, r in cohort.iterrows()]
    results_by_ticker: dict[str, StockSummary] = {}

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        futures = {
            pool.submit(_summarize_one, api_key, row, as_of): str(row["ticker"])
            for row in rows
        }
        for fut in as_completed(futures):
            ticker = futures[fut]
            results_by_ticker[ticker] = fut.result()

    # Preserve cohort order (ARF descending)
    ordered = [results_by_ticker[str(r["ticker"])] for r in rows
               if str(r["ticker"]) in results_by_ticker]

    # Union of citations across all stocks, deduped
    all_citations: list[Citation] = []
    seen = set()
    for s in ordered:
        for c in s.citations:
            if c.uri and c.uri not in seen:
                seen.add(c.uri)
                all_citations.append(c)

    raw_text = "\n\n".join(
        f"### {s.ticker}\nHEADLINE: {s.headline}\nBULLETS:\n" +
        "\n".join(f"- {b}" for b in s.bullets) +
        f"\nRECONCILE: {s.reconcile}"
        for s in ordered
    )

    log.info(
        "Gemini report: model=%s stocks=%d total_citations=%d",
        MODEL, len(ordered), len(all_citations),
    )
    return GeminiReport(
        as_of=as_of,
        cohort=cohort["ticker"].tolist(),
        stocks=ordered,
        citations=all_citations,
        raw_text=raw_text,
        model=MODEL,
    )


def cohort_for_overview(snapshot_df: pd.DataFrame) -> list[str]:
    """Top 5 by ARF in each leg, concat — matches the Home page layout."""
    out: list[str] = []
    for leg in ["US", "China"]:
        sub = snapshot_df[snapshot_df["leg"] == leg].dropna(subset=["arf"])
        out.extend(sub.sort_values("arf", ascending=False).head(5)["ticker"].tolist())
    return out


def to_session_cache_key(as_of: date, cohort: list[str]) -> str:
    return json.dumps({"as_of": as_of.isoformat(), "cohort": sorted(cohort)})


# ---------- DB serialization ----------

OVERVIEW_COHORT_KEY = "overview"


def summary_to_db_row(
    s: StockSummary,
    as_of: date,
    cohort_key: str,
    model: str,
    generated_at,
) -> dict:
    return {
        "as_of_date": as_of,
        "ticker": s.ticker,
        "cohort_key": cohort_key,
        "name": s.name,
        "headline": s.headline,
        "bullets_json": json.dumps(s.bullets, ensure_ascii=False),
        "reconcile": s.reconcile,
        "domain_mentions_json": json.dumps(s.domain_mentions, ensure_ascii=False),
        "search_queries_json": json.dumps(s.search_queries, ensure_ascii=False),
        "citations_json": json.dumps(
            [{"title": c.title, "uri": c.uri} for c in s.citations],
            ensure_ascii=False,
        ),
        "model": model,
        "generated_at": generated_at,
    }


def _json_loads_safe(s: str | None) -> list:
    if not s:
        return []
    try:
        v = json.loads(s)
        return v if isinstance(v, list) else []
    except (TypeError, ValueError):
        return []


def db_rows_to_report(rows_df: pd.DataFrame, as_of: date) -> GeminiReport | None:
    """Build a GeminiReport from a query_gemini_summaries() result.

    Returns None if the dataframe is empty.
    """
    if rows_df is None or len(rows_df) == 0:
        return None

    stocks: list[StockSummary] = []
    seen, all_citations = set(), []
    model = ""
    for _, r in rows_df.iterrows():
        citations = [
            Citation(title=str(c.get("title", "")), uri=str(c.get("uri", "")))
            for c in _json_loads_safe(r.get("citations_json"))
        ]
        s = StockSummary(
            ticker=str(r.get("ticker") or ""),
            name=str(r.get("name") or r.get("ticker") or ""),
            headline=str(r.get("headline") or ""),
            bullets=[str(b) for b in _json_loads_safe(r.get("bullets_json"))],
            reconcile=str(r.get("reconcile") or ""),
            citations=citations,
            search_queries=[
                str(q) for q in _json_loads_safe(r.get("search_queries_json"))
            ],
            domain_mentions=[
                str(d) for d in _json_loads_safe(r.get("domain_mentions_json"))
            ],
        )
        stocks.append(s)
        model = str(r.get("model") or model)
        for c in citations:
            if c.uri and c.uri not in seen:
                seen.add(c.uri)
                all_citations.append(c)

    return GeminiReport(
        as_of=as_of,
        cohort=[s.ticker for s in stocks],
        stocks=stocks,
        citations=all_citations,
        raw_text="",
        model=model,
    )


# ---------- Institutional research synthesis (thermometer) ----------

RESEARCH_COHORT_KEY = "research"


@dataclass
class ResearchSynthesis:
    as_of: date
    cohort: list[str]
    text: str
    citations: list[Citation]
    model: str


_RESEARCH_SYSTEM_PROMPT = """You are a buy-side strategist writing a concise \
Chinese-language synthesis of SELL-SIDE research coverage, to sit beside a \
quantitative AI-relevance / valuation-froth model (ARF).

You are GIVEN, as ground truth, a table of recent institutional reports (broker \
ratings, consensus price targets, EPS forecasts) for a cohort of stocks, plus \
each stock's ARF froth reading. Treat that table as authoritative — do NOT invent \
ratings or targets that are not in it.

Your job:
1. Summarise where the sell-side consensus stands for the cohort (ratings skew, \
target upside/downside).
2. Reconcile it against the ARF model: call out DIVERGENCES explicitly — e.g. a \
name ARF flags as froth (D1, ROE<cost-of-equity, high P/S) that the street still \
rates 买入 with large target upside, or vice versa.
3. You MAY use Google Search for brief recent context, but every searched fact \
must cite its source domain in parentheses, e.g. "(reuters.com)". Facts from the \
provided report table need no citation.

Compliance: objective, rules-based research framing only. No buy/sell advice.

Output: Chinese markdown, ≤350 words, EXACTLY these sections, no preamble:
### 一、卖方一致预期概览
### 二、与 ARF 估值读数的背离
### 三、需要关注的个股"""


def _research_digest(
    consensus_df: pd.DataFrame,
    snapshot_df: pd.DataFrame,
    research_df: pd.DataFrame,
    max_titles: int = 3,
) -> str:
    """Format the ground-truth report table + ARF readings into a prompt block."""
    name_lookup = dict(zip(snapshot_df["ticker"], snapshot_df["name"], strict=False))
    cons_lookup = {str(r["ticker"]): r for _, r in consensus_df.iterrows()}

    blocks: list[str] = []
    for _, row in snapshot_df.iterrows():
        ticker = str(row["ticker"])
        c = cons_lookup.get(ticker)
        if c is None:
            continue
        parts = [f"{ticker} ({name_lookup.get(ticker, '')}) — {_factor_line(row)}"]

        cons_str = (
            f"机构={int(c['n_institutions'])} 报告={int(c['n_reports'])} "
            f"评级=[{c['rating_summary']}]"
        )
        if pd.notna(c["consensus_target"]):
            cons_str += f" 目标价={c['consensus_target']:.2f}{c['currency']}"
        if pd.notna(c["implied_upside_pct"]):
            cons_str += f" 隐含空间={c['implied_upside_pct']:+.1f}%"
        if pd.notna(c["eps_forecast"]):
            cons_str += f" EPS预测={c['eps_forecast']:.2f}"
        parts.append("  卖方: " + cons_str)

        rep = research_df[
            (research_df["ticker"] == ticker)
            & (research_df["source"] != "yfinance-consensus")
        ].dropna(subset=["report_date"]).sort_values("report_date", ascending=False)
        for _, rr in rep.head(max_titles).iterrows():
            parts.append(
                f"    · {rr['report_date']} {rr.get('institution') or ''} "
                f"[{rr.get('rating') or '—'}] {rr.get('title') or ''}"
            )
        blocks.append("\n".join(parts))
    return "\n\n".join(blocks)


def synthesize_research(
    snapshot_df: pd.DataFrame,
    research_df: pd.DataFrame,
    as_of: date,
    cohort: list[str] | None = None,
) -> ResearchSynthesis:
    """One grounded Gemini call synthesising sell-side coverage vs ARF froth.

    Raises RuntimeError if GEMINI_API_KEY is unset. The research-report table is
    passed as ground truth; Google Search only adds recent colour.
    """
    if not is_enabled():
        raise RuntimeError("GEMINI_API_KEY not set")

    from google import genai
    from google.genai import types

    from arf.fetchers.research import compute_consensus

    if cohort is None:
        cohort = cohort_for_overview(snapshot_df)
    sub = snapshot_df[snapshot_df["ticker"].isin(cohort)].copy()
    sub = sub.sort_values("arf", ascending=False, na_position="last")

    prices = {
        str(t): p
        for t, p in zip(snapshot_df["ticker"], snapshot_df.get("price"), strict=False)
        if pd.notna(p)
    }
    consensus_df = compute_consensus(research_df, prices)
    digest = _research_digest(consensus_df, sub, research_df)
    if not digest.strip():
        return ResearchSynthesis(
            as_of=as_of, cohort=cohort, text="", citations=[], model=MODEL
        )

    prompt = (
        f"Snapshot date: {as_of.isoformat()}\n"
        f"Cohort: top-5 ARF per leg (US + China).\n\n"
        f"=== GROUND-TRUTH INSTITUTIONAL RESEARCH + ARF READINGS ===\n"
        f"{digest}\n\n"
        f"Write the synthesis now, following the exact 3-section format."
    )

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"].strip())
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.2,
        system_instruction=_RESEARCH_SYSTEM_PROMPT,
    )
    response = client.models.generate_content(
        model=MODEL, contents=prompt, config=config
    )
    text = response.text or ""
    citations, _ = _extract_citations(response)
    log.info(
        "Research synthesis: model=%s cohort=%d citations=%d chars=%d",
        MODEL, len(cohort), len(citations), len(text),
    )
    return ResearchSynthesis(
        as_of=as_of, cohort=cohort, text=text, citations=citations, model=MODEL
    )


# ---------- AI-Analyst & AI-Screener Additions ----------

_ANALYST_SYSTEM_PROMPT = """You are a senior quantitative investment analyst writing a comprehensive Multi-Factor Narrative-Technical Synthesis Report. Your job is to reconcile a stock's quantitative data (ARF score, technical indicators, chip distribution, and backtesting performance) with qualitative recent developments (news, earnings, catalysts) sourced via Google Search.

Hard Rules:
1. ALWAYS use Google Search. Fire at least 3 distinct queries to find recent news (last 14 days) regarding the company's business developments, earnings, product catalysts, and regulatory context.
2. Maintain strict COMPLIANCE. Frame all conclusions as objective, rules-based research findings. NEVER provide investment recommendations, buying advice, or financial advisory statements. Focus on explaining narrative-technical alignment.
3. Every news fact must cite its source domain in parentheses, e.g. "(bloomberg.com)".
4. Organize your response into exactly these four sections using Markdown:
   - ### 1. 基本面与 AI 叙事剖析 (Fundamental & AI Narrative Analysis)
   - ### 2. 技术面与筹码微观结构 (Technical & Chip Microstructure)
   - ### 3. 历史回测绩效评估 (Historical Backtest Performance Evaluation)
   - ### 4. 综合多因子研究结论 (Integrated Multi-Factor Synthesis)
"""

def generate_narrative_technical_report(
    api_key: str,
    ticker: str,
    name: str,
    arf_row: dict,
    tech_row: dict,
    chip_metrics: tuple,
    backtest_summary: str
) -> dict:
    """Generate a comprehensive narrative-technical synthesis report using grounded Gemini.
    
    Returns a dictionary with 'report_text', 'citations', and 'queries'.
    """
    from google import genai
    from google.genai import types
    
    profit_ratio, avg_cost, c90_min, c90_max, c70_min, c70_max = chip_metrics
    
    # Format data blocks for the prompt
    arf_block = (
        f"ARF Score: {arf_row.get('arf', 'N/A'):.1f} (Decile: D{arf_row.get('decile', 'N/A')})\n"
        f"E_score (Exposure): {arf_row.get('e_score', 'N/A'):.1f}\n"
        f"V_score (Valuation Stretch): {arf_row.get('v_score', 'N/A'):.1f}\n"
        f"Forward P/E: {arf_row.get('forward_pe', 'N/A')}\n"
        f"P/S Ratio: {arf_row.get('ps_ratio', 'N/A')}\n"
        f"ROE: {arf_row.get('roe', 0.0)*100:.1f}%\n"
        f"Revenue YoY Growth: {arf_row.get('revenue_yoy_growth', 0.0)*100:.1f}%\n"
        f"Froth Flag: {arf_row.get('froth_flag', False)}"
    )
    
    tech_block = (
        f"Technical Score: {tech_row.get('technical_score', 50.0):.1f}/100\n"
        f"MA 5/10/20/30/60/120: {tech_row.get('ma5', 0):.2f}/{tech_row.get('ma10', 0):.2f}/{tech_row.get('ma20', 0):.2f}/{tech_row.get('ma30', 0):.2f}/{tech_row.get('ma60', 0):.2f}/{tech_row.get('ma120', 0):.2f}\n"
        f"MA Bullish Alignment: {tech_row.get('ma_bullish_alignment', False)}\n"
        f"RSI (14): {tech_row.get('rsi', 50.0):.1f}\n"
        f"MACD DIF/DEA/Hist: {tech_row.get('macd_dif', 0):.2f}/{tech_row.get('macd_dea', 0):.2f}/{tech_row.get('macd_hist', 0):.2f}\n"
        f"Bollinger Position (0-1): {(tech_row.get('close', 0) - tech_row.get('bollinger_lower', 0)) / (tech_row.get('bollinger_upper', 1) - tech_row.get('bollinger_lower', 0)) if (tech_row.get('bollinger_upper', 1) - tech_row.get('bollinger_lower', 0)) > 0 else 0.5:.2f}\n"
        f"ATR (14): {tech_row.get('atr', 0):.2f}"
    )
    
    chip_block = (
        f"Profit Chips Ratio: {profit_ratio*100:.1f}%\n"
        f"Average Holding Cost: ¥{avg_cost:.2f}\n"
        f"70% Cost Interval: ¥{c70_min:.2f} ~ ¥{c70_max:.2f}\n"
        f"90% Cost Interval: ¥{c90_min:.2f} ~ ¥{c90_max:.2f}"
    )
    
    prompt = (
        f"Stock Analysis Target: {ticker} — {name}\n\n"
        f"=== FACTOR DATA ===\n"
        f"[1. AI Relevance Factor (ARF)]\n{arf_block}\n\n"
        f"[2. Technical Indicators]\n{tech_block}\n\n"
        f"[3. Chip Distribution (CYQ)]\n{chip_block}\n\n"
        f"=== HISTORICAL BACKTEST PERFORMANCE ===\n"
        f"{backtest_summary}\n\n"
        f"=== INSTRUCTIONS ===\n"
        f"1. Conduct a grounded search to find recent material news and catalysts for {ticker} ({name}) over the last 14 days.\n"
        f"2. Synthesize the narrative layer (ARF - whether the stock is pricing in heavy AI hype) and the technical layer (momentum, scores, chip microstructure).\n"
        f"3. Write a highly professional, objective Multi-Factor Synthesis report. Adhere strictly to the four-section markdown format and compliance guidelines."
    )
    
    try:
        client = genai.Client(api_key=api_key.strip())
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.2,
            system_instruction=_ANALYST_SYSTEM_PROMPT,
        )
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=config,
        )
        report_text = response.text or ""
        cits, queries = _extract_citations(response)
        return {
            "report_text": report_text,
            "citations": cits,
            "queries": queries
        }
    except Exception as e:
        log.exception(f"AI-Analyst report generation failed for {ticker}")
        return {
            "report_text": f"⚠️ **生成研究报告失败**：{str(e)}",
            "citations": [],
            "queries": []
        }


_SCREENER_SYSTEM_PROMPT = """You are a database compiler. Your job is to translate a user's natural language stock screening query into a single, valid DuckDB SQL query.

We have two tables in our DuckDB database:
1. `snapshots` table:
   - `ticker` (TEXT, primary key)
   - `as_of_date` (DATE, primary key)
   - `leg` (TEXT, 'US' or 'China')
   - `layer` (TEXT, 'L1' to 'L5', representing the 5-layer AI stack:
      - 'L1' = Energy / 能源 (e.g. NextEra, CATL, grid, power, batteries)
      - 'L2' = Chips / 芯片 / 半导体 (e.g. NVIDIA, AMD, Intel, Broadcom, Marvell, SMIC, Cambricon, ASML, ARM)
      - 'L3' = Infra / 基础设施 / 光模块 / 光器件 / 数据中心 / 服务器 (e.g. Arista, Equinix, Coherent, Lumentum, InnoLight, Eoptolink, TFC, Accelink, Inspur, GDS, VNET)
      - 'L4' = Models / 大模型 / 算法模型 (e.g. Zhipu)
      - 'L5' = Apps / 应用 / 软件 / 自动驾驶 (e.g. Microsoft, Salesforce, Palantir, Tencent, Alibaba, Baidu, XPeng))
   - `name` (TEXT)
   - `arf` (DOUBLE, AI Relevance Factor, 0-100)
   - `decile` (INTEGER, 1-10, where 1 is highest ARF)
   - `e_score` (DOUBLE, AI exposure, 0-100)
   - `v_score` (DOUBLE, valuation stretch, 0-100)
   - `froth_flag` (BOOLEAN, True if bubble warning)
   - `price` (DOUBLE, local price)
   - `market_cap_usd` (DOUBLE)
   - `roe` (DOUBLE, as decimal, e.g. 0.15 for 15%)
   - `ps_ratio` (DOUBLE)
   - `forward_pe` (DOUBLE)
   - `revenue_yoy_growth` (DOUBLE, as decimal, e.g. 0.25 for 25%)

2. `technical_metrics` table:
   - `ticker` (TEXT, primary key)
   - `as_of_date` (DATE, primary key)
   - `technical_score` (DOUBLE, 0-100)
   - `ma5`, `ma10`, `ma20`, `ma30`, `ma60`, `ma120` (DOUBLE)
   - `ma_bullish_alignment` (BOOLEAN, True if ma5 > ma10 > ma20 > ma30 > ma60 > ma120)
   - `rsi` (DOUBLE, 0-100)
   - `macd_dif`, `macd_dea`, `macd_hist` (DOUBLE)
   - `bollinger_mid`, `bollinger_upper`, `bollinger_lower` (DOUBLE)
   - `atr` (DOUBLE)
   - `chip_profit_ratio` (DOUBLE, 0.0-1.0, representing % of chips in profit)
   - `chip_avg_cost` (DOUBLE)

Rules:
1. Join the two tables on `ticker` and `as_of_date`.
2. The user will specify conditions. Translate them accurately.
   - "获利盘" / "获利筹码" refers to `chip_profit_ratio` (e.g. "获利盘大于80%" -> `chip_profit_ratio > 0.8`).
   - "均线多头" / "均线多头排列" refers to `ma_bullish_alignment = TRUE`.
   - "技术评分" / "技术面得分" refers to `technical_score`.
   - "泡沫预警" / "泡沫" refers to `froth_flag = TRUE`.
   - "估值拉伸" refers to `v_score` or `ps_ratio`.
   - "E分" / "AI曝光" refers to `e_score`.
   - "芯片" / "半导体" / "芯片题材" / "半导体题材" / "芯片板块" / "半导体板块" refers to `layer = 'L2'`.
   - "光模块" / "光器件" / "基础设施" / "数据中心" / "服务器" / "光通信" / "光模块题材" refers to `layer = 'L3'`.
   - "大模型" / "大模型题材" / "算法模型" / "模型题材" refers to `layer = 'L4'`.
   - "应用" / "软件" / "AI应用" / "自动驾驶" / "软件应用" refers to `layer = 'L5'`.
   - "能源" / "电力" / "算力能源" / "电力能源" refers to `layer = 'L1'`.
3. ALWAYS filter by the given `as_of_date` to ensure we query the active snapshot (e.g. `s.as_of_date = '2026-05-28'`).
4. Output ONLY the raw SQL query. Do not wrap it in markdown code blocks, do not add explanations, do not write anything else. Just the plain SQL string.

Example 1:
User Query: "均线多头，且获利盘小于30%"
Output:
SELECT s.ticker, s.name, s.arf, s.decile, t.technical_score, t.rsi, t.chip_profit_ratio FROM snapshots s JOIN technical_metrics t ON s.ticker = t.ticker AND s.as_of_date = t.as_of_date WHERE s.as_of_date = '2026-05-28' AND t.ma_bullish_alignment = TRUE AND t.chip_profit_ratio < 0.3 ORDER BY s.arf DESC

Example 2:
User Query: "芯片题材"
Output:
SELECT s.ticker, s.name, s.arf, s.decile, s.layer, t.technical_score FROM snapshots s JOIN technical_metrics t ON s.ticker = t.ticker AND s.as_of_date = t.as_of_date WHERE s.as_of_date = '2026-05-28' AND s.layer = 'L2' ORDER BY s.arf DESC
"""

def parse_nlp_screener_query(
    api_key: str,
    query: str,
    as_of_date: date
) -> str:
    """Translate a natural language stock screening query into a valid DuckDB SQL query using Gemini."""
    from google import genai
    
    prompt = (
        f"Snapshot Date: {as_of_date.isoformat()}\n"
        f"User Screener Query: {query}\n\n"
        f"Generate the exact DuckDB SQL query following the schema and rules. Return ONLY the raw SQL text."
    )
    
    try:
        client = genai.Client(api_key=api_key.strip())
        response = client.models.generate_content(
            model="gemini-2.5-flash",  # Flash is excellent and fast for structured text/SQL generation
            contents=prompt,
            config=dict(
                temperature=0.0,
                system_instruction=_SCREENER_SYSTEM_PROMPT
            )
        )
        sql = response.text or ""
        
        # Strip any accidental markdown formatting
        sql = sql.strip()
        if sql.startswith("```"):
            sql = sql.split("\n", 1)[1]
        if sql.endswith("```"):
            sql = sql.rsplit("\n", 1)[0]
        sql = sql.strip().strip("`").strip()
        
        # Basic validation: must start with SELECT
        if not sql.upper().startswith("SELECT"):
            return f"-- Generated query was invalid:\n-- {sql}"
            
        return sql
    except Exception as e:
        log.exception("NLP SQL compilation failed")
        return f"-- Error compiling query: {str(e)}"


# ---------- Weekly One-Click Synthesis ----------

_WEEKLY_SYNTHESIS_SYSTEM_PROMPT = """You are a senior cross-asset strategist at a quantitative research house. You are
writing the weekly "AI Stack Bubble Monitor" synthesis report. You receive:
1. Thermometer deltas (froth count changes week-over-week for US and China legs)
2. Top-5 China A+H stocks by ARF with their backtest performance across 3 strategies
3. ARF snapshot summary statistics

Your job is to produce a bilingual (Chinese primary, with English section headers) report
with EXACTLY these four sections in Markdown:

### 1. 市场温度概览 (Market Temperature Overview)
Interpret the thermometer — are we heating up or cooling down? Reference the absolute and
relative froth counts, EV/Sales percentile, and implied growth gap changes.

### 2. 个股ARF趋势解读 (Stock ARF Trend Interpretation)
For the top-5 stocks, explain why they rank highest. Reference their E_score, V_score,
decile, and key fundamentals (P/S, ROE, forward P/E).

### 3. 量化策略回测洞察 (Quantitative Backtest Insights)
Summarize the backtest results across the 5 stocks × 3 strategies. Which strategy worked
best overall? Which stocks showed the strongest alpha signals? Reference specific Sharpe
ratios, returns, and max drawdowns.

### 4. 综合研判与风险提示 (Synthesis & Risk Warnings)
Tie together the narrative, technical, and backtest layers. Identify the biggest risk
factors. This section MUST include a compliance disclaimer that this is objective research,
NOT investment advice.

Hard rules:
1. ALWAYS use Google Search. Fire at least 3 distinct queries about the latest macro
   context of China's AI sector, US-China tech decoupling, and any regulatory changes.
2. Every factual claim from search MUST cite the source domain in parentheses.
3. Keep the report under 1500 words total.
4. Use Chinese as the primary language with English section headers.
"""


def generate_weekly_synthesis(report_data) -> dict:
    """Generate a weekly synthesis report using grounded Gemini.

    Args:
        report_data: ReportData from arf.oneclick

    Returns:
        dict with 'report_text', 'citations', 'queries'
    """
    from google import genai
    from google.genai import types

    if not is_enabled():
        return {"report_text": "", "citations": [], "queries": []}

    api_key = os.environ["GEMINI_API_KEY"].strip()

    # Build the data context for the prompt
    from arf.oneclick import _backtest_summary_for_gemini

    thermo_block = "=== 泡沫温度计周度变化 ===\n"
    for d in report_data.thermo_deltas:
        thermo_block += (
            f"{d.leg}: 绝对泡沫数={d.absolute_froth} ({d.absolute_froth_delta}), "
            f"相对泡沫数={d.relative_froth} ({d.relative_froth_delta}), "
            f"EV/Sales分位数={d.median_ev_sales_pct:.1f}% ({d.ev_sales_delta}), "
            f"隐含增长差值={d.median_growth_gap:.2f}% ({d.growth_gap_delta})\n"
        )

    snapshot_block = (
        f"=== 快照摘要 ===\n"
        f"日期: {report_data.as_of}\n"
        f"美股 D1数量: {report_data.d1_us}, 泡沫预警: {report_data.froth_us}\n"
        f"中股 D1数量: {report_data.d1_china}, 泡沫预警: {report_data.froth_china}\n"
    )

    backtest_block = "=== Top 5 中国A+H股回测概要 ===\n"
    backtest_block += _backtest_summary_for_gemini(report_data.backtest_stocks)

    prompt = (
        f"{snapshot_block}\n"
        f"{thermo_block}\n"
        f"{backtest_block}\n"
        f"=== 指令 ===\n"
        f"基于以上数据，撰写本周 AI Stack Bubble Monitor 综合研报。\n"
        f"务必联网检索最新宏观和行业动态，引用来源域名。\n"
        f"严格按照四个章节的格式输出。"
    )

    try:
        client = genai.Client(api_key=api_key)
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.3,
            system_instruction=_WEEKLY_SYNTHESIS_SYSTEM_PROMPT,
        )
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=config,
        )
        report_text = response.text or ""
        cits, queries = _extract_citations(response)
        log.info(
            "Weekly synthesis: model=%s len=%d citations=%d queries=%d",
            MODEL, len(report_text), len(cits), len(queries),
        )
        return {
            "report_text": report_text,
            "citations": cits,
            "queries": queries,
        }
    except Exception as exc:
        log.exception("Weekly Gemini synthesis failed")
        return {
            "report_text": f"⚠️ AI 综合研判生成失败：{exc}",
            "citations": [],
            "queries": [],
        }


