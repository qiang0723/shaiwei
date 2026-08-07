"""M6-3C real Top20 release, approval, and runtime contracts."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.model_attribution.effect_contract import write_once_document
from shaiwei.research.topk_conversion.contract import ConversionError, ProtocolBundle


REAL_PROTOCOL = PROJECT_ROOT / "config/m6_csi800_topk20_conversion_real_release_v1.yaml"
SCHEDULE_ADDENDUM = PROJECT_ROOT / "config/m6_csi800_topk20_conversion_schedule_addendum_v1.yaml"
ORIGINAL_M6_SCOPE = PROJECT_ROOT / "config/m6_csi800_model_attribution_release_scope_v1.json"
APPROVAL_ACTION = "M6_TOPK20_CONVERSION_EFFECT_ONCE_WITH_INTERNAL_REPLAY_AND_INDEPENDENT_AUDIT"
SCOPE_KIND = "TOPK20_REAL_EFFECT_RELEASE_READY_NOT_EXECUTION_APPROVAL"
SCOPE_SCHEMA = "m6-topk20-conversion-release-scope-v1"
IMAGE = "shaiwei:m6-topk-conversion-release-v1"

RUNNER_COMMAND = [
    "python", "-m", "shaiwei.research.topk_conversion.real_run",
    "--release", "/inputs/release.json", "--approval", "/inputs/approval.json",
    "--provider-root", "/qlib", "--m6-effect-root", "/m6-effect",
    "--m6-audit", "/inputs/m6-audit.json", "--output-root", "/outputs",
]
AUDITOR_COMMAND = [
    "python", "-m", "shaiwei.research.topk_conversion.real_audit",
    "--release", "/inputs/release.json", "--approval", "/inputs/approval.json",
    "--effect-root", "/outputs", "--audit-root", "/audit",
]


def mapping(path: Path, *, yaml_document: bool = False) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        value = yaml.safe_load(raw) if yaml_document else json.loads(raw)
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise ConversionError(f"M6-3C document is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise ConversionError(f"M6-3C document is not a mapping: {path.name}")
    return value


def expected_authority() -> dict[str, Any]:
    return {
        "release_ready": True,
        "execution_authorized": False,
        "qlib_read_authorized": False,
        "sealed_m6_effect_read_authorized": False,
        "reused_prediction_read_authorized": False,
        "top30_compatibility_backtest_authorized": False,
        "real_top20_backtest_authorized": False,
        "formal_effect_output_write_authorized": False,
        "independent_audit_authorized": False,
        "model_fit_authorized": False,
        "prediction_generation_authorized": False,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False,
        "env_or_secret_read_authorized": False,
        "forward_signal_authorized": False,
        "paper_portfolio_authorized": False,
        "production_authorization": "none",
    }


def expected_inputs(protocol: RealProtocol) -> dict[str, Any]:
    original = mapping(ORIGINAL_M6_SCOPE)
    effect = protocol.document["predecessors"]["authoritative_m6_effect"]
    audit = protocol.document["predecessors"]["authoritative_m6_audit"]
    return {
        "qlib": dict(original["scope"]["inputs"]),
        "sealed_m6_effect": {
            "root": effect["root"],
            "file_count": effect["file_count"],
            "total_bytes": effect["byte_count"],
            "tree_sha256": effect["tree_sha256"],
            "report_sha256": effect["report_sha256"],
            "first_pass_bundle_sha256": effect["first_pass_bundle_sha256"],
            "replay_bundle_sha256": effect["replay_bundle_sha256"],
        },
        "sealed_m6_audit": {
            "path": audit["path"],
            "sha256": audit["sha256"],
            "independent_audit": "PASS",
        },
        "original_m6_release": {
            "path": str(ORIGINAL_M6_SCOPE.relative_to(PROJECT_ROOT)),
            "document_sha256": sha256_file(ORIGINAL_M6_SCOPE),
            "release_scope_sha256": original["release_scope_sha256"],
        },
    }


def _validate_protocol(document: dict[str, Any]) -> None:
    if document.get("protocol_id") != "m6-csi800-topk20-conversion-real-release-v1":
        raise ConversionError("M6-3C release protocol identity differs")
    if document.get("stage") != "RESULT_BLIND_REAL_TOPK20_RELEASE_PREPARATION_ONLY":
        raise ConversionError("M6-3C release protocol stage differs")
    approval = document.get("release_and_approval", {})
    if approval.get("release_scope_kind") != SCOPE_KIND:
        raise ConversionError("M6-3C scope kind differs")
    if approval.get("approval_action") != APPROVAL_ACTION:
        raise ConversionError("M6-3C approval action differs")
    if document.get("stop_condition", {}).get("no_real_effect_or_qlib_read_before_approval") is not True:
        raise ConversionError("M6-3C preapproval stop is absent")


def _validate_addendum(document: dict[str, Any]) -> None:
    if document.get("addendum_id") != "m6-csi800-topk20-conversion-schedule-addendum-v1":
        raise ConversionError("M6-3 schedule addendum identity differs")
    correction = document.get("correction", {})
    if correction.get("decision_or_gate_change") is not False:
        raise ConversionError("M6-3 schedule addendum changes the decision")
    overlap = correction.get("scheduled_top20_overlap_vs_clean_control", {})
    if overlap.get("aggregation") != (
        "unweighted_arithmetic_mean_across_all_rebalance_dates_in_W1_through_W6"
    ):
        raise ConversionError("M6-3 schedule overlap aggregation differs")


@dataclass(frozen=True)
class RealProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    result: dict[str, Any]
    result_sha256: str
    engineering_sha256: str
    addendum: dict[str, Any]
    addendum_sha256: str

    @classmethod
    def load(cls, path: Path = REAL_PROTOCOL) -> "RealProtocol":
        bundle = ProtocolBundle.load()
        document = mapping(path.resolve(), yaml_document=True)
        _validate_protocol(document)
        predecessors = document["predecessors"]
        expected = {
            "result_protocol": bundle.result_sha256,
            "engineering_protocol": bundle.engineering_sha256,
        }
        for key, digest in expected.items():
            row = predecessors[key]
            if row["sha256"] != digest or sha256_file(PROJECT_ROOT / row["path"]) != digest:
                raise ConversionError(f"M6-3C {key} predecessor differs")
        manifest = predecessors["engineering_manifest"]
        if sha256_file(PROJECT_ROOT / manifest["path"]) != manifest["sha256"]:
            raise ConversionError("M6-3C engineering manifest differs")
        addendum = mapping(SCHEDULE_ADDENDUM, yaml_document=True)
        _validate_addendum(addendum)
        return cls(
            path=path.resolve(), document=document, sha256=sha256_file(path.resolve()),
            result=bundle.result, result_sha256=bundle.result_sha256,
            engineering_sha256=bundle.engineering_sha256, addendum=addendum,
            addendum_sha256=sha256_file(SCHEDULE_ADDENDUM),
        )


def validate_scope(scope: dict[str, Any], protocol: RealProtocol) -> None:
    if scope.get("scope_kind") != SCOPE_KIND or scope.get("protocol_id") != protocol.document["protocol_id"]:
        raise ConversionError("M6-3C release scope identity differs")
    hashes = scope.get("protocols", {})
    expected_hashes = {
        "real_release_sha256": protocol.sha256,
        "result_sha256": protocol.result_sha256,
        "engineering_sha256": protocol.engineering_sha256,
        "schedule_addendum_sha256": protocol.addendum_sha256,
    }
    if hashes != expected_hashes:
        raise ConversionError("M6-3C protocol hashes differ")
    implementation, image = scope.get("implementation", {}), scope.get("image", {})
    commit, snapshot = implementation.get("git_commit"), implementation.get("code_snapshot_sha256")
    if not isinstance(commit, str) or len(commit) != 40 or implementation.get("origin_main_commit") != commit:
        raise ConversionError("M6-3C implementation is not bound to origin/main")
    if image.get("reference") != IMAGE or image.get("git_commit") != commit:
        raise ConversionError("M6-3C image Git identity differs")
    if image.get("code_snapshot_sha256") != snapshot or not str(image.get("image_id", "")).startswith("sha256:"):
        raise ConversionError("M6-3C image content identity differs")
    if image.get("platform") not in {"linux/arm64", "linux/amd64"}:
        raise ConversionError("M6-3C image platform differs")
    if scope.get("authority") != expected_authority():
        raise ConversionError("M6-3C preapproval authority differs")
    if scope.get("inputs") != expected_inputs(protocol):
        raise ConversionError("M6-3C frozen inputs differ")
    if scope.get("execution") != {
        "approval_action": APPROVAL_ACTION, "runner_invocation_count": 1,
        "complete_internal_passes": ["first_pass", "replay"],
        "independent_auditor_invocation_count": 1,
        "portfolio_attempt_count_consumed_at_first_top20_effect_read": 2,
        "model_attempt_increment": 0, "same_release_retry_authorized": False,
    }:
        raise ConversionError("M6-3C execution count differs")
    docker = protocol.document["docker"]
    container = scope.get("container", {})
    common = {
        "compose_path": docker["compose_file"], "network_mode": "none", "read_only_root": True,
        "run_as_non_root": True, "cap_drop_all": True, "no_new_privileges": True,
        "env_file_mounted": False, "docker_socket_mounted": False,
        "full_project_root_mounted": False, "production_ledger_mounted": False,
    }
    if any(container.get(key) != value for key, value in common.items()):
        raise ConversionError("M6-3C container boundary differs")
    if container.get("compose_sha256") != sha256_file(PROJECT_ROOT / docker["compose_file"]):
        raise ConversionError("M6-3C compose identity differs")
    runner, auditor = container.get("runner", {}), container.get("auditor", {})
    expected_runner = ("m6-topk-effect-runner", RUNNER_COMMAND, 4, "8g", 192, docker["runner_mounts"])
    expected_auditor = ("m6-topk-effect-auditor", AUDITOR_COMMAND, 2, "4g", 128, docker["auditor_mounts"])
    if tuple(runner.get(key) for key in ("service", "command", "cpus", "memory", "pids_limit", "mounts")) != expected_runner:
        raise ConversionError("M6-3C runner boundary differs")
    if tuple(auditor.get(key) for key in ("service", "command", "cpus", "memory", "pids_limit", "mounts")) != expected_auditor:
        raise ConversionError("M6-3C auditor boundary differs")
    if scope.get("outputs") != {
        "effect_root": "data/research/m6_csi800_topk20_conversion_v1/effect",
        "audit_root": "data/research/m6_csi800_topk20_conversion_v1/effect-audit",
        "experiment_ledger_write_authorized": False,
    }:
        raise ConversionError("M6-3C output boundary differs")


@dataclass(frozen=True)
class ReleaseScope:
    path: Path
    document: dict[str, Any]
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, protocol: RealProtocol) -> "ReleaseScope":
        document = mapping(path.resolve())
        if set(document) != {"schema_version", "release_scope_sha256", "scope"}:
            raise ConversionError("M6-3C release document fields differ")
        if document.get("schema_version") != SCOPE_SCHEMA or not isinstance(document.get("scope"), dict):
            raise ConversionError("M6-3C release document schema differs")
        digest = canonical_sha256(document["scope"])
        if document.get("release_scope_sha256") != digest:
            raise ConversionError("M6-3C release self hash differs")
        validate_scope(document["scope"], protocol)
        return cls(path.resolve(), document, document["scope"], digest)

    def verify_runtime_identity(self) -> dict[str, str]:
        expected = self.scope["implementation"]
        actual = {"git_commit": git_head(), "code_snapshot_sha256": code_snapshot_sha256()}
        if actual["git_commit"] != expected["git_commit"] or actual["code_snapshot_sha256"] != expected["code_snapshot_sha256"]:
            raise ConversionError("M6-3C runtime identity differs")
        manifest = os.getenv("SHAIWEI_RELEASE_MANIFEST", "").strip()
        if not manifest or sha256_file(Path(manifest)) != self.scope["image"]["release_manifest_sha256"]:
            raise ConversionError("M6-3C embedded release manifest differs")
        return actual


@dataclass(frozen=True)
class Approval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: ReleaseScope) -> "Approval":
        document = mapping(path.resolve())
        expected = {
            "schema_version": "m6-topk20-conversion-approval-v1",
            "release_scope_sha256": release.sha256, "action": APPROVAL_ACTION,
            "qlib_read_authorized": True, "sealed_m6_effect_read_authorized": True,
            "reused_prediction_read_authorized": True,
            "top30_compatibility_backtest_authorized": True, "real_top20_backtest_authorized": True,
            "formal_effect_output_write_authorized": True, "independent_audit_authorized": True,
            "model_fit_authorized": False, "prediction_generation_authorized": False,
            "experiment_ledger_write_authorized": False, "external_network_authorized": False,
            "env_or_secret_read_authorized": False, "production_authorization": "none",
        }
        if set(document) != set(expected) | {"approved_at", "consumed"}:
            raise ConversionError("M6-3C approval fields differ")
        if any(document.get(key) != value for key, value in expected.items()):
            raise ConversionError("M6-3C approval authority differs")
        if not document.get("approved_at") or document.get("consumed") is not False:
            raise ConversionError("M6-3C approval state differs")
        return cls(path.resolve(), document, sha256_file(path.resolve()))


__all__ = [
    "APPROVAL_ACTION", "AUDITOR_COMMAND", "Approval", "IMAGE", "ORIGINAL_M6_SCOPE",
    "RUNNER_COMMAND", "RealProtocol", "ReleaseScope", "SCOPE_KIND", "SCOPE_SCHEMA",
    "expected_authority", "expected_inputs", "mapping", "validate_scope", "write_once_document",
]
