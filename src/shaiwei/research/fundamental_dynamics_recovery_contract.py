"""Frozen contract and immutable predecessor evidence for F2-0R."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.fundamental_dynamics_contract import EXPECTED_FEATURES
from shaiwei.research.fundamental_pit_contract import FeatureSpec, FundamentalPitError
from shaiwei.research.fundamental_pit_recovery_contract import project_relative


PROTOCOL_SCHEMA = "f2-csi800-fundamental-dynamics-recovery-v2"
PROTOCOL_ID = "f2-csi800-fundamental-dynamics-recovery-data-feature-gate-v2"
GO_VERDICT = "GO_F2_FUNDAMENTAL_DYNAMICS_RECOVERY_DATA_FEATURE_GATE_ONLY"
NO_GO_VERDICT = "NO_GO_F2_FUNDAMENTAL_DYNAMICS_RECOVERY_DATA_FEATURE_GATE"
V1_MANIFEST_PATH = "data/research/f2_csi800_fundamental_dynamics_v1/manifest.json"


@dataclass(frozen=True)
class FundamentalDynamicsRecoveryProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    features: tuple[FeatureSpec, ...]

    @classmethod
    def load(cls, path: Path) -> "FundamentalDynamicsRecoveryProtocol":
        if not path.is_file():
            raise FundamentalPitError("F2-0R protocol is missing")
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise FundamentalPitError("F2-0R protocol must be a YAML object")
        cls._validate(document)
        features = tuple(
            FeatureSpec(
                feature_id=str(item["feature_id"]),
                formula=str(item["formula"]),
                inputs=tuple(str(value) for value in item["inputs"]),
            )
            for item in document["features"]
        )
        return cls(path=path, document=document, sha256=sha256_file(path), features=features)

    @staticmethod
    def _validate(document: dict[str, Any]) -> None:
        if document.get("schema_version") != PROTOCOL_SCHEMA or document.get("protocol_id") != PROTOCOL_ID:
            raise FundamentalPitError("F2-0R protocol identity differs from the freeze")
        if document.get("result_blind_claim") is not False:
            raise FundamentalPitError("F2-0R must disclose known predecessor data quality")
        _validate_predecessor(document.get("predecessor", {}))
        _validate_recovery_change(document.get("recovery_change", {}))
        _validate_unchanged_sections(document)
        _validate_gates(document.get("gates", {}))
        outputs = document.get("outputs", {})
        if (
            outputs.get("predecessor_outputs_must_not_be_rewritten") is not True
            or outputs.get("feature_values_must_not_be_committed") is not True
        ):
            raise FundamentalPitError("F2-0R output authority differs from the freeze")
        expected = {"go": GO_VERDICT, "no_go": NO_GO_VERDICT, "strategy_effective": "NOT_EVALUATED"}
        if document.get("terminal_verdicts") != expected:
            raise FundamentalPitError("F2-0R terminal verdicts differ from the freeze")

    @property
    def required_apis(self) -> tuple[str, ...]:
        return tuple(str(value) for value in self.document["sources"]["required_apis"])

    def project_path(self, key: str, *, project_root: Path = PROJECT_ROOT) -> Path:
        return project_relative(project_root, str(self.document["outputs"][key]))


def _validate_predecessor(predecessor: dict[str, Any]) -> None:
    expected = {
        "protocol_id": "f2-csi800-fundamental-dynamics-data-feature-gate-v1",
        "verdict": "NO_GO_F2_FUNDAMENTAL_DYNAMICS_DATA_FEATURE_GATE",
        "protocol_sha256": "9c0b4e2522f9e6b24da92e9c1d04d1c3402add455efa7c73ecdfaf524bd2e81b",
        "tracked_manifest": "config/f2_csi800_fundamental_dynamics_manifest_v1.json",
        "tracked_manifest_sha256": "ea97a4fedf82b1115c4bda51c10730d88a1171fe7609baca6684a7b44448c64b",
        "ignored_manifest_sha256": "ea97a4fedf82b1115c4bda51c10730d88a1171fe7609baca6684a7b44448c64b",
        "feature_panel_sha256": "d451663ce7f664df1b5408ef794ef38244fe3f814313544ec9625534ea164fd3",
        "quality_report_sha256": "229d78766c96b355f691a0cd2ffec6a142dfc973a3dc35ca3ff28568bda17beb",
        "known_quality_no_consecutive_pair_rows": 1,
        "known_missing_pair_key": "20180531/000939.SZ",
        "preserve_without_rewrite": True,
    }
    if predecessor != expected:
        raise FundamentalPitError("F2-0R predecessor identity differs from the freeze")


def _validate_recovery_change(change: dict[str, Any]) -> None:
    expected = {
        "changed_dimension": "missing_pair_verdict_semantics_only",
        "old_rule": "quality_no_consecutive_pair_rows_must_equal_zero",
        "new_rule": "legal_unestimable_rows_remain_null_and_frozen_coverage_gates_decide_usability",
        "exact_missing_row_allowlist_forbidden": True,
        "count_specific_threshold_forbidden": True,
        "missing_pair_imputation_forbidden": True,
        "current_or_future_statement_backfill_forbidden": True,
        "formula_change_forbidden": True,
        "pit_change_forbidden": True,
        "sample_change_forbidden": True,
        "coverage_threshold_change_forbidden": True,
        "f2_effects_still_forbidden": True,
    }
    if change != expected:
        raise FundamentalPitError("F2-0R recovery change differs from the freeze")


def _feature_identity(items: list[dict[str, Any]]) -> tuple[tuple[str, str, int], ...]:
    return tuple(
        (str(item.get("feature_id")), str(item.get("formula")), int(item.get("expected_direction")))
        for item in items
    )


def _validate_unchanged_sections(document: dict[str, Any]) -> None:
    v1_path = PROJECT_ROOT / "config/f2_csi800_fundamental_dynamics_v1.yaml"
    if sha256_file(v1_path) != document["predecessor"]["protocol_sha256"]:
        raise FundamentalPitError("F2-0R predecessor protocol was rewritten")
    v1 = yaml.safe_load(v1_path.read_text(encoding="utf-8"))
    for section in ("scope", "family_boundary", "sources", "point_in_time", "denominator_policy"):
        if document.get(section) != v1.get(section):
            raise FundamentalPitError(f"F2-0R changed frozen {section}")
    if _feature_identity(document.get("features", [])) != EXPECTED_FEATURES:
        raise FundamentalPitError("F2-0R changed frozen feature identity")
    if any(
        document.get(key) != v1.get(key)
        for key in (
            "non_finite_output",
            "winsorization_authorized",
            "neutralization_authorized",
            "orientation_authorized",
        )
    ):
        raise FundamentalPitError("F2-0R changed frozen transformation authority")


def _validate_gates(gates: dict[str, Any]) -> None:
    expected = {
        "predecessor_identity_preserved": True,
        "required_sources_present": True,
        "required_source_columns_present": True,
        "latest_batches_integrity_pass": True,
        "source_identity_conflicts": 0,
        "open_calendar_complete_for_scope": True,
        "formation_dates_after_quality_start": "at_least_90",
        "membership_count_each_formation": {"minimum": 700, "maximum": 900},
        "bse_rows": 0,
        "duplicate_feature_keys": 0,
        "current_mixed_component_period_rows": 0,
        "predecessor_mixed_component_period_rows": 0,
        "nonconsecutive_pair_rows": 0,
        "future_availability_rows": 0,
        "pair_absent_rows_with_nonnull_available_date": 0,
        "pair_absent_rows_with_any_nonnull_feature": 0,
        "pair_present_rows_missing_end_date": 0,
        "feature_aggregate_coverage_minimum": 0.85,
        "feature_worst_formation_coverage_minimum": 0.75,
        "quality_no_consecutive_pair_rows": "diagnostic_without_fixed_count_gate",
    }
    if gates != expected:
        raise FundamentalPitError("F2-0R gates differ from the freeze")


def verify_predecessor_data(
    protocol: FundamentalDynamicsRecoveryProtocol,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    expected = protocol.document["predecessor"]
    tracked = project_relative(project_root, str(expected["tracked_manifest"]))
    ignored = project_relative(project_root, V1_MANIFEST_PATH)
    if not tracked.is_file() or sha256_file(tracked) != expected["tracked_manifest_sha256"]:
        raise FundamentalPitError("F2-0R predecessor tracked manifest differs")
    if not ignored.is_file() or sha256_file(ignored) != expected["ignored_manifest_sha256"]:
        raise FundamentalPitError("F2-0R predecessor ignored manifest differs")
    manifest = json.loads(tracked.read_text(encoding="utf-8"))
    if manifest != json.loads(ignored.read_text(encoding="utf-8")):
        raise FundamentalPitError("F2-0R predecessor manifests disagree")
    feature = project_relative(project_root, str(manifest["feature_panel"]["path"]))
    report = project_relative(project_root, str(manifest["report"]["path"]))
    if not feature.is_file() or sha256_file(feature) != expected["feature_panel_sha256"]:
        raise FundamentalPitError("F2-0R predecessor feature panel differs")
    if not report.is_file() or sha256_file(report) != expected["quality_report_sha256"]:
        raise FundamentalPitError("F2-0R predecessor report differs")
    if (
        manifest.get("protocol_id") != expected["protocol_id"]
        or manifest.get("verdict") != expected["verdict"]
        or manifest.get("diagnostic_counts", {}).get("quality_no_consecutive_pair_rows")
        != expected["known_quality_no_consecutive_pair_rows"]
    ):
        raise FundamentalPitError("F2-0R predecessor decision differs")
    return {
        "protocol_id": manifest["protocol_id"],
        "verdict": manifest["verdict"],
        "tracked_manifest_sha256": sha256_file(tracked),
        "ignored_manifest_sha256": sha256_file(ignored),
        "feature_panel_sha256": sha256_file(feature),
        "quality_report_sha256": sha256_file(report),
        "known_quality_no_consecutive_pair_rows": expected["known_quality_no_consecutive_pair_rows"],
    }
