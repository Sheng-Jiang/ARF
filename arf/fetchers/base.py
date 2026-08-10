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
    currency: str = "USD"           # trading currency of the quote
    fx_rate_usd: float = 1.0        # units of `currency` per USD
    # Currency the income/cash-flow statements are reported in. For ADRs this
    # differs from `currency`: BABA/BIDU/PDD trade in USD but report in CNY,
    # TSM trades in USD but reports in TWD. The reverse-DCF divides market cap
    # by FCF, so it needs the market cap in *this* currency, not the trading
    # one. Defaults track `currency` when a fetcher does not set them.
    financial_currency: str | None = None
    financial_fx_usd: float | None = None   # units of financial_currency per USD
    data_source: str = ""
