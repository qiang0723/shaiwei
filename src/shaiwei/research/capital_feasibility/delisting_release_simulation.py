"""M6-5C post-hoc paper-v2 replay with PIT delisting-risk exits."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pandas as pd

from shaiwei.paper.engine import policy_sha256
from shaiwei.paper.risk_exit_engine import execute_paper_day
from shaiwei.paper.risk_exit_policy import PaperDelistingRiskPortfolio
from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.production_conversion.contract import ProtocolError

from .delisting_risk import RiskOverlayState, RiskPolicy, evaluate_risk_overlay
from .simulation import (
    _capacity,
    _code,
    _date,
    _rebalance_diagnostic,
    frozen_policy,
)
from .source_reader import RawSources


RISK_POLICY = RiskPolicy(
    trigger_price=Decimal("1.0"),
    trigger_sessions=10,
    target_weight=Decimal(1) / Decimal(30),
)


def risk_portfolio() -> PaperDelistingRiskPortfolio:
    values = frozen_policy().model_dump()
    values.update(
        {
            "account_id": "m6_head30_delisting_risk",
            "execution_policy_version": "paper-v2-delisting-risk-exit",
            "risk_trigger_price_cny": 1.0,
            "risk_trigger_consecutive_closes": 10,
            "risk_exit_latched": True,
            "risk_cash_reserve_authorized": True,
        }
    )
    return PaperDelistingRiskPortfolio(**values)


def _instrument(code: str) -> str:
    value = _code(code)
    symbol, exchange = value.split(".")
    if exchange not in {"SH", "SZ"}:
        raise ProtocolError("M6-5C contains a forbidden target instrument")
    return f"{exchange}{symbol}"


def _signal(codes: tuple[str, ...], due: bool) -> dict[str, Any]:
    return {
        "rebalance_due": due,
        "orders": [
            {
                "instrument": _instrument(code),
                "rank": rank,
                "target_weight": 1.0 / 30.0,
            }
            for rank, code in enumerate(codes, start=1)
        ],
    }


def _previous_open_day(sources: RawSources, execution_date: str) -> str:
    calendar = sources.trade_cal.copy()
    candidates = calendar.loc[
        calendar["is_open"].astype(str).eq("1")
        & calendar["cal_date"].astype(str).lt(execution_date),
        "cal_date",
    ].astype(str)
    if candidates.empty:
        raise ProtocolError(f"M6-5C prior official session is absent: {execution_date}")
    return max(candidates)


def _observations(
    treatment: dict[str, Any], sources: RawSources
) -> list[dict[str, object]]:
    targets = {
        _code(code)
        for rebalance in treatment["rebalances"]
        for code in rebalance["targets"]
    }
    dates = [_date(row["date"]) for row in treatment["daily"]]
    first_as_of = _previous_open_day(sources, min(dates))
    calendar = sorted(
        sources.trade_cal.loc[
            sources.trade_cal["is_open"].astype(str).eq("1")
            & sources.trade_cal["cal_date"].astype(str).le(first_as_of),
            "cal_date",
        ].astype(str).unique()
    )
    if len(calendar) < RISK_POLICY.trigger_sessions:
        raise ProtocolError("M6-5C risk bootstrap calendar is incomplete")
    # Keep the same 90-day source horizon as the frozen reader. Ten *valid*
    # closes may span more than ten official sessions when a security is suspended.
    start = calendar[-min(90, len(calendar))]
    end = _previous_open_day(sources, max(dates))
    frame = sources.daily.loc[
        sources.daily["ts_code"].isin(targets)
        & sources.daily["trade_date"].between(start, end),
        ["ts_code", "trade_date", "close"],
    ].copy()
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    if (
        frame.duplicated(["ts_code", "trade_date"]).any()
        or frame["ts_code"].str.endswith(".BJ").any()
        or frame["close"].isna().any()
        or frame["close"].le(0).any()
    ):
        raise ProtocolError("M6-5C risk observations are invalid")
    return frame.sort_values(["trade_date", "ts_code"]).to_dict("records")


def _risk_capacity(
    result: Any,
    *,
    as_of: str,
    forced_exit_codes: tuple[str, ...],
    sources: RawSources,
) -> list[dict[str, Any]]:
    forced = set(forced_exit_codes)
    return [
        _capacity(
            sources.daily,
            str(fill["ts_code"]),
            as_of,
            float(fill["notional"]),
        )
        for fill in result.fills
        if str(fill["ts_code"]) in forced and fill["side"] == "SELL"
    ]


def run_window(
    name: str,
    treatment: dict[str, Any],
    sources: RawSources,
) -> dict[str, Any]:
    policy = risk_portfolio()
    dates = [_date(row["date"]) for row in treatment["daily"]]
    rebalances = {_date(row["trade_date"]): row for row in treatment["rebalances"]}
    if not rebalances or any(day not in dates for day in rebalances):
        raise ProtocolError(f"M6-5C rebalance date differs: {name}")
    active_targets = tuple(_code(code) for code in next(iter(rebalances.values()))["targets"])
    observations = _observations(treatment, sources)
    state = None
    risk_state = RiskOverlayState()
    daily_rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    risk_trace: list[dict[str, Any]] = []
    benchmark_base_close: float | None = None
    for execution_date in dates:
        rebalance = rebalances.get(execution_date)
        if rebalance:
            active_targets = tuple(_code(code) for code in rebalance["targets"])
        as_of = _previous_open_day(sources, execution_date)
        held_before = tuple(sorted(state.positions)) if state else ()
        visible = [row for row in observations if str(row["trade_date"]) <= as_of]
        decision = evaluate_risk_overlay(
            visible,
            as_of=as_of,
            target_codes=active_targets,
            held_codes=held_before,
            policy=RISK_POLICY,
            previous_state=risk_state,
        )
        risk_state = decision.next_state
        signal = _signal(decision.eligible_target_codes, bool(rebalance))
        market = sources.daily.loc[sources.daily["trade_date"].eq(execution_date)]
        signal_market = sources.daily.loc[sources.daily["trade_date"].eq(as_of)]
        index_rows = sources.index_daily.loc[
            sources.index_daily["trade_date"].eq(execution_date)
        ]
        if len(index_rows) != 1:
            raise ProtocolError(f"M6-5C benchmark row count differs: {execution_date}")
        index_row = index_rows.iloc[0]
        benchmark_base_close = benchmark_base_close or float(index_row["close"])
        result = execute_paper_day(
            policy=policy,
            state=state,
            signal=signal,
            signal_sha256=canonical_sha256(signal),
            execution_date=execution_date,
            daily=market,
            signal_daily=signal_market,
            index_row=index_row,
            stock_basic=sources.stock_basic,
            namechange=sources.namechange,
            suspend=sources.suspend,
            trade_cal=sources.trade_cal,
            dividends=sources.dividends,
            run_id=f"m6-5c-{name}-{execution_date}",
            market_batch_id=sources.manifest_sha256[:20],
            forced_exit_codes=decision.forced_exit_codes,
        )
        state = result.state
        capacity = _risk_capacity(
            result,
            as_of=as_of,
            forced_exit_codes=decision.forced_exit_codes,
            sources=sources,
        )
        risk_orders = [
            order
            for order in result.orders
            if order.get("execution_reason") == "DELISTING_PRICE_RISK_EXIT"
        ]
        risk_trace.append(
            {
                "execution_date": execution_date,
                "as_of": as_of,
                "held_before": list(held_before),
                "target_codes": list(active_targets),
                "decision": decision.as_dict(),
                "risk_orders": risk_orders,
                "held_after": sorted(state.positions),
                "risk_capacity": capacity,
            }
        )
        base_nav = float(result.nav["normalized_nav"])
        cumulative_fee = float(result.nav["cumulative_fees"])
        daily_rows.append(
            {
                "date": execution_date,
                "net_asset": float(result.nav["net_asset"]),
                "normalized_nav": base_nav,
                "benchmark_nav": float(index_row["close"]) / benchmark_base_close,
                "cost_1_5_nav": base_nav - 0.5 * cumulative_fee / policy.initial_cash,
                "cost_2_nav": base_nav - cumulative_fee / policy.initial_cash,
                "daily_fees": float(result.nav["daily_fees"]),
                "cash": float(result.nav["cash"]),
                "drawdown": float(result.nav["drawdown"]),
            }
        )
        if rebalance:
            signal_date = _date(rebalance["signal_date"])
            if signal_date != as_of:
                raise ProtocolError("M6-5C rebalance signal clock differs")
            diagnostics.append(
                _rebalance_diagnostic(
                    result,
                    list(active_targets),
                    signal_date,
                    sources,
                )
            )
    return {
        "window": name,
        "policy_sha256": policy_sha256(policy),
        "daily": daily_rows,
        "rebalances": diagnostics,
        "ideal_daily": treatment["daily"],
        "official_open_dates": sorted(
            sources.trade_cal.loc[
                sources.trade_cal["is_open"].astype(str).eq("1")
                & sources.trade_cal["cal_date"].astype(str).le(max(dates)),
                "cal_date",
            ].astype(str).unique()
        ),
        "risk_observations": observations,
        "risk_trace": risk_trace,
    }


def run_all(bundle: dict[str, Any], sources: RawSources) -> dict[str, Any]:
    return {
        "schema_version": "m6-head30-500k-delisting-risk-simulation-pass-v1",
        "windows": {
            name: run_window(name, treatment, sources)
            for name, treatment in bundle["treatments"].items()
        },
    }
