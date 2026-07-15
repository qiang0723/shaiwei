"""严格按交易步计数的双周 TopkDropoutStrategy。"""

from qlib.backtest.decision import TradeDecisionWO
from qlib.contrib.strategy import TopkDropoutStrategy


def is_rebalance_step(trade_step: int, rebalance_days: int) -> bool:
    if rebalance_days < 1:
        raise ValueError("rebalance_days must be positive")
    return trade_step >= 0 and trade_step % rebalance_days == 0


class BiweeklyTopkDropoutStrategy(TopkDropoutStrategy):
    def __init__(self, *, rebalance_days: int = 10, **kwargs):
        super().__init__(**kwargs)
        if rebalance_days < 1:
            raise ValueError("rebalance_days must be positive")
        self.rebalance_days = rebalance_days

    def generate_trade_decision(self, execute_result=None):
        trade_step = self.trade_calendar.get_trade_step()
        if not is_rebalance_step(trade_step, self.rebalance_days):
            return TradeDecisionWO([], self)
        return super().generate_trade_decision(execute_result=execute_result)
