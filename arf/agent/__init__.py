"""ARF Autonomous Investment Research Agent package."""
from typing import Any

from arf.agent.radar import discover_supply_chain_candidates, scan_valuation_anomalies
from arf.agent.schemas import (
    CandidateCompany,
    CIODecisionPacket,
    DecisionAction,
    GateVerdict,
    InvestmentDecisionRecord,
    KillCondition,
    OpportunityCard,
    OpportunityStage,
    ProposalTicket,
    QuantFactorSnapshot,
    WatchdogAlert,
)
from arf.agent.thesis import compile_investment_decision_record, generate_opportunity_card
from arf.agent.tools import (
    fetch_external_candidate,
    get_stock_quant_profile,
    query_quant_database,
    search_value_chain_layer,
)

_CIO_LOOP_EXPORTS = {
    "build_cio_decision_packet",
    "default_kill_conditions_for_row",
    "evaluate_cio_gates",
    "evaluate_thesis_watchdog",
    "scan_material_deltas",
    "simulate_supply_chain_shock",
}


def __getattr__(name: str) -> Any:
    if name in _CIO_LOOP_EXPORTS:
        from arf.agent import cio_loop
        return getattr(cio_loop, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "CIODecisionPacket",
    "CandidateCompany",
    "DecisionAction",
    "GateVerdict",
    "InvestmentDecisionRecord",
    "KillCondition",
    "OpportunityCard",
    "OpportunityStage",
    "ProposalTicket",
    "QuantFactorSnapshot",
    "WatchdogAlert",
    "build_cio_decision_packet",
    "compile_investment_decision_record",
    "default_kill_conditions_for_row",
    "discover_supply_chain_candidates",
    "evaluate_cio_gates",
    "evaluate_thesis_watchdog",
    "fetch_external_candidate",
    "generate_opportunity_card",
    "get_stock_quant_profile",
    "query_quant_database",
    "scan_material_deltas",
    "scan_valuation_anomalies",
    "search_value_chain_layer",
    "simulate_supply_chain_shock",
]
