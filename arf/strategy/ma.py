import backtrader as bt
from .base import BaseStrategy

class MaStrategy(BaseStrategy):
    """Simple Moving Average (SMA) Trend Following Strategy.
    
    Buys when the price crosses above the SMA, sells when it crosses below.
    """

    _name = "MA"
    params = (
        ("maperiod", 15),
        ("printlog", False),
    )

    def __init__(self) -> None:
        super().__init__()
        self.dataclose = self.datas[0].close
        self.order = None
        self.buyprice = None
        self.buycomm = None

        # Add a Simple Moving Average indicator
        self.sma = bt.indicators.SMA(self.datas[0], period=self.params.maperiod)

    def next(self) -> None:
        # Log the closing price
        self.log(f"Close, {self.dataclose[0]:.2f}")

        # If an order is pending, wait
        if self.order:
            return

        # Check position and signals
        if not self.position:
            if self.dataclose[0] > self.sma[0]:
                self.log(f"BUY CREATE, {self.dataclose[0]:.2f}")
                self.order = self.buy()
        else:
            if self.dataclose[0] < self.sma[0]:
                self.log(f"SELL CREATE, {self.dataclose[0]:.2f}")
                self.order = self.sell()
