"""双价值链 (dual AI value-chain) market-cap computation.

Aggregates per-layer, per-leg market cap for the constituent companies listed
in config/value_chain.yaml. Constituents already covered by the scored
72-name ARF universe reuse that day's fetched market cap instead of a second
network round-trip; a handful of tickers outside the universe are fetched
directly; private/pre-IPO names use a manually maintained static valuation
(see config/value_chain.yaml for the update convention).
"""
import json
import logging
from datetime import date
from pathlib import Path

import yaml

from arf.config import UniverseEntry
from arf.fetchers.base import StockData
from arf.fetchers.china import fetch_china
from arf.fetchers.us import fetch_us

log = logging.getLogger(__name__)


def load_value_chain_config(path: Path = Path("config/value_chain.yaml")) -> list[dict]:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return raw["layers"]


def _fetch_extra(ticker: str, leg: str, as_of: date) -> float | None:
    """Fetch market cap for a ticker that's outside the scored ARF universe."""
    entry = UniverseEntry(
        ticker=ticker, name=ticker, leg=leg, layer=None,
        pure_play_pct=0.0, primary_exchange="", policy_premium=False,
    )
    try:
        sd: StockData = fetch_us(entry, as_of) if leg == "US" else fetch_china(entry, as_of)
        return sd.market_cap_usd
    except Exception:
        log.warning("value_chain: extra fetch failed for %s", ticker, exc_info=True)
        return None


def compute_value_chain(
    as_of: date,
    universe_market_caps: dict[str, float],
    config_path: Path = Path("config/value_chain.yaml"),
) -> list[dict]:
    """Compute per-layer/leg market-cap totals for the dual value-chain page.

    `universe_market_caps` maps ticker -> market_cap_usd from the day's
    already-fetched scored ARF universe.

    Returns a list of dicts ready for arf.db.upsert_value_chain: one row per
    (leg, layer) with a `market_cap_usd` total and a `constituents_json`
    breakdown (name, market_cap_usd, source) for hover text. A constituent
    whose market cap can't be resolved is logged and excluded from the total
    rather than treated as zero.
    """
    layers = load_value_chain_config(config_path)
    rows: list[dict] = []
    for layer_cfg in layers:
        layer = layer_cfg["layer"]
        layer_name = layer_cfg["name"]
        for leg in ("US", "China"):
            constituents = []
            total = 0.0
            for company in layer_cfg.get(leg, []):
                name = company["name"]
                source = company["source"]
                if source == "static":
                    cap = company["static_usd_b"] * 1e9
                elif source == "universe":
                    cap = universe_market_caps.get(company["ticker"])
                elif source == "extra":
                    cap = _fetch_extra(company["ticker"], leg, as_of)
                else:
                    raise ValueError(f"Unknown source {source!r} for {name} in value_chain.yaml")

                if cap is None:
                    log.warning(
                        "value_chain: no market cap for %s (%s) — excluded from %s/%s total",
                        name, company.get("ticker"), leg, layer,
                    )
                    continue
                total += cap
                constituents.append({"name": name, "market_cap_usd": cap, "source": source})

            rows.append({
                "leg": leg,
                "layer": layer,
                "layer_name": layer_name,
                "market_cap_usd": total,
                "constituents_json": json.dumps(constituents, ensure_ascii=False),
            })
    return rows
