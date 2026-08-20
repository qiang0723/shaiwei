"""Paper-v1 historical simulation for the frozen M6-5B Head30 targets."""

from __future__ import annotations

from datetime import date
from statistics import median
from typing import Any

import pandas as pd

from shaiwei.config import PaperPortfolio
from shaiwei.paper.engine import execute_day, policy_sha256
from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.production_conversion.contract import ProtocolError

from .source_reader import RawSources


def frozen_policy() -> PaperPortfolio:
    return PaperPortfolio(
        enabled=True, account_id="model_baseline", initial_cash=500000.0,
        currency="RMB", benchmark="000906.SH", execution_policy_version="paper-v1",
        forward_start_date=date(2026, 7, 23), commission_rate=0.0003,
        minimum_commission=5.0, stamp_tax_rate=0.0005, transfer_fee_rate=0.00001,
        main_board_lot_size=100, star_minimum_lot=200,
        st_main_ten_percent_effective=date(2026, 7, 6), stale_price_trade_days=20,
        accounting_tolerance=0.01,
    )


def _date(value: object) -> str:
    return str(value).replace("-", "")[:8]


def _code(value: str) -> str:
    return f"{value[2:]}.{value[:2]}" if value[:2] in {"SH", "SZ", "BJ"} else value


def _signal(targets: list[str], due: bool) -> dict[str, Any]:
    return {
        "rebalance_due": due,
        "orders": [
            {"instrument": code, "rank": rank, "target_weight": 1.0 / 30.0}
            for rank, code in enumerate(targets, start=1)
        ],
    }


def _capacity(daily: pd.DataFrame, code: str, signal_date: str, notional: float) -> dict[str, Any]:
    history = daily.loc[
        daily["ts_code"].eq(code) & daily["trade_date"].lt(signal_date),
        ["trade_date", "amount_rmb"],
    ].dropna().sort_values("trade_date").tail(20)
    valid = history.loc[history["amount_rmb"].gt(0), "amount_rmb"]
    if len(valid) < 15:
        raise ProtocolError(f"M6-5B capacity history is incomplete: {code}|{signal_date}")
    reference = float(median(valid.tolist()))
    return {
        "ts_code": code, "signal_date": signal_date, "observation_count": len(valid),
        "median_amount_rmb": reference, "order_notional_rmb": notional,
        "limit_rmb": reference * 0.05, "violation": notional > reference * 0.05,
    }


def _rebalance_diagnostic(
    result: Any, targets: list[str], signal_date: str, sources: RawSources,
) -> dict[str, Any]:
    net_asset = float(result.nav["net_asset"])
    weights = {
        row["ts_code"]: float(row["market_value"]) / net_asset
        for row in result.nav["positions"]
    }
    target_codes = [_code(code) for code in targets]
    l1 = sum(abs(weights.get(code, 0.0) - 1.0 / 30.0) for code in target_codes)
    l1 += sum(weight for code, weight in weights.items() if code not in set(target_codes))
    l1 += float(result.nav["cash_ratio"])
    capacity = [
        _capacity(sources.daily, str(fill["ts_code"]), signal_date, float(fill["notional"]))
        for fill in result.fills
    ]
    rejected = sum(
        order.get("side") == "BUY" and order.get("reject_reason") == "BELOW_MIN_LOT"
        for order in result.orders
    )
    invalid_lots = sum(
        (str(fill["ts_code"]).startswith(("688", "689")) and int(fill["position_after"]) < 200)
        or (not str(fill["ts_code"]).startswith(("688", "689")) and int(fill["quantity"]) % 100 != 0)
        for fill in result.fills if fill["side"] == "BUY"
    )
    return {
        "trade_date": result.nav["trade_date"], "signal_date": signal_date,
        "targets": targets, "target_sha256": canonical_sha256(targets),
        "position_count": len(result.nav["positions"]),
        "cash_ratio": float(result.nav["cash_ratio"]), "target_l1_error": l1,
        "minimum_lot_rejection_count": rejected, "target_buy_leg_count": 30,
        "capacity": capacity,
        "capacity_violation_count": sum(row["violation"] for row in capacity),
        "invalid_lot_fill_count": invalid_lots,
        "accounting_difference": float(result.nav["equation_difference"]),
        "negative_cash": float(result.nav["cash"]) < 0,
    }


def run_window(name: str, treatment: dict[str, Any], sources: RawSources) -> dict[str, Any]:
    policy = frozen_policy()
    dates = [_date(row["date"]) for row in treatment["daily"]]
    rebalances = {_date(row["trade_date"]): row for row in treatment["rebalances"]}
    if not rebalances or any(date not in dates for date in rebalances):
        raise ProtocolError(f"M6-5B rebalance date differs: {name}")
    first_targets = list(next(iter(rebalances.values()))["targets"])
    active_targets, state = first_targets, None
    daily_rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    benchmark_base_close: float | None = None
    for execution_date in dates:
        rebalance = rebalances.get(execution_date)
        if rebalance:
            active_targets = list(rebalance["targets"])
        signal_date = _date(rebalance["signal_date"]) if rebalance else execution_date
        market = sources.daily.loc[sources.daily["trade_date"].eq(execution_date)]
        signal_market = sources.daily.loc[sources.daily["trade_date"].eq(signal_date)]
        index_rows = sources.index_daily.loc[sources.index_daily["trade_date"].eq(execution_date)]
        if len(index_rows) != 1:
            raise ProtocolError(f"M6-5B benchmark row count differs: {execution_date}")
        index_row = index_rows.iloc[0]
        benchmark_base_close = benchmark_base_close or float(index_row["close"])
        signal = _signal(active_targets, bool(rebalance))
        result = execute_day(
            policy=policy, state=state, signal=signal,
            signal_sha256=canonical_sha256(signal), execution_date=execution_date,
            daily=market, signal_daily=signal_market, index_row=index_row,
            stock_basic=sources.stock_basic, namechange=sources.namechange,
            suspend=sources.suspend, trade_cal=sources.trade_cal,
            dividends=sources.dividends, run_id=f"m6-5b-{name}-{execution_date}",
            market_batch_id=sources.manifest_sha256[:20],
        )
        state = result.state
        base_nav = float(result.nav["normalized_nav"])
        cumulative_fee = float(result.nav["cumulative_fees"])
        daily_rows.append({
            "date": execution_date, "net_asset": float(result.nav["net_asset"]),
            "normalized_nav": base_nav,
            "benchmark_nav": float(index_row["close"]) / benchmark_base_close,
            "cost_1_5_nav": base_nav - 0.5 * cumulative_fee / policy.initial_cash,
            "cost_2_nav": base_nav - cumulative_fee / policy.initial_cash,
            "daily_fees": float(result.nav["daily_fees"]),
            "cash": float(result.nav["cash"]), "drawdown": float(result.nav["drawdown"]),
        })
        if rebalance:
            diagnostics.append(_rebalance_diagnostic(result, active_targets, signal_date, sources))
    return {
        "window": name, "policy_sha256": policy_sha256(policy),
        "daily": daily_rows, "rebalances": diagnostics,
        "ideal_daily": treatment["daily"],
    }


def run_all(bundle: dict[str, Any], sources: RawSources) -> dict[str, Any]:
    return {
        "schema_version": "m6-head30-500k-simulation-pass-v1",
        "windows": {
            name: run_window(name, treatment, sources)
            for name, treatment in bundle["treatments"].items()
        },
    }
