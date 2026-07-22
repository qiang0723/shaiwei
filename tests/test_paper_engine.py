from decimal import Decimal

import pandas as pd
import pytest

from shaiwei.config import load
from shaiwei.paper.engine import (
    PaperEngineError,
    Position,
    PortfolioState,
    calculate_fees,
    execute_day,
    opening_status,
    policy_sha256,
)


def _policy(**updates):
    return load().paper_portfolio.model_copy(update=updates)


def _calendar(*days: str) -> pd.DataFrame:
    return pd.DataFrame({"cal_date": list(days), "is_open": [1] * len(days)})


def _stock(*codes: str, list_date: str = "20100101") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_code": code,
                "list_date": list_date,
                "delist_date": None,
            }
            for code in codes
        ]
    )


def _names(*codes: str, st: bool = False) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_code": code,
                "name": "ST样本" if st else "普通样本",
                "start_date": "20100101",
                "end_date": None,
            }
            for code in codes
        ]
    )


def _suspend() -> pd.DataFrame:
    return pd.DataFrame(columns=["ts_code", "trade_date", "suspend_timing", "suspend_type"])


def _signal(codes: list[str], *, rebalance: bool = True) -> dict[str, object]:
    weight = 1 / len(codes)
    return {
        "rebalance_due": rebalance,
        "orders": [
            {
                "instrument": f"{code.split('.')[1]}{code.split('.')[0]}",
                "rank": rank,
                "target_weight": weight,
            }
            for rank, code in enumerate(codes, start=1)
        ],
    }


def _daily(day: str, values: dict[str, tuple[float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_code": code,
                "trade_date": day,
                "open": open_price,
                "pre_close": pre_close,
                "close": close,
                "vol": 1000,
            }
            for code, (open_price, pre_close, close) in values.items()
        ]
    )


def _index(day: str, open_price: float = 100, close: float = 101) -> pd.Series:
    return pd.Series({"ts_code": "000906.SH", "trade_date": day, "open": open_price, "close": close})


def test_frozen_policy_uses_half_million_rmb_and_stable_hash():
    policy = _policy()
    assert policy.initial_cash == 500_000
    assert policy.currency == "RMB"
    assert policy_sha256(policy) == policy_sha256(policy)


def test_fee_components_keep_broker_assumption_separate_from_statutory_fees():
    policy = _policy()
    buy = calculate_fees(Decimal("10000"), "BUY", policy)
    sell = calculate_fees(Decimal("10000"), "SELL", policy)
    assert buy == {
        "commission": Decimal("5.00"),
        "stamp_tax": Decimal("0"),
        "transfer_fee": Decimal("0.10"),
        "total": Decimal("5.10"),
    }
    assert sell["commission"] == Decimal("5.00")
    assert sell["stamp_tax"] == Decimal("5.00")
    assert sell["transfer_fee"] == Decimal("0.10")
    assert sell["total"] == Decimal("10.10")


def test_main_st_limit_switches_from_five_to_ten_percent_on_20260706():
    code = "600001.SH"
    stock = _stock(code)
    names = _names(code, st=True)
    calendar = _calendar(
        "20100104", "20100105", "20100106", "20100107", "20100108",
        "20260703", "20260706", "20260707",
    )
    before = _daily("20260703", {code: (10.8, 10.0, 10.8)})
    after = _daily("20260707", {code: (10.8, 10.0, 10.8)})
    assert opening_status(
        code=code,
        side="BUY",
        trade_date="20260703",
        daily=before,
        stock_basic=stock,
        namechange=names,
        suspend=_suspend(),
        trade_cal=calendar,
        policy=_policy(),
    )[0] == "BUY_LIMIT_UP"
    assert opening_status(
        code=code,
        side="BUY",
        trade_date="20260707",
        daily=after,
        stock_basic=stock,
        namechange=names,
        suspend=_suspend(),
        trade_cal=calendar,
        policy=_policy(),
    )[0] == "OK"


