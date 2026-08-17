"""Pure aggregate diagnostics for the closed R3G-2 discovery result."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from shaiwei.research.trend_swing.r3g3.contract import SCENARIOS, DiagnosticProtocol
from shaiwei.research.trend_swing.r3g3.evidence import R3G3Error
from shaiwei.research.trend_swing.r3g3.reader import DiagnosticInputs, PointInputs


def _number(value: Any) -> float:
    result = float(value)
    if not np.isfinite(result):
        raise R3G3Error("R3G-3 metric is not finite")
    return result


def _distribution(series: pd.Series) -> dict[str, float]:
    values = pd.to_numeric(series, errors="raise").astype(float)
    if values.empty or not np.isfinite(values).all():
        raise R3G3Error("R3G-3 distribution is invalid")
    return {
        "mean": float(values.mean()),
        "median": float(values.median()),
        "p10": float(values.quantile(0.10)),
        "p90": float(values.quantile(0.90)),
        "maximum": float(values.max()),
    }


def _group_counts(frame: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    grouped = frame.groupby(columns, dropna=False, sort=True).size().rename("count").reset_index()
    return [
        {**{column: str(getattr(row, column)) for column in columns}, "count": int(row.count)}
        for row in grouped.itertuples(index=False)
    ]


def _holding_bucket(days: int, protocol: DiagnosticProtocol) -> str:
    for row in protocol.document["frozen_groupings"]["holding_trade_days"]:
        maximum = row["maximum"]
        if days >= int(row["minimum"]) and (maximum is None or days <= int(maximum)):
            return str(row["label"])
    raise R3G3Error("R3G-3 holding duration has no frozen bucket")


def _episodes(point: PointInputs, protocol: DiagnosticProtocol) -> pd.DataFrame:
    dates = {day: index for index, day in enumerate(point.nav["trade_date"].astype(str))}
    rows: list[dict[str, Any]] = []
    for episode_id, group in point.trades.groupby("episode_id", sort=True):
        buys, sells = group.loc[group["side"].eq("BUY")], group.loc[group["side"].eq("SELL")]
        closed = group.loc[group["closed_trade"].astype(bool)]
        if buys.empty or sells.empty or len(closed) != 1:
            raise R3G3Error("R3G-3 episode is not uniquely closed")
        first, terminal = str(buys["trade_date"].min()), str(closed.iloc[0]["trade_date"])
        if first not in dates or terminal not in dates or dates[terminal] <= dates[first]:
            raise R3G3Error("R3G-3 holding interval is invalid")
        gross = _number(sells["gross_notional"].sum() - buys["gross_notional"].sum())
        fees = _number(group["fees"].sum())
        net, stored = gross - fees, _number(closed.iloc[0]["closed_trade_pnl"])
        if not np.isclose(net, stored, rtol=0.0, atol=1e-6):
            raise R3G3Error("R3G-3 episode PnL does not reconcile")
        holding = dates[terminal] - dates[first]
        rows.append(
            {
                "episode": str(episode_id),
                "terminal_date": terminal,
                "terminal_year": terminal[:4],
                "terminal_reason": str(closed.iloc[0]["reason"]),
                "holding_days": holding,
                "holding_bucket": _holding_bucket(holding, protocol),
                "gross_pnl": gross,
                "fees": fees,
                "net_pnl": net,
            }
        )
    return pd.DataFrame(rows)


def _pnl_groups(episodes: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    total_absolute = float(episodes.groupby(column, sort=True)["net_pnl"].sum().abs().sum())
    rows: list[dict[str, Any]] = []
    for label, group in episodes.groupby(column, sort=True):
        net = float(group["net_pnl"].sum())
        rows.append(
            {
                "group": str(label),
                "closed_trade_count": len(group),
                "win_rate": float(group["net_pnl"].gt(0).mean()),
                "net_pnl_rmb": net,
                "absolute_group_pnl_share": abs(net) / total_absolute if total_absolute else None,
            }
        )
    return rows


def _order_diagnostic(point: PointInputs) -> dict[str, Any]:
    orders = point.orders.copy()
    filled = orders["status"].isin(["FILLED", "PARTIAL"])
    first = orders.loc[orders["side"].eq("BUY") & orders["batch"].eq(1)]
    second = orders.loc[orders["side"].eq("BUY") & orders["batch"].eq(2)]
    entries = orders.loc[orders["side"].eq("BUY") & filled]

    def fill_rate(frame: pd.DataFrame) -> float | None:
        return float(frame["status"].isin(["FILLED", "PARTIAL"]).mean()) if len(frame) else None

    entry_notional = _number(entries["filled_notional"].sum()) if len(entries) else 0.0
    second_notional = _number(
        second.loc[second["status"].isin(["FILLED", "PARTIAL"]), "filled_notional"].sum()
    ) if len(second) else 0.0
    nav_map = point.nav.set_index(point.nav["trade_date"].astype(str))["nav"].astype(float)
    weights = [
        _number(row.filled_notional) / _number(nav_map[str(row.trade_date)])
        for row in entries.itertuples(index=False)
    ]
    capacity = orders.loc[orders["capacity_limited"].astype(bool)]
    return {
        "total_order_count": len(orders),
        "first_batch_order_count": len(first),
        "first_batch_fill_rate": fill_rate(first),
        "second_batch_order_count": len(second),
        "second_batch_fill_rate": fill_rate(second),
        "second_batch_entry_notional_share": second_notional / entry_notional if entry_notional else None,
        "new_entry_day_count": int(entries["trade_date"].astype(str).nunique()),
        "order_status_counts": _group_counts(orders, ["side", "batch", "status"]),
        "unfilled_or_pending_reason_counts": _group_counts(
            orders.loc[~filled], ["side", "batch", "status", "reason"]
        ),
        "capacity_limited_counts": _group_counts(capacity, ["side", "status"]),
        "filled_entry_same_day_nav_share": _distribution(pd.Series(weights)) if weights else None,
    }


def _participation(point: PointInputs) -> dict[str, Any]:
    nav = point.nav.copy()
    invested = nav.loc[nav["position_count"].astype(int).gt(0)]
    counts = nav["position_count"].astype(int).value_counts().sort_index()
    return {
        "calendar_day_count": len(nav),
        "invested_day_count": len(invested),
        "invested_day_rate": len(invested) / len(nav),
        "cash_ratio_all_days": _distribution(nav["cash_ratio"]),
        "gross_weight_all_days": _distribution(nav["gross_weight"]),
        "cash_ratio_invested_days": _distribution(invested["cash_ratio"]) if len(invested) else None,
        "gross_weight_invested_days": _distribution(invested["gross_weight"]) if len(invested) else None,
        "position_count_distribution": [
            {"position_count": int(index), "day_count": int(value)} for index, value in counts.items()
        ],
        "maximum_position_count": int(nav["position_count"].max()),
        "maximum_security_weight": _number(nav["maximum_security_weight"].max()),
        "maximum_industry_weight": _number(nav["maximum_industry_weight"].max()),
    }


def _trade_economics(point: PointInputs, protocol: DiagnosticProtocol) -> dict[str, Any]:
    episodes = _episodes(point, protocol)
    gross, fees, net = (
        _number(episodes["gross_pnl"].sum()),
        _number(episodes["fees"].sum()),
        _number(episodes["net_pnl"].sum()),
    )
    if not np.isclose(gross - fees, net, rtol=0.0, atol=1e-6):
        raise R3G3Error("R3G-3 aggregate PnL does not reconcile")
    winners, losers = episodes.loc[episodes["net_pnl"].gt(0)], episodes.loc[episodes["net_pnl"].lt(0)]
    winner_mean = _number(winners["net_pnl"].mean()) if len(winners) else None
    loser_mean = _number(losers["net_pnl"].mean()) if len(losers) else None
    return {
        "closed_trade_count": len(episodes),
        "gross_pnl_before_fees_rmb": gross,
        "fees_rmb": fees,
        "net_pnl_rmb": net,
        "pnl_reconciliation_delta_rmb": gross - fees - net,
        "win_rate": float(episodes["net_pnl"].gt(0).mean()),
        "winner_mean_rmb": winner_mean,
        "loser_mean_rmb": loser_mean,
        "profit_loss_ratio": winner_mean / abs(loser_mean) if winner_mean and loser_mean else None,
        "expectancy_rmb": _number(episodes["net_pnl"].mean()),
        "terminal_exit_groups": _pnl_groups(episodes, "terminal_reason"),
        "holding_duration_groups": _pnl_groups(episodes, "holding_bucket"),
        "calendar_year_groups": _pnl_groups(episodes, "terminal_year"),
    }


def _costs(point: PointInputs) -> dict[str, Any]:
    values = {
        scenario: _number(point.summaries[scenario]["pooled_net_return"])
        for scenario in SCENARIOS
    }
    base = values["base_1x"]
    return {
        "pooled_net_return": values,
        "delta_from_base": {scenario: value - base for scenario, value in values.items()},
    }


def compute_diagnostic(protocol: DiagnosticProtocol, inputs: DiagnosticInputs) -> dict[str, Any]:
    points: dict[str, Any] = {}
    for role, point_hash in protocol.points:
        point = inputs.points[role]
        points[role] = {
            "point_hash": point_hash,
            "participation": _participation(point),
            "orders": _order_diagnostic(point),
            "trade_economics": _trade_economics(point, protocol),
            "cost_scenarios": _costs(point),
        }
    primary = points["primary"]
    trade, participation, orders = (
        primary["trade_economics"], primary["participation"], primary["orders"]
    )
    loss_driver = "NEGATIVE_PRE_FEE_TRADE_ECONOMICS" if trade["gross_pnl_before_fees_rmb"] < 0 else (
        "FEES_EXCEED_POSITIVE_PRE_FEE_EDGE" if trade["net_pnl_rmb"] < 0 else "NO_REALIZED_LOSS"
    )
    return {
        "schema_version": "ts-v5-r3g3-discovery-diagnostic-report-v1",
        "protocol_sha256": protocol.sha256,
        "parent_verdict": "REJECT_TS_V5_R3G2_DISCOVERY",
        "parent_strategy_effective": "REJECT",
        "strategy_effect_attempt_increment": 0,
        "window": {"start": "20210104", "end": "20231229", "role": "discovery"},
        "source_identity": inputs.identity,
        "points": points,
        "observed_bottlenecks": [
            {
                "id": "REALIZED_LOSS_DECOMPOSITION",
                "classification": "VERIFIED",
                "finding": loss_driver,
                "gross_pnl_before_fees_rmb": trade["gross_pnl_before_fees_rmb"],
                "fees_rmb": trade["fees_rmb"],
                "net_pnl_rmb": trade["net_pnl_rmb"],
            },
            {
                "id": "CAPITAL_PARTICIPATION",
                "classification": "VERIFIED",
                "finding": "LOW_OBSERVED_PARTICIPATION",
                "invested_day_rate": participation["invested_day_rate"],
                "mean_gross_weight": participation["gross_weight_all_days"]["mean"],
                "mean_gross_weight_when_invested": participation["gross_weight_invested_days"]["mean"],
            },
            {
                "id": "ORDER_FUNNEL",
                "classification": "VERIFIED",
                "finding": "OBSERVED_ORDER_AND_FILL_COUNTS_ONLY",
                "first_batch_order_count": orders["first_batch_order_count"],
                "first_batch_fill_rate": orders["first_batch_fill_rate"],
                "new_entry_day_count": orders["new_entry_day_count"],
            },
        ],
        "unresolved_questions": [
            "whether_a_different_signal_mechanism_can_raise_participation_without_reducing_expectancy",
            "whether_a_different_exit_mechanism_can_create_positive_pre_fee_trade_economics",
            "which_single_mechanically_distinct_ts_v6_hypothesis_should_be_frozen_before_new_effect_read",
        ],
        "verdict": "GO_DIAGNOSTIC_COMPUTATION_R3G2_REJECT_UNCHANGED",
        "strategy_effective": "REJECT_UNCHANGED",
        "production_authorization": "none",
    }
