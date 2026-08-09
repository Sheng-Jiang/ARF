from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

import yaml

Leg = Literal["US", "China", "Europe-ref", "Pre-IPO"]
Layer = Literal["L1", "L2", "L3", "L4", "L5"]
Cohort = Literal["core", "newcomer", "watch"]


@dataclass
class UniverseEntry:
    ticker: str
    name: str
    leg: Leg
    layer: Layer | None
    pure_play_pct: float
    primary_exchange: str
    policy_premium: bool
    notes: str = field(default="")
    # Quarterly-pool fields (see scripts/build_pool_universe.py).
    cohort: Cohort = "watch"          # core | newcomer | watch
    pool: str | None = None           # active quarter id, e.g. "2026Q3"
    listed_at: date | None = None     # first public listing date


def _parse_date(value: object) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def load_universe(path: Path = Path("config/universe.yaml")) -> list[UniverseEntry]:
    with open(path) as f:
        raw = yaml.safe_load(f)
    entries = []
    for item in raw:
        entries.append(
            UniverseEntry(
                ticker=str(item["ticker"]),
                name=str(item["name"]),
                leg=item["leg"],
                layer=item.get("layer"),
                pure_play_pct=float(item.get("pure_play_pct", 0)),
                primary_exchange=str(item.get("primary_exchange", "")),
                policy_premium=bool(item.get("policy_premium", False)),
                notes=str(item.get("notes", "")),
                cohort=item.get("cohort", "watch"),
                pool=item.get("pool"),
                listed_at=_parse_date(item.get("listed_at")),
            )
        )
    return entries


def get_leg(universe: list[UniverseEntry], leg: str) -> list[UniverseEntry]:
    return [e for e in universe if e.leg == leg]


def get_pool_entries(
    universe: list[UniverseEntry], pool: str | None = None
) -> list[UniverseEntry]:
    """Entries in the active pool (or a specific quarter); excludes watchlist."""
    return [e for e in universe if e.pool == pool]


def get_cohort(universe: list[UniverseEntry], cohort: str) -> list[UniverseEntry]:
    return [e for e in universe if e.cohort == cohort]
