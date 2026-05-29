"""Ask Gemini — qualitative news layer on top of ARF scores.

Wraps Gemini 2.5 Pro with the Google Search grounding tool. The model is given
the snapshot rows as ground truth and asked to summarise recent news per stock,
returning structured per-ticker cards rendered by the webapp.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

log = logging.getLogger(__name__)

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")


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


@dataclass
class GeminiReport:
    as_of: date
    cohort: list[str]
    stocks: list[StockSummary]
    citations: list[Citation]
    raw_text: str
    model: str


def _format_row(row: pd.Series) -> str:
    """Compact one-line dump of a stock's ARF context for the prompt."""

    def f(k: str, fmt: str = "{:.1f}") -> str:
        v = row.get(k)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "?"
        try:
            return fmt.format(float(v))
        except (TypeError, ValueError):
            return str(v)

    froth = "★FROTH" if bool(row.get("froth_flag")) else ""
    return (
        f"- {row.get('ticker')} ({row.get('name', '')}) — leg={row.get('leg')} "
        f"layer={row.get('layer')} decile=D{int(row['decile']) if pd.notna(row.get('decile')) else '?'} "
        f"ARF={f('arf')} E={f('e_score')} V={f('v_score')} "
        f"fwd_PE={f('forward_pe')} P/S={f('ps_ratio')} ROE={f('roe', '{:.1%}')} "
        f"rev_yoy={f('revenue_yoy_growth', '{:.1%}')} {froth}"
    )


_SYSTEM_PROMPT = """You are a sell-side analyst writing a brief news-and-narrative
companion to a quantitative AI-relevance factor (ARF) ranking. The user has
already computed the factor — DO NOT restate or re-derive the scores. Your job is
to source recent (last 14 days) news that explains the narrative around each name
and reconcile it with the factor reading.

Rules:
1. Use Google Search to find news. Cite sources.
2. For each stock, output a section with this exact structure:

### <TICKER>
HEADLINE: <one sentence, ≤25 words>
BULLETS:
- <fact + source domain in parens>
- <fact + source domain in parens>
- <fact + source domain in parens>
RECONCILE: <one sentence linking the news to the ARF/E/V/decile shown>

3. Order stocks the same way they were given (ARF descending).
4. If you cannot find material news for a stock, say so honestly in the BULLETS
   instead of fabricating.
5. Never claim the ARF score itself is wrong. The factor is the ground truth in
   this exercise.
"""


def _build_user_prompt(rows_df: pd.DataFrame, as_of: date) -> str:
    rows = "\n".join(_format_row(r) for _, r in rows_df.iterrows())
    return (
        f"Snapshot date: {as_of.isoformat()}\n"
        f"Methodology recap: ARF = √(E_score × V_score) within each leg, "
        f"percentile-ranked to 0–100. D1 = top decile (most stretched by AI narrative). "
        f"★FROTH = D1 + ROE < cost-of-equity (10% US / 12% China) + P/S > 25.\n\n"
        f"Cohort (top by ARF):\n{rows}\n\n"
        f"Now produce the per-stock sections. Cover every stock listed above, in the same order."
    )


_SECTION_RE = re.compile(r"^###\s+([A-Za-z0-9\.\-]+)\s*$", re.MULTILINE)


def _parse_sections(
    text: str,
    cohort_df: pd.DataFrame,
) -> list[StockSummary]:
    """Split the model output into per-stock summaries.

    Resilient to small format drift — accepts any leading whitespace, missing
    fields just leave defaults.
    """
    matches = list(_SECTION_RE.finditer(text))
    out: list[StockSummary] = []
    name_lookup = dict(zip(cohort_df["ticker"], cohort_df["name"], strict=False))

    for i, m in enumerate(matches):
        ticker = m.group(1).strip()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end]

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

        out.append(StockSummary(
            ticker=ticker,
            name=name_lookup.get(ticker, ticker),
            headline=headline,
            bullets=bullets,
            reconcile=reconcile,
        ))
    return out


def _extract_citations(response) -> list[Citation]:
    """Pull grounding citations from the SDK response (best-effort, schema-tolerant)."""
    out: list[Citation] = []
    try:
        candidates = getattr(response, "candidates", None) or []
        for cand in candidates:
            gm = getattr(cand, "grounding_metadata", None)
            chunks = getattr(gm, "grounding_chunks", None) or []
            for ch in chunks:
                web = getattr(ch, "web", None)
                if web is None:
                    continue
                out.append(Citation(
                    title=str(getattr(web, "title", "") or ""),
                    uri=str(getattr(web, "uri", "") or ""),
                ))
    except Exception:  # noqa: BLE001
        log.exception("Failed to extract citations — returning empty list")

    seen, deduped = set(), []
    for c in out:
        if c.uri and c.uri not in seen:
            seen.add(c.uri)
            deduped.append(c)
    return deduped


def summarize_stocks(
    snapshot_df: pd.DataFrame,
    tickers: list[str],
    as_of: date,
) -> GeminiReport:
    """Call Gemini with Google Search grounding; return parsed report.

    Raises RuntimeError if GEMINI_API_KEY is unset.
    """
    if not is_enabled():
        raise RuntimeError("GEMINI_API_KEY not set")

    from google import genai
    from google.genai import types

    cohort = snapshot_df[snapshot_df["ticker"].isin(tickers)].copy()
    cohort = cohort.sort_values("arf", ascending=False, na_position="last")
    if cohort.empty:
        return GeminiReport(
            as_of=as_of, cohort=tickers, stocks=[],
            citations=[], raw_text="", model=MODEL,
        )

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.2,
        system_instruction=_SYSTEM_PROMPT,
    )
    response = client.models.generate_content(
        model=MODEL,
        contents=_build_user_prompt(cohort, as_of),
        config=config,
    )

    text = response.text or ""
    summaries = _parse_sections(text, cohort)
    citations = _extract_citations(response)

    log.info(
        "Gemini summary: model=%s tickers=%d parsed=%d citations=%d",
        MODEL, len(cohort), len(summaries), len(citations),
    )
    return GeminiReport(
        as_of=as_of,
        cohort=cohort["ticker"].tolist(),
        stocks=summaries,
        citations=citations,
        raw_text=text,
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
