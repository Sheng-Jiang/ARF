"""Data schemas for ARF Autonomous Investment Agent."""
from __future__ import annotations

import math
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class OpportunityStage(StrEnum):
    """The lifecycle state machine of an Opportunity Alpha."""
    DISCOVERED = "discovered"            # Surfaced by Radar or supply chain traversal
    QUALIFIED = "qualified"              # Passes fundamental liquidity & layer alignment
    UNDER_REVIEW = "under_review"        # Actively debated by Bull/Bear research workers
    THESIS_FORMULATED = "thesis_formulated"  # 5-step IDR compiled & G3 risk gate checked
    COMMITTEE_PENDING = "committee_pending"  # Awaiting human PM review / sign-off
    ACTIVE_WATCH = "active_watch"        # Monitored on watchlist for valuation entry zone
    HARVESTED = "harvested"              # Target achieved or profit realized
    INVALIDATED = "invalidated"          # Quantitative invalidation threshold breached


class GateVerdict(StrEnum):
    """Outcome of the Outside-Model G3 mechanical risk gate."""
    PASSED = "PASSED"
    BLOCKED_FROTH = "BLOCKED_FROTH"
    BLOCKED_HURDLE = "BLOCKED_HURDLE"
    BLOCKED_VALUATION_STRETCH = "BLOCKED_VALUATION_STRETCH"
    BLOCKED_INSUFFICIENT_CRITERIA = "BLOCKED_INSUFFICIENT_CRITERIA"


class DecisionAction(StrEnum):
    """Recommended action in Step 5 of the Investment Decision Record."""
    BUY_ZONE = "BUY_ZONE"
    MONITOR = "MONITOR"
    AVOID_FROTH = "AVOID_FROTH"
    HARVEST = "HARVEST"
    INVALIDATE = "INVALIDATE"


class KillCondition(BaseModel):
    """Machine-executable thesis invalidation predicate."""
    metric: str
    operator: Literal["<", "<=", ">", ">=", "=="]
    threshold: float | bool
    description: str = ""

    def evaluate(self, metrics: dict[str, Any]) -> tuple[bool, str]:
        """Safely evaluate this kill condition against a metrics dictionary.

        Returns:
            (triggered: bool, detail: str)
        """
        val = metrics.get(self.metric)
        if val is None:
            return False, "metric missing"
        if isinstance(val, float) and math.isnan(val):
            return False, "metric missing"

        try:
            if self.operator == "==":
                if isinstance(self.threshold, bool):
                    triggered = bool(val) == bool(self.threshold)
                else:
                    triggered = float(val) == float(self.threshold)
            elif self.operator == "<":
                triggered = float(val) < float(self.threshold)
            elif self.operator == "<=":
                triggered = float(val) <= float(self.threshold)
            elif self.operator == ">":
                triggered = float(val) > float(self.threshold)
            elif self.operator == ">=":
                triggered = float(val) >= float(self.threshold)
            else:
                return False, f"unsupported operator {self.operator}"
        except (ValueError, TypeError) as exc:
            return False, f"evaluation error: {exc}"

        desc_suffix = f" ({self.description})" if self.description else ""
        if triggered:
            detail = f"{self.metric}={val} breached {self.operator} {self.threshold}{desc_suffix}"
        else:
            detail = f"{self.metric}={val} holds (not {self.operator} {self.threshold})"
        return triggered, detail


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


class InvestmentDecisionRecord(BaseModel):
    """5-step causal Investment Decision Record (IDR) ensuring complete auditability.
    
    Modelled after WoW's Agent Decision Record (ADR), this structure bridges
    quantitative factor profiles, qualitative research deliberation, deterministic
    governance gates, and operational boundary conditions.
    """
    idr_id: str
    ticker: str
    name: str
    as_of_date: str
    stage: OpportunityStage = OpportunityStage.THESIS_FORMULATED
    
    # Step 1: Trigger & Observation
    trigger_type: str = "radar_scan"
    trigger_summary: str = ""
    observed_metrics: QuantFactorSnapshot | None = None
    
    # Step 2: Normative Basis & Policy Bounds
    leg: str = "US"
    layer: str = "L3"
    cost_of_equity: float = 0.10
    policy_rules_evaluated: list[str] = Field(default_factory=list)
    
    # Step 3: Adversarial Deliberation
    bull_arguments: list[str] = Field(default_factory=list)
    bear_arguments: list[str] = Field(default_factory=list)
    deliberation_synthesis: str = ""
    
    # Step 4: Outside-Model Authority Gate (G3)
    gate_verdict: GateVerdict = GateVerdict.PASSED
    gate_details: str = ""
    froth_flag: bool = False
    hurdle_met: bool = True
    
    # Step 5: Action Taken & Operational Boundaries
    recommended_action: DecisionAction = DecisionAction.MONITOR
    valuation_entry_zone: str = ""
    invalidation_criteria: str = ""
    confidence_score: float = Field(default=50.0, ge=0.0, le=100.0)
    catalysts: list[str] = Field(default_factory=list)
    citations: list[dict[str, str]] = Field(default_factory=list)
    kill_conditions: list[KillCondition] = Field(default_factory=list)
    
    # Governance & Model Provenance
    human_pm_decision: str | None = None
    human_pm_notes: str | None = None
    model: str = "gemini-3.8-flash"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


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
    kill_conditions: list[KillCondition] = Field(default_factory=list)
    model: str = "gemini-3.8-flash"
    idr_id: str | None = None


class WatchdogAlert(BaseModel):
    """Structured alert emitted by the Executable Thesis Watchdog."""
    ticker: str
    name: str = ""
    alert_type: Literal[
        "THESIS_INVALIDATED",
        "FROTH_CIRCUIT_BREAKER",
        "HARVEST_TARGET_REACHED",
        "G_STAR_DIVERGENCE",
    ]
    severity: Literal["CRITICAL", "WARNING", "INFO"] = "WARNING"
    triggered_rule: str
    current_value: str
    recommended_action: DecisionAction


class ProposalTicket(BaseModel):
    """Actionable trade or research proposal for portfolio construction."""
    ticker: str
    name: str = ""
    leg: str = "US"
    layer: str = "L2"
    action: Literal[
        "INITIATE_LONG",
        "ADD_LONG",
        "TRIM_HARVEST",
        "EXIT_INVALIDATED",
        "SHORT_FROTH",
        "HOLD_MONITOR",
    ]
    conviction: float = Field(default=0.0, ge=-1.0, le=1.0)
    expected_beat_pct: float | None = None
    eps_surprise_prob: float | None = None
    expected_return_p50: float | None = None
    regime_breakout_prob: float | None = None
    gate_verdict: GateVerdict = GateVerdict.PASSED
    gate_details: str = ""
    rationale: str = ""
    kill_conditions: list[KillCondition] = Field(default_factory=list)


class CIODecisionPacket(BaseModel):
    """Push-first daily or event-driven decision packet from the Autonomous CIO."""
    packet_id: str
    as_of_date: str
    regime_summary: str
    shock_scenario: dict[str, float] = Field(default_factory=dict)
    watchdog_alerts: list[WatchdogAlert] = Field(default_factory=list)
    proposals: list[ProposalTicket] = Field(default_factory=list)
    markdown_brief: str = ""
