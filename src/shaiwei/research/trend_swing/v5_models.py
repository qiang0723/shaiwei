"""Strict, code-free contracts for TS-v5 mechanism candidates."""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

STRICT = ConfigDict(extra="forbid")
SAFE_TEXT = re.compile(r"^[^\x00-\x08\x0b\x0c\x0e-\x1f]{1,800}$")
FORBIDDEN_TEXT = re.compile(
    r"(?:https?://|file://|(?:^|\s)/(?:Users|workspace|etc|tmp)/|\.\./|\$\{|"
    r"\b(?:python|bash|zsh|shell|docker|curl|wget|select|insert|delete|drop)\b|"
    r"sk-[A-Za-z0-9]{8,}|(?:已|已经)(?:盈利|验证|回测通过)|适合实盘|生产授权)",
    re.IGNORECASE,
)


class Mechanism(StrEnum):
    VOLATILITY_ADAPTIVE_PULLBACK = "VOLATILITY_ADAPTIVE_PULLBACK"
    WEEKLY_STRUCTURE_QUANTILE = "WEEKLY_STRUCTURE_QUANTILE"
    BREAKOUT_RETEST = "BREAKOUT_RETEST"
    MOVING_AVERAGE_RESUMPTION = "MOVING_AVERAGE_RESUMPTION"
    CONTRACTION_EXPANSION = "CONTRACTION_EXPANSION"
    RELATIVE_STRENGTH_PULLBACK = "RELATIVE_STRENGTH_PULLBACK"


class ReferenceFrame(StrEnum):
    PREVIOUS_COMPLETE_WEEK_VWAP = "PREVIOUS_COMPLETE_WEEK_VWAP"
    PREVIOUS_COMPLETE_WEEK_RANGE = "PREVIOUS_COMPLETE_WEEK_RANGE"
    PRIOR_WEEKLY_BREAKOUT_LEVEL = "PRIOR_WEEKLY_BREAKOUT_LEVEL"
    DAILY_MEDIUM_MOVING_AVERAGE = "DAILY_MEDIUM_MOVING_AVERAGE"
    COMPLETE_WEEK_CONTRACTION_RANGE = "COMPLETE_WEEK_CONTRACTION_RANGE"
    STOCK_SECTOR_RELATIVE_STRENGTH_PEAK = "STOCK_SECTOR_RELATIVE_STRENGTH_PEAK"


class PullbackMeasure(StrEnum):
    ATR_MULTIPLE = "ATR_MULTIPLE"
    WEEKLY_RANGE_QUANTILE = "WEEKLY_RANGE_QUANTILE"
    BREAKOUT_RETEST_DISTANCE = "BREAKOUT_RETEST_DISTANCE"
    ATR_DISTANCE_TO_MOVING_AVERAGE = "ATR_DISTANCE_TO_MOVING_AVERAGE"
    RANGE_AND_VOLUME_CONTRACTION = "RANGE_AND_VOLUME_CONTRACTION"
    RELATIVE_STRENGTH_DRAWDOWN = "RELATIVE_STRENGTH_DRAWDOWN"


class Confirmation(StrEnum):
    CLOSE_RECLAIMS_REFERENCE = "CLOSE_RECLAIMS_REFERENCE"
    CLOSE_ABOVE_PRIOR_DAY_HIGH = "CLOSE_ABOVE_PRIOR_DAY_HIGH"
    CLOSE_ABOVE_SHORT_MOVING_AVERAGE = "CLOSE_ABOVE_SHORT_MOVING_AVERAGE"
    PRICE_AND_VOLUME_EXPAND = "PRICE_AND_VOLUME_EXPAND"
    RELATIVE_STRENGTH_TURNS_UP = "RELATIVE_STRENGTH_TURNS_UP"


