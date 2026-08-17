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
        or report.get("strategy_effective") != parent["strategy_effective"]
        or report.get("holdout") is not None
        or audit.get("independent_audit") != "PASS"
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

