import datetime
from typing import Any

from pydantic import BaseModel


class AkshareParams(BaseModel):
    """Parameters for AkShare market data fetching."""
    symbol: str
    period: str
    start_date: str
    end_date: str
    adjust: str

class BacktraderParams(BaseModel):
    """Parameters for Backtrader backtesting execution."""
    start_date: datetime.date
    end_date: datetime.date
    start_cash: float
    commission_fee: float
    # Percent of available equity deployed per trade (PercentSizer). Defaults to
    # 95% to leave headroom for commission so buy orders aren't rejected.
    sizer_percent: float = 95.0
    # Legacy fixed share count — retained for backward compatibility; no longer
    # used now that backtests size by percent of equity.
    stake: int = 100

class StrategyBase(BaseModel):
    """Schema representing a trading strategy and its parameter ranges for optimization."""
    name: str
    params: dict[str, Any]
