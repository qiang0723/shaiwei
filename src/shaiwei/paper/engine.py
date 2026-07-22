"""Pure paper-portfolio execution and accounting for one official trade date."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
import numpy as np
import pandas as pd

from shaiwei.config import PaperPortfolio
from shaiwei.shadow.reconciliation import tushare_code
from shaiwei.transform.universe import st_flags_on

CENT = Decimal("0.01")
ZERO = Decimal("0")


class PaperEngineError(RuntimeError):
    pass


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal | float | str) -> Decimal:
    return _decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def policy_sha256(policy: PaperPortfolio) -> str:
    return hashlib.sha256(_canonical(policy.model_dump(mode="json"))).hexdigest()


@dataclass
class Position:
    quantity: int
    cost_basis: str
    realized_pnl: str = "0.00"
    last_close: str = ""
    last_price_date: str = ""

    @property
    def cost(self) -> Decimal:
        return _decimal(self.cost_basis)


@dataclass
class Entitlement:
    action_id: str
    ts_code: str
    record_date: str
    entitled_quantity: int
    cash_per_share: str
    stock_per_share: str
    pay_date: str
    div_listdate: str
    cash_paid: bool = False
    stock_paid: bool = False


@dataclass
class PortfolioState:
    account_id: str
    cash: str
    positions: dict[str, Position] = field(default_factory=dict)
    entitlements: dict[str, Entitlement] = field(default_factory=dict)
    cumulative_fees: str = "0.00"
    cumulative_dividends: str = "0.00"
    benchmark_base_open: str = ""
    peak_nav: str = "1"
    last_trade_date: str = ""

    @property
    def cash_value(self) -> Decimal:
        return _decimal(self.cash)

    @classmethod
    def initial(cls, policy: PaperPortfolio, benchmark_open: object) -> "PortfolioState":
        return cls(
            account_id=policy.account_id,
            cash=f"{_money(policy.initial_cash):.2f}",
            benchmark_base_open=str(_decimal(benchmark_open)),
        )

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "PortfolioState":
        return cls(
            account_id=str(payload["account_id"]),
            cash=str(payload["cash"]),
            positions={
                str(code): Position(**position)
                for code, position in dict(payload.get("positions", {})).items()
            },
            entitlements={
                str(key): Entitlement(**entitlement)
                for key, entitlement in dict(payload.get("entitlements", {})).items()
            },
            cumulative_fees=str(payload.get("cumulative_fees", "0.00")),
            cumulative_dividends=str(payload.get("cumulative_dividends", "0.00")),
            benchmark_base_open=str(payload.get("benchmark_base_open", "")),
            peak_nav=str(payload.get("peak_nav", "1")),
            last_trade_date=str(payload.get("last_trade_date", "")),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "account_id": self.account_id,
            "cash": self.cash,
            "positions": {code: asdict(position) for code, position in sorted(self.positions.items())},
            "entitlements": {
                key: asdict(entitlement) for key, entitlement in sorted(self.entitlements.items())
            },
            "cumulative_fees": self.cumulative_fees,
            "cumulative_dividends": self.cumulative_dividends,
            "benchmark_base_open": self.benchmark_base_open,
            "peak_nav": self.peak_nav,
            "last_trade_date": self.last_trade_date,
        }


@dataclass(frozen=True)
class DayResult:
    state: PortfolioState
    orders: tuple[dict[str, object], ...]
    fills: tuple[dict[str, object], ...]
    corporate_actions: tuple[dict[str, object], ...]
    nav: dict[str, object]


def calculate_fees(notional: Decimal, side: str, policy: PaperPortfolio) -> dict[str, Decimal]:
    if notional <= 0:
        raise PaperEngineError("fee notional must be positive")
    commission = max(
        _money(notional * _decimal(policy.commission_rate)),
        _money(policy.minimum_commission),
    )
    transfer = _money(notional * _decimal(policy.transfer_fee_rate))
    stamp = _money(notional * _decimal(policy.stamp_tax_rate)) if side == "SELL" else ZERO
    return {
        "commission": commission,
        "stamp_tax": stamp,
        "transfer_fee": transfer,
        "total": _money(commission + stamp + transfer),
    }


def _board(code: str) -> str:
    symbol, exchange = code.split(".")
    if exchange == "SH" and symbol.startswith(("688", "689")):
        return "STAR"
    if exchange == "SZ" and symbol.startswith(("300", "301")):
        return "CHINEXT"
    return "MAIN"


def _stock_basic_row(stock_basic: pd.DataFrame, code: str) -> pd.Series:
    rows = stock_basic.loc[stock_basic["ts_code"].astype(str).eq(code)].copy()
    if rows.empty:
        raise PaperEngineError(f"stock_basic missing security: {code}")
    return rows.sort_values("list_date").iloc[-1]


def _first_five_sessions(
    stock_basic: pd.DataFrame,
    trade_cal: pd.DataFrame,
    code: str,
    trade_date: str,
) -> bool:
    list_date = str(_stock_basic_row(stock_basic, code)["list_date"])
    sessions = sorted(
        trade_cal.loc[
            trade_cal["is_open"].astype(str).eq("1")
            & trade_cal["cal_date"].astype(str).between(list_date, trade_date),
            "cal_date",
        ].astype(str).unique()
    )
    return trade_date in sessions[:5]


def _is_st(namechange: pd.DataFrame, code: str, trade_date: str) -> bool:
    observations = pd.DataFrame({"ts_code": [code], "trade_date": [trade_date]})
    return bool(st_flags_on(namechange, observations).iloc[0])


def _open_suspended(suspend: pd.DataFrame, code: str, trade_date: str) -> bool:
    if suspend.empty:
        return False
    rows = suspend.loc[
        suspend["ts_code"].astype(str).eq(code)
        & suspend["trade_date"].astype(str).eq(trade_date)
        & suspend["suspend_type"].astype(str).eq("S")
    ]
    for row in rows.itertuples(index=False):
        timing = "" if pd.isna(row.suspend_timing) else str(row.suspend_timing).strip()
        if not timing or timing.startswith(("09:15", "09:25", "09:30")):
            return True
    return False


def opening_status(
    *,
    code: str,
    side: str,
    trade_date: str,
    daily: pd.DataFrame,
    stock_basic: pd.DataFrame,
    namechange: pd.DataFrame,
    suspend: pd.DataFrame,
    trade_cal: pd.DataFrame,
    policy: PaperPortfolio,
) -> tuple[str, Decimal | None]:
    if code.endswith(".BJ"):
        raise PaperEngineError("BSE instrument is forbidden in paper portfolio")
    rows = daily.loc[daily["ts_code"].astype(str).eq(code)]
    if len(rows) != 1:
        return "MISSING_PRICE", None
    row = rows.iloc[0]
    try:
        open_price = _decimal(row["open"])
        pre_close = _decimal(row["pre_close"])
        volume = _decimal(row["vol"])
    except Exception:
        return "MISSING_PRICE", None
    if open_price <= 0 or pre_close <= 0 or volume <= 0:
        return "MISSING_PRICE", None
    if _open_suspended(suspend, code, trade_date):
        return "OPEN_SUSPENDED", open_price
    threshold: Decimal | None
    if _first_five_sessions(stock_basic, trade_cal, code, trade_date):
        threshold = None
    elif _board(code) in {"STAR", "CHINEXT"}:
        threshold = Decimal("0.20")
    elif _is_st(namechange, code, trade_date):
        effective = policy.st_main_ten_percent_effective.strftime("%Y%m%d")
        threshold = Decimal("0.10") if trade_date >= effective else Decimal("0.05")
    else:
        threshold = Decimal("0.10")
    if threshold is not None:
        opening_change = open_price / pre_close - 1
        tolerance = Decimal("0.01") / pre_close
        if side == "BUY" and opening_change >= threshold - tolerance:
            return "BUY_LIMIT_UP", open_price
        if side == "SELL" and opening_change <= -threshold + tolerance:
            return "SELL_LIMIT_DOWN", open_price
    return "OK", open_price


def _desired_quantity(code: str, target_value: Decimal, price: Decimal, policy: PaperPortfolio) -> int:
    raw = int((target_value / price).to_integral_value(rounding=ROUND_FLOOR))
    if _board(code) == "STAR":
        return raw if raw >= policy.star_minimum_lot else 0
    return raw // policy.main_board_lot_size * policy.main_board_lot_size


def _sell_quantity(code: str, current: int, desired: int, policy: PaperPortfolio) -> int:
    difference = current - desired
    if difference <= 0:
        return 0
    if desired == 0:
        return current
    if _board(code) == "STAR":
        return difference if difference >= policy.star_minimum_lot else 0
    return difference // policy.main_board_lot_size * policy.main_board_lot_size


def _implemented_actions(
    dividends: pd.DataFrame,
    *,
    relevant_codes: set[str],
    after_date: str,
    through_date: str,
) -> list[dict[str, object]]:
    if dividends.empty:
        return []
    required = {
        "ts_code",
        "end_date",
        "ann_date",
        "div_proc",
        "stk_div",
        "cash_div_tax",
        "record_date",
        "pay_date",
        "div_listdate",
        "imp_ann_date",
    }
    if missing := required - set(dividends.columns):
        raise PaperEngineError(f"dividend data missing fields: {sorted(missing)}")
    rows = dividends.loc[
        dividends["div_proc"].astype("string").str.contains("实施", na=False)
        & dividends["ts_code"].astype("string").isin(relevant_codes)
    ].copy()
    implementation_date = rows["imp_ann_date"].astype("string").str.strip()
    announcement_date = rows["ann_date"].astype("string").str.strip()
    rows["_order"] = implementation_date.where(
        implementation_date.notna() & implementation_date.ne(""),
        announcement_date,
    )
    rows = rows.loc[rows["_order"].notna() & rows["_order"].le(through_date)]
    rows = rows.sort_values("_order").drop_duplicates(["ts_code", "end_date"], keep="last")
    rows = rows.loc[
        rows["record_date"].astype("string").gt(after_date)
        & rows["record_date"].astype("string").le(through_date)
    ]
    actions: list[dict[str, object]] = []
    for row in rows.itertuples(index=False):
        cash = ZERO if pd.isna(row.cash_div_tax) else _decimal(row.cash_div_tax)
        stock = ZERO if pd.isna(row.stk_div) else _decimal(row.stk_div)
        if cash <= 0 and stock <= 0:
            continue
        record_date = "" if pd.isna(row.record_date) else str(row.record_date)
        pay_date = "" if pd.isna(row.pay_date) else str(row.pay_date)
        list_date = "" if pd.isna(row.div_listdate) else str(row.div_listdate)
        if not record_date or (cash > 0 and not pay_date) or (stock > 0 and not list_date):
            raise PaperEngineError(f"implemented corporate action has incomplete dates: {row.ts_code}")
        identity = {
            "ts_code": str(row.ts_code),
            "end_date": str(row.end_date),
            "record_date": record_date,
            "pay_date": pay_date,
            "div_listdate": list_date,
            "cash_per_share": str(cash),
            "stock_per_share": str(stock),
        }
        actions.append({**identity, "action_id": hashlib.sha256(_canonical(identity)).hexdigest()[:20]})
    return actions


def _apply_due_actions(
    state: PortfolioState,
    *,
    day: str,
    actions: list[dict[str, object]],
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    cash = state.cash_value
    for entitlement in state.entitlements.values():
        if entitlement.pay_date == day and not entitlement.cash_paid:
            amount = _money(_decimal(entitlement.cash_per_share) * entitlement.entitled_quantity)
            cash = _money(cash + amount)
            entitlement.cash_paid = True
            state.cumulative_dividends = f"{_money(_decimal(state.cumulative_dividends) + amount):.2f}"
            events.append(
                {
                    "action_id": entitlement.action_id,
                    "event": "CASH_DIVIDEND",
                    "ts_code": entitlement.ts_code,
                    "quantity": entitlement.entitled_quantity,
                    "amount": f"{amount:.2f}",
                    "cash_after": f"{cash:.2f}",
                    "position_after": state.positions.get(
                        entitlement.ts_code, Position(0, "0.00")
                    ).quantity,
                }
            )
        if entitlement.div_listdate == day and not entitlement.stock_paid:
            raw = _decimal(entitlement.stock_per_share) * entitlement.entitled_quantity
            shares = int(raw.to_integral_value(rounding=ROUND_FLOOR))
            if raw != shares:
                raise PaperEngineError("fractional stock dividend requires authoritative rounding evidence")
            if shares:
                position = state.positions.get(entitlement.ts_code)
                if position is None:
                    raise PaperEngineError("stock dividend entitlement has no position")
                position.quantity += shares
            entitlement.stock_paid = True
            events.append(
                {
                    "action_id": entitlement.action_id,
                    "event": "STOCK_DIVIDEND",
                    "ts_code": entitlement.ts_code,
                    "quantity": shares,
                    "amount": "0.00",
                    "cash_after": f"{cash:.2f}",
                    "position_after": state.positions.get(
                        entitlement.ts_code, Position(0, "0.00")
                    ).quantity,
                }
            )
    state.cash = f"{cash:.2f}"
    return events


def _capture_entitlements(
    state: PortfolioState,
    *,
    day: str,
    actions: list[dict[str, object]],
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for action in actions:
        action_id = str(action["action_id"])
        if action["record_date"] != day or action_id in state.entitlements:
            continue
        code = str(action["ts_code"])
        quantity = state.positions.get(code, Position(0, "0.00")).quantity
        if quantity <= 0:
            continue
        state.entitlements[action_id] = Entitlement(
            action_id=action_id,
            ts_code=code,
            record_date=day,
            entitled_quantity=quantity,
            cash_per_share=str(action["cash_per_share"]),
            stock_per_share=str(action["stock_per_share"]),
            pay_date=str(action["pay_date"]),
            div_listdate=str(action["div_listdate"]),
        )
        events.append(
            {
                "action_id": action_id,
                "event": "ENTITLEMENT",
                "ts_code": code,
                "quantity": quantity,
                "amount": "0.00",
                "cash_after": state.cash,
                "position_after": quantity,
            }
        )
    return events


def _intermediate_action_events(
    state: PortfolioState,
    *,
    execution_date: str,
    actions: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not state.last_trade_date:
        return []
    start = datetime.strptime(state.last_trade_date, "%Y%m%d").date() + timedelta(days=1)
    end = datetime.strptime(execution_date, "%Y%m%d").date()
    events: list[dict[str, object]] = []
    cursor = start
    while cursor < end:
        day = cursor.strftime("%Y%m%d")
        events.extend(_apply_due_actions(state, day=day, actions=actions))
        events.extend(_capture_entitlements(state, day=day, actions=actions))
        cursor += timedelta(days=1)
    return events


def _target_weights(signal: dict[str, object]) -> tuple[dict[str, Decimal], dict[str, int]]:
    orders = signal.get("orders")
    if not isinstance(orders, list):
        raise PaperEngineError("signal orders must be a list")
    weights: dict[str, Decimal] = {}
    ranks: dict[str, int] = {}
    for order in orders:
        if not isinstance(order, dict):
            raise PaperEngineError("signal order must be an object")
        instrument = str(order["instrument"])
        if instrument.upper().startswith("BJ"):
            raise PaperEngineError("BSE instrument is forbidden in paper signal")
        code = tushare_code(instrument)
        if code.endswith(".BJ") or code in weights:
            raise PaperEngineError("paper signal contains forbidden or duplicate instrument")
        weights[code] = _decimal(order["target_weight"])
        ranks[code] = int(order["rank"])
    if not np.isclose(float(sum(weights.values(), ZERO)), 1.0, atol=1e-9):
        raise PaperEngineError("signal target weights must sum to one")
    return weights, ranks


def _order(
    *,
    run_id: str,
    code: str,
    side: str,
    target_weight: Decimal,
    desired_quantity: int,
    requested_quantity: int,
    status: str = "PENDING",
    reject_reason: str = "",
) -> dict[str, object]:
    key = f"{run_id}|{code}|{side}"
    return {
        "order_id": hashlib.sha256(key.encode()).hexdigest()[:20],
        "ts_code": code,
        "side": side,
        "target_weight": str(target_weight),
        "desired_quantity": desired_quantity,
        "requested_quantity": requested_quantity,
        "filled_quantity": 0,
        "status": status,
        "reject_reason": reject_reason,
    }


def _fill(
    *,
    order: dict[str, object],
    quantity: int,
    price: Decimal,
    fees: dict[str, Decimal],
    market_batch_id: str,
    reference_close: Decimal | None,
    cash_after: Decimal,
    position_after: int,
) -> dict[str, object]:
    notional = _money(price * quantity)
    deviation = None if reference_close is None else float(price / reference_close - 1)
    return {
        "fill_id": hashlib.sha256(f"{order['order_id']}|{quantity}|{price}".encode()).hexdigest()[:20],
        "order_id": order["order_id"],
        "ts_code": order["ts_code"],
        "side": order["side"],
        "quantity": quantity,
        "price": str(price),
        "notional": f"{notional:.2f}",
        "commission": f"{fees['commission']:.2f}",
        "stamp_tax": f"{fees['stamp_tax']:.2f}",
        "transfer_fee": f"{fees['transfer_fee']:.2f}",
        "total_fee": f"{fees['total']:.2f}",
        "market_batch_id": market_batch_id,
        "open_deviation": deviation,
        "cash_after": f"{cash_after:.2f}",
        "position_after": position_after,
    }


def _valuation(
    state: PortfolioState,
    *,
    execution_date: str,
    daily: pd.DataFrame,
    index_row: pd.Series,
    stock_basic: pd.DataFrame,
    trade_cal: pd.DataFrame,
    opening_equity: Decimal,
    gross_notional: Decimal,
    daily_fees: Decimal,
    policy: PaperPortfolio,
) -> dict[str, object]:
    market_value = ZERO
    positions: list[dict[str, object]] = []
    stale = False
    open_dates = sorted(
        trade_cal.loc[trade_cal["is_open"].astype(str).eq("1"), "cal_date"].astype(str).unique()
    )
    for code, position in sorted(state.positions.items()):
        basic = _stock_basic_row(stock_basic, code)
        delist_date = "" if pd.isna(basic.get("delist_date")) else str(basic.get("delist_date"))
        if delist_date and delist_date <= execution_date:
            raise PaperEngineError(f"delisted position requires an explicit disposal rule: {code}")
        rows = daily.loc[daily["ts_code"].astype(str).eq(code)]
        if len(rows) == 1 and pd.notna(rows.iloc[0]["close"]) and float(rows.iloc[0]["close"]) > 0:
            position.last_close = str(_decimal(rows.iloc[0]["close"]))
            position.last_price_date = execution_date
        if not position.last_close or not position.last_price_date:
            raise PaperEngineError(f"position has no valid valuation price: {code}")
        stale_days = sum(position.last_price_date < day <= execution_date for day in open_dates)
        stale = stale or stale_days > policy.stale_price_trade_days
        value = _money(_decimal(position.last_close) * position.quantity)
        market_value += value
        positions.append(
            {
                "ts_code": code,
                "quantity": position.quantity,
                "close": position.last_close,
                "price_date": position.last_price_date,
                "stale_trade_days": stale_days,
                "market_value": f"{value:.2f}",
                "cost_basis": position.cost_basis,
                "realized_pnl": position.realized_pnl,
            }
        )
    market_value = _money(market_value)
    cash = state.cash_value
    net_asset = _money(cash + market_value)
    equation_difference = _money(net_asset - cash - market_value)
    if abs(equation_difference) > _decimal(policy.accounting_tolerance):
        raise PaperEngineError("accounting identity failed")
    initial = _decimal(policy.initial_cash)
    normalized_nav = net_asset / initial
    peak = max(_decimal(state.peak_nav), normalized_nav)
    state.peak_nav = str(peak)
    benchmark_close = _decimal(index_row["close"])
    benchmark_nav = benchmark_close / _decimal(state.benchmark_base_open)
    return {
        "trade_date": execution_date,
        "cash": f"{cash:.2f}",
        "market_value": f"{market_value:.2f}",
        "net_asset": f"{net_asset:.2f}",
        "normalized_nav": str(normalized_nav),
        "benchmark_nav": str(benchmark_nav),
        "net_excess": str(normalized_nav - benchmark_nav),
        "drawdown": str(normalized_nav / peak - 1),
        "turnover": str(ZERO if opening_equity == 0 else gross_notional / opening_equity),
        "daily_fees": f"{daily_fees:.2f}",
        "cumulative_fees": state.cumulative_fees,
        "cumulative_dividends": state.cumulative_dividends,
        "cash_ratio": str(ZERO if net_asset == 0 else cash / net_asset),
        "equation_difference": f"{equation_difference:.2f}",
        "freshness_status": "STALE" if stale else "PASS",
        "positions": positions,
    }


def execute_day(
    *,
    policy: PaperPortfolio,
    state: PortfolioState | None,
    signal: dict[str, object],
    signal_sha256: str,
    execution_date: str,
    daily: pd.DataFrame,
    signal_daily: pd.DataFrame,
    index_row: pd.Series,
    stock_basic: pd.DataFrame,
    namechange: pd.DataFrame,
    suspend: pd.DataFrame,
    trade_cal: pd.DataFrame,
    dividends: pd.DataFrame,
    run_id: str,
    market_batch_id: str,
) -> DayResult:
    if str(index_row["trade_date"]) != execution_date:
        raise PaperEngineError("benchmark row does not match execution date")
    if state is None:
        state = PortfolioState.initial(policy, index_row["open"])
    if state.account_id != policy.account_id:
        raise PaperEngineError("paper state account does not match policy")
    if state.last_trade_date and state.last_trade_date >= execution_date:
        raise PaperEngineError("paper execution dates must be strictly increasing")
    weights, ranks = _target_weights(signal)
    action_after = state.last_trade_date or (
        datetime.strptime(execution_date, "%Y%m%d").date() - timedelta(days=1)
    ).strftime("%Y%m%d")
    actions = _implemented_actions(
        dividends,
        relevant_codes=set(state.positions) | set(weights),
        after_date=action_after,
        through_date=execution_date,
    )
    action_events = _intermediate_action_events(
        state,
        execution_date=execution_date,
        actions=actions,
    )
    action_events.extend(_apply_due_actions(state, day=execution_date, actions=actions))
    rebalance_due = bool(signal.get("rebalance_due", True))
    open_prices: dict[str, Decimal] = {}
    for code in set(state.positions) | set(weights):
        rows = daily.loc[daily["ts_code"].astype(str).eq(code)]
        if len(rows) == 1 and pd.notna(rows.iloc[0]["open"]) and float(rows.iloc[0]["open"]) > 0:
            open_prices[code] = _decimal(rows.iloc[0]["open"])
        elif code in state.positions and state.positions[code].last_close:
            open_prices[code] = _decimal(state.positions[code].last_close)
    opening_equity = state.cash_value + sum(
        (open_prices[code] * position.quantity for code, position in state.positions.items()),
        ZERO,
    )
    desired = {
        code: _desired_quantity(code, opening_equity * weight, open_prices[code], policy)
        if code in open_prices
        else 0
        for code, weight in weights.items()
    }
    reference_close = {
        str(row.ts_code): _decimal(row.close)
        for row in signal_daily.loc[:, ["ts_code", "close"]].itertuples(index=False)
        if pd.notna(row.close) and float(row.close) > 0
    }
    orders: list[dict[str, object]] = []
    fills: list[dict[str, object]] = []
    gross_notional = ZERO
    daily_fees = ZERO
    cash = state.cash_value
    if rebalance_due:
        sell_codes = sorted(
            code
            for code, position in state.positions.items()
            if position.quantity > desired.get(code, 0)
        )
        for code in sell_codes:
            position = state.positions[code]
            quantity = _sell_quantity(code, position.quantity, desired.get(code, 0), policy)
            if quantity <= 0:
                continue
            order = _order(
                run_id=run_id,
                code=code,
                side="SELL",
                target_weight=weights.get(code, ZERO),
                desired_quantity=desired.get(code, 0),
                requested_quantity=quantity,
            )
            status, price = opening_status(
                code=code,
                side="SELL",
                trade_date=execution_date,
                daily=daily,
                stock_basic=stock_basic,
                namechange=namechange,
                suspend=suspend,
                trade_cal=trade_cal,
                policy=policy,
            )
            if status != "OK" or price is None:
                order.update(status="REJECTED", reject_reason=status)
                orders.append(order)
                continue
            notional = _money(price * quantity)
            fees = calculate_fees(notional, "SELL", policy)
            old_quantity = position.quantity
            removed_cost = _money(position.cost * quantity / old_quantity)
            realized = _money(notional - fees["total"] - removed_cost)
            position.quantity -= quantity
            position.cost_basis = f"{_money(position.cost - removed_cost):.2f}"
            position.realized_pnl = f"{_money(_decimal(position.realized_pnl) + realized):.2f}"
            cash = _money(cash + notional - fees["total"])
            order.update(status="FILLED", filled_quantity=quantity)
            fill = _fill(
                order=order,
                quantity=quantity,
                price=price,
                fees=fees,
                market_batch_id=market_batch_id,
                reference_close=reference_close.get(code),
                cash_after=cash,
                position_after=position.quantity,
            )
            orders.append(order)
            fills.append(fill)
            gross_notional += notional
            daily_fees += fees["total"]
            if position.quantity == 0:
                del state.positions[code]
        buy_codes = sorted(weights, key=lambda code: (ranks[code], code))
        for code in buy_codes:
            current = state.positions.get(code, Position(0, "0.00")).quantity
            requested = max(0, desired[code] - current)
            if requested == 0:
                if current == 0 and desired[code] == 0:
                    orders.append(
                        _order(
                            run_id=run_id,
                            code=code,
                            side="BUY",
                            target_weight=weights[code],
                            desired_quantity=0,
                            requested_quantity=0,
                            status="REJECTED",
                            reject_reason="BELOW_MIN_LOT",
                        )
                    )
                continue
            order = _order(
                run_id=run_id,
                code=code,
                side="BUY",
                target_weight=weights[code],
                desired_quantity=desired[code],
                requested_quantity=requested,
            )
            status, price = opening_status(
                code=code,
                side="BUY",
                trade_date=execution_date,
                daily=daily,
                stock_basic=stock_basic,
                namechange=namechange,
                suspend=suspend,
                trade_cal=trade_cal,
                policy=policy,
            )
            if status != "OK" or price is None:
                order.update(status="REJECTED", reject_reason=status)
                orders.append(order)
                continue
            quantity = requested
            step = 1 if _board(code) == "STAR" else policy.main_board_lot_size
            minimum = policy.star_minimum_lot if _board(code) == "STAR" and current == 0 else step
            while quantity >= minimum:
                notional = _money(price * quantity)
                fees = calculate_fees(notional, "BUY", policy)
                if notional + fees["total"] <= cash:
                    break
                quantity -= step
            if quantity < minimum:
                order.update(status="REJECTED", reject_reason="INSUFFICIENT_CASH")
                orders.append(order)
                continue
            notional = _money(price * quantity)
            fees = calculate_fees(notional, "BUY", policy)
            position = state.positions.setdefault(code, Position(0, "0.00"))
            position.quantity += quantity
            position.cost_basis = f"{_money(position.cost + notional + fees['total']):.2f}"
            cash = _money(cash - notional - fees["total"])
            order.update(
                status="FILLED" if quantity == requested else "PARTIALLY_FILLED",
                filled_quantity=quantity,
                reject_reason="" if quantity == requested else "CASH_LIMIT",
            )
            fill = _fill(
                order=order,
                quantity=quantity,
                price=price,
                fees=fees,
                market_batch_id=market_batch_id,
                reference_close=reference_close.get(code),
                cash_after=cash,
                position_after=position.quantity,
            )
            orders.append(order)
            fills.append(fill)
            gross_notional += notional
            daily_fees += fees["total"]
    state.cash = f"{_money(cash):.2f}"
    state.cumulative_fees = f"{_money(_decimal(state.cumulative_fees) + daily_fees):.2f}"
    action_events.extend(_capture_entitlements(state, day=execution_date, actions=actions))
    nav = _valuation(
        state,
        execution_date=execution_date,
        daily=daily,
        index_row=index_row,
        stock_basic=stock_basic,
        trade_cal=trade_cal,
        opening_equity=opening_equity,
        gross_notional=_money(gross_notional),
        daily_fees=_money(daily_fees),
        policy=policy,
    )
    state.last_trade_date = execution_date
    return DayResult(
        state=state,
        orders=tuple(orders),
        fills=tuple(fills),
        corporate_actions=tuple(action_events),
        nav=nav,
    )
