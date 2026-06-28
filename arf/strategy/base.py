import logging

import backtrader as bt

log = logging.getLogger(__name__)

class BaseStrategy(bt.Strategy):
    """Base strategy providing logging, order execution tracking, and trade lifecycle hooks."""

    _name = "base"
    params = (("printlog", False),)

    def log(self, txt: str, dt: bt.datetime.date | None = None, doprint: bool = False) -> None:
        """Logging function for this strategy."""
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.date(0)
            log.info(f"{dt.isoformat()}, {txt}")

    def notify_order(self, order: bt.Order) -> None:
        if order.status in [order.Submitted, order.Accepted]:
            # Order submitted/accepted to/by broker - nothing to do
            return

        # Check if an order has been completed
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f"BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm {order.executed.comm:.2f}"
                )
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:  # Sell
                self.log(
                    f"SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Comm {order.executed.comm:.2f}"
                )

            self.bar_executed = len(self)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("Order Canceled/Margin/Rejected")

        # Clear pending order
        self.order = None

    def notify_trade(self, trade: bt.Trade) -> None:
        if not trade.isclosed:
            return
        self.log(f"OPERATION PROFIT, GROSS {trade.pnl:.2f}, NET {trade.pnlcomm:.2f}")

    def next(self) -> None:
        pass

    def stop(self) -> None:
        params = [f"{k}_{v}" for k, v in self.params._getkwargs().items() if k != "printlog"]
        self.log(
            "({} {}) Ending Value {:.2f}".format(self._name, " ".join(params), self.broker.getvalue()),
            doprint=True,
        )
