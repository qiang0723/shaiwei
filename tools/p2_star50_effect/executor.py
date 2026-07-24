"""Deterministic PIT portfolio construction and next-open research execution."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np
import pandas as pd

from tools.p2_star50_effect.contract import EffectGateFailure
from tools.p2_star50_effect.metrics import maximum_drawdown_from_returns, net_excess_return


def source_code(instrument: str) -> str:
    value = str(instrument).upper()
    if value.startswith("SH") and len(value) == 8:
        return f"{value[2:]}.SH"
    if value.startswith("SZ") and len(value) == 8:
        return f"{value[2:]}.SZ"
    if value.endswith((".SH", ".SZ", ".BJ")):
        return value
    raise EffectGateFailure(f"unsupported qlib instrument code: {instrument}")


def normalize_predictions(predictions: pd.Series) -> pd.DataFrame:
    if not isinstance(predictions.index, pd.MultiIndex) or predictions.index.nlevels != 2:
        raise EffectGateFailure("model predictions must use a two-level datetime/instrument index")
    frame = predictions.rename("score").reset_index()
    frame.columns = ["trade_date", "instrument", "score"]
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y%m%d")
    frame["ts_code"] = frame["instrument"].map(source_code)
    frame["score"] = pd.to_numeric(frame["score"], errors="coerce")
    frame = frame.dropna(subset=["score"])
    if frame.duplicated(["trade_date", "ts_code"]).any():
        raise EffectGateFailure("prediction keys are not unique")
    if frame["ts_code"].str.endswith(".BJ").any():
        raise EffectGateFailure("predictions contain forbidden .BJ instruments")
    return frame.sort_values(["trade_date", "score", "ts_code"], ascending=[True, False, True])


@dataclass
class ExecutionResult:
    daily: pd.DataFrame
    holdings: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict[str, Any]


def _fee(notional: float, rate: float, minimum: float) -> float:
    if notional <= 0:
        return 0.0
    return max(minimum, notional * rate)


def _row_map(frame: pd.DataFrame) -> dict[tuple[str, str], dict[str, Any]]:
    if frame.duplicated(["trade_date", "ts_code"]).any():
        raise EffectGateFailure("market/member keys are not unique")
    return {
        (str(row.trade_date), str(row.ts_code)): row._asdict()
        for row in frame.itertuples(index=False)
    }


def _median_amounts(
    signal_date: str,
    codes: list[str],
    calendar: list[str],
    amount_by_key: dict[tuple[str, str], float],
    lookback: int,
) -> dict[str, tuple[int, float]]:
    position = calendar.index(signal_date)
    dates = calendar[max(0, position - lookback + 1) : position + 1]
    result: dict[str, tuple[int, float]] = {}
    for code in codes:
        values = [
            float(amount_by_key[(date, code)])
            for date in dates
            if (date, code) in amount_by_key
            and np.isfinite(amount_by_key[(date, code)])
            and amount_by_key[(date, code)] > 0
        ]
        result[code] = (len(values), float(np.median(values)) if values else float("nan"))
    return result


def _select_target(
    *,
    signal_date: str,
    scores: pd.DataFrame,
    member_rows: pd.DataFrame,
    current_target: list[str],
    holdings: dict[str, int],
    close_prices: dict[str, float],
    nav: float,
    liquidity: dict[str, tuple[int, float]],
    protocol: dict[str, Any],
) -> tuple[list[str], dict[str, float], dict[str, Any]]:
    portfolio = protocol["portfolio"]
    topk = int(portfolio["topk"])
    n_drop = int(portfolio["n_drop"])
    if n_drop != int(portfolio["ranking_dropout_limit_applies_after_hard_exclusions"]):
        raise EffectGateFailure("frozen n_drop semantics are inconsistent")
    target_weight = float(portfolio["target_weight_per_name"])
    minimum_days = int(portfolio["minimum_valid_liquidity_days"])
    minimum_amount = float(portfolio["minimum_median_daily_amount_rmb"])
    capacity_ratio = float(portfolio["maximum_order_to_median_daily_amount"])
    maximum_industry_weight = float(portfolio["maximum_pit_sw_l1_industry_weight"])
    max_industry_names = int(math.floor(maximum_industry_weight / target_weight + 1e-12))

    members = member_rows.set_index("ts_code", drop=False)
    ranked = scores.loc[scores["ts_code"].isin(members.index)].copy()
    ranked = ranked.sort_values(["score", "ts_code"], ascending=[False, True])
    eligible: list[str] = []
    capacities: dict[str, float] = {}
    industries: dict[str, str] = {}
    for row in ranked.itertuples(index=False):
        code = str(row.ts_code)
        member = members.loc[code]
        if isinstance(member, pd.DataFrame):
            raise EffectGateFailure("duplicate member row during selection")
        industry = str(member.get("industry", "")).strip()
        count, median = liquidity.get(code, (0, float("nan")))
        if (
            code.endswith(".BJ")
            or bool(member.get("is_st", False))
            or not bool(member.get("has_market_bar", False))
            or not industry
            or industry.lower() in {"nan", "none", "<na>"}
            or count < minimum_days
            or not np.isfinite(median)
            or median < minimum_amount
        ):
            continue
        current_value = holdings.get(code, 0) * close_prices.get(code, 0.0)
        requested = max(0.0, target_weight * nav - current_value)
        capacity = capacity_ratio * median
        if holdings.get(code, 0) == 0 and requested > capacity + 1e-8:
            continue
        eligible.append(code)
        capacities[code] = capacity
        industries[code] = industry

    eligible_set = set(eligible)
    current_valid = [code for code in current_target if code in eligible_set]
    greedy: list[str] = []
    industry_counts: dict[str, int] = {}
    for code in eligible:
        industry = industries[code]
        if industry_counts.get(industry, 0) >= max_industry_names:
            continue
        greedy.append(code)
        industry_counts[industry] = industry_counts.get(industry, 0) + 1
        if len(greedy) == topk:
            break

    greedy_set = set(greedy)
    score_map = dict(zip(ranked["ts_code"], ranked["score"], strict=False))
    ranking_remove = sorted(
        (code for code in current_valid if code not in greedy_set),
        key=lambda code: (score_map.get(code, -np.inf), code),
    )[:n_drop]
    retained = [code for code in current_valid if code not in set(ranking_remove)]
    result = list(retained)
    industry_counts = {}
    for code in result:
        industry = industries[code]
        industry_counts[industry] = industry_counts.get(industry, 0) + 1
    for code in greedy:
        if code in result:
            continue
        industry = industries[code]
        if industry_counts.get(industry, 0) >= max_industry_names:
            continue
        result.append(code)
        industry_counts[industry] = industry_counts.get(industry, 0) + 1
        if len(result) == topk:
            break
    if len(result) > topk or len(set(result)) != len(result):
        raise EffectGateFailure("target selection violated TopK uniqueness")
    return result, {code: capacities[code] for code in result}, {
        "signal_date": signal_date,
        "eligible_count": len(eligible),
        "selected_count": len(result),
        "ranking_drop_count": len(ranking_remove),
    }


def execute_period(
    *,
    predictions: pd.Series,
    market: pd.DataFrame,
    member_days: pd.DataFrame,
    benchmark: pd.DataFrame,
    start: str,
    end: str,
    cost_multiplier: float,
    extra_slippage_each_side: float,
    protocol: dict[str, Any],
) -> ExecutionResult:
    """Run one independent cash-start period under the frozen execution rules."""
    pred = normalize_predictions(predictions)
    start_key, end_key = start.replace("-", ""), end.replace("-", "")
    benchmark = benchmark.copy()
    benchmark["trade_date"] = benchmark["trade_date"].astype(str)
    benchmark = benchmark.loc[benchmark["trade_date"].between(start_key, end_key)].sort_values(
        "trade_date"
    )
    calendar = benchmark["trade_date"].drop_duplicates().tolist()
    if not calendar:
        raise EffectGateFailure(f"empty evaluation calendar: {start}~{end}")
    if benchmark["trade_date"].duplicated().any():
        raise EffectGateFailure("benchmark dates are not unique")

    market = market.copy()
    market["trade_date"] = market["trade_date"].astype(str)
    market["ts_code"] = market["ts_code"].astype(str)
    member_days = member_days.copy()
    member_days["trade_date"] = member_days["trade_date"].astype(str)
    member_days["ts_code"] = member_days["ts_code"].astype(str)
    pred = pred.loc[pred["trade_date"].isin(calendar)]
    if pred.empty:
        raise EffectGateFailure(f"no predictions in evaluation period: {start}~{end}")
    market_rows = _row_map(market)
    market_by_date: dict[str, dict[str, dict[str, Any]]] = {}
    for (date, code), row in market_rows.items():
        market_by_date.setdefault(date, {})[code] = row
    members_by_date = {
        str(day): group.copy() for day, group in member_days.groupby("trade_date", sort=False)
    }
    scores_by_date = {str(day): group.copy() for day, group in pred.groupby("trade_date", sort=False)}
    amount_by_key = {
        (str(row.trade_date), str(row.ts_code)): float(row.amount)
        for row in market.loc[:, ["trade_date", "ts_code", "amount"]].itertuples(index=False)
        if pd.notna(row.amount)
    }

    portfolio = protocol["portfolio"]
    execution = protocol["execution"]
    cash = float(portfolio["account_rmb"])
    holdings: dict[str, int] = {}
    last_close: dict[str, float] = {}
    current_target: list[str] = []
    pending: dict[str, tuple[list[str], dict[str, float]]] = {}
    daily_rows: list[dict[str, Any]] = []
    holding_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    previous_nav = cash
    rebalance_count = 0
    open_rate = float(execution["open_cost"]) * cost_multiplier + extra_slippage_each_side
    close_rate = float(execution["close_cost"]) * cost_multiplier + extra_slippage_each_side
    minimum_cost = float(execution["minimum_cost_rmb"])
    target_weight = float(portfolio["target_weight_per_name"])
    lookback = int(portfolio["liquidity_lookback_trade_days"])

    for day_index, day in enumerate(calendar):
        day_market = market_by_date.get(day, {})
        for code, row in day_market.items():
            close_value = row.get("close")
            if close_value is not None and pd.notna(close_value) and float(close_value) > 0:
                last_close[code] = float(close_value)

        if day in pending:
            current_target, target_capacity = pending.pop(day)
            nav_open = cash
            for code, quantity in holdings.items():
                row = day_market.get(code)
                price = float(row["open"]) if row and pd.notna(row.get("open")) else last_close.get(code)
                if price is None or not np.isfinite(price):
                    raise EffectGateFailure(f"held position has no valuation price: {code}/{day}")
                nav_open += quantity * price
            target_value = target_weight * nav_open

            for code in sorted(list(holdings)):
                row = day_market.get(code)
                price = float(row["open"]) if row and pd.notna(row.get("open")) else None
                if price is None or price <= 0 or bool(row.get("limit_sell", False)):
                    continue
                desired = int(math.floor(target_value / price)) if code in current_target else 0
                quantity = max(0, holdings[code] - desired)
                if quantity <= 0:
                    continue
                notional = quantity * price
                fee = _fee(notional, close_rate, minimum_cost)
                cash += notional - fee
                holdings[code] -= quantity
                trade_rows.append(
                    {
                        "trade_date": day,
                        "ts_code": code,
                        "side": "SELL",
                        "quantity": quantity,
                        "price": price,
                        "notional": notional,
                        "cost": fee,
                    }
                )
                if holdings[code] == 0:
                    del holdings[code]

            for code in current_target:
                row = day_market.get(code)
                price = float(row["open"]) if row and pd.notna(row.get("open")) else None
                if price is None or price <= 0 or bool(row.get("limit_buy", False)):
                    continue
                current = holdings.get(code, 0)
                desired = int(math.floor(target_value / price))
                quantity = max(0, desired - current)
                capacity_quantity = int(math.floor(target_capacity.get(code, 0.0) / price))
                quantity = min(quantity, capacity_quantity)
                affordable = max(0, int(math.floor(max(0.0, cash - minimum_cost) / (price * (1 + open_rate)))))
                quantity = min(quantity, affordable)
                if current == 0 and quantity < int(execution["minimum_star_purchase_lot"]):
                    continue
                if quantity <= 0:
                    continue
                notional = quantity * price
                fee = _fee(notional, open_rate, minimum_cost)
                if notional + fee > cash + 1e-6:
                    raise EffectGateFailure("buy affordability calculation exceeded cash")
                cash -= notional + fee
                holdings[code] = current + quantity
                trade_rows.append(
                    {
                        "trade_date": day,
                        "ts_code": code,
                        "side": "BUY",
                        "quantity": quantity,
                        "price": price,
                        "notional": notional,
                        "cost": fee,
                    }
                )

        nav = cash
        values: dict[str, float] = {}
        for code, quantity in holdings.items():
            row = day_market.get(code)
            close = float(row["close"]) if row and pd.notna(row.get("close")) else last_close.get(code)
            if close is None or not np.isfinite(close):
                raise EffectGateFailure(f"held position has no close valuation: {code}/{day}")
            values[code] = quantity * close
            nav += values[code]
        if not np.isfinite(nav) or nav <= 0:
            raise EffectGateFailure("portfolio NAV is non-finite or non-positive")
        daily_return = nav / previous_nav - 1.0
        benchmark_row = benchmark.loc[benchmark["trade_date"].eq(day)].iloc[0]
        benchmark_return = float(benchmark_row["pct_chg"]) / 100.0
        daily_rows.append(
            {
                "trade_date": day,
                "daily_net_return": daily_return,
                "benchmark_return": benchmark_return,
                "nav": nav,
                "cash": cash,
            }
        )
        for code, value in sorted(values.items()):
            holding_rows.append(
                {
                    "trade_date": day,
                    "ts_code": code,
                    "weight": value / nav,
                    "quantity": holdings[code],
                }
            )
        previous_nav = nav

        if day_index % int(portfolio["rebalance_trade_days"]) == 0 and day_index + 1 < len(calendar):
            if day not in scores_by_date or day not in members_by_date:
                raise EffectGateFailure(f"missing PIT score/member input on signal date: {day}")
            codes = scores_by_date[day]["ts_code"].astype(str).tolist()
            liquidity = _median_amounts(day, codes, sorted(set(market["trade_date"])), amount_by_key, lookback)
            close_prices = {
                code: (
                    float(day_market[code]["close"])
                    if code in day_market and pd.notna(day_market[code].get("close"))
                    else last_close.get(code, 0.0)
                )
                for code in set(codes) | set(holdings)
            }
            selected, capacities, selection = _select_target(
                signal_date=day,
                scores=scores_by_date[day],
                member_rows=members_by_date[day],
                current_target=current_target,
                holdings=holdings,
                close_prices=close_prices,
                nav=nav,
                liquidity=liquidity,
                protocol=protocol,
            )
            pending[calendar[day_index + 1]] = (selected, capacities)
            selection_rows.append(selection)
            rebalance_count += 1

    daily = pd.DataFrame(daily_rows)
    holding_frame = pd.DataFrame(
        holding_rows,
        columns=["trade_date", "ts_code", "weight", "quantity"],
    )
    trades = pd.DataFrame(
        trade_rows,
        columns=["trade_date", "ts_code", "side", "quantity", "price", "notional", "cost"],
    )
    metrics = {
        "trade_days": int(len(daily)),
        "rebalance_count": int(rebalance_count),
        "strategy_return": float((1.0 + daily["daily_net_return"]).prod() - 1.0),
        "benchmark_return": float((1.0 + daily["benchmark_return"]).prod() - 1.0),
        "net_excess": net_excess_return(daily["daily_net_return"], daily["benchmark_return"]),
        "maximum_drawdown": maximum_drawdown_from_returns(daily["daily_net_return"]),
        "trade_count": int(len(trades)),
        "turnover_notional": float(trades["notional"].sum()) if len(trades) else 0.0,
        "cost_rmb": float(trades["cost"].sum()) if len(trades) else 0.0,
        "minimum_selected_names": int(min((row["selected_count"] for row in selection_rows), default=0)),
        "maximum_selected_names": int(max((row["selected_count"] for row in selection_rows), default=0)),
    }
    return ExecutionResult(daily=daily, holdings=holding_frame, trades=trades, metrics=metrics)
