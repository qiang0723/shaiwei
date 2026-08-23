from __future__ import annotations

from decimal import Decimal
import hashlib
import json

import pandas as pd
import pytest

from shaiwei.config import load
from shaiwei.paper.engine import (
    PaperEngineError,
    PortfolioState,
    Position,
    execute_day,
)
from shaiwei.paper.risk_exit_engine import execute_paper_day
from shaiwei.paper.risk_exit_policy import PaperDelistingRiskPortfolio


GOLDEN_SHA256 = "dd7b40b33b75f7e5b261bebaf64b8d1e748d6e42f62225da0b4d490f6e9d1faa"


def _paper_v1(*, initial_cash: float = 10_000):
    return load().paper_portfolio.model_copy(update={"initial_cash": initial_cash})


def _risk_policy(*, initial_cash: float = 10_000) -> PaperDelistingRiskPortfolio:
    values = load().paper_portfolio.model_dump()
    values.update(
        {
            "account_id": "m6_head30_delisting_risk",
            "execution_policy_version": "paper-v2-delisting-risk-exit",
            "initial_cash": initial_cash,
            "risk_trigger_price_cny": 1.0,
            "risk_trigger_consecutive_closes": 10,
            "risk_exit_latched": True,
            "risk_cash_reserve_authorized": True,
        }
    )
    return PaperDelistingRiskPortfolio(**values)


def _calendar(*days: str) -> pd.DataFrame:
    return pd.DataFrame({"cal_date": list(days), "is_open": [1] * len(days)})


def _stock(*codes: str, delist: tuple[str, str] | None = None) -> pd.DataFrame:
    rows = [
        {"ts_code": code, "list_date": "20100101", "delist_date": None}
        for code in codes
    ]
    frame = pd.DataFrame(rows)
    if delist:
        frame.loc[frame["ts_code"].eq(delist[0]), "delist_date"] = delist[1]
    return frame


def _names(*codes: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ts_code": code, "name": "普通样本", "start_date": "20100101", "end_date": None}
            for code in codes
        ]
    )


def _suspend(code: str = "", day: str = "") -> pd.DataFrame:
    columns = ["ts_code", "trade_date", "suspend_timing", "suspend_type"]
    if not code:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(
        [{"ts_code": code, "trade_date": day, "suspend_timing": None, "suspend_type": "S"}]
    )


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


def _index(day: str, *, open_price: float = 100, close: float = 101) -> pd.Series:
    return pd.Series(
        {"ts_code": "000906.SH", "trade_date": day, "open": open_price, "close": close}
    )


def _signal(
    weights: tuple[tuple[str, float], ...], *, rebalance: bool = True
) -> dict[str, object]:
    return {
        "rebalance_due": rebalance,
        "orders": [
            {
                "instrument": f"{code.split('.')[1]}{code.split('.')[0]}",
                "rank": rank,
                "target_weight": weight,
            }
            for rank, (code, weight) in enumerate(weights, start=1)
        ],
    }


def _pack(result) -> dict[str, object]:
    return {
        "state": result.state.to_dict(),
        "orders": list(result.orders),
        "fills": list(result.fills),
        "corporate_actions": list(result.corporate_actions),
        "nav": result.nav,
    }


