from __future__ import annotations

from decimal import Decimal

import pytest

from shaiwei.research.capital_feasibility.delisting_risk import (
    DelistingRiskError,
    RiskOverlayState,
    RiskPolicy,
    evaluate_risk_overlay,
)


POLICY = RiskPolicy(Decimal("1.00"), 10, Decimal("0.03333333333333333"))


def _rows(code: str = "002505.SZ", *, count: int = 10, close: str = "0.90") -> list[dict]:
    return [
        {"ts_code": code, "trade_date": f"202406{day:02d}", "close": close}
        for day in range(1, count + 1)
    ]


def _decision(
    rows: list[dict],
    *,
    targets: tuple[str, ...] = ("002505.SZ", "000001.SZ"),
    held: tuple[str, ...] = (),
    state: RiskOverlayState | None = None,
    as_of: str = "20240610",
):
    return evaluate_risk_overlay(
        rows,
        as_of=as_of,
        target_codes=targets,
        held_codes=held,
        policy=POLICY,
        previous_state=state,
    )


def test_ten_strictly_lower_closes_block_buy_without_replacement() -> None:
    decision = _decision(_rows())

    assert decision.blocked_buy_codes == ("002505.SZ",)
    assert decision.forced_exit_codes == ()
    assert decision.eligible_target_codes == ("000001.SZ",)
    assert decision.cash_reserve_weight == "0.03333333333333333"
    assert decision.evidence[0]["trade_dates"] == [f"202406{day:02d}" for day in range(1, 11)]
    assert decision.evidence[0]["state"] == "BUY_BLOCKED"


def test_nine_closes_or_price_equal_to_one_do_not_trigger() -> None:
    assert _decision(_rows(count=9), as_of="20240609").blocked_buy_codes == ()
    rows = _rows(count=9) + [{"ts_code": "002505.SZ", "trade_date": "20240610", "close": "1.00"}]
    assert _decision(rows).blocked_buy_codes == ()


def test_close_at_or_above_threshold_resets_the_observed_streak() -> None:
    rows = _rows(count=8)
    rows.append({"ts_code": "002505.SZ", "trade_date": "20240609", "close": "1.01"})
    rows.extend(
        {"ts_code": "002505.SZ", "trade_date": f"202406{day:02d}", "close": "0.80"}
        for day in range(10, 19)
    )
    assert _decision(rows, as_of="20240618").blocked_buy_codes == ()


def test_held_trigger_is_latched_until_position_is_disposed() -> None:
    first = _decision(_rows(), held=("002505.SZ",))
    assert first.forced_exit_codes == ("002505.SZ",)
    assert first.blocked_buy_codes == ()
    assert first.eligible_target_codes == ("000001.SZ",)

    recovered = _rows() + [
        {"ts_code": "002505.SZ", "trade_date": "20240611", "close": "1.10"}
    ]
    second = _decision(
        recovered,
        held=("002505.SZ",),
        state=first.next_state,
        as_of="20240611",
    )
    assert second.forced_exit_codes == ("002505.SZ",)
    assert second.evidence[0]["triggered_as_of"] == "20240610"

    disposed = _decision(
        recovered,
        held=(),
        state=second.next_state,
        targets=("000001.SZ",),
        as_of="20240611",
    )
    assert disposed.disposed_codes == ("002505.SZ",)
    assert disposed.next_state.exit_latches == ()
    assert disposed.evidence[0]["state"] == "DISPOSED"


def test_future_rows_are_invisible_and_replay_is_deterministic() -> None:
    visible = _rows(count=9)
    with_future = visible + [
        {"ts_code": "002505.SZ", "trade_date": "20240611", "close": "0.50"},
        {"ts_code": "002505.SZ", "trade_date": "20240612", "close": "not-a-price"},
    ]
    first = _decision(visible, as_of="20240609")
    second = _decision(with_future, as_of="20240609")
    assert first.as_dict() == second.as_dict()
    assert _decision(visible, as_of="20240609").as_dict() == first.as_dict()


@pytest.mark.parametrize(
    ("rows", "targets", "message"),
    [
        (_rows() + [_rows()[0]], ("002505.SZ",), "duplicate security date"),
        ([{"ts_code": "430001.BJ", "trade_date": "20240601", "close": "1"}], ("430001.BJ",), "Beijing"),
        ([{"ts_code": "002505.SZ", "trade_date": "20240601", "close": "0"}], ("002505.SZ",), "close is invalid"),
        (_rows(), ("002505.SZ", "002505.SZ"), "target_codes contains duplicates"),
    ],
)
def test_invalid_keys_prices_and_target_identity_fail_closed(
    rows: list[dict], targets: tuple[str, ...], message: str
) -> None:
    with pytest.raises(DelistingRiskError, match=message):
        _decision(rows, targets=targets)
