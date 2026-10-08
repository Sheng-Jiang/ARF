"""Opportunity Radar & Discovery Engine for the ARF Agent."""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from arf.agent.schemas import CandidateCompany
from arf.agent.tools import query_quant_database
from arf.db import init_db, upsert_candidate

log = logging.getLogger(__name__)

RADAR_MODEL = os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash")


def _extract_json_payload(text: str) -> dict[str, Any]:
    """Robustly extract a JSON dictionary from a model response."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace : last_brace + 1])
        except Exception:
            pass
    return {}


def scan_valuation_anomalies(
    as_of: date | None = None,
    db_path: Path = Path("data/arf.db"),
) -> dict[str, list[dict[str, Any]]]:
    """Proactively scan the latest snapshot for quantitative opportunity and risk anomalies.
    
    Identifies:
    1. 'garp_opportunities': High exposure + elite ROE + moderate valuation (D4-D7).
    2. 'froth_warnings': Extreme multiple stretch with insufficient capital returns.
    3. 'technical_breakouts': Strong chip profit support + moving average alignment.
    """
    date_filter = f"s.as_of_date = '{as_of.isoformat()}'" if as_of else "s.as_of_date = (SELECT MAX(as_of_date) FROM snapshots)"

    # 1. GARP Opportunities
    garp_sql = f"""
    SELECT s.ticker, s.name, s.leg, s.layer, s.arf, s.decile, s.e_score, s.v_score,
           s.roe, s.forward_pe, s.ps_ratio, s.implied_growth,
           t.technical_score, t.chip_profit_ratio
    FROM snapshots s
    LEFT JOIN technical_metrics t ON s.ticker = t.ticker AND s.as_of_date = t.as_of_date
    WHERE {date_filter}
      AND s.e_score >= 55.0
      AND s.v_score <= 60.0
      AND s.decile >= 3
      AND s.roe >= 0.18
      AND s.froth_flag = FALSE
    ORDER BY s.roe DESC, s.e_score DESC
    """

    # 2. Froth Warnings (Short / Risk avoidance)
    froth_sql = f"""
    SELECT s.ticker, s.name, s.leg, s.layer, s.arf, s.decile, s.e_score, s.v_score,
           s.roe, s.forward_pe, s.ps_ratio, s.froth_flag,
           t.technical_score, t.chip_profit_ratio
    FROM snapshots s
    LEFT JOIN technical_metrics t ON s.ticker = t.ticker AND s.as_of_date = t.as_of_date
    WHERE {date_filter}
      AND (s.froth_flag = TRUE OR (s.decile = 1 AND s.roe < 0.10))
    ORDER BY s.v_score DESC
    """

    # 3. Technical Breakouts
    breakout_sql = f"""
    SELECT s.ticker, s.name, s.leg, s.layer, s.arf, s.decile,
           t.technical_score, t.chip_profit_ratio, t.chip_avg_cost, t.rsi
    FROM snapshots s
    JOIN technical_metrics t ON s.ticker = t.ticker AND s.as_of_date = t.as_of_date
    WHERE {date_filter}
      AND t.ma_bullish_alignment = TRUE
      AND t.chip_profit_ratio >= 0.70
      AND t.technical_score >= 65.0
    ORDER BY t.chip_profit_ratio DESC
    """

    return {
        "garp_opportunities": query_quant_database(garp_sql, db_path=db_path),
        "froth_warnings": query_quant_database(froth_sql, db_path=db_path),
        "technical_breakouts": query_quant_database(breakout_sql, db_path=db_path),
    }


_DISCOVERY_SYSTEM_PROMPT = """You are an AI hardware and infrastructure supply-chain intelligence agent.
Your objective is to discover publicly traded companies (US, HK, or China A-share) that are material suppliers or pure-play beneficiaries of a given AI theme or bottleneck.

Rules:
1. ALWAYS USE GOOGLE SEARCH to verify that the companies are currently publicly traded and actively supply the indicated tech.
2. CLASSIFY into the 5-layer cake:
   - L1: Energy / Power / Cooling (SMR nuclear, grid, liquid cooling, power converters)
   - L2: Chips / Processors / Memory (GPU, ASIC, HBM, packaging, foundry)
   - L3: Infrastructure / Networking / Optics (optical transceivers, DSP, switches, copper cables, ODMs)
   - L4: Foundation Models / AI Platforms
   - L5: AI Enterprise Applications / Physical AI / Robotics
3. OUTPUT STRICT JSON with an array of candidates.

JSON Format:
{
  "theme": "<Theme explored>",
  "candidates": [
    {
      "ticker": "<Exact exchange ticker, e.g. VRT or 300308.SZ or 0100.HK>",
      "name": "<Company English and Chinese name>",
      "leg": "US" | "China",
      "layer": "L1" | "L2" | "L3" | "L4" | "L5",
      "pure_play_est": <float 0-100 of AI revenue exposure>,
      "supply_role": "<Specific product or niche, e.g. Liquid cooling cold plates for hyperscale racks>",
      "key_customers": ["<Customer 1>", "<Customer 2>"],
      "notes": "<Brief thesis summary with domain citations>"
    }
  ]
}
"""


def discover_supply_chain_candidates(
    theme: str,
    api_key: str | None = None,
    db_path: Path = Path("data/arf.db"),
    stage_to_db: bool = True,
) -> list[CandidateCompany]:
    """Discover unmapped or emerging AI supply chain beneficiaries using Gemini with Google Search."""
    key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
    if not key or key.startswith("PLACEHOLDER"):
        raise RuntimeError("GEMINI_API_KEY is required for candidate discovery.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.2,
        system_instruction=_DISCOVERY_SYSTEM_PROMPT,
    )

    prompt = f"Search and discover the top publicly traded companies in the following AI supply chain area: {theme}"

    response = client.models.generate_content(
        model=RADAR_MODEL,
        contents=prompt,
        config=config,
    )

    parsed = _extract_json_payload(response.text or "")
    raw_list = parsed.get("candidates", [])
    if not raw_list:
        log.warning("No candidates found in model response: %r", response.text)

    candidates: list[CandidateCompany] = []
    conn = init_db(db_path) if stage_to_db else None

    try:
        for c in raw_list:
            cand = CandidateCompany(
                ticker=c["ticker"],
                name=c.get("name", c["ticker"]),
                leg=c.get("leg", "US"),
                layer=c.get("layer", "L3"),
                source=f"radar:{theme[:30]}",
                status="discovered",
                pure_play_est=float(c.get("pure_play_est", 50.0)),
                supply_role=c.get("supply_role", ""),
                key_customers=c.get("key_customers", []),
                notes=c.get("notes", ""),
            )
            candidates.append(cand)

            if stage_to_db and conn:
                upsert_candidate(conn, {
                    "ticker": cand.ticker,
                    "name": cand.name,
                    "leg": cand.leg,
                    "layer": cand.layer,
                    "source": cand.source,
                    "discovered_at": cand.discovered_at,
                    "status": cand.status,
                    "pure_play_est": cand.pure_play_est,
                    "supply_role": cand.supply_role,
                    "key_customers_json": cand.key_customers,
                    "notes": cand.notes,
                })
    finally:
        if conn:
            conn.close()

    return candidates
