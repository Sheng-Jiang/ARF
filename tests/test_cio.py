"""Tests for the AI CIO replay engine's pure pieces."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

pytest.importorskip("hedge_fund")

from hedge_fund.backtesting import FundBacktestMetrics, FundBacktestResult  # noqa: E402
from hedge_fund.fund import load_spec  # noqa: E402
from hedge_fund.pipeline.models import DecisionRecord  # noqa: E402
from hedge_fund.pipeline.session import SessionRecord  # noqa: E402
from hedge_fund.risk.limits import ClampEvent  # noqa: E402

from arf.cio import (  # noqa: E402
    PreloadedDataClient,
    build_cockpit,
    default_mandate_path,
    replay_window,
)


def _frames() -> dict[str, pd.DataFrame]:
    return {
        "NVDA": pd.DataFrame({
            "ticker": ["NVDA", "NVDA"],
            "date": [date(2026, 10, 1), date(2026, 10, 2)],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1000, 1100],
        }),
    }


class TestPreloadedDataClient:
    def test_slices_bars_by_date(self):
        client = PreloadedDataClient(_frames())
        bars = client.get_prices("nvda", "2026-10-01", "2026-10-01")
        assert [bar.close for bar in bars] == [101.0]
        assert bars[0].time == "2026-10-01T20:00:00Z"

    def test_rejects_intraday(self):
        client = PreloadedDataClient(_frames())
        assert client.get_prices("NVDA", "2026-10-01", "2026-10-02", interval="minute") == []

    def test_snapshot_is_the_last_bar(self):
        snapshot = PreloadedDataClient(_frames()).get_snapshot("NVDA")
        assert snapshot is not None
        assert snapshot.price == 102.0

    def test_missing_fundamentals_are_empty_not_fabricated(self):
        client = PreloadedDataClient(_frames())
        assert client.get_financial_metrics("NVDA", "2026-10-02") == []
        assert client.get_company_facts("NVDA") is None


def _synthetic_result() -> FundBacktestResult:
    spec = load_spec(default_mandate_path())
    decision = DecisionRecord(
        fund=spec.name,
        as_of="2026-10-17",
        spec=spec,
        universe=["NVDA", "MSFT"],
        marks={"NVDA": 100.0, "MSFT": 200.0},
        skipped=[],
        strategies=[],
        target_weights={"NVDA": 0.2, "MSFT": -0.2},
        clamps=[ClampEvent(limit="max_position_pct", ticker="MSFT", before=0.25, after=0.20)],
        final_weights={"NVDA": 0.2, "MSFT": -0.2},
    )
    record = SessionRecord(
        fund=spec.name,
        session="2026-10-18",
        universe=["NVDA", "MSFT"],
        nav=100_000.0,
        cash=70_000.0,
        positions={"NVDA": 100, "MSFT": -50},
        marks={"NVDA": 100.0, "MSFT": 200.0},
        benchmark="SPY",
        benchmark_close=500.0,
        rebalance=True,
        decision=decision,
        code_version="test",
        mandate_hash="test",
    )
    metrics = FundBacktestMetrics(
        total_return_pct=0.05,
        annualized_return_pct=0.10,
        sharpe_ratio=1.2,
        max_drawdown_pct=0.03,
        benchmark_return_pct=0.02,
        excess_return_pct=0.03,
        n_cycles=1,
        n_orders=2,
    )
    return FundBacktestResult(
        fund=spec.name,
        start="2026-10-01",
        end="2026-10-18",
        rebalance="weekly",
        benchmark="SPY",
        universe=["NVDA", "MSFT"],
        capital=100_000.0,
        dates=["2026-10-18"],
        nav=[100_000.0],
        benchmark_nav=[100_000.0],
        metrics=metrics,
        records=[record],
    )


class TestBuildCockpit:
    @pytest.fixture
    def snapshot_df(self):
        return pd.DataFrame([
            {"ticker": "NVDA", "name": "NVIDIA", "layer": "L2"},
            {"ticker": "MSFT", "name": "Microsoft", "layer": "L4"},
        ])

    def test_book_orders_and_clamps_come_from_the_record(self, snapshot_df):
        cockpit = build_cockpit(
            _synthetic_result(), snapshot_df=snapshot_df, spec_path=default_mandate_path()
        )
        assert cockpit.last_session == "2026-10-18"
        assert cockpit.kpis["nav"] == 100_000.0
        assert cockpit.kpis["net_exposure"] == pytest.approx(0.0)
        assert cockpit.kpis["gross_exposure"] == pytest.approx(0.2)

        book = cockpit.positions.set_index("代码")
        assert book.loc["NVDA", "方向"] == "LONG"
        assert book.loc["MSFT", "方向"] == "SHORT"
        assert book.loc["NVDA", "层级"] == "L2"

        orders = cockpit.staged_orders.set_index("代码")
        # Target 20% of 100k at 100 = 200 shares; 100 already held.
        assert orders.loc["NVDA", "操作"] == "BUY"
        assert orders.loc["NVDA", "数量"] == 100
        # Target -20% at 200 = -100 shares; -50 already held.
        assert orders.loc["MSFT", "操作"] == "SELL"
        assert orders.loc["MSFT", "数量"] == 50

        assert len(cockpit.clamps) == 1
        assert cockpit.clamps.iloc[0]["Ticker"] == "MSFT"

        layers = cockpit.layer_exposure.set_index("Layer")
        assert layers.loc["L2 芯片与硬件系统", "Exposure"] == 10_000.0
        assert layers.loc["L4 云计算与基础模型", "Exposure"] == -10_000.0

    def test_replay_window_ends_on_as_of(self):
        start, end = replay_window(date(2026, 10, 18), days=30)
        assert end == "2026-10-18"
        assert start == "2026-09-18"

    def test_mandate_ships_with_the_package(self):
        assert default_mandate_path().exists()
