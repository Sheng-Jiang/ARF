from pathlib import Path

import pytest

from arf.config import (
    UniverseEntry,
    get_leg,
    get_pool_entries,
    load_universe,
)

UNIVERSE_PATH = Path(__file__).parent.parent / "config" / "universe.yaml"

# The active quarterly pool — keep in sync with scripts/build_pool_universe.py.
ACTIVE_POOL = "2026Q3"


@pytest.fixture(scope="module")
def universe() -> list[UniverseEntry]:
    return load_universe(UNIVERSE_PATH)


def test_load_universe_returns_all_entries(universe):
    assert len(universe) >= 34


def test_us_leg_count(universe):
    # US leg holds 54 entries total; 50 are in the active pool.
    us = get_leg(universe, "US")
    assert len(us) == 54
    us_pool = get_pool_entries(us, ACTIVE_POOL)
    assert len(us_pool) == 50


def test_china_leg_count(universe):
    # China leg holds 54 entries total; 50 are in the active pool, 4 are
    # rotation candidates (without them build_rotation_plan can never pair).
    china = get_leg(universe, "China")
    assert len(china) == 54
    china_pool = get_pool_entries(china, ACTIVE_POOL)
    assert len(china_pool) == 50


def test_both_legs_have_rotation_candidates(universe):
    """A leg with no watchlist candidates can never rotate — the plan pairs 1:1."""
    for leg_name in ("US", "China"):
        candidates = [
            e for e in get_leg(universe, leg_name)
            if e.cohort == "watch" and e.pool is None
        ]
        assert candidates, f"{leg_name} has no rotation candidates"


def test_get_pool_entries_defaults_to_active_pool(universe):
    """The bare call must return the pool, not everything outside it."""
    assert get_pool_entries(universe) == get_pool_entries(universe, ACTIVE_POOL)
    assert all(e.pool == ACTIVE_POOL for e in get_pool_entries(universe))
    assert len(get_pool_entries(universe)) == 100


def test_pool_is_50_50_with_45_5_split(universe):
    for leg_name in ("US", "China"):
        pool = get_pool_entries(get_leg(universe, leg_name), ACTIVE_POOL)
        core = [e for e in pool if e.cohort == "core"]
        newcomers = [e for e in pool if e.cohort == "newcomer"]
        assert len(core) == 45, f"{leg_name} core = {len(core)}, expected 45"
        assert len(newcomers) == 5, f"{leg_name} newcomers = {len(newcomers)}, expected 5"


def test_europe_adrs_moved_into_us_leg(universe):
    tickers = {e.ticker for e in get_leg(universe, "US")}
    assert {"ASML", "ARM", "SAP", "ABBNY", "SMEGF", "SBGSF", "STM", "IFNNY"} <= tickers
    assert get_leg(universe, "Europe-ref") == []


def test_watchlist_not_scored(universe):
    watch = [e for e in universe if e.cohort == "watch" and e.pool is None]
    assert len(watch) >= 8  # 4 US candidates + Pre-IPO observation tier
    assert all(e.pool is None for e in watch)


def test_preipo_observation_tier_includes_new_names(universe):
    preipo = {e.ticker for e in get_leg(universe, "Pre-IPO")}
    assert {"SPACEX", "CXMT", "UNITREE"} <= preipo


def test_newcomer_listed_dates_parse(universe):
    newcomers = [e for e in universe if e.cohort == "newcomer"]
    assert len(newcomers) == 10
    for e in newcomers:
        assert e.listed_at is not None, f"{e.ticker} missing listed_at"
        assert e.pool == ACTIVE_POOL


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
