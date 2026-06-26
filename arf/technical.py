"""Technical Indicator and Chip Distribution Scoring Engine.

Provides vectorised calculations for standard indicators (MAs, MACD, RSI, 
Bollinger Bands, ATR) and a custom, cloud-safe mathematical Chip Distribution (CYQ) model.
Also implements a heuristic 0-100 Technical Score combining trend, momentum, 
volatility, and market micro-structure (chips).
"""
from typing import Tuple, Dict, Any
import numpy as np
import pandas as pd

def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate standard technical indicators on a daily price history DataFrame.
    
    df must contain columns: ['date', 'open', 'high', 'low', 'close', 'volume']
    Returns a copy of the DataFrame with added indicator columns.
    """
    df = df.copy().sort_values("date").reset_index(drop=True)
    
    # 1. Moving Averages
    for ma in [5, 10, 20, 30, 60, 120]:
        df[f"ma{ma}"] = df["close"].rolling(window=ma).mean()
        # Calculate slope as % change over last 3 days
        df[f"ma{ma}_slope"] = df[f"ma{ma}"].pct_change(periods=3) * 100.0
        
    # Bullish Alignment (多头排列): MA5 > MA10 > MA20 > MA30 > MA60 > MA120
    df["ma_bullish_alignment"] = (
        (df["ma5"] > df["ma10"]) &
        (df["ma10"] > df["ma20"]) &
        (df["ma20"] > df["ma30"]) &
        (df["ma30"] > df["ma60"]) &
        (df["ma60"] > df["ma120"])
    )
    
    # 2. MACD (12, 26, 9)
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd_dif"] = ema12 - ema26
    df["macd_dea"] = df["macd_dif"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = (df["macd_dif"] - df["macd_dea"]) * 2.0
    
    # 3. RSI (14)
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    # Guard against division by zero
    rs = np.where(avg_loss == 0, np.nan, avg_gain / avg_loss)
    df["rsi"] = np.where(avg_loss == 0, 100.0, np.where(avg_gain == 0, 0.0, 100.0 - (100.0 / (1.0 + rs))))
    
    # 4. Bollinger Bands (20, 2)
    df["bollinger_mid"] = df["close"].rolling(window=20).mean()
    std20 = df["close"].rolling(window=20).std()
    df["bollinger_upper"] = df["bollinger_mid"] + 2.0 * std20
    df["bollinger_lower"] = df["bollinger_mid"] - 2.0 * std20
    
    # 5. ATR (14)
    h_l = df["high"] - df["low"]
    h_pc = (df["high"] - df["close"].shift(1)).abs()
    l_pc = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
    df["atr"] = tr.rolling(window=14).mean()
    
    return df

def calculate_chip_distribution(
    df: pd.DataFrame, 
    outstanding_shares: float, 
    lookback: int = 150
) -> Tuple[float, float, float, float, float, float]:
    """Calculate chip distribution metrics using decayed historical typical prices.
    
    Uses a high-fidelity decayed-weight model: older cohorts are decayed exponentially
    by the daily turnover rate (volume / outstanding shares), representing liquidity churn.
    
    Args:
        df: DataFrame containing ['high', 'low', 'close', 'volume']
        outstanding_shares: Total shares outstanding (for turnover rate)
        lookback: Historical window to calculate distribution (default 150 days)
        
    Returns:
        Tuple: (profit_ratio, avg_cost, cost_90_min, cost_90_max, cost_70_min, cost_70_max)
    """
    if len(df) < 10 or outstanding_shares <= 0:
        last_val = df["close"].iloc[-1] if len(df) > 0 else 0.0
        return 0.5, last_val, last_val, last_val, last_val, last_val
        
    # Extract historical window
    sub_df = df.tail(lookback).copy()
    
    # 1. Calculate typical price for each day (peaking representation of daily cost)
    sub_df["typical_price"] = (sub_df["high"] + sub_df["low"] + sub_df["close"]) / 3.0
    
    # 2. Calculate daily turnover rate (T)
    # AkShare volume is in hands (1 hand = 100 shares)
    sub_df["turnover"] = ((sub_df["volume"] * 100.0) / outstanding_shares).clip(upper=0.5)
    
    prices = sub_df["typical_price"].values
    turnover = sub_df["turnover"].values
    n = len(sub_df)
    
    # 3. Compute decayed weights
    # W_i = T_i * Product_{j=i+1}^N (1 - T_j)
    # Computed efficiently in reverse
    weights = np.zeros(n)
    factor = 1.0
    for i in range(n - 1, -1, -1):
        weights[i] = turnover[i] * factor
        factor *= (1.0 - turnover[i])
        
    # Normalise weights to sum to 1.0 (representing 100% of outstanding shares)
    w_sum = weights.sum()
    if w_sum > 0:
        weights /= w_sum
    else:
        weights = np.ones(n) / n
        
    # 4. Compute metrics
    # Average cost
    avg_cost = float(np.sum(prices * weights))
    
    # Profit ratio (share of chips below current close price)
    current_close = df["close"].iloc[-1]
    profit_ratio = float(np.sum(weights[prices < current_close]))
    
    # Cost intervals (quantiles of the weighted cost distribution)
    sort_idx = np.argsort(prices)
    sorted_prices = prices[sort_idx]
    sorted_weights = weights[sort_idx]
    cum_weights = np.cumsum(sorted_weights)
    
    def get_percentile_price(p: float) -> float:
        idx = np.searchsorted(cum_weights, p)
        if idx >= len(sorted_prices):
            return float(sorted_prices[-1])
        return float(sorted_prices[idx])
        
    cost_90_min = get_percentile_price(0.05)
    cost_90_max = get_percentile_price(0.95)
    cost_70_min = get_percentile_price(0.15)
    cost_70_max = get_percentile_price(0.85)
    
    return profit_ratio, avg_cost, cost_90_min, cost_90_max, cost_70_min, cost_70_max

def score_stock_technical(
    indicator_row: pd.Series,
    chip_metrics: Tuple[float, float, float, float, float, float]
) -> float:
    """Compute a heuristic Technical Score (0-100) combining multiple factors.
    
    Factors and weights:
    - Trend (40%): Moving averages alignment, price positions, and slopes.
    - Momentum (20%): RSI ranges, MACD histogram, and cross states.
    - Volatility (20%): Bollinger Band positions and squeeze states.
    - Chip Market-Structure (20%): Profit ratio and average cost support.
    
    Args:
        indicator_row: A pandas Series containing the latest indicators (row in df)
        chip_metrics: Tuple of chip distribution outputs
        
    Returns:
        float: Technical Score (0-100)
    """
    close = float(indicator_row.get("close", 0))
    if close <= 0:
        return 0.0
        
    profit_ratio, avg_cost, c90_min, c90_max, c70_min, c70_max = chip_metrics
    
    # ── 1. Trend Factor (Max 40 pts) ──────────────────────────────────────────
    trend_score = 0.0
    
    # Points for being above major moving averages
    mas = {"ma5": 3, "ma10": 3, "ma20": 4, "ma30": 5, "ma60": 5, "ma120": 5}
    for ma_name, pts in mas.items():
        ma_val = indicator_row.get(ma_name)
        if ma_val and not pd.isna(ma_val) and close > ma_val:
            trend_score += pts
            
    # Points for Bullish Alignment (多头排列)
    if bool(indicator_row.get("ma_bullish_alignment", False)):
        trend_score += 10.0
        
    # Points for positive slope on medium-term MA (MA20 or MA30)
    ma20_slope = indicator_row.get("ma20_slope", 0)
    if ma20_slope and not pd.isna(ma20_slope) and ma20_slope > 0:
        trend_score += 5.0
        
    # ── 2. Momentum Factor (Max 20 pts) ───────────────────────────────────────
    momentum_score = 0.0
    
    # RSI scoring (prefer steady rising strength, penalise extreme overbought)
    rsi = float(indicator_row.get("rsi", 50))
    if 50 <= rsi <= 70:
        momentum_score += 10.0  # optimal bullish range
    elif 40 <= rsi < 50:
        momentum_score += 7.0   # mild strength
    elif 30 <= rsi < 40:
        momentum_score += 4.0   # weak, but not yet oversold
    elif rsi < 30:
        momentum_score += 6.0   # oversold, potential bounce candidate
    elif 70 < rsi <= 80:
        momentum_score += 5.0   # overextended strength
    else:  # rsi > 80
        momentum_score += 1.0   # extremely overbought, high warning
        
    # MACD scoring
    macd_hist = indicator_row.get("macd_hist", 0)
    macd_dif = indicator_row.get("macd_dif", 0)
    macd_dea = indicator_row.get("macd_dea", 0)
    
    if macd_hist and not pd.isna(macd_hist) and macd_hist > 0:
        momentum_score += 5.0  # histogram positive (bullish momentum)
    if macd_dif and macd_dea and not pd.isna(macd_dif) and not pd.isna(macd_dea) and macd_dif > macd_dea:
        momentum_score += 5.0  # DIF > DEA (golden cross state)
        
    # ── 3. Volatility & Bollinger Position (Max 20 pts) ──────────────────────
    vol_score = 0.0
    
    bb_mid = indicator_row.get("bollinger_mid")
    bb_upper = indicator_row.get("bollinger_upper")
    bb_lower = indicator_row.get("bollinger_lower")
    
    if bb_upper and bb_lower and bb_upper > bb_lower and not pd.isna(bb_upper) and not pd.isna(bb_lower):
        # Calculate relative position in BB (0 = lower band, 1 = upper band)
        b_pos = (close - bb_lower) / (bb_upper - bb_lower)
        
        if 0.1 <= b_pos <= 0.6:
            vol_score += 15.0  # rising from lower band, healthy room to grow
        elif 0.6 < b_pos <= 0.85:
            vol_score += 10.0  # strong uptrend near upper band
        elif b_pos < 0.1:
            vol_score += 8.0   # extreme oversold, support potential
        elif 0.85 < b_pos <= 0.95:
            vol_score += 5.0   # highly extended, warning
        else:  # b_pos > 0.95
            vol_score += 1.0   # hugging upper band, overextended risk
            
        # Volatility squeeze check
        # If BB bandwidth is narrow relative to historical, breakout imminent
        width = (bb_upper - bb_lower) / bb_mid if bb_mid else 0.1
        vol_score += 5.0 * (1.0 - min(width, 1.0))  # higher points for tighter squeeze
    else:
        vol_score += 10.0  # neutral fallback
        
    # ── 4. Chip Market-Structure (Max 20 pts) ─────────────────────────────────
    chip_score = 0.0
    
    # Scoring based on profit ratio (获利比例)
    if profit_ratio >= 0.80:
        chip_score += 15.0  # strong support, locked-in chips, low overhead resistance
    elif 0.50 <= profit_ratio < 0.80:
        chip_score += 10.0  # moderate profit support
    elif 0.20 <= profit_ratio < 0.50:
        chip_score += 5.0   # heavy resistance above
    else:
        chip_score += 2.0   # extreme heavy resistance (most holders in loss, selling pressure on rise)
        
    # Proximity to average cost support
    # If price is close to average cost (within -2% to +5%), it's a strong support zone
    cost_diff = (close - avg_cost) / avg_cost if avg_cost > 0 else 0
    if -0.02 <= cost_diff <= 0.05:
        chip_score += 5.0
        
    # Combine all elements
    total_score = trend_score + momentum_score + vol_score + chip_score
    return float(np.clip(total_score, 0.0, 100.0))