class CancellationRule(StrEnum):
    STRUCTURE_LOW_BROKEN = "STRUCTURE_LOW_BROKEN"
    NEXT_OPEN_ABOVE_REFERENCE = "NEXT_OPEN_ABOVE_REFERENCE"
    MARKET_OR_SECTOR_GATE_LOST = "MARKET_OR_SECTOR_GATE_LOST"
    LIQUIDITY_GATE_LOST = "LIQUIDITY_GATE_LOST"
    MAX_WAIT_EXPIRED = "MAX_WAIT_EXPIRED"


class Feature(StrEnum):
    ADJUSTED_DAILY_OHLCV = "ADJUSTED_DAILY_OHLCV"
    COMPLETE_WEEK_OHLCV = "COMPLETE_WEEK_OHLCV"
    COMPLETE_MONTH_OHLCV = "COMPLETE_MONTH_OHLCV"
    DAILY_ATR = "DAILY_ATR"
    WEEKLY_VWAP = "WEEKLY_VWAP"
    WEEKLY_RANGE = "WEEKLY_RANGE"
    DAILY_MOVING_AVERAGE = "DAILY_MOVING_AVERAGE"
    STOCK_SECTOR_RELATIVE_STRENGTH = "STOCK_SECTOR_RELATIVE_STRENGTH"
    MARKET_AND_SECTOR_TREND = "MARKET_AND_SECTOR_TREND"
    PIT_INDUSTRY_MEMBERSHIP = "PIT_INDUSTRY_MEMBERSHIP"
    PIT_MARKET_CAP = "PIT_MARKET_CAP"
    DAILY_AND_WEEKLY_AMOUNT = "DAILY_AND_WEEKLY_AMOUNT"


class ParameterId(StrEnum):
    ATR_LOOKBACK_DAYS = "ATR_LOOKBACK_DAYS"
    PULLBACK_ATR_MULTIPLE = "PULLBACK_ATR_MULTIPLE"
    WEEKLY_RANGE_QUANTILE = "WEEKLY_RANGE_QUANTILE"
    BREAKOUT_LOOKBACK_WEEKS = "BREAKOUT_LOOKBACK_WEEKS"
    RETEST_TOLERANCE_ATR = "RETEST_TOLERANCE_ATR"
    MOVING_AVERAGE_LOOKBACK_DAYS = "MOVING_AVERAGE_LOOKBACK_DAYS"
    MOVING_AVERAGE_TOLERANCE_ATR = "MOVING_AVERAGE_TOLERANCE_ATR"
    CONTRACTION_LOOKBACK_WEEKS = "CONTRACTION_LOOKBACK_WEEKS"
    RANGE_CONTRACTION_QUANTILE = "RANGE_CONTRACTION_QUANTILE"
    VOLUME_EXPANSION_RATIO = "VOLUME_EXPANSION_RATIO"
    RELATIVE_STRENGTH_LOOKBACK_DAYS = "RELATIVE_STRENGTH_LOOKBACK_DAYS"
    RELATIVE_STRENGTH_DRAWDOWN_QUANTILE = "RELATIVE_STRENGTH_DRAWDOWN_QUANTILE"
    RECOVERY_CONFIRMATION_DAYS = "RECOVERY_CONFIRMATION_DAYS"
    MAXIMUM_WAIT_DAYS = "MAXIMUM_WAIT_DAYS"


