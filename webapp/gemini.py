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
    key = os.getenv("GEMINI_API_KEY", "")
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
        client = genai.Client(api_key=api_key)
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

    api_key = os.environ["GEMINI_API_KEY"]
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