def test_first_five_sessions_have_no_price_limit_and_open_suspension_still_blocks():
    code = "688001.SH"
    calendar = _calendar("20260701", "20260702", "20260703", "20260706", "20260707")
    daily = _daily("20260707", {code: (15.0, 10.0, 14.0)})
    assert opening_status(
        code=code,
        side="BUY",
        trade_date="20260707",
        daily=daily,
        stock_basic=_stock(code, list_date="20260701"),
        namechange=_names(code),
        suspend=_suspend(),
        trade_cal=calendar,
        policy=_policy(),
    )[0] == "OK"
    suspended = pd.DataFrame(
        [
            {
                "ts_code": code,
                "trade_date": "20260707",
                "suspend_timing": None,
                "suspend_type": "S",
            }
        ]
    )
    assert opening_status(
        code=code,
        side="BUY",
        trade_date="20260707",
        daily=daily,
        stock_basic=_stock(code, list_date="20260701"),
        namechange=_names(code),
        suspend=suspended,
        trade_cal=calendar,
        policy=_policy(),
    )[0] == "OPEN_SUSPENDED"


def test_half_million_account_executes_lots_and_preserves_accounting_identity():
    codes = ["600001.SH", "000001.SZ"]
    day = "20260717"
    daily = _daily(day, {codes[0]: (10, 9.9, 10.2), codes[1]: (20, 19.8, 19.5)})
    result = execute_day(
        policy=_policy(),
        state=None,
        signal=_signal(codes),
        signal_sha256="s" * 64,
        execution_date=day,
        daily=daily,
        signal_daily=daily,
        index_row=_index(day),
        stock_basic=_stock(*codes),
        namechange=_names(*codes),
        suspend=_suspend(),
        trade_cal=_calendar(day),
        dividends=pd.DataFrame(),
        run_id="run1",
        market_batch_id="batch1",
    )
    assert len(result.fills) == 2
    assert all(int(fill["quantity"]) % 100 == 0 for fill in result.fills)
    assert Decimal(result.nav["equation_difference"]) == 0
    assert Decimal(result.nav["net_asset"]) == (
        Decimal(result.nav["cash"]) + Decimal(result.nav["market_value"])
    )
    assert Decimal(result.state.cumulative_fees) > 0


def test_star_target_below_two_hundred_shares_is_rejected_without_fake_position():
    code = "688001.SH"
    day = "20260717"
    daily = _daily(day, {code: (100, 100, 101)})
    result = execute_day(
        policy=_policy(initial_cash=10_000),
        state=None,
        signal=_signal([code]),
        signal_sha256="s" * 64,
        execution_date=day,
        daily=daily,
        signal_daily=daily,
        index_row=_index(day),
        stock_basic=_stock(code),
        namechange=_names(code),
        suspend=_suspend(),
        trade_cal=_calendar(day),
        dividends=pd.DataFrame(),
        run_id="run2",
        market_batch_id="batch2",
    )
    assert result.fills == ()
    assert result.orders[0]["status"] == "REJECTED"
    assert result.orders[0]["reject_reason"] == "BELOW_MIN_LOT"
    assert result.state.positions == {}
    assert result.nav["net_asset"] == "10000.00"


def test_bse_instrument_fails_closed_instead_of_being_silently_dropped():
    code = "920001.BJ"
    day = "20260717"
    with pytest.raises(PaperEngineError, match="BSE instrument is forbidden"):
        execute_day(
            policy=_policy(initial_cash=10_000),
            state=None,
            signal=_signal([code]),
            signal_sha256="b" * 64,
            execution_date=day,
            daily=_daily(day, {code: (10, 10, 10)}),
            signal_daily=_daily(day, {code: (10, 10, 10)}),
            index_row=_index(day),
            stock_basic=_stock(code),
            namechange=_names(code),
            suspend=_suspend(),
            trade_cal=_calendar(day),
            dividends=pd.DataFrame(),
            run_id="run-bse",
            market_batch_id="batch-bse",
        )


