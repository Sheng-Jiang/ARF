import backtrader as bt

from .base import BaseStrategy


class TechnicalPandasData(bt.feeds.PandasData):
    """Custom Pandas Data Feed for Backtrader that exposes the pre-calculated Technical Score.
    
    Standard fields (open, high, low, close, volume) are inherited.
    We add 'technical_score' as a new line.
    """
    lines = ('technical_score',)
    params = (('technical_score', -1),)  # -1 means auto-detect column index by name

class TechnicalScoreStrategy(BaseStrategy):
    """Technical Score Trading Strategy.
    
    A quantitative strategy that trades on the 0-100 multi-factor Technical Score:
    - BUY when the score crosses above the buy_threshold (typically 70, indicating strong trend and momentum).
    - SELL/EXIT when the score falls below the sell_threshold (typically 30, indicating trend breakdown or weakness).
    """

    _name = "TechnicalScore"
    params = (
        ("printlog", False),
        ("buy_threshold", 70.0),
        ("sell_threshold", 30.0),
    )

    def __init__(self) -> None:
        super().__init__()
        self.dataclose = self.datas[0].close
        self.technical_score = self.datas[0].technical_score
        self.order = None
        self.buyprice = None
        self.buycomm = None

    def next(self) -> None:
        self.log(f"Close: {self.dataclose[0]:.2f}, Tech Score: {self.technical_score[0]:.1f}")

        # If an order is pending, wait
        if self.order:
            return

        # Position entry and exit signals
        if not self.position:
            if self.technical_score[0] >= self.params.buy_threshold:
                self.log(f"BUY CREATE (Score={self.technical_score[0]:.1f}), Price: {self.dataclose[0]:.2f}")
                self.order = self.buy()
        else:
            if self.technical_score[0] <= self.params.sell_threshold:
                self.log(f"SELL CREATE (Score={self.technical_score[0]:.1f}), Price: {self.dataclose[0]:.2f}")
                self.order = self.sell()
