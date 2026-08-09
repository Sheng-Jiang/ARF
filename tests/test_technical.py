"""Unit tests for arf.technical indicators and scoring."""
import pandas as pd

from arf.technical import (
    calculate_chip_distribution,
    calculate_technical_indicators,
    score_history,
    score_stock_technical,
)


def test_calculate_technical_indicators():
    """Verify that technical indicators are computed correctly and without errors."""
    # Create 150 days of dummy data with a steady upward trend
    dates = pd.date_range(start="2026-01-01", periods=150, freq="D")
    close_prices = [100.0 + i * 0.5 for i in range(150)]  # 100.0 to 174.5
    high_prices = [p + 1.0 for p in close_prices]
    low_prices = [p - 1.0 for p in close_prices]
    open_prices = close_prices
    volume = [10000] * 150
    
    df = pd.DataFrame({
        "date": dates,
        "open": open_prices,
        "high": high_prices,
        "low": low_prices,
        "close": close_prices,
        "volume": volume
    })
    
    res = calculate_technical_indicators(df)
    
    # Check shape and columns
    assert len(res) == 150
    assert "ma5" in res.columns
    assert "macd_dif" in res.columns
    assert "rsi" in res.columns
    assert "bollinger_upper" in res.columns
    assert "atr" in res.columns
    
    # Since it's a steady upward trend:
    # 1. Price should be above all MAs
    latest = res.iloc[-1]
    assert latest["close"] > latest["ma5"]
    assert latest["close"] > latest["ma20"]
    assert latest["close"] > latest["ma120"]
    assert latest["ma_bullish_alignment"]
    
    # 2. RSI should be highly bullish (typically > 70 for strong steady uptrend)
    assert latest["rsi"] > 70.0
    
    # 3. Bollinger Bands upper > mid > lower
    assert latest["bollinger_upper"] > latest["bollinger_mid"]
    assert latest["bollinger_mid"] > latest["bollinger_lower"]
    
    # 4. ATR should be positive and close to the daily range (high - low = 2.0, plus gap if any)
    assert latest["atr"] > 0
    assert abs(latest["atr"] - 2.0) < 0.1

def test_calculate_chip_distribution():
    """Test the custom, cloud-safe mathematical chip distribution model."""
    # Create 150 days of dummy data
    # In the first 100 days, price is stable at 100
    # In the last 50 days, price rises to 150
    dates = pd.date_range(start="2026-01-01", periods=150, freq="D")
    close_prices = [100.0] * 100 + [100.0 + (i - 100) * 1.0 for i in range(100, 150)]  # 100 to 149
    high_prices = [p + 1.0 for p in close_prices]
    low_prices = [p - 1.0 for p in close_prices]
    volume = [5000] * 150  # 5,000 hands = 500,000 shares per day
    
    df = pd.DataFrame({
        "date": dates,
        "open": close_prices,
        "high": high_prices,
        "low": low_prices,
        "close": close_prices,
        "volume": volume
    })
    
    outstanding_shares = 100_000_000  # 100M outstanding shares
    # Daily turnover = (5000 * 100) / 100M = 500,000 / 100,000,000 = 0.005 (0.5%)
    
    profit_ratio, avg_cost, c90_min, c90_max, c70_min, c70_max = calculate_chip_distribution(
        df, outstanding_shares, lookback=150
    )
    
    # Verification:
    # 1. Profit ratio should be high since the current close (149.0) is near the historical high
    assert 0.8 <= profit_ratio <= 1.0
    
    # 2. Average cost should be between 100 and 150, skewed towards the more recent prices
    # due to exponential decay, but still influenced by the 100 days at 100
    assert 100.0 < avg_cost < 149.0
    
    # 3. Cost intervals should make sense
    assert c90_min <= c70_min
    assert c70_max <= c90_max
    assert c90_min <= avg_cost <= c90_max
    assert 99.0 <= c90_min <= 101.0  # 5th percentile should be near the initial 100 price

def test_score_stock_technical_bullish():
    """Verify that a highly bullish stock gets a high Technical Score."""
    # Mock a highly bullish row
    indicator_row = pd.Series({
        "close": 150.0,
        "ma5": 148.0,
        "ma10": 145.0,
        "ma20": 140.0,
        "ma30": 138.0,
        "ma60": 130.0,
        "ma120": 120.0,
        "ma20_slope": 1.5,
        "ma_bullish_alignment": True,
        "rsi": 65.0,            # optimal bullish
        "macd_hist": 0.5,       # positive
        "macd_dif": 3.0,
        "macd_dea": 2.5,        # golden cross
        "bollinger_mid": 140.0,
        "bollinger_upper": 152.0,
        "bollinger_lower": 128.0
    })
    
    # Mock a high support chip distribution
    # profit_ratio, avg_cost, c90_min, c90_max, c70_min, c70_max
    chip_metrics = (0.95, 145.0, 125.0, 151.0, 135.0, 148.0)
    
    score = score_stock_technical(indicator_row, chip_metrics)
    
    # Bullish indicators should yield a very high score (typically > 80)
    assert 80.0 <= score <= 100.0