def _golden(*, explicit_empty: bool) -> str:
    policy = _paper_v1()
    codes = ("600001.SH", "000001.SZ")
    first_day, second_day = "20260716", "20260717"
    first_daily = _daily(
        first_day,
        {codes[0]: (10, 9.9, 10.2), codes[1]: (20, 19.8, 19.5)},
    )
    executor = execute_paper_day if explicit_empty else execute_day
    first = executor(
        policy=policy,
        state=None,
        signal=_signal(((codes[0], 0.5), (codes[1], 0.5))),
        signal_sha256="a" * 64,
        execution_date=first_day,
        daily=first_daily,
        signal_daily=first_daily,
        index_row=_index(first_day),
        stock_basic=_stock(*codes),
        namechange=_names(*codes),
        suspend=_suspend(),
        trade_cal=_calendar(first_day, second_day),
        dividends=pd.DataFrame(),
        run_id="golden-day-1",
        market_batch_id="golden-batch-1",
        **({"forced_exit_codes": ()} if explicit_empty else {}),
    )
    second_daily = _daily(
        second_day,
        {codes[0]: (11, 10.2, 11.1), codes[1]: (21, 19.5, 21.2)},
    )
    second = executor(
        policy=policy,
        state=PortfolioState.from_dict(first.state.to_dict()),
        signal=_signal(((codes[1], 1.0),)),
        signal_sha256="b" * 64,
        execution_date=second_day,
        daily=second_daily,
        signal_daily=first_daily,
        index_row=_index(second_day, open_price=101, close=102),
        stock_basic=_stock(*codes),
        namechange=_names(*codes),
        suspend=_suspend(),
        trade_cal=_calendar(first_day, second_day),
        dividends=pd.DataFrame(),
        run_id="golden-day-2",
        market_batch_id="golden-batch-2",
        **({"forced_exit_codes": ()} if explicit_empty else {}),
    )
    document = {
        "schema_version": "paper-v1-sell-regression-golden-v1",
        "first": _pack(first),
        "second": _pack(second),
    }
    payload = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _held_state(policy, code: str = "002505.SZ") -> PortfolioState:
    return PortfolioState(
        account_id=policy.account_id,
        cash="1000.00",
        positions={
            code: Position(
                1000,
                "9000.00",
                last_close="10",
                last_price_date="20260716",
            )
        },
        benchmark_base_open="100",
        last_trade_date="20260716",
    )


def _risk_run(
    *,
    policy=None,
    state=None,
    forced: tuple[str, ...] = ("002505.SZ",),
    target: tuple[tuple[str, float], ...] = (("000001.SZ", 0.5),),
    risky_market: tuple[float, float, float] | None = (10, 10, 10),
    suspend: bool = False,
):
    policy = policy or _risk_policy()
    state = state or _held_state(policy)
    day = "20260717"
    values = {"000001.SZ": (20, 20, 20)}
    if risky_market is not None:
        values["002505.SZ"] = risky_market
    daily = _daily(day, values)
    return execute_paper_day(
        policy=policy,
        state=state,
        signal=_signal(target, rebalance=False),
        signal_sha256="r" * 64,
        execution_date=day,
        daily=daily,
        signal_daily=daily,
        index_row=_index(day),
        stock_basic=_stock("002505.SZ", "000001.SZ"),
        namechange=_names("002505.SZ", "000001.SZ"),
        suspend=_suspend("002505.SZ", day) if suspend else _suspend(),
        trade_cal=_calendar(
            "20260710",
            "20260713",
            "20260714",
            "20260715",
            "20260716",
            day,
        ),
        dividends=pd.DataFrame(),
        run_id="risk-exit-day",
        market_batch_id="risk-batch",
        forced_exit_codes=forced,
    )


def test_paper_v1_default_and_explicit_empty_keep_frozen_golden_identity() -> None:
    assert _golden(explicit_empty=False) == GOLDEN_SHA256
    assert _golden(explicit_empty=True) == GOLDEN_SHA256


def test_non_rebalance_risk_exit_sells_without_buying_or_redistributing() -> None:
    result = _risk_run()
    assert len(result.orders) == len(result.fills) == 1
    assert result.orders[0]["side"] == "SELL"
    assert result.orders[0]["execution_reason"] == "DELISTING_PRICE_RISK_EXIT"
    assert result.orders[0]["requested_quantity"] == 1000
    assert result.state.positions == {}
    assert Decimal(result.state.cash) > Decimal("1000")
    assert result.nav["equation_difference"] == "0.00"


