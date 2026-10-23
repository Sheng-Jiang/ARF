"""AI CIO replay engine.

The cockpit does not invent a portfolio: it replays the ARF mandate over the
US leg with the same engine `aihf backtest` uses, then reads the last
`SessionRecord` to build the book, the pending orders and the scorecard.

This module is deliberately Streamlit-free so it can be unit-tested and run
from a notebook. Data loading lives in `webapp.data` for the webapp and in
`arf.storage` for the batch job.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from hedge_fund.backtesting import FundBacktestResult, backtest_fund
from hedge_fund.data.models import (
    CompanyFacts,
    CompanyNews,
    Earnings,
    EarningsRecord,
    FinancialMetrics,
    InsiderTrade,
    Price,
    PriceSnapshot,
)
from hedge_fund.fund import Fund, load_spec
from hedge_fund.scorecard import Scorecard, score
from hedge_fund.signals import ALPHA_MODEL_REGISTRY

LAYER_LABELS = {
    "L1": "L1 能源与算力中心",
    "L2": "L2 芯片与硬件系统",
    "L3": "L3 网络与光互联",
    "L4": "L4 云计算与基础模型",
    "L5": "L5 行业 AI 软件应用",
}


def default_mandate_path() -> Path:
    """The ARF mandate shipped with this repository/image."""
    return Path(__file__).resolve().parents[1] / "config" / "arf-mandate.yaml"


class PreloadedDataClient:
    """A DataClient that serves prices already read from ARF's DuckDB.

    The webapp cannot open its own read-only DuckDB connection while it holds
    the shared read-write one, and a replay asks for a rolling window on every
    session. Preloading the frames once and slicing them in memory avoids both
    problems. Fundamental/news methods return empty because the ARF mandate
    only staffs the quant `arf` model.
    """

    def __init__(self, prices: dict[str, pd.DataFrame]) -> None:
        self._frames = {ticker.strip().upper(): frame for ticker, frame in prices.items()}
        self._bars: dict[str, list[Price]] = {}

    def _all_bars(self, ticker: str) -> list[Price]:
        ticker = ticker.strip().upper()
        if ticker not in self._bars:
            frame = self._frames.get(ticker)
            self._bars[ticker] = self._to_prices(frame) if frame is not None else []
        return self._bars[ticker]

    @staticmethod
    def _to_prices(frame: pd.DataFrame) -> list[Price]:
        bars: list[Price] = []
        for row in frame.itertuples(index=False):
            close = row.close
            if close is None or pd.isna(close) or close <= 0:
                continue
            bars.append(
                Price(
                    time=f"{pd.Timestamp(row.date):%Y-%m-%d}T20:00:00Z",
                    open=float(row.open) if pd.notna(row.open) else float(close),
                    high=float(row.high) if pd.notna(row.high) else float(close),
                    low=float(row.low) if pd.notna(row.low) else float(close),
                    close=float(close),
                    volume=int(row.volume) if pd.notna(row.volume) else 0,
                )
            )
        return bars

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        interval: str = "day",
        interval_multiplier: int = 1,
        **kwargs: Any,
    ) -> list[Price]:
        if interval != "day":
            return []
        start = start_date[:10]
        end = end_date[:10]
        return [bar for bar in self._all_bars(ticker) if start <= bar.time[:10] <= end]

    def get_snapshot(self, ticker: str) -> PriceSnapshot | None:
        bars = self._all_bars(ticker)
        if not bars:
            return None
        last = bars[-1]
        return PriceSnapshot(ticker=ticker.strip().upper(), price=last.close, time=last.time)

    def get_financial_metrics(
        self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10
    ) -> list[FinancialMetrics]:
        return []

    def get_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[CompanyNews]:
        return []

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[InsiderTrade]:
        return []

    def get_company_facts(self, ticker: str) -> CompanyFacts | None:
        return None

    def get_earnings(self, ticker: str) -> Earnings | None:
        return None

    def get_earnings_history(
        self, ticker: str, limit: int = 12
    ) -> list[EarningsRecord]:
        return []

    def get_market_cap(self, ticker: str, end_date: str) -> float | None:
        return None


@dataclass
class CockpitState:
    """Everything the page renders, derived from one replay."""

    kpis: dict[str, float | int | None]
    positions: pd.DataFrame
    layer_exposure: pd.DataFrame
    staged_orders: pd.DataFrame
    clamps: pd.DataFrame
    pod_weights: pd.DataFrame
    nav_curve: pd.DataFrame
    scorecard: Scorecard | None
    last_session: str
    order_note: str = ""
    notes: list[str] = field(default_factory=list)


def run_replay(
    *,
    snapshots_df: pd.DataFrame,
    prices: dict[str, pd.DataFrame],
    mandate_path: str | Path,
    universe: list[str] | tuple[str, ...],
    start: str,
    end: str,
) -> FundBacktestResult:
    """Replay the mandate over *universe* using preloaded ARF inputs."""

    spec = load_spec(Path(mandate_path))
    models: dict[str, list[Any]] = {}
    for strategy in spec.strategies:
        staff: list[Any] = []
        for model_spec in strategy.models:
            cls = ALPHA_MODEL_REGISTRY[model_spec.name]
            params = dict(model_spec.params)
            if model_spec.name == "arf":
                params["snapshots_df"] = snapshots_df
            staff.append(cls(**params))
        models[strategy.name] = staff

    fund = Fund(spec, models=models)
    client = PreloadedDataClient(prices)
    return backtest_fund(fund, start, end, client, list(universe))


def replay_window(as_of: date, days: int = 120) -> tuple[str, str]:
    """A replay window ending at *as_of*, long enough for several rebalances."""
    return (as_of - timedelta(days=days)).isoformat(), as_of.isoformat()


def build_cockpit(
    result: FundBacktestResult,
    *,
    snapshot_df: pd.DataFrame,
    spec_path: str | Path,
) -> CockpitState:
    """Turn a completed replay into the cockpit's tables and KPI values."""
    spec = load_spec(Path(spec_path))
    last = result.records[-1]
    snapshot = snapshot_df.set_index("ticker", drop=False) if not snapshot_df.empty else None

    positions_rows: list[dict[str, Any]] = []
    layer_values: dict[str, float] = {}
    for ticker, shares in last.positions.items():
        if not shares:
            continue
        mark = last.marks.get(ticker) or last.price_at(ticker) or 0.0
        value = shares * mark
        meta = snapshot.loc[ticker] if snapshot is not None and ticker in snapshot.index else None
        layer = str(meta["layer"]) if meta is not None else "—"
        weight = value / last.nav if last.nav else 0.0
        positions_rows.append({
            "代码": ticker,
            "公司": meta["name"] if meta is not None else ticker,
            "方向": "LONG" if shares > 0 else "SHORT",
            "层级": layer,
            "持股数": int(shares),
            "收盘价": round(float(mark), 2),
            "持仓市值 ($)": round(float(value), 0),
            "组合权重": weight,
            "单票上限 (20%)": "⚠️ 超限" if abs(weight) > spec.risk.max_position_pct else "✅ 达标",
        })
        layer_values[layer] = layer_values.get(layer, 0.0) + value

    layer_rows = [
        {"Layer": LAYER_LABELS.get(layer, layer), "Exposure": layer_values.get(layer, 0.0)}
        for layer in sorted(LAYER_LABELS)
    ]

    decision = last.decision
    last_cycle = next(
        (record.executed for record in reversed(result.records) if record.executed is not None),
        None,
    )
    order_rows: list[dict[str, Any]] = []
    order_note = ""
    if decision is not None:
        # A decision made at the last close: derive the shares it would trade.
        for ticker, weight in decision.final_weights.items():
            mark = decision.marks.get(ticker) or last.marks.get(ticker)
            if not mark:
                continue
            target = round(weight * last.nav / mark)
            delta = target - last.positions.get(ticker, 0)
            if delta == 0:
                continue
            order_rows.append({
                "代码": ticker,
                "操作": "BUY" if delta > 0 else "SELL",
                "数量": abs(int(delta)),
                "预估成交价": round(float(mark), 2),
                "金额 ($)": round(abs(delta) * float(mark), 0),
                "目标权重": weight,
            })
        order_note = f"待执行决策 · {decision.as_of}"
    elif last_cycle is not None:
        # The replay window ended between rebalances: show what was last done.
        for order in last_cycle.orders:
            order_rows.append({
                "代码": order.ticker,
                "操作": order.side.upper(),
                "数量": order.quantity,
                "预估成交价": round(float(order.price), 2),
                "金额 ($)": round(order.quantity * float(order.price), 0),
                "目标权重": last_cycle.final_weights.get(order.ticker),
            })
        order_note = f"最近一次已执行调仓 · {last_cycle.as_of}"

    clamp_source = decision.clamps if decision is not None else (
        last_cycle.clamps if last_cycle is not None else []
    )
    clamp_rows = [
        {
            "Ticker": clamp.ticker or "FUND",
            "Limit": clamp.limit,
            "Before": clamp.before,
            "After": clamp.after,
            "Status": "Clamped" if clamp.before != clamp.after else "Passed",
        }
        for clamp in clamp_source
    ]

    net = sum(shares * (last.marks.get(t, 0.0) or 0.0) for t, shares in last.positions.items())
    gross = sum(
        abs(shares * (last.marks.get(t, 0.0) or 0.0))
        for t, shares in last.positions.items()
    )
    metrics = result.metrics
    kpis: dict[str, float | int | None] = {
        "nav": float(last.nav),
        "total_return": float(metrics.total_return_pct),
        "cash": float(last.cash),
        "cash_pct": float(last.cash / last.nav) if last.nav else None,
        "net_exposure": float(net / last.nav) if last.nav else None,
        "gross_exposure": float(gross / last.nav) if last.nav else None,
        "excess_return": float(metrics.excess_return_pct),
        "benchmark_return": float(metrics.benchmark_return_pct),
        "sharpe": float(metrics.sharpe_ratio),
        "max_drawdown": float(metrics.max_drawdown_pct),
        "n_cycles": int(metrics.n_cycles),
        "n_orders": int(metrics.n_orders),
    }

    nav_curve = pd.DataFrame({
        "Date": pd.to_datetime(result.dates),
        "ARF Fund NAV": result.nav,
        "SPY Benchmark": result.benchmark_nav,
    })

    pod_weights = pd.DataFrame([
        {
            "Pod": strategy.display_name or strategy.name,
            "Weight": strategy.weight,
            "Models": ", ".join(model.name for model in strategy.models),
        }
        for strategy in spec.strategies
    ])

    notes: list[str] = []
    if decision is None:
        notes.append("回放窗口在两次调仓之间结束；订单表显示最近一次已执行调仓。")

    try:
        scorecard = score(result.records)
    except ValueError as exc:
        scorecard = None
        notes.append(f"计分卡不可用：{exc}")

    return CockpitState(
        kpis=kpis,
        positions=pd.DataFrame(positions_rows),
        layer_exposure=pd.DataFrame(layer_rows),
        staged_orders=pd.DataFrame(order_rows),
        clamps=pd.DataFrame(clamp_rows),
        pod_weights=pod_weights,
        nav_curve=nav_curve,
        scorecard=scorecard,
        last_session=last.session,
        order_note=order_note,
        notes=notes,
    )


def fetch_benchmark(ticker: str, start: date, end: date) -> pd.DataFrame:
    """Benchmark bars for the replay; ARF's yfinance fetcher has retries."""
    from arf.fetchers.prices import fetch_daily_prices_any

    return fetch_daily_prices_any(ticker, start.isoformat(), end.isoformat())
