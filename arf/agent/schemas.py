"""Data schemas for ARF Autonomous Investment Agent."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class CandidateCompany(BaseModel):
    """A company discovered by the Radar Agent staged for qualification."""
    ticker: str
    name: str = ""
    leg: Literal["US", "China"] = "US"
    layer: Literal["L1", "L2", "L3", "L4", "L5"] | None = None
    source: str = "radar"
    discovered_at: date = Field(default_factory=date.today)
    status: Literal["discovered", "qualified", "monitored", "rejected"] = "discovered"
    pure_play_est: float | None = None
    supply_role: str = ""
    key_customers: list[str] = Field(default_factory=list)
    notes: str = ""


class QuantFactorSnapshot(BaseModel):
    """Quantitative baseline extracted from ARF engine tools."""
    ticker: str
    name: str
    leg: str
    layer: str | None = None
    as_of_date: str | date = ""
    price: float | None = None
    market_cap_usd: float | None = None
    arf: float | None = None
    decile: int | None = None
    e_score: float | None = None
    v_score: float | None = None
    froth_flag: bool = False
    roe: float | None = None
    forward_pe: float | None = None
    ps_ratio: float | None = None
    revenue_yoy_growth: float | None = None
    gross_margin: float | None = None
    implied_growth: float | None = None
    implied_growth_gap: float | None = None
    technical_score: float | None = None
    chip_profit_ratio: float | None = None
    chip_avg_cost: float | None = None
    ma_bullish: bool = False


class OpportunityCard(BaseModel):
    """Standardized institutional opportunity memo produced by the Agent."""
    thesis_id: str
    ticker: str
    name: str
    leg: str
    layer: str | None = None
    as_of_date: str
    thesis_type: Literal["long_opportunity", "garp_value", "froth_short", "neutral_watch"]
    title: str
    
    # Financial metrics snapshot
    quant_profile: QuantFactorSnapshot | None = None
    
    # Qualitative multi-perspective debate
    bull_case: str
    bear_case: str
    synthesis: str
    
    # Tactical action plan
    valuation_entry_zone: str
    invalidation_criteria: str
    confidence_score: float = Field(default=50.0, ge=0.0, le=100.0)
    catalysts: list[str] = Field(default_factory=list)
    citations: list[dict[str, str]] = Field(default_factory=list)
    model: str = "gemini-3.7-flash"