def test_dividend_entitlement_is_captured_on_record_date_and_paid_later():
    code = "600001.SH"
    first_day = "20260717"
    second_day = "20260720"
    dividends = pd.DataFrame(
        [
            {
                "ts_code": code,
                "end_date": "20251231",
                "ann_date": "20260501",
                "div_proc": "实施",
                "stk_div": 0.0,
                "cash_div_tax": 0.08,
                "record_date": first_day,
                "pay_date": second_day,
                "div_listdate": None,
                "imp_ann_date": "20260714",
            },
            {
                "ts_code": code,
                "end_date": "20251231",
                "ann_date": "20260501",
                "div_proc": "实施",
                "stk_div": 0.0,
                "cash_div_tax": 0.80,
                "record_date": first_day,
                "pay_date": second_day,
                "div_listdate": None,
                "imp_ann_date": "20260718",
            },
        ]
    )
    first_daily = _daily(first_day, {code: (10, 10, 10)})
    first = execute_day(
        policy=_policy(initial_cash=10_000),
        state=None,
        signal=_signal([code]),
        signal_sha256="a" * 64,
        execution_date=first_day,
        daily=first_daily,
        signal_daily=first_daily,
        index_row=_index(first_day),
        stock_basic=_stock(code),
        namechange=_names(code),
        suspend=_suspend(),
        trade_cal=_calendar(first_day, second_day),
        dividends=dividends,
        run_id="run3",
        market_batch_id="batch3",
    )
    entitlement_event = next(
        event for event in first.corporate_actions if event["event"] == "ENTITLEMENT"
    )
    assert entitlement_event["record_date"] == first_day
    assert entitlement_event["pay_date"] == second_day
    assert entitlement_event["cash_per_share"] == "0.08"
    entitlement = next(iter(first.state.entitlements.values()))
    assert entitlement.cash_per_share == "0.08"
    cash_before = Decimal(first.state.cash)
    held = first.state.positions[code].quantity
    second_daily = _daily(second_day, {code: (9.92, 10, 10.1)})
    second = execute_day(
        policy=_policy(initial_cash=10_000),
        state=PortfolioState.from_dict(first.state.to_dict()),
        signal=_signal([code], rebalance=False),
        signal_sha256="b" * 64,
        execution_date=second_day,
        daily=second_daily,
        signal_daily=first_daily,
        index_row=_index(second_day, open_price=101, close=102),
        stock_basic=_stock(code),
        namechange=_names(code),
        suspend=_suspend(),
        trade_cal=_calendar(first_day, second_day),
        dividends=dividends,
        run_id="run4",
        market_batch_id="batch4",
    )
    expected = Decimal("0.08") * held
    assert Decimal(second.state.cash) == cash_before + expected
    assert second.state.cumulative_dividends == f"{expected:.2f}"
    assert any(event["event"] == "CASH_DIVIDEND" for event in second.corporate_actions)


def test_sell_limit_down_keeps_actual_position_instead_of_target_weight():
    code = "600001.SH"
    replacement = "000001.SZ"
    policy = _policy(initial_cash=10_000)
    state = PortfolioState(
        account_id=policy.account_id,
        cash="0.00",
        positions={code: Position(1000, "9000.00", last_close="10", last_price_date="20260716")},
        benchmark_base_open="100",
        last_trade_date="20260716",
    )
    daily = _daily("20260717", {code: (9.0, 10.0, 9.0), replacement: (10, 10, 10)})
    result = execute_day(
        policy=policy,
        state=state,
        signal=_signal([replacement]),
        signal_sha256="c" * 64,
        execution_date="20260717",
        daily=daily,
        signal_daily=daily,
        index_row=_index("20260717"),
        stock_basic=_stock(code, replacement),
        namechange=_names(code, replacement),
        suspend=_suspend(),
        trade_cal=_calendar(
            "20100104", "20100105", "20100106", "20100107", "20100108",
            "20260716", "20260717",
        ),
        dividends=pd.DataFrame(),
        run_id="run5",
        market_batch_id="batch5",
    )
    sell = next(order for order in result.orders if order["side"] == "SELL")
    assert sell["status"] == "REJECTED"
    assert sell["reject_reason"] == "SELL_LIMIT_DOWN"
    assert result.state.positions[code].quantity == 1000
