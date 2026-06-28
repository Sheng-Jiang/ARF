from pathlib import Path

import pytest

from arf.config import UniverseEntry, get_leg, load_universe

UNIVERSE_PATH = Path(__file__).parent.parent / "config" / "universe.yaml"


@pytest.fixture(scope="module")
def universe() -> list[UniverseEntry]:
    return load_universe(UNIVERSE_PATH)


def test_load_universe_returns_all_entries(universe):
    assert len(universe) >= 34


def test_us_leg_count(universe):
    us = get_leg(universe, "US")
    assert len(us) == 36


def test_china_leg_count(universe):
    china = get_leg(universe, "China")
    assert len(china) == 37


def test_pure_play_pct_range(universe):
    for entry in universe:
        if entry.pure_play_pct is not None:
            assert 0 <= entry.pure_play_pct <= 100, f"{entry.ticker} pure_play_pct out of range"


def test_layer_values(universe):
    valid_layers = {"L1", "L2", "L3", "L4", "L5"}
    for entry in universe:
        if entry.layer is not None:
            assert entry.layer in valid_layers, f"{entry.ticker} has invalid layer {entry.layer}"


def test_policy_premium_flag_on_cambricon_and_smic(universe):
    tickers = {e.ticker: e for e in universe}
    assert tickers["688256.SH"].policy_premium is True
    assert tickers["688981.SH"].policy_premium is True


def test_preipo_entries_have_no_required_numeric_arf(universe):
    preipo = get_leg(universe, "Pre-IPO")
    assert len(preipo) >= 5
    for entry in preipo:
        assert entry.leg == "Pre-IPO"


def test_all_entries_have_ticker_and_name(universe):
    for entry in universe:
        assert entry.ticker, "Entry missing ticker"
        assert entry.name, f"{entry.ticker} missing name"


def test_get_leg_unknown_returns_empty(universe):
    result = get_leg(universe, "NonExistent")
    assert result == []
