from dataclasses import dataclass
from datetime import date


@dataclass
class StockData:
    ticker: str
    as_of_date: date

    # Market data
    price: float | None = None
    market_cap_usd: float | None = None
    ev_usd: float | None = None
    shares_outstanding: float | None = None

    # Trailing fundamentals (TTM)
    revenue_ttm: float | None = None
    revenue_yoy_growth: float | None = None
    gross_margin: float | None = None
    operating_income: float | None = None
    net_income: float | None = None
    net_income_excl_nonrecurring: float | None = None  # 扣非, China names
    free_cash_flow: float | None = None
    total_equity: float | None = None
    roe: float | None = None
    roic: float | None = None

    # Forward estimates
    forward_pe: float | None = None
    eps_2yr_cagr: float | None = None
    revenue_3yr_cagr: float | None = None
    revenue_ntm: float | None = None

    # Valuation ratios
    ps_ratio: float | None = None
    ev_sales: float | None = None
    ev_sales_5yr_percentile: float | None = None

    # Metadata
    currency: str = "USD"
    fx_rate_usd: float = 1.0
    data_source: str = ""