ARCHETYPE_CONTRACT = {
    Mechanism.VOLATILITY_ADAPTIVE_PULLBACK: (
        ReferenceFrame.PREVIOUS_COMPLETE_WEEK_VWAP,
        PullbackMeasure.ATR_MULTIPLE,
        {ParameterId.ATR_LOOKBACK_DAYS, ParameterId.PULLBACK_ATR_MULTIPLE},
    ),
    Mechanism.WEEKLY_STRUCTURE_QUANTILE: (
        ReferenceFrame.PREVIOUS_COMPLETE_WEEK_RANGE,
        PullbackMeasure.WEEKLY_RANGE_QUANTILE,
        {ParameterId.WEEKLY_RANGE_QUANTILE},
    ),
    Mechanism.BREAKOUT_RETEST: (
        ReferenceFrame.PRIOR_WEEKLY_BREAKOUT_LEVEL,
        PullbackMeasure.BREAKOUT_RETEST_DISTANCE,
        {ParameterId.BREAKOUT_LOOKBACK_WEEKS, ParameterId.RETEST_TOLERANCE_ATR},
    ),
    Mechanism.MOVING_AVERAGE_RESUMPTION: (
        ReferenceFrame.DAILY_MEDIUM_MOVING_AVERAGE,
        PullbackMeasure.ATR_DISTANCE_TO_MOVING_AVERAGE,
        {ParameterId.MOVING_AVERAGE_LOOKBACK_DAYS, ParameterId.MOVING_AVERAGE_TOLERANCE_ATR},
    ),
    Mechanism.CONTRACTION_EXPANSION: (
        ReferenceFrame.COMPLETE_WEEK_CONTRACTION_RANGE,
        PullbackMeasure.RANGE_AND_VOLUME_CONTRACTION,
        {
            ParameterId.CONTRACTION_LOOKBACK_WEEKS,
            ParameterId.RANGE_CONTRACTION_QUANTILE,
            ParameterId.VOLUME_EXPANSION_RATIO,
        },
    ),
    Mechanism.RELATIVE_STRENGTH_PULLBACK: (
        ReferenceFrame.STOCK_SECTOR_RELATIVE_STRENGTH_PEAK,
        PullbackMeasure.RELATIVE_STRENGTH_DRAWDOWN,
        {
            ParameterId.RELATIVE_STRENGTH_LOOKBACK_DAYS,
            ParameterId.RELATIVE_STRENGTH_DRAWDOWN_QUANTILE,
        },
    ),
}

PARAMETER_BOUNDS = {
    ParameterId.ATR_LOOKBACK_DAYS: (Decimal("10"), Decimal("30"), "INTEGER"),
    ParameterId.PULLBACK_ATR_MULTIPLE: (Decimal("0.25"), Decimal("2.00"), "DECIMAL"),
    ParameterId.WEEKLY_RANGE_QUANTILE: (Decimal("0.15"), Decimal("0.65"), "DECIMAL"),
    ParameterId.BREAKOUT_LOOKBACK_WEEKS: (Decimal("4"), Decimal("26"), "INTEGER"),
    ParameterId.RETEST_TOLERANCE_ATR: (Decimal("0.10"), Decimal("1.50"), "DECIMAL"),
    ParameterId.MOVING_AVERAGE_LOOKBACK_DAYS: (Decimal("10"), Decimal("60"), "INTEGER"),
    ParameterId.MOVING_AVERAGE_TOLERANCE_ATR: (Decimal("0.10"), Decimal("1.50"), "DECIMAL"),
    ParameterId.CONTRACTION_LOOKBACK_WEEKS: (Decimal("3"), Decimal("12"), "INTEGER"),
    ParameterId.RANGE_CONTRACTION_QUANTILE: (Decimal("0.10"), Decimal("0.50"), "DECIMAL"),
    ParameterId.VOLUME_EXPANSION_RATIO: (Decimal("1.00"), Decimal("2.50"), "DECIMAL"),
    ParameterId.RELATIVE_STRENGTH_LOOKBACK_DAYS: (Decimal("20"), Decimal("120"), "INTEGER"),
    ParameterId.RELATIVE_STRENGTH_DRAWDOWN_QUANTILE: (
        Decimal("0.10"),
        Decimal("0.60"),
        "DECIMAL",
    ),
    ParameterId.RECOVERY_CONFIRMATION_DAYS: (Decimal("1"), Decimal("3"), "INTEGER"),
    ParameterId.MAXIMUM_WAIT_DAYS: (Decimal("2"), Decimal("10"), "INTEGER"),
}

