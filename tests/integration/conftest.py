from datetime import date
from pathlib import Path

import pytest

from arf.config import UniverseEntry, load_universe

_UNIVERSE_PATH = Path(__file__).parent.parent.parent / "config" / "universe.yaml"


@pytest.fixture(scope="session")
def universe() -> list[UniverseEntry]:
    return load_universe(_UNIVERSE_PATH)


@pytest.fixture(scope="session")
def today() -> date:
    return date.today()
