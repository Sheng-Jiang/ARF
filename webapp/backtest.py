"""Backtrader backtesting runner for the Streamlit webapp."""
import logging
import datetime
import backtrader as bt
import backtrader.analyzers as btanalyzers
import pandas as pd
from typing import Dict, Any

from arf.strategy import STRATEGIES, TechnicalPandasData
from webapp.schemas import BacktraderParams, StrategyBase

log = logging.getLogger(__name__)

def run_backtrader(
    stock_df: pd.DataFrame,
    strategy: StrategyBase,
    bt_params: BacktraderParams
) -> pd.DataFrame:
    """Run Backtrader backtest with parameter optimization.
    
    Supports grid search over parameter ranges, and automatically selects the
    appropriate data feed (e.g. TechnicalPandasData for TechnicalScoreStrategy).
    
    Args:
        stock_df: DataFrame containing price history.
        strategy: StrategyBase schema with strategy name and parameters to optimize.
        bt_params: BacktraderParams schema with cash, commission, and sizes.
        
    Returns:
        pd.DataFrame: Performance results for each parameter combination.
    """
    if stock_df.empty:
        log.warning("Empty stock dataframe passed to Backtrader")
        return pd.DataFrame()

    # Create a copy and standardise column names
    df = stock_df.copy()
    rename_cols = {
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume"
    }
    df = df.rename(columns={k: v for k, v in rename_cols.items() if k in df.columns})
    df.index = pd.to_datetime(df["date"])
    
    # 1. Select the correct data feed
    # TechnicalScoreStrategy requires the 'technical_score' column
    is_tech_strategy = "TechnicalScore" in strategy.name or "智能技术评分" in strategy.name
    
    if is_tech_strategy:
        if "technical_score" not in df.columns:
            # Fallback in case technical_score is missing
            df["technical_score"] = 50.0  # neutral
        data = TechnicalPandasData(
            dataname=df,
            fromdate=bt_params.start_date,
            todate=bt_params.end_date
        )
    else:
        data = bt.feeds.PandasData(
            dataname=df,
            fromdate=bt_params.start_date,
            todate=bt_params.end_date
        )
        
    # 2. Retrieve strategy class
    strategy_class = STRATEGIES.get(strategy.name)
    if strategy_class is None:
        # Fallback in case of slight name differences
        for name, cls in STRATEGIES.items():
            if strategy.name in name or name in strategy.name:
                strategy_class = cls
                break
        if strategy_class is None:
            raise ValueError(f"Strategy '{strategy.name}' not found in STRATEGIES registry")
            
    # 3. Initialize Cerebro engine
    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    cerebro.broker.setcash(bt_params.start_cash)
    cerebro.broker.setcommission(commission=bt_params.commission_fee)
    cerebro.addsizer(bt.sizers.FixedSize, stake=bt_params.stake)
    
    # 4. Add Analyzers
    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="sharpe", riskfreerate=0.0)
    cerebro.addanalyzer(btanalyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(btanalyzers.Returns, _name="returns")
    
    # 5. Prepare parameters for optimization
    # Backtrader's optstrategy requires each parameter value to be an iterable (list/range).
    # If a parameter is a scalar, we wrap it in a list to support uniform execution.
    optimized_params = {}
    for k, v in strategy.params.items():
        if isinstance(v, (list, range, tuple)):
            optimized_params[k] = v
        else:
            optimized_params[k] = [v]
            
    cerebro.optstrategy(strategy_class, **optimized_params)
    
    # 6. Run Backtest
    log.info(f"Running Backtrader on {strategy.name} with parameter grid...")
    back = cerebro.run()
    
    # 7. Collect and parse results
    results_list = []
    for x in back:
        # x is a list containing the strategy instance for a single parameter run
        run = x[0]
        
        # Extract parameter values for this run
        row = {}
        for param in strategy.params.keys():
            row[param] = run.params._getkwargs()[param]
            
        # Extract performance metrics safely (handle potential NaNs/Zeros)
        try:
            row["return"] = run.analyzers.returns.get_analysis().get("rnorm100", 0.0)
            if row["return"] is None or pd.isna(row["return"]):
                row["return"] = 0.0
        except Exception:
            row["return"] = 0.0
            
        try:
            row["dd"] = run.analyzers.drawdown.get_analysis().get("max", {}).get("drawdown", 0.0)
            if row["dd"] is None or pd.isna(row["dd"]):
                row["dd"] = 0.0
        except Exception:
            row["dd"] = 0.0
            
        try:
            sharpe_val = run.analyzers.sharpe.get_analysis().get("sharperatio")
            row["sharpe"] = sharpe_val if sharpe_val is not None and not pd.isna(sharpe_val) else 0.0
        except Exception:
            row["sharpe"] = 0.0
            
        results_list.append(row)
        
    # Convert to DataFrame
    results_df = pd.DataFrame(results_list)
    return results_df