@pytest.mark.parametrize(
    ("market", "suspended", "reason"),
    [
        ((9, 10, 9), False, "SELL_LIMIT_DOWN"),
        ((10, 10, 10), True, "OPEN_SUSPENDED"),
        (None, False, "MISSING_PRICE"),
    ],
)
def test_failed_risk_exit_preserves_position_and_cash(
    market: tuple[float, float, float] | None,
    suspended: bool,
    reason: str,
) -> None:
    result = _risk_run(risky_market=market, suspend=suspended)
    assert result.fills == ()
    assert result.orders[0]["status"] == "REJECTED"
    assert result.orders[0]["reject_reason"] == reason
    assert result.state.positions["002505.SZ"].quantity == 1000
    assert result.state.cash == "1000.00"


def test_underweight_target_is_allowed_only_for_risk_policy() -> None:
    day = "20260717"
    code = "000001.SZ"
    daily = _daily(day, {code: (10, 10, 10)})
    arguments = {
        "state": None,
        "signal": _signal(((code, 0.5),)),
        "signal_sha256": "u" * 64,
        "execution_date": day,
        "daily": daily,
        "signal_daily": daily,
        "index_row": _index(day),
        "stock_basic": _stock(code),
        "namechange": _names(code),
        "suspend": _suspend(),
        "trade_cal": _calendar(day),
        "dividends": pd.DataFrame(),
        "run_id": "underweight",
        "market_batch_id": "underweight-batch",
    }
    with pytest.raises(PaperEngineError, match="weights must sum to one"):
        execute_day(policy=_paper_v1(), **arguments)
    result = execute_paper_day(policy=_risk_policy(), **arguments)
    assert Decimal(result.nav["cash_ratio"]) > Decimal("0.49")


@pytest.mark.parametrize(
    ("policy_kind", "forced", "target", "state_code", "message"),
    [
        ("v1", ("002505.SZ",), (("000001.SZ", 1.0),), "002505.SZ", "requires paper-v2"),
        ("v2", ("002505.SZ", "002505.SZ"), (("000001.SZ", 0.5),), "002505.SZ", "duplicate"),
        ("v2", ("600001.SH",), (("000001.SZ", 0.5),), "002505.SZ", "unheld"),
        ("v2", ("002505.SZ",), (("002505.SZ", 0.5),), "002505.SZ", "remains in target"),
        ("v2", ("430001.BJ",), (("000001.SZ", 0.5),), "430001.BJ", "BSE"),
    ],
)
def test_forced_exit_authority_and_identity_fail_closed(
    policy_kind: str,
    forced: tuple[str, ...],
    target: tuple[tuple[str, float], ...],
    state_code: str,
    message: str,
) -> None:
    policy = _paper_v1() if policy_kind == "v1" else _risk_policy()
    state = _held_state(policy, state_code)
    with pytest.raises(PaperEngineError, match=message):
        _risk_run(policy=policy, state=state, forced=forced, target=target)


def test_risk_policy_does_not_override_unresolved_delisting_guard() -> None:
    policy = _risk_policy()
    code = "002505.SZ"
    day = "20240830"
    state = _held_state(policy, code)
    state.last_trade_date = "20240829"
    state.positions[code].last_price_date = "20240829"
    daily = _daily(day, {code: (10, 10, 10)})
    with pytest.raises(PaperEngineError, match="explicit disposal rule"):
        execute_paper_day(
            policy=policy,
            state=state,
            signal=_signal((), rebalance=False),
            signal_sha256="d" * 64,
            execution_date=day,
            daily=daily,
            signal_daily=daily,
            index_row=_index(day),
            stock_basic=_stock(code, delist=(code, day)),
            namechange=_names(code),
            suspend=_suspend(),
            trade_cal=_calendar("20240829", day),
            dividends=pd.DataFrame(),
            run_id="risk-delist-guard",
            market_batch_id="risk-delist-batch",
        )
