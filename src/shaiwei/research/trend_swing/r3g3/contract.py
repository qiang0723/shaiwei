"""Frozen protocol and sealed-parent validation for R3G-3."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from shaiwei.research.trend_swing.r3g3.evidence import R3G3Error, canonical_sha256, sha256_file


EXPECTED_SCHEMA = "ts-v5-r3g3-discovery-diagnostic-protocol-v1"
EXPECTED_STATUS = "RESULT_KNOWN_DETAIL_BLIND_DIAGNOSTIC_PROTOCOL_FROZEN_PENDING_IMPLEMENTATION"
RECOVERY_R1_SCHEMA = "ts-v5-r3g3-diagnostic-entrypoint-recovery-scope-v1"
RECOVERY_R1_ACTION = (
    "TS_R3G3_DISCOVERY_FAILURE_DIAGNOSTIC_ENTRYPOINT_RECOVERY_ONCE_WITH_REPLAY_AND_"
    "INDEPENDENT_AUDIT"
)
RECOVERY_R2_SCHEMA = "ts-v5-r3g3-diagnostic-parent-authority-recovery-scope-v1"
RECOVERY_R2_ACTION = (
    "TS_R3G3_DISCOVERY_FAILURE_DIAGNOSTIC_PARENT_AUTHORITY_RECOVERY_ONCE_WITH_REPLAY_"
    "AND_INDEPENDENT_AUDIT"
)
AUDIT_RECOVERY_SCHEMA = "ts-v5-r3g3-diagnostic-auditor-entrypoint-recovery-scope-v1"
AUDIT_RECOVERY_ACTION = (
    "TS_R3G3_DISCOVERY_FAILURE_DIAGNOSTIC_INDEPENDENT_AUDIT_ENTRYPOINT_RECOVERY_ONCE"
)
POINT_ROLES = ("primary", "confirmation_neighbour", "tolerance_neighbour")
SCENARIOS = ("base_1x", "all_costs_2x", "base_plus_10bp_slippage_each_side")


def _mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise R3G3Error(f"R3G-3 document is missing or invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise R3G3Error(f"R3G-3 document is not a mapping: {path.name}")
    return value


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise R3G3Error(f"R3G-3 JSON is missing or invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise R3G3Error(f"R3G-3 JSON is not a mapping: {path.name}")
    return value


def _validate_static(document: Mapping[str, Any]) -> None:
    execution = document.get("execution_contract", {})
    boundary = document.get("allowed_read_boundary", {})
    terminal = document.get("terminal_boundary", {})
    if (
        document.get("schema_version") != EXPECTED_SCHEMA
        or document.get("status") != EXPECTED_STATUS
        or document.get("production_authorization") != "none"
        or tuple(boundary.get("points", {})) != POINT_ROLES
        or tuple(boundary.get("aggregate_json_each_point", {}).get("scenarios", ())) != SCENARIOS
        or boundary.get("pass") != "first_pass"
        or boundary.get("partition") != "discovery"
        or boundary.get("replay_detail_read") != "forbidden"
        or boundary.get("holdout_path_or_value_read") != "forbidden"
        or boundary.get("partial_2026_path_or_value_read") != "forbidden"
        or execution.get("strategy_effect_attempt_increment") != 0
        or execution.get("model_training_prediction_or_backtest") != "forbidden"
        or execution.get("external_network_or_provider") != "forbidden"
        or terminal.get("r3g2_verdict_may_change") is not False
        or terminal.get("holdout_may_open") is not False
    ):
        raise R3G3Error("R3G-3 frozen protocol authority differs")


@dataclass(frozen=True)
class DiagnosticProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path) -> "DiagnosticProtocol":
        document = _mapping(path)
        _validate_static(document)
        return cls(path=path.resolve(), document=document, sha256=sha256_file(path))

    @property
    def points(self) -> tuple[tuple[str, str], ...]:
        return tuple(self.document["allowed_read_boundary"]["points"].items())


def verify_entrypoint_recovery(
    path: Path,
    protocol: DiagnosticProtocol,
    prior_authorization_path: Path | None = None,
) -> tuple[str, str]:
    document = _mapping(path)
    prior = document.get("prior_invocation", {})
    recovery = document.get("recovery", {})
    schema, action = document.get("schema_version"), document.get("action")
    if (
        schema not in {RECOVERY_R1_SCHEMA, RECOVERY_R2_SCHEMA}
        or action not in {RECOVERY_R1_ACTION, RECOVERY_R2_ACTION}
        or (schema == RECOVERY_R1_SCHEMA and action != RECOVERY_R1_ACTION)
        or (schema == RECOVERY_R2_SCHEMA and action != RECOVERY_R2_ACTION)
        or document.get("status") != "FROZEN_BEFORE_RECOVERY_EXECUTION"
        or document.get("parent_protocol_sha256") != protocol.sha256
        or recovery.get("invocation_count") != 1
        or recovery.get("strategy_effect_attempt_increment") != 0
        or recovery.get("external_network") is not False
        or recovery.get("holdout_read") is not False
        or recovery.get("production_authorization") != "none"
    ):
        raise R3G3Error("R3G-3 entrypoint recovery scope differs")
    if schema == RECOVERY_R1_SCHEMA:
        valid_prior = (
            prior.get("failure_stage") == "argparse_dispatch_before_run_function"
            and prior.get("sealed_input_read") is False
            and prior.get("authorization_written") is False
            and prior.get("output_written") is False
            and prior.get("strategy_effect_attempt_increment") == 0
        )
    else:
        expected_authorization = document.get("prior_recovery", {}).get(
            "authorization_sha256"
        )
        valid_prior = (
            prior_authorization_path is not None
            and prior_authorization_path.is_file()
            and sha256_file(prior_authorization_path) == expected_authorization
            and prior.get("failure_stage") == "parent_authority_validation_before_detail_read"
            and prior.get("detail_parquet_read") is False
            and prior.get("diagnostic_computed") is False
            and prior.get("strategy_effect_attempt_increment") == 0
        )
    if not valid_prior:
        raise R3G3Error("R3G-3 prior recovery evidence differs")
    return sha256_file(path), str(action)


def verify_auditor_recovery(
    path: Path,
    protocol: DiagnosticProtocol,
    diagnostic_root: Path,
) -> tuple[str, str]:
    document = _mapping(path)
    prior = document.get("prior_invocation", {})
    diagnostic = document.get("frozen_diagnostic", {})
    recovery = document.get("recovery", {})
    bindings = {
        "authorization.json": diagnostic.get("authorization_sha256"),
        "report.json": diagnostic.get("report_sha256"),
        "manifest.json": diagnostic.get("manifest_sha256"),
    }
    if (
        document.get("schema_version") != AUDIT_RECOVERY_SCHEMA
        or document.get("status") != "FROZEN_BEFORE_AUDITOR_RECOVERY_EXECUTION"
        or document.get("action") != AUDIT_RECOVERY_ACTION
        or document.get("parent_protocol_sha256") != protocol.sha256
        or prior.get("failure_stage") != "argparse_dispatch_before_audit_function"
        or prior.get("diagnostic_detail_read") is not False
        or prior.get("audit_output_written") is not False
        or recovery.get("invocation_count") != 1
        or recovery.get("runner_may_rerun") is not False
        or recovery.get("external_network") is not False
        or recovery.get("holdout_read") is not False
        or recovery.get("production_authorization") != "none"
        or any(
            expected is None
            or not (diagnostic_root / name).is_file()
            or sha256_file(diagnostic_root / name) != expected
            for name, expected in bindings.items()
        )
    ):
        raise R3G3Error("R3G-3 auditor recovery scope differs")
    return sha256_file(path), AUDIT_RECOVERY_ACTION


def _verify_first_pass_manifest(protocol: DiagnosticProtocol, inputs: Path) -> dict[str, Any]:
    manifest = read_json(inputs / "first-pass-manifest.json")
    files: dict[str, str] = {}
    discovery = inputs / "discovery"
    for path in sorted(discovery.rglob("*")):
        if path.is_file():
            files[f"discovery/{path.relative_to(discovery).as_posix()}"] = sha256_file(path)
    files["pass_summary.json"] = sha256_file(inputs / "first-pass-summary.json")
    expected = {
        "schema_version": "ts-v5-r3g2-effect-pass-manifest-v1",
        "file_count": len(files),
        "files": files,
        "bundle_sha256": canonical_sha256(files),
    }
    parent = protocol.document["frozen_parent"]["first_pass_manifest"]
    if (
        sha256_file(inputs / "first-pass-manifest.json") != parent["sha256"]
        or manifest != expected
        or manifest.get("bundle_sha256") != parent["bundle_sha256"]
        or any("holdout" in name or "2026" in name for name in files)
    ):
        raise R3G3Error("R3G-3 first-pass manifest or discovery boundary differs")
    return manifest


def verify_parent_sources(protocol: DiagnosticProtocol, inputs: Path) -> dict[str, Any]:
    parent = protocol.document["frozen_parent"]
    bindings = {
        "report.json": parent["result_report"]["sha256"],
        "parent-audit.json": parent["independent_audit"]["sha256"],
        "first-pass-summary.json": parent["first_pass_summary"]["sha256"],
        "partition-summary.json": parent["discovery_partition_summary"]["sha256"],
    }
    for name, expected in bindings.items():
        path = inputs / name
        if not path.is_file() or sha256_file(path) != expected:
            raise R3G3Error(f"R3G-3 sealed parent differs: {name}")
    report, audit = read_json(inputs / "report.json"), read_json(inputs / "parent-audit.json")
    if (
        report.get("verdict") != parent["authoritative_verdict"]
        or report.get("strategy_effective") != "PENDING_INDEPENDENT_AUDIT"
        or report.get("holdout") is not None
        or audit.get("independent_audit") != "PASS"
        or audit.get("verdict") != parent["authoritative_verdict"]
        or audit.get("strategy_effective") != parent["strategy_effective"]
    ):
        raise R3G3Error("R3G-3 parent authority or holdout firewall differs")
    manifest = _verify_first_pass_manifest(protocol, inputs)
    return {
        "protocol_sha256": protocol.sha256,
        "parent_report_sha256": bindings["report.json"],
        "parent_audit_sha256": bindings["parent-audit.json"],
        "first_pass_manifest_sha256": parent["first_pass_manifest"]["sha256"],
        "first_pass_bundle_sha256": manifest["bundle_sha256"],
    }
