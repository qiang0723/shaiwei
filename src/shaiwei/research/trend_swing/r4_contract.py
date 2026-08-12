"""Frozen TS-1A-R4 result-blind protocol and artifact identities."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.contract import (
    TrendSwingError,
    project_path,
    sha256_file,
)


PROTOCOL_PATH = PROJECT_ROOT / "config/ts_v3_pullback_state_preflight_v1.yaml"
ADDENDUM_PATH = PROJECT_ROOT / "config/ts_v3_pullback_state_operationalization_v1.yaml"
R3_MANIFEST_PATH = (
    PROJECT_ROOT / "data/research/trend_swing/ts-v3-data-gate-r3/input_manifest.json"
)
R4_OUTPUT_DIR = PROJECT_ROOT / "data/research/trend_swing/ts-v3-pullback-state-r4"
EVENT_PATH = R4_OUTPUT_DIR / "true_events.parquet"
DAILY_PATH = R4_OUTPUT_DIR / "anonymous_daily.parquet"
REPORT_PATH = R4_OUTPUT_DIR / "profile_report.json"
AUDIT_PATH = R4_OUTPUT_DIR / "audit.json"


def _yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(project_path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TrendSwingError(f"TS R4 expected YAML mapping: {path.name}")
    return value


def load_r3_manifest(path: Path = R3_MANIFEST_PATH) -> dict[str, Any]:
    resolved = project_path(path)
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TrendSwingError("TS R4 R3 manifest must be a mapping")
    return value


def _forbidden_authority(document: dict[str, Any]) -> None:
    authority = document.get("authorization", {})
    allowed_true = {
        "offline_engineering_and_fixture",
        "read_price_and_reference_fields_through_candidate_next_open",
    }
    for key, value in authority.items():
        if key in allowed_true:
            if value is not True:
                raise TrendSwingError(f"TS R4 allowed authority disabled: {key}")
        elif value is not False:
            raise TrendSwingError(f"TS R4 forbidden authority broadened: {key}")


def _validate_protocol(document: dict[str, Any]) -> None:
    if (
        document.get("protocol_id") != "ts-v3-pullback-state-preflight-v1"
        or document.get("stage") != "RESULT_BLIND_PULLBACK_STATE_AND_BENCHMARK_PREFLIGHT"
    ):
        raise TrendSwingError("unexpected TS R4 protocol identity or stage")
    _forbidden_authority(document)
    scope = document.get("scope", {})
    if (
        scope.get("universe_id") != "csi800-pit-v1"
        or scope.get("bse_included") is not False
        or scope.get("st_allowed") is not False
    ):
        raise TrendSwingError("TS R4 universe boundary differs")
    weekly = document.get("weekly_plan", {})
    if (
        weekly.get("pullback_line")
        != "previous_complete_week_vwap_adjusted_times_0_96"
        or weekly.get("initial_structure_stop")
        != "previous_complete_week_low_adjusted_times_0_98"
    ):
        raise TrendSwingError("TS R4 pullback or stop rule differs")
    stop = document.get("next_open_preflight", {}).get("structure_stop_distance", {})
    if stop != {"minimum_exclusive": 0.0, "maximum_exclusive": 0.15}:
        raise TrendSwingError("TS R4 stop-distance gate differs")
    sample = document.get("result_blind_evaluability_gate", {})
    expected = {
        "true_legal_entry_event_count_minimum": 60,
        "distinct_true_legal_entry_day_count_minimum": 40,
        "each_calendar_year_true_legal_entry_event_count_minimum": 3,
        "calendar_years_with_at_least_8_true_legal_entry_events_minimum": 4,
        "required_calendar_years": [2019, 2020, 2021, 2022, 2023, 2024],
        "threshold_change_after_profile": "forbidden",
    }
    if sample != expected:
        raise TrendSwingError("TS R4 evaluability gate differs")
    attempts = document.get("attempt_and_change_control", {})
    if (
        attempts.get("result_blind_profile_attempt_count") != 1
        or attempts.get("independent_audit_attempt_count") != 1
        or attempts.get("strategy_effect_attempt_count") != 0
        or attempts.get("same_scope_profile_rerun") != "forbidden"
    ):
        raise TrendSwingError("TS R4 attempt controls differ")


@dataclass(frozen=True)
class R4Protocol:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = PROTOCOL_PATH) -> "R4Protocol":
        resolved = project_path(path)
        document = _yaml(resolved)
        _validate_protocol(document)
        return cls(resolved, document, sha256_file(resolved))

    @property
    def start_date(self) -> str:
        return str(self.document["scope"]["profile_start_date"])

    @property
    def end_date(self) -> str:
        return str(self.document["scope"]["profile_end_date"])


@dataclass(frozen=True)
class R4Addendum:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(
        cls,
        protocol: R4Protocol,
        path: Path = ADDENDUM_PATH,
    ) -> "R4Addendum":
        resolved = project_path(path)
        document = _yaml(resolved)
        predecessor = document.get("predecessor", {})
        if (
            document.get("stage") != "RESULT_BLIND_IMPLEMENTATION_CLARIFICATION_ONLY"
            or predecessor.get("protocol_id") != protocol.document["protocol_id"]
            or predecessor.get("protocol_sha256") != protocol.sha256
            or predecessor.get("immutable_and_not_rewritten") is not True
        ):
            raise TrendSwingError("TS R4 addendum predecessor differs")
        if any(value is not False for value in document.get("authority", {}).values()):
            raise TrendSwingError("TS R4 addendum broadened authority")
        next_open = document.get("next_open_semantics", {})
        if (
            next_open.get("date")
            != "immediately_next_SSE_official_open_day_after_confirmation"
            or next_open.get("later_security_bar_substitution") != "forbidden"
            or next_open.get("confirmation_and_next_day_adjustment_factor_exact_match_required")
            is not True
        ):
            raise TrendSwingError("TS R4 next-open semantics differ")
        return cls(resolved, document, sha256_file(resolved))


def validate_bound_inputs(protocol: R4Protocol, manifest_path: Path = R3_MANIFEST_PATH) -> None:
    predecessor = protocol.document["predecessor"]
    if sha256_file(project_path(manifest_path)) != predecessor["r3_input_manifest_file_sha256"]:
        raise TrendSwingError("TS R4 R3 manifest physical hash differs")