COMMON_FEATURES = {
    Feature.ADJUSTED_DAILY_OHLCV,
    Feature.COMPLETE_WEEK_OHLCV,
    Feature.COMPLETE_MONTH_OHLCV,
    Feature.MARKET_AND_SECTOR_TREND,
    Feature.PIT_INDUSTRY_MEMBERSHIP,
    Feature.PIT_MARKET_CAP,
    Feature.DAILY_AND_WEEKLY_AMOUNT,
}

MECHANISM_FEATURES = {
    Mechanism.VOLATILITY_ADAPTIVE_PULLBACK: {Feature.DAILY_ATR, Feature.WEEKLY_VWAP},
    Mechanism.WEEKLY_STRUCTURE_QUANTILE: {Feature.WEEKLY_RANGE},
    Mechanism.BREAKOUT_RETEST: {Feature.WEEKLY_RANGE, Feature.DAILY_ATR},
    Mechanism.MOVING_AVERAGE_RESUMPTION: {Feature.DAILY_MOVING_AVERAGE, Feature.DAILY_ATR},
    Mechanism.CONTRACTION_EXPANSION: {Feature.WEEKLY_RANGE},
    Mechanism.RELATIVE_STRENGTH_PULLBACK: {Feature.STOCK_SECTOR_RELATIVE_STRENGTH},
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _safe_text(value: str) -> str:
    if not SAFE_TEXT.fullmatch(value) or FORBIDDEN_TEXT.search(value):
        raise ValueError("text contains prohibited executable, path, secret, or authority claims")
    return value


class ParameterSlot(BaseModel):
    model_config = STRICT

    parameter_id: ParameterId
    value_type: Literal["INTEGER", "DECIMAL"]
    minimum: str
    maximum: str
    search_points_maximum: Annotated[int, Field(ge=2, le=7)]

    @field_validator("minimum", "maximum")
    @classmethod
    def validate_decimal(cls, value: str) -> str:
        if not re.fullmatch(r"-?(?:0|[1-9]\d*)(?:\.\d{1,6})?", value):
            raise ValueError("parameter bounds must be exact decimal strings")
        try:
            if not Decimal(value).is_finite():
                raise ValueError("parameter bound is not finite")
        except InvalidOperation as exc:
            raise ValueError("invalid parameter bound") from exc
        return value

    @model_validator(mode="after")
    def validate_range(self) -> "ParameterSlot":
        low, high = Decimal(self.minimum), Decimal(self.maximum)
        if low >= high:
            raise ValueError("parameter minimum must be below maximum")
        if self.value_type == "INTEGER" and (low != low.to_integral() or high != high.to_integral()):
            raise ValueError("integer parameter bounds must be integral")
        allowed_low, allowed_high, allowed_type = PARAMETER_BOUNDS[self.parameter_id]
        if self.value_type != allowed_type or low < allowed_low or high > allowed_high:
            raise ValueError("parameter slot exceeds its frozen type or safe range")
        return self


class EntryDesign(BaseModel):
    model_config = STRICT

    reference_frame: ReferenceFrame
    pullback_measure: PullbackMeasure
    recovery_confirmation: Confirmation
    cancellation_rules: Annotated[list[CancellationRule], Field(min_length=2, max_length=5)]

    @field_validator("cancellation_rules")
    @classmethod
    def validate_cancellations(cls, values: list[CancellationRule]) -> list[CancellationRule]:
        if len(set(values)) != len(values):
            raise ValueError("cancellation rules must be unique")
        required = {CancellationRule.STRUCTURE_LOW_BROKEN, CancellationRule.MARKET_OR_SECTOR_GATE_LOST}
        if not required.issubset(values):
            raise ValueError("structural and market/sector cancellation rules are mandatory")
        return values


class CandidateLineage(BaseModel):
    model_config = STRICT

    mode: Literal["INDEPENDENT", "ADVERSARIAL_REVISION"]
    parent_candidate_fingerprints: Annotated[list[str], Field(max_length=2)]

    @field_validator("parent_candidate_fingerprints")
    @classmethod
    def validate_fingerprints(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values) or any(not re.fullmatch(r"[0-9a-f]{64}", item) for item in values):
            raise ValueError("parent fingerprints must be unique SHA-256 values")
        return values

    @model_validator(mode="after")
    def validate_mode(self) -> "CandidateLineage":
        expected = 0 if self.mode == "INDEPENDENT" else 1
        if len(self.parent_candidate_fingerprints) != expected:
            raise ValueError("lineage mode has the wrong parent count")
        return self


class MechanismCandidate(BaseModel):
    model_config = STRICT

    schema_version: Literal["ts-v5-mechanism-candidate-v1"]
    primary_mechanism: Mechanism
    hypothesis: Annotated[str, Field(min_length=20, max_length=500)]
    economic_rationale_draft: Annotated[str, Field(min_length=20, max_length=800)]
    change_summary: Annotated[str, Field(min_length=10, max_length=300)]
    entry_design: EntryDesign
    parameter_slots: Annotated[list[ParameterSlot], Field(min_length=1, max_length=8)]
    required_features: Annotated[list[Feature], Field(min_length=2, max_length=12)]
    falsification_conditions: Annotated[list[str], Field(min_length=2, max_length=5)]
    lineage: CandidateLineage

    @field_validator("hypothesis", "economic_rationale_draft", "change_summary")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _safe_text(value)

    @field_validator("falsification_conditions")
    @classmethod
    def validate_falsification(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("falsification conditions must be unique")
        return [_safe_text(value) for value in values]

    @field_validator("required_features")
    @classmethod
    def validate_features(cls, values: list[Feature]) -> list[Feature]:
        if len(set(values)) != len(values):
            raise ValueError("required features must be unique")
        return values

    @model_validator(mode="after")
    def validate_mechanism(self) -> "MechanismCandidate":
        reference, measure, mandatory = ARCHETYPE_CONTRACT[self.primary_mechanism]
        if self.entry_design.reference_frame != reference or self.entry_design.pullback_measure != measure:
            raise ValueError("entry design is inconsistent with the primary mechanism")
        parameter_ids = [slot.parameter_id for slot in self.parameter_slots]
        if len(set(parameter_ids)) != len(parameter_ids):
            raise ValueError("parameter slots must be unique")
        if not mandatory.issubset(parameter_ids):
            raise ValueError("candidate is missing a mandatory mechanism parameter")
        shared = {ParameterId.RECOVERY_CONFIRMATION_DAYS, ParameterId.MAXIMUM_WAIT_DAYS}
        if not set(parameter_ids).issubset(mandatory | shared):
            raise ValueError("candidate contains a parameter from another mechanism")
        evaluation_count = 1
        for slot in self.parameter_slots:
            evaluation_count *= slot.search_points_maximum
        if evaluation_count > 196:
            raise ValueError("candidate parameter search exceeds 196 evaluations")
        required_features = COMMON_FEATURES | MECHANISM_FEATURES[self.primary_mechanism]
        if not required_features.issubset(self.required_features):
            raise ValueError("candidate omits a required product or mechanism feature")
        return self

    def fingerprint(self) -> str:
        return hashlib.sha256(canonical_json(self.model_dump(mode="json")).encode()).hexdigest()

    def semantic_signature(self) -> str:
        semantic = {
            "primary_mechanism": self.primary_mechanism,
            "entry_design": self.entry_design.model_dump(mode="json"),
            "parameter_slots": sorted(
                (slot.model_dump(mode="json") for slot in self.parameter_slots),
                key=lambda row: row["parameter_id"],
            ),
            "required_features": sorted(self.required_features),
        }
        return hashlib.sha256(canonical_json(semantic).encode()).hexdigest()


def candidate_schema() -> dict[str, Any]:
    return MechanismCandidate.model_json_schema()
