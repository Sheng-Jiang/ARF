"""Thesis generator and Opportunity Card compiler using Gemini Flash."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import date
from pathlib import Path

from arf.agent.radar import _extract_json_payload
from arf.agent.schemas import (
    DecisionAction,
    GateVerdict,
    InvestmentDecisionRecord,
    OpportunityCard,
    OpportunityStage,
    QuantFactorSnapshot,
)
from arf.agent.tools import get_stock_quant_profile
from arf.db import init_db, upsert_idr, upsert_thesis

log = logging.getLogger(__name__)

THESIS_MODEL = os.getenv("GEMINI_FLASH_MODEL", "gemini-3.8-flash")


_THESIS_SYSTEM_PROMPT = """You are a senior buy-side tech investment analyst specializing in the global AI hardware and software value chain (Jensen Huang's 5-layer cake).

You are given:
1. Complete quantitative factor profile (ARF score, Decile, E_score AI exposure, V_score valuation stretch, ROE, Forward P/E, P/S, Reverse DCF implied growth gap, CYQ chip profit ratio, and momentum).
2. The company's ticker, name, leg (US or China), and layer (L1 Energy, L2 Chips, L3 Infra, L4 Models, L5 Apps).

Your mission is to perform a rigorous Bull vs. Bear debate and compile an actionable Opportunity Card.

Hard Rules:
1. CONDUCT GOOGLE SEARCH: Run at least 2 distinct searches to find the latest material catalysts, earnings reports, customer order volumes, or regulatory updates from the past 30 days.
2. CITATIONS: Include source domains in parentheses for news facts, e.g. "(bloomberg.com)", "(reuters.com)", "(caixin.com)".
3. RIGOROUS VALUATION ANCHOR:
   - If ARF is in D1-D2 with ROE < WACC, vigorously challenge bubble froth.
   - If ARF is in D4-D7 with elite ROE (>25%) and strong exposure, examine whether this is a Mispriced GARP (Growth At a Reasonable Price) opportunity.
   - Reconcile the reverse-DCF implied growth gap (g* vs consensus).
4. COMPLIANCE & RISK: Objective research framing only. Clearly state explicit thesis invalidation criteria (e.g. margin compression, loss of tier-1 customer allocation).
5. OUTPUT: Strict JSON matching the required schema.

Required JSON format:
{
  "thesis_type": "long_opportunity" | "garp_value" | "froth_short" | "neutral_watch",
  "title": "<Concise, punchy thesis title, <= 12 words>",
  "bull_case": "<2-3 paragraphs detailing structural drivers, moat, hyperscaler demand, and quantitative support>",
  "bear_case": "<2-3 paragraphs detailing red-team risks, valuation stretch, customer concentration, geopolitical threats>",
  "synthesis": "<1-2 paragraphs giving final research verdict on risk/reward asymmetry>",
  "valuation_entry_zone": "<Specific quantitative entry zone, e.g., 'Forward P/E < 26, ARF D4-D6, CYQ cost support at ¥125'>",
  "invalidation_criteria": "<Explicit conditions that break the thesis, e.g., 'Gross margin drops below 40% or hyperscaler capex cuts'>",
  "confidence_score": <number between 10.0 and 95.0>,
  "catalysts": [
    "<Catalyst 1 with expected timeframe>",
    "<Catalyst 2 with expected timeframe>"
  ]
}
"""


def _extract_citations_and_text(response) -> tuple[str, list[dict[str, str]]]:
    """Extract response text and web search citations."""
    text = response.text or ""
    citations: list[dict[str, str]] = []
    try:
        for cand in (getattr(response, "candidates", None) or []):
            gm = getattr(cand, "grounding_metadata", None)
            if not gm:
                continue
            for ch in (getattr(gm, "grounding_chunks", None) or []):
                web = getattr(ch, "web", None)
                if web and getattr(web, "uri", None):
                    citations.append({
                        "title": str(getattr(web, "title", "") or ""),
                        "uri": str(getattr(web, "uri", "") or ""),
                    })
    except Exception:
        pass

    # Deduplicate citations
    seen = set()
    deduped = []
    for c in citations:
        if c["uri"] not in seen:
            seen.add(c["uri"])
            deduped.append(c)
    return text, deduped


def compile_investment_decision_record(
    ticker: str,
    as_of: date,
    api_key: str | None = None,
    db_path: Path = Path("data/arf.db"),
    persist: bool = True,
) -> tuple[OpportunityCard, InvestmentDecisionRecord]:
    """Compile an institutional Opportunity Card and a 5-step Investment Decision Record (IDR)."""
    key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
    if not key or key.startswith("PLACEHOLDER"):
        raise RuntimeError("GEMINI_API_KEY is not set or valid.")

    quant_profile = get_stock_quant_profile(ticker, as_of, db_path=db_path)
    if not quant_profile:
        raise ValueError(f"No quantitative data found for {ticker} as of {as_of}.")

    # get_stock_quant_profile falls back to the most recent snapshot when the
    # requested as_of has no row. Label the card with the date of the data we
    # actually got, not the date we asked for, so the persisted thesis never
    # claims a snapshot it wasn't built from.
    data_as_of = as_of
    raw_profile_date = quant_profile.get("as_of_date")
    if raw_profile_date:
        try:
            data_as_of = date.fromisoformat(str(raw_profile_date)[:10])
        except (TypeError, ValueError):
            log.warning(
                "Unparseable as_of_date %r in quant profile for %s; using requested %s",
                raw_profile_date, ticker, as_of,
            )
    if data_as_of != as_of:
        log.warning(
            "No snapshot for %s on %s; generated card from %s data instead.",
            ticker, as_of, data_as_of,
        )

    name = quant_profile.get("name") or ticker
    leg = quant_profile.get("leg") or "US"
    layer = quant_profile.get("layer") or "L3"

    prompt_context = (
        f"Snapshot Date: {data_as_of.isoformat()}\n"
        f"Target Stock: {ticker} ({name}) | Leg: {leg} | Layer: {layer}\n\n"
        f"=== QUANTITATIVE ARF PROFILE ===\n"
        f"- ARF Score: {quant_profile.get('arf', 'N/A')} (Decile: D{quant_profile.get('decile', 'N/A')})\n"
        f"- AI Exposure (E_score): {quant_profile.get('e_score', 'N/A')}\n"
        f"- Valuation Stretch (V_score): {quant_profile.get('v_score', 'N/A')}\n"
        f"- Froth Warning Flag: {quant_profile.get('froth_flag', False)}\n"
        f"- Reverse-DCF Implied Growth g*: {quant_profile.get('implied_growth', 'N/A')}\n"
        f"- Implied Growth Gap vs Consensus: {quant_profile.get('implied_growth_gap', 'N/A')}\n"
        f"- Forward P/E: {quant_profile.get('forward_pe', 'N/A')}\n"
        f"- P/S Ratio: {quant_profile.get('ps_ratio', 'N/A')}\n"
        f"- ROE: {quant_profile.get('roe', 'N/A')}\n"
        f"- Gross Margin: {quant_profile.get('gross_margin', 'N/A')}\n"
        f"- Revenue YoY Growth: {quant_profile.get('revenue_yoy_growth', 'N/A')}\n"
        f"- Technical Score: {quant_profile.get('technical_score', 'N/A')}\n"
        f"- Chip Profit Ratio (CYQ): {quant_profile.get('chip_profit_ratio', 'N/A')}\n"
        f"- Moving Average Alignment: {'Bullish' if quant_profile.get('ma_bullish') else 'Neutral/Bearish'}\n\n"
        f"Generate the comprehensive Bull vs. Bear debate and output the JSON Opportunity Card now."
    )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.2,
        system_instruction=_THESIS_SYSTEM_PROMPT,
    )

    response = client.models.generate_content(
        model=THESIS_MODEL,
        contents=prompt_context,
        config=config,
    )

    raw_text, citations = _extract_citations_and_text(response)
    parsed = _extract_json_payload(raw_text)

    idr_uuid = uuid.uuid4().hex[:6]
    thesis_id = f"th_{ticker.lower()}_{data_as_of.strftime('%Y%m%d')}_{idr_uuid}"
    idr_id = f"idr_{ticker.lower()}_{data_as_of.strftime('%Y%m%d')}_{idr_uuid}"

    # Evaluate Outside-Model G3 Risk Gate
    cost_of_equity = 0.10 if leg == "US" else 0.12
    is_froth = bool(quant_profile.get("froth_flag", False))
    roe_val = quant_profile.get("roe")
    hurdle_met = bool(roe_val is not None and roe_val >= cost_of_equity)
    thesis_type = parsed.get("thesis_type", "neutral_watch")
    invalidation_criteria = parsed.get("invalidation_criteria", "")

    if is_froth and thesis_type == "long_opportunity":
        gate_verdict = GateVerdict.BLOCKED_FROTH
        gate_details = "G3 Gate: Target is froth-flagged (ARF in D1, ROE < WACC, P/S > 25). Long recommendation prohibited."
        recommended_action = DecisionAction.AVOID_FROTH
    elif thesis_type == "garp_value" and not hurdle_met:
        gate_verdict = GateVerdict.BLOCKED_HURDLE
        roe_str = f"{roe_val:.1%}" if roe_val is not None else "N/A"
        gate_details = f"G3 Gate: ROE ({roe_str}) fails required hurdle rate ({cost_of_equity:.1%})."
        recommended_action = DecisionAction.MONITOR
    elif not invalidation_criteria or len(str(invalidation_criteria).strip()) < 15:
        gate_verdict = GateVerdict.BLOCKED_INSUFFICIENT_CRITERIA
        gate_details = "G3 Gate: Lacks explicit, quantitative invalidation criteria."
        recommended_action = DecisionAction.MONITOR
    else:
        gate_verdict = GateVerdict.PASSED
        gate_details = "G3 Gate: Passed all outside-model risk predicates."
        if thesis_type in ("long_opportunity", "garp_value"):
            recommended_action = DecisionAction.BUY_ZONE
        else:
            recommended_action = DecisionAction.MONITOR

    # Compile the 5-step Investment Decision Record (IDR)
    bull_case_raw = parsed.get("bull_case", "")
    bear_case_raw = parsed.get("bear_case", "")
    bull_args = [b.strip() for b in bull_case_raw.split("\n\n") if b.strip()] or [bull_case_raw]
    bear_args = [b.strip() for b in bear_case_raw.split("\n\n") if b.strip()] or [bear_case_raw]

    idr = InvestmentDecisionRecord(
        idr_id=idr_id,
        ticker=ticker,
        name=name,
        as_of_date=data_as_of.isoformat(),
        stage=OpportunityStage.THESIS_FORMULATED,
        trigger_type="valuation_pullback" if thesis_type == "garp_value" else "factor_scan",
        trigger_summary=f"{ticker} analyzed as of {data_as_of.isoformat()} with ARF={quant_profile.get('arf')} (D{quant_profile.get('decile')})",
        observed_metrics=QuantFactorSnapshot(**quant_profile),
        leg=leg,
        layer=layer,
        cost_of_equity=cost_of_equity,
        policy_rules_evaluated=[
            f"WACC Hurdle >= {cost_of_equity:.1%}",
            "Froth flag exclusion on Long Opportunity",
            "Mandatory quantitative invalidation criteria",
        ],
        bull_arguments=bull_args,
        bear_arguments=bear_args,
        deliberation_synthesis=parsed.get("synthesis", ""),
        gate_verdict=gate_verdict,
        gate_details=gate_details,
        froth_flag=is_froth,
        hurdle_met=hurdle_met,
        recommended_action=recommended_action,
        valuation_entry_zone=parsed.get("valuation_entry_zone", ""),
        invalidation_criteria=invalidation_criteria,
        confidence_score=float(parsed.get("confidence_score", 50.0)),
        catalysts=parsed.get("catalysts", []),
        citations=citations,
        model=THESIS_MODEL,
    )

    card = OpportunityCard(
        thesis_id=thesis_id,
        ticker=ticker,
        name=name,
        leg=leg,
        layer=layer,
        as_of_date=data_as_of.isoformat(),
        thesis_type=thesis_type,
        title=parsed.get("title", f"Investment Thesis for {ticker}"),
        quant_profile=QuantFactorSnapshot(**quant_profile),
        bull_case=bull_case_raw,
        bear_case=bear_case_raw,
        synthesis=parsed.get("synthesis", ""),
        valuation_entry_zone=parsed.get("valuation_entry_zone", ""),
        invalidation_criteria=invalidation_criteria,
        confidence_score=float(parsed.get("confidence_score", 50.0)),
        catalysts=parsed.get("catalysts", []),
        citations=citations,
        model=THESIS_MODEL,
        idr_id=idr_id,
    )

    if persist:
        conn = init_db(db_path)
        try:
            upsert_thesis(conn, {
                "thesis_id": card.thesis_id,
                "ticker": card.ticker,
                "as_of_date": data_as_of,
                "thesis_type": card.thesis_type,
                "title": card.title,
                "bull_case": card.bull_case,
                "bear_case": card.bear_case,
                "synthesis": card.synthesis,
                "valuation_entry_zone": card.valuation_entry_zone,
                "invalidation_criteria": card.invalidation_criteria,
                "confidence_score": card.confidence_score,
                "catalysts_json": card.catalysts,
                "model": card.model,
            })
            upsert_idr(conn, idr.model_dump())
        finally:
            conn.close()

    return card, idr


def generate_opportunity_card(
    ticker: str,
    as_of: date,
    api_key: str | None = None,
    db_path: Path = Path("data/arf.db"),
    persist: bool = True,
) -> OpportunityCard:
    """Generate an institutional Opportunity Card for a stock using Gemini Flash."""
    card, _ = compile_investment_decision_record(
        ticker=ticker,
        as_of=as_of,
        api_key=api_key,
        db_path=db_path,
        persist=persist,
    )
    return card
