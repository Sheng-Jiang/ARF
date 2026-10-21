"""ARF Autonomous Investment Research Agent package."""
from arf.agent.radar import discover_supply_chain_candidates, scan_valuation_anomalies
from arf.agent.schemas import (
    CandidateCompany,
    DecisionAction,
    GateVerdict,
    InvestmentDecisionRecord,
    OpportunityCard,
    OpportunityStage,
    QuantFactorSnapshot,
)
from arf.agent.thesis import compile_investment_decision_record, generate_opportunity_card
from arf.agent.tools import (
    fetch_external_candidate,
    get_stock_quant_profile,
    query_quant_database,
    search_value_chain_layer,
)

__all__ = [
    "CandidateCompany",
    "DecisionAction",
    "GateVerdict",
    "InvestmentDecisionRecord",
    "OpportunityCard",
    "OpportunityStage",
    "QuantFactorSnapshot",
    "compile_investment_decision_record",
    "discover_supply_chain_candidates",
    "fetch_external_candidate",
    "generate_opportunity_card",
    "get_stock_quant_profile",
    "query_quant_database",
    "scan_valuation_anomalies",
    "search_value_chain_layer",
]
