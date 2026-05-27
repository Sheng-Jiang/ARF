from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

Leg = Literal["US", "China", "Europe-ref", "Pre-IPO"]
Layer = Literal["L1", "L2", "L3", "L4", "L5"]


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
            )
        )
    return entries


def get_leg(universe: list[UniverseEntry], leg: str) -> list[UniverseEntry]:
    return [e for e in universe if e.leg == leg]
