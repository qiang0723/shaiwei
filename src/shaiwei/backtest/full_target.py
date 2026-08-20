"""Qlib adapter for the production rank-head equal-weight target policy."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import numpy as np
import pandas as pd
from qlib.backtest.decision import Order, OrderDir, TradeDecisionWO
from qlib.contrib.strategy.signal_strategy import BaseSignalStrategy

from shaiwei.backtest.strategy import is_rebalance_step


class FullTargetStrategyError(RuntimeError):
    """Raised when a target portfolio cannot be constructed without guessing."""


def _finite_positive_price(value: object) -> float | None:
    """Normalize an exchange or position price without inventing a fallback."""
    if isinstance(value, (bool, np.bool_)):
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    return price if np.isfinite(price) and price > 0 else None


def ranked_topk(scores: pd.Series, *, topk: int) -> tuple[str, ...]:
    """Return deterministic score-descending, instrument-ascending targets."""
    if not isinstance(scores, pd.Series) or topk < 1:
        raise FullTargetStrategyError("rank-head scores or topk are invalid")
    if isinstance(scores.index, pd.MultiIndex) or scores.index.has_duplicates:
        raise FullTargetStrategyError("rank-head scores must have unique instrument keys")
    frame = scores.rename("score").reset_index()
    frame.columns = ["instrument", "score"]
    frame["instrument"] = frame["instrument"].astype(str)
    forbidden = frame["instrument"].str.upper().str.startswith("BJ") | frame[
        "instrument"
    ].str.upper().str.endswith(".BJ")
    if forbidden.any():
        raise FullTargetStrategyError("rank-head scores contain a forbidden BSE instrument")
    frame["score"] = pd.to_numeric(frame["score"], errors="raise")
    frame = frame.dropna(subset=["score"])
    if not np.isfinite(frame["score"].to_numpy(dtype=float)).all():
        raise FullTargetStrategyError("rank-head scores contain a nonfinite value")
    if len(frame) < topk:
        raise FullTargetStrategyError("rank-head score cross-section is insufficient")
    ranked = frame.sort_values(
        ["score", "instrument"], ascending=[False, True], kind="mergesort"
    )
    return tuple(ranked["instrument"].head(topk))


def equal_weight_target_amounts(
    targets: Sequence[str],
    *,
    account_value: float,
    risk_degree: float,
    prices: Mapping[str, float],
    round_amount: Callable[[str, float], float],
) -> dict[str, float]:
    """Convert an equal-weight target into legal quantities at execution prices."""
    if not targets or len(set(targets)) != len(targets):
        raise FullTargetStrategyError("equal-weight targets are empty or duplicated")
    if not np.isfinite(account_value) or account_value <= 0:
        raise FullTargetStrategyError("account value is not positive and finite")
    if not np.isfinite(risk_degree) or not 0 < risk_degree <= 1:
        raise FullTargetStrategyError("risk degree must be in (0, 1]")
    target_value = account_value * risk_degree / len(targets)
    amounts: dict[str, float] = {}
    for code in targets:
        price = float(prices.get(code, float("nan")))
        if not np.isfinite(price) or price <= 0:
            amounts[code] = 0.0
            continue
        amount = float(round_amount(code, target_value / price))
        if not np.isfinite(amount) or amount < 0:
            raise FullTargetStrategyError("rounded target quantity is invalid")
        amounts[code] = amount
    return amounts


def position_deltas(
    current: Mapping[str, float], target: Mapping[str, float]
) -> tuple[dict[str, float], dict[str, float]]:
    """Return positive sell and buy quantities for a full target rebalance."""
    sells = {
        code: float(amount - target.get(code, 0.0))
        for code, amount in current.items()
        if amount - target.get(code, 0.0) > 1e-12
    }
    buys = {
        code: float(amount - current.get(code, 0.0))
        for code, amount in target.items()
        if amount - current.get(code, 0.0) > 1e-12
    }
    return sells, buys


class BiweeklyRankHeadEqualWeightStrategy(BaseSignalStrategy):
    """Every N trade days, target the current deterministic TopK at equal weight."""

    def __init__(
        self,
        *,
        topk: int = 30,
        rebalance_days: int = 10,
        risk_degree: float,
        forbid_all_trade_at_limit: bool = False,
        **kwargs,
    ):
        if topk < 1 or rebalance_days < 1:
            raise ValueError("topk and rebalance_days must be positive")
        if isinstance(risk_degree, bool) or not np.isfinite(risk_degree) or risk_degree != 1.0:
            raise ValueError("production full-target risk_degree must equal the frozen value 1.0")
        super().__init__(risk_degree=risk_degree, **kwargs)
        self.topk = topk
        self.rebalance_days = rebalance_days
        self.forbid_all_trade_at_limit = forbid_all_trade_at_limit
        self.rebalance_evidence: list[dict[str, object]] = []
        self._previous_targets: tuple[str, ...] = ()

    def _price(self, code: str, start, end, direction: OrderDir) -> float | None:
        value = self.trade_exchange.get_deal_price(
            stock_id=code, start_time=start, end_time=end, direction=direction
        )
        return _finite_positive_price(value)

    def _valuation_price(self, code: str, start, end) -> float:
        price = self._price(code, start, end, OrderDir.SELL)
        if price is not None:
            return price
        fallback = _finite_positive_price(self.trade_position.get_stock_price(code))
        if fallback is None:
            raise FullTargetStrategyError(
                f"held instrument has no finite positive valuation price: {code}"
            )
        return fallback

    def _tradable(self, code: str, start, end, direction: OrderDir) -> bool:
        effective_direction = None if self.forbid_all_trade_at_limit else direction
        return bool(
            self.trade_exchange.is_stock_tradable(
                stock_id=code,
                start_time=start,
                end_time=end,
                direction=effective_direction,
            )
        )

    def generate_trade_decision(self, execute_result=None):
        trade_step = self.trade_calendar.get_trade_step()
        if not is_rebalance_step(trade_step, self.rebalance_days):
            return TradeDecisionWO([], self)
        trade_start, trade_end = self.trade_calendar.get_step_time(trade_step)
        signal_start, signal_end = self.trade_calendar.get_step_time(trade_step, shift=1)
        scores = self.signal.get_signal(start_time=signal_start, end_time=signal_end)
        if isinstance(scores, pd.DataFrame):
            scores = scores.iloc[:, 0]
        if scores is None:
            return TradeDecisionWO([], self)
        targets = ranked_topk(scores, topk=self.topk)

        current = self.trade_position
        current_amounts = current.get_stock_amount_dict()
        valuation_prices = {
            code: self._valuation_price(code, trade_start, trade_end)
            for code in current_amounts
        }
        account_value = current.get_cash() + sum(
            current_amounts[code] * valuation_prices[code] for code in current_amounts
        )
        buy_prices = {}
        for code in targets:
            price = self._price(code, trade_start, trade_end, OrderDir.BUY)
            buy_prices[code] = price if price is not None else float("nan")

        def round_amount(code: str, amount: float) -> float:
            return float(
                self.trade_exchange.round_amount_by_trade_unit(
                    amount,
                    self.trade_exchange.get_factor(
                        stock_id=code, start_time=trade_start, end_time=trade_end
                    ),
                )
            )

        desired = equal_weight_target_amounts(
            targets,
            account_value=account_value,
            risk_degree=self.get_risk_degree(trade_step),
            prices=buy_prices,
            round_amount=round_amount,
        )
        sells, buys = position_deltas(current_amounts, desired)
        previous = set(self._previous_targets)
        retained = previous & set(targets)
        retained_reweight_notional = sum(
            abs(desired[code] - float(current_amounts.get(code, 0.0)))
            * float(buy_prices[code])
            for code in retained
            if np.isfinite(buy_prices[code])
        )
        self.rebalance_evidence.append(
            {
                "trade_date": pd.Timestamp(trade_start).strftime("%Y-%m-%d"),
                "signal_date": pd.Timestamp(signal_start).strftime("%Y-%m-%d"),
                "targets": list(targets),
                "previous_targets": list(self._previous_targets),
                "replacement_count": len(set(targets) - previous),
                "retained_reweight_notional": float(retained_reweight_notional),
                "account_value": float(account_value),
            }
        )
        self._previous_targets = targets
        sell_orders: list[Order] = []
        for code, amount in sorted(sells.items()):
            if not self._tradable(code, trade_start, trade_end, OrderDir.SELL):
                continue
            order = Order(code, amount, OrderDir.SELL, trade_start, trade_end)
            if self.trade_exchange.check_order(order):
                sell_orders.append(order)
        buy_orders = [
            Order(code, buys[code], OrderDir.BUY, trade_start, trade_end)
            for code in targets
            if code in buys and self._tradable(code, trade_start, trade_end, OrderDir.BUY)
        ]
        return TradeDecisionWO(sell_orders + buy_orders, self)


__all__ = [
    "BiweeklyRankHeadEqualWeightStrategy",
    "FullTargetStrategyError",
    "equal_weight_target_amounts",
    "position_deltas",
    "ranked_topk",
]
