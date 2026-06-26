import datetime
from typing import Any, Dict
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
    stake: int

class StrategyBase(BaseModel):
    """Schema representing a trading strategy and its parameter ranges for optimization."""
    name: str
    params: Dict[str, Any]
