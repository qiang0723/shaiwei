"""Pure PIT state machine for the versioned price-delisting risk overlay."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping
import re


_CODE = re.compile(r"[0-9]{6}\.(?:SH|SZ)\Z")
_DATE = re.compile(r"[0-9]{8}\Z")


class DelistingRiskError(RuntimeError):
    """Raised when PIT risk instructions cannot be constructed safely."""


def _date(value: object, field: str) -> str:
    text = str(value)
    if not _DATE.fullmatch(text):
        raise DelistingRiskError(f"delisting risk {field} is invalid")
    try:
        datetime.strptime(text, "%Y%m%d")
    except ValueError as error:
        raise DelistingRiskError(f"delisting risk {field} is invalid") from error
    return text


def _code(value: object) -> str:
    text = str(value).upper()
    if text.endswith(".BJ"):
        raise DelistingRiskError("Beijing instrument is forbidden in delisting risk overlay")
    if not _CODE.fullmatch(text):
        raise DelistingRiskError("delisting risk instrument is invalid")
    return text


def _price(value: object) -> Decimal:
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise DelistingRiskError("delisting risk close is invalid") from error
    if not price.is_finite() or price <= 0:
        raise DelistingRiskError("delisting risk close is invalid")
    return price


@dataclass(frozen=True)
class RiskPolicy:
    trigger_price: Decimal
    trigger_sessions: int
    target_weight: Decimal

    def validate(self) -> None:
        if not self.trigger_price.is_finite() or self.trigger_price <= 0 or self.trigger_sessions < 1:
            raise DelistingRiskError("delisting risk policy trigger is invalid")
        if not self.target_weight.is_finite() or self.target_weight <= 0 or self.target_weight > 1:
            raise DelistingRiskError("delisting risk target weight is invalid")


@dataclass(frozen=True)
class RiskTrigger:
    ts_code: str
    triggered_as_of: str
    trade_dates: tuple[str, ...]
    closes: tuple[str, ...]
    reason_code: str = "CONSECUTIVE_CLOSES_STRICTLY_BELOW_ONE_YUAN"

    def validate(self, policy: RiskPolicy) -> None:
        if _code(self.ts_code) != self.ts_code or _date(
            self.triggered_as_of, "triggered_as_of"
        ) != self.triggered_as_of:
            raise DelistingRiskError("delisting risk trigger identity differs")
        if len(self.trade_dates) != policy.trigger_sessions or len(self.closes) != len(
            self.trade_dates
        ):
            raise DelistingRiskError("delisting risk trigger evidence length differs")
        dates = tuple(_date(value, "trigger trade_date") for value in self.trade_dates)
        prices = tuple(_price(value) for value in self.closes)
        if dates != tuple(sorted(dates)) or len(set(dates)) != len(dates):
            raise DelistingRiskError("delisting risk trigger dates differ")
        if dates[-1] > self.triggered_as_of or any(
            value >= policy.trigger_price for value in prices
        ):
            raise DelistingRiskError("delisting risk trigger evidence differs")

    def as_dict(self, *, state: str) -> dict[str, object]:
        return {
            "ts_code": self.ts_code,
            "state": state,
            "triggered_as_of": self.triggered_as_of,
            "trade_dates": list(self.trade_dates),
            "closes": list(self.closes),
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True)
class RiskOverlayState:
    exit_latches: tuple[RiskTrigger, ...] = ()

    def validate(self, policy: RiskPolicy) -> None:
        codes = [trigger.ts_code for trigger in self.exit_latches]
        if len(codes) != len(set(codes)) or codes != sorted(codes):
            raise DelistingRiskError("delisting risk latch state differs")
        for trigger in self.exit_latches:
            trigger.validate(policy)


@dataclass(frozen=True)
class RiskOverlayDecision:
    as_of: str
    blocked_buy_codes: tuple[str, ...]
    forced_exit_codes: tuple[str, ...]
    disposed_codes: tuple[str, ...]
    eligible_target_codes: tuple[str, ...]
    cash_reserve_weight: str
    evidence: tuple[dict[str, object], ...]
    next_state: RiskOverlayState

    def as_dict(self) -> dict[str, object]:
        return {
            "as_of": self.as_of,
            "blocked_buy_codes": list(self.blocked_buy_codes),
            "forced_exit_codes": list(self.forced_exit_codes),
            "disposed_codes": list(self.disposed_codes),
            "eligible_target_codes": list(self.eligible_target_codes),
            "cash_reserve_weight": self.cash_reserve_weight,
            "evidence": list(self.evidence),
            "next_state": {
                "exit_latches": [
                    trigger.as_dict(state="EXIT_LATCHED")
                    for trigger in self.next_state.exit_latches
                ]
            },
        }


def _relevant_codes(values: Iterable[object], field: str) -> tuple[str, ...]:
    codes = tuple(_code(value) for value in values)
    if len(codes) != len(set(codes)):
        raise DelistingRiskError(f"delisting risk {field} contains duplicates")
    return codes


def _active_triggers(
    rows: Iterable[Mapping[str, object]],
    *,
    as_of: str,
    relevant: set[str],
    policy: RiskPolicy,
) -> dict[str, RiskTrigger]:
    observations: dict[str, dict[str, Decimal]] = {code: {} for code in relevant}
    for row in rows:
        code = _code(row.get("ts_code", ""))
        trade_date = _date(row.get("trade_date", ""), "trade_date")
        if trade_date > as_of or code not in relevant:
            continue
        close = _price(row.get("close"))
        if trade_date in observations[code]:
            raise DelistingRiskError("delisting risk contains duplicate security date")
        observations[code][trade_date] = close
    active: dict[str, RiskTrigger] = {}
    for code, by_date in observations.items():
        streak: list[tuple[str, Decimal]] = []
        for trade_date, close in sorted(by_date.items()):
            streak = [*streak, (trade_date, close)] if close < policy.trigger_price else []
        if len(streak) < policy.trigger_sessions:
            continue
        evidence = streak[-policy.trigger_sessions :]
        active[code] = RiskTrigger(
            ts_code=code,
            triggered_as_of=as_of,
            trade_dates=tuple(day for day, _ in evidence),
            closes=tuple(str(close) for _, close in evidence),
        )
    return active


def evaluate_risk_overlay(
    rows: Iterable[Mapping[str, object]],
    *,
    as_of: str,
    target_codes: Iterable[object],
    held_codes: Iterable[object],
    policy: RiskPolicy,
    previous_state: RiskOverlayState | None = None,
) -> RiskOverlayDecision:
    """Build deterministic buy blocks and latched exits using data visible at ``as_of``."""
    policy.validate()
    as_of = _date(as_of, "as_of")
    targets = _relevant_codes(target_codes, "target_codes")
    held = _relevant_codes(held_codes, "held_codes")
    prior = previous_state or RiskOverlayState()
    prior.validate(policy)
    relevant = set(targets) | set(held) | {item.ts_code for item in prior.exit_latches}
    active = _active_triggers(rows, as_of=as_of, relevant=relevant, policy=policy)
    prior_by_code = {item.ts_code: item for item in prior.exit_latches}
    held_set = set(held)
    disposed = tuple(sorted(set(prior_by_code) - held_set))
    latches = {
        code: prior_by_code[code] if code in prior_by_code else active[code]
        for code in sorted(held_set & (set(prior_by_code) | set(active)))
    }
    forced = tuple(latches)
    blocked = tuple(code for code in targets if code in active and code not in held_set)
    excluded_targets = set(blocked) | (set(forced) & set(targets))
    eligible = tuple(code for code in targets if code not in excluded_targets)
    reserve = policy.target_weight * len(excluded_targets)
    evidence = [
        prior_by_code[code].as_dict(state="DISPOSED")
        for code in disposed
    ]
    for code in sorted(set(blocked) | set(forced)):
        trigger = latches[code] if code in latches else active[code]
        evidence.append(
            trigger.as_dict(state="EXIT_LATCHED" if code in latches else "BUY_BLOCKED")
        )
    next_state = RiskOverlayState(exit_latches=tuple(latches.values()))
    next_state.validate(policy)
    return RiskOverlayDecision(
        as_of=as_of,
        blocked_buy_codes=blocked,
        forced_exit_codes=forced,
        disposed_codes=disposed,
        eligible_target_codes=eligible,
        cash_reserve_weight=str(reserve),
        evidence=tuple(evidence),
        next_state=next_state,
    )
