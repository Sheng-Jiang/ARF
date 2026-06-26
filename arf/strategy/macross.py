import backtrader as bt
from .base import BaseStrategy

class MaCrossStrategy(BaseStrategy):
    """Dual Moving Average Crossover Strategy.
    
    Buys when the fast SMA crosses above the slow SMA (golden cross),
    and sells when it crosses below (death cross).
    """

    _name = "MaCross"
    params = (
        ("printlog", False),
        ("fast_length", 10),
        ("slow_length", 50),
    )

    def __init__(self) -> None:
        super().__init__()
        self.dataclose = self.datas[0].close
        self.order = None
        self.buyprice = None
        self.buycomm = None

        # Add Fast and Slow SMAs
        ma_fast = bt.indicators.SMA(self.datas[0], period=self.params.fast_length)
        ma_slow = bt.indicators.SMA(self.datas[0], period=self.params.slow_length)

        # CrossOver indicator: returns 1.0 for upward crossover, -1.0 for downward crossover
        self.crossover = bt.indicators.CrossOver(ma_fast, ma_slow)

    def next(self) -> None:
        self.log(f"Close, {self.dataclose[0]:.2f}")

        if self.order:
            return

        if not self.position:
            if self.crossover[0] > 0:
                self.log(f"BUY CREATE, {self.dataclose[0]:.2f}")
                self.order = self.buy()
        else:
            if self.crossover[0] < 0:
                self.log(f"SELL CREATE, {self.dataclose[0]:.2f}")
                self.order = self.sell()