def test_score_stock_technical_bearish():
    """Verify that a highly bearish stock gets a low Technical Score."""
    # Mock a highly bearish row
    indicator_row = pd.Series({
        "close": 90.0,
        "ma5": 92.0,
        "ma10": 95.0,
        "ma20": 100.0,
        "ma30": 102.0,
        "ma60": 110.0,
        "ma120": 120.0,
        "ma20_slope": -2.0,
        "ma_bullish_alignment": False,
        "rsi": 25.0,            # oversold
        "macd_hist": -0.8,      # negative
        "macd_dif": -4.0,
        "macd_dea": -3.0,       # death cross state
        "bollinger_mid": 100.0,
        "bollinger_upper": 112.0,
        "bollinger_lower": 88.0
    })
    
    # Mock a low support chip distribution (only 10% in profit, avg cost far above)
    chip_metrics = (0.10, 105.0, 85.0, 115.0, 95.0, 110.0)
    
    score = score_stock_technical(indicator_row, chip_metrics)
    
    # Bearish indicators should yield a very low score (typically < 30)
    assert 0.0 <= score <= 35.0


def test_calculate_chip_distribution_us_scaling():
    """Test that US volume scaling (is_a_share=False) works correctly in the chip model."""
    # Create 150 days of dummy data
    dates = pd.date_range(start="2026-01-01", periods=150, freq="D")
    close_prices = [100.0] * 100 + [100.0 + (i - 100) * 1.0 for i in range(100, 150)]  # 100 to 149
    high_prices = [p + 1.0 for p in close_prices]
    low_prices = [p - 1.0 for p in close_prices]
    # For US, volume from yfinance is in shares (e.g. 500,000 shares per day)
    volume = [500_000] * 150  
    
    df = pd.DataFrame({
        "date": dates,
        "open": close_prices,
        "high": high_prices,
        "low": low_prices,
        "close": close_prices,
        "volume": volume
    })
    
    outstanding_shares = 100_000_000  # 100M outstanding shares
    # Daily turnover = 500k / 100M = 0.005 (0.5%)
    
    # Calculate with is_a_share=False (multiplier = 1.0)
    profit_ratio, avg_cost, c90_min, c90_max, c70_min, c70_max = calculate_chip_distribution(
        df, outstanding_shares, lookback=150, is_a_share=False
    )
    
    # The output metrics should be identical to the hands-based calculation since
    # volume in shares (500k) with multiplier=1.0 yields the exact same daily turnover rate (0.5%)
    # as volume in hands (5k) with multiplier=100.0.
    assert 0.8 <= profit_ratio <= 1.0
    assert 100.0 < avg_cost < 149.0
    assert c90_min <= avg_cost <= c90_max
    assert 99.0 <= c90_min <= 101.0


def test_score_history_per_row():
    """score_history should produce one point-in-time score per bar."""
    dates = pd.date_range(start="2026-01-01", periods=150, freq="D")
    # Downtrend for the first half, uptrend for the second half.
    close_prices = [200.0 - i * 1.0 for i in range(75)] + [125.0 + (i - 75) * 1.0 for i in range(75, 150)]
    high_prices = [p + 1.0 for p in close_prices]
    low_prices = [p - 1.0 for p in close_prices]
    df = pd.DataFrame({
        "date": dates,
        "open": close_prices,
        "high": high_prices,
        "low": low_prices,
        "close": close_prices,
        "volume": [10_000] * 150,
    })

    ind = calculate_technical_indicators(df)
    scored = score_history(ind, outstanding_shares=100_000_000, is_a_share=False)

    # One score per row, all within bounds, and the column is added.
    assert "technical_score" in scored.columns
    assert len(scored) == len(df)
    assert scored["technical_score"].between(0.0, 100.0).all()
    assert not scored["technical_score"].isna().any()

    # Late (uptrend) bars should score higher than early (downtrend) bars.
    assert scored["technical_score"].iloc[-1] > scored["technical_score"].iloc[80]

    # The last bar matches a direct one-shot computation (no look-ahead drift).
    chip = calculate_chip_distribution(ind, 100_000_000, lookback=150, is_a_share=False)
    direct = score_stock_technical(ind.iloc[-1], chip)
    assert abs(scored["technical_score"].iloc[-1] - direct) < 1e-9


def test_score_history_empty():
    """score_history on an empty frame returns an empty technical_score column."""
    empty = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    out = score_history(empty, outstanding_shares=100_000_000)
    assert "technical_score" in out.columns
    assert len(out) == 0

