"""M6-2 real-effect protocol, release, approval, and immutable-file contracts."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.model_attribution.contract import (
    AttributionError,
    ProtocolBundle,
    canonical_json,
    canonical_sha256,
    sha256_file,
)


REAL_RELEASE_PROTOCOL = PROJECT_ROOT / "config/m6_csi800_model_attribution_real_release_v1.yaml"
ENGINEERING_MANIFEST = PROJECT_ROOT / "config/m6_csi800_model_attribution_engineering_manifest_v1.json"
APPROVAL_ACTION = "M6_REAL_EFFECT_ONCE_WITH_INTERNAL_REPLAY_AND_INDEPENDENT_AUDIT"
SCOPE_KIND = "REAL_EFFECT_RELEASE_READY_NOT_EXECUTION_APPROVAL"


def _expected_authority() -> dict[str, Any]:
    return {
        "release_ready": True,
        "execution_authorized": False,
        "real_qlib_feature_or_price_read_authorized": False,
        "real_label_or_effect_read_authorized": False,
        "real_model_fit_authorized": False,
        "real_prediction_authorized": False,
        "real_backtest_authorized": False,
        "formal_effect_output_write_authorized": False,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False,
        "env_or_secret_read_authorized": False,
        "forward_signal_authorized": False,
        "paper_portfolio_authorized": False,
        "production_authorization": "none",
    }


def _expected_mounts(protocol: EffectProtocol, role: str) -> list[dict[str, str]]:
    return [dict(row) for row in protocol.document["docker"][f"{role}_mounts"]]


def _validate_release_scope(scope: dict[str, Any], protocol: EffectProtocol) -> None:
    if scope.get("scope_kind") != SCOPE_KIND:
        raise AttributionError("M6 release scope kind differs")
    if scope.get("protocol_id") != protocol.document["protocol_id"]:
        raise AttributionError("M6 release protocol identity differs")
    if scope.get("protocol_sha256") != protocol.sha256:
        raise AttributionError("M6 release protocol hash differs")
    if scope.get("result_protocol_sha256") != protocol.result_sha256:
        raise AttributionError("M6 result protocol hash differs in release")
    predecessor = protocol.document["predecessors"]["engineering_manifest"]
    if scope.get("engineering_manifest_sha256") != predecessor["sha256"]:
        raise AttributionError("M6 engineering manifest hash differs in release")
    implementation = scope.get("implementation", {})
    image = scope.get("image", {})
    commit = implementation.get("git_commit")
    snapshot = implementation.get("code_snapshot_sha256")
    if not isinstance(commit, str) or len(commit) != 40:
        raise AttributionError("M6 implementation commit is invalid")
    if implementation.get("origin_main_commit") != commit:
        raise AttributionError("M6 implementation was not bound to origin/main")
    if implementation.get("code_bundle_sha256") != snapshot:
        raise AttributionError("M6 implementation code bundle differs")
    if image.get("reference") != protocol.document["docker"]["image"]:
        raise AttributionError("M6 image reference differs")
    if image.get("git_commit") != commit or image.get("code_snapshot_sha256") != snapshot:
        raise AttributionError("M6 image release identity differs")
    if not str(image.get("image_id", "")).startswith("sha256:"):
        raise AttributionError("M6 image content identity is invalid")
    if image.get("platform") not in {"linux/arm64", "linux/amd64"}:
        raise AttributionError("M6 image platform differs")
    engineering = _mapping(ENGINEERING_MANIFEST)
    expected_inputs = {
        key: engineering["frozen_inputs"][key]
        for key in (
            "qlib_manifest_sha256",
            "qlib_tree_sha256",
            "qlib_file_count",
            "calendar_sha256",
            "calendar_row_count",
        )
    }
    if scope.get("inputs") != expected_inputs:
        raise AttributionError("M6 release input identity differs")
    if scope.get("authority") != _expected_authority():
        raise AttributionError("M6 release authority differs")
    expected_execution = {
        "approval_action": APPROVAL_ACTION,
        "runner_invocation_count": 1,
        "complete_internal_passes": ["first_pass", "replay"],
        "independent_auditor_invocation_count": 1,
        "alternative_attempt_count_consumed_at_first_real_effect_read": 2,
        "same_release_retry_authorized": False,
    }
    if scope.get("execution") != expected_execution:
        raise AttributionError("M6 release execution count differs")
    container = scope.get("container", {})
    expected_common = {
        "compose_path": protocol.document["docker"]["compose_file"],
        "network_mode": "none",
        "read_only_root": True,
        "run_as_non_root": True,
        "cap_drop_all": True,
        "no_new_privileges": True,
        "env_file_mounted": False,
        "docker_socket_mounted": False,
        "full_project_root_mounted": False,
        "production_ledger_mounted": False,
    }
    if any(container.get(key) != value for key, value in expected_common.items()):
        raise AttributionError("M6 release container boundary differs")
    compose_path = PROJECT_ROOT / expected_common["compose_path"]
    if container.get("compose_sha256") != sha256_file(compose_path):
        raise AttributionError("M6 release compose identity differs")
    if container.get("runner", {}).get("mounts") != _expected_mounts(protocol, "runner"):
        raise AttributionError("M6 release runner mounts differ")
    if container.get("auditor", {}).get("mounts") != _expected_mounts(protocol, "auditor"):
        raise AttributionError("M6 release auditor mounts differ")
    runner = container.get("runner", {})
    expected_runner_command = [
        "python",
        "-m",
        "shaiwei.research.model_attribution.effect_run",
        "--release",
        "/inputs/release.json",
        "--approval",
        "/inputs/approval.json",
        "--provider-root",
        "/qlib",
        "--output-root",
        "/outputs",
    ]
    expected_auditor_command = [
        "python",
        "-m",
        "shaiwei.research.model_attribution.effect_audit",
        "--release",
        "/inputs/release.json",
        "--approval",
        "/inputs/approval.json",
        "--effect-root",
        "/outputs",
        "--audit-root",
        "/audit",
    ]
    auditor = container.get("auditor", {})
    if runner.get("service") != "m6-effect-runner" or runner.get("command") != expected_runner_command:
        raise AttributionError("M6 release runner command differs")
    if auditor.get("service") != "m6-effect-auditor" or auditor.get("command") != expected_auditor_command:
        raise AttributionError("M6 release auditor command differs")
    if (runner.get("cpus"), runner.get("memory"), runner.get("pids_limit")) != (6, "12g", 256):
        raise AttributionError("M6 release runner resources differ")
    if (auditor.get("cpus"), auditor.get("memory"), auditor.get("pids_limit")) != (2, "4g", 256):
        raise AttributionError("M6 release auditor resources differ")
    outputs = scope.get("outputs", {})
    if outputs != {
        "effect_root": "data/research/m6_csi800_model_attribution_v1/effect",
        "audit_root": "data/research/m6_csi800_model_attribution_v1/effect-audit",
        "experiment_ledger_write_authorized": False,
    }:
        raise AttributionError("M6 release outputs differ")


def _mapping(path: Path, *, yaml_document: bool = False) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        value = yaml.safe_load(raw) if yaml_document else json.loads(raw)
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise AttributionError(f"M6 document is missing or invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise AttributionError(f"M6 document is not a mapping: {path.name}")
    return value


def write_once_bytes(path: Path, payload: bytes) -> tuple[str, bool]:
    import hashlib

    digest = hashlib.sha256(payload).hexdigest()
    if path.exists():
        if path.read_bytes() != payload:
            raise AttributionError(f"M6 write-once conflict: {path.name}")
        return digest, True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return digest, False


def write_once_document(path: Path, value: Any) -> tuple[str, bool]:
    return write_once_bytes(path, canonical_json(value) + b"\n")


def validate_release_protocol(document: dict[str, Any]) -> None:
    if document.get("protocol_id") != "m6-csi800-model-attribution-real-release-v1":
        raise AttributionError("unexpected M6-2 release protocol identity")
    if document.get("stage") != "RESULT_BLIND_REAL_RELEASE_PREPARATION_ONLY":
        raise AttributionError("M6-2 release stage differs")
    authority = document.get("authority", {})
    forbidden = (
        "real_qlib_feature_or_price_read_authorized",
        "real_label_or_effect_read_authorized",
        "real_model_fit_authorized",
        "real_prediction_authorized",
        "real_backtest_authorized",
        "formal_effect_output_write_authorized",
        "experiment_ledger_write_authorized",
        "forward_signal_authorized",
        "paper_portfolio_authorized",
        "external_runtime_network_authorized",
        "env_or_secret_read_authorized",
    )
    if any(authority.get(key) is not False for key in forbidden):
        raise AttributionError("M6-2 preapproval authority was broadened")
    if authority.get("production_authorization") != "none":
        raise AttributionError("M6-2 cannot authorize production")
    counting = document.get("execution_counting", {})
    if counting.get("complete_internal_passes") != ["first_pass", "replay"]:
        raise AttributionError("M6-2 complete pass set differs")
    if counting.get("alternative_attempt_count_consumed_at_first_real_effect_read") != 2:
        raise AttributionError("M6-2 attempt count differs")
    approval = document.get("release_and_approval", {})
    if approval.get("approval_action") != APPROVAL_ACTION:
        raise AttributionError("M6-2 approval action differs")
    if approval.get("release_scope_kind") != SCOPE_KIND:
        raise AttributionError("M6-2 release scope kind differs")


@dataclass(frozen=True)
class EffectProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    result: dict[str, Any]
    result_sha256: str

    @classmethod
    def load(cls, path: Path = REAL_RELEASE_PROTOCOL) -> "EffectProtocol":
        bundle = ProtocolBundle.load()
        resolved = path.resolve()
        document = _mapping(resolved, yaml_document=True)
        validate_release_protocol(document)
        predecessors = document["predecessors"]
        if predecessors["result_protocol"]["sha256"] != bundle.result_sha256:
            raise AttributionError("M6-2 result protocol predecessor differs")
        manifest_path = PROJECT_ROOT / predecessors["engineering_manifest"]["path"]
        if sha256_file(manifest_path) != predecessors["engineering_manifest"]["sha256"]:
            raise AttributionError("M6-2 engineering manifest predecessor differs")
        return cls(
            path=resolved,
            document=document,
            sha256=sha256_file(resolved),
            result=bundle.result,
            result_sha256=bundle.result_sha256,
        )


@dataclass(frozen=True)
class EffectReleaseScope:
    path: Path
    document: dict[str, Any]
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, protocol: EffectProtocol) -> "EffectReleaseScope":
        document = _mapping(path.resolve())
        if set(document) != {"schema_version", "release_scope_sha256", "scope"}:
            raise AttributionError("M6 release scope document fields differ")
        if document.get("schema_version") != "m6-model-attribution-release-scope-v1":
            raise AttributionError("M6 release scope schema differs")
        scope = document.get("scope")
        if not isinstance(scope, dict):
            raise AttributionError("M6 release scope body is invalid")
        digest = canonical_sha256(scope)
        if document.get("release_scope_sha256") != digest:
            raise AttributionError("M6 release scope self hash differs")
        _validate_release_scope(scope, protocol)
        return cls(path=path.resolve(), document=document, scope=scope, sha256=digest)

    def verify_runtime_identity(self) -> dict[str, str]:
        implementation = self.scope["implementation"]
        actual = {
            "git_commit": git_head(),
            "code_snapshot_sha256": code_snapshot_sha256(),
        }
        expected = {
            "git_commit": implementation["git_commit"],
            "code_snapshot_sha256": implementation["code_snapshot_sha256"],
        }
        if actual != expected:
            raise AttributionError("M6 release runtime identity differs")
        if self.scope["image"]["git_commit"] != actual["git_commit"]:
            raise AttributionError("M6 runtime image Git identity differs")
        if self.scope["image"]["code_snapshot_sha256"] != actual["code_snapshot_sha256"]:
            raise AttributionError("M6 runtime image code identity differs")
        release_manifest = os.getenv("SHAIWEI_RELEASE_MANIFEST", "").strip()
        if not release_manifest:
            raise AttributionError("M6 runtime embedded release manifest is absent")
        if sha256_file(Path(release_manifest)) != self.scope["image"]["release_manifest_sha256"]:
            raise AttributionError("M6 runtime embedded release manifest hash differs")
        return actual


@dataclass(frozen=True)
class EffectApproval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: EffectReleaseScope) -> "EffectApproval":
        document = _mapping(path.resolve())
        expected = {
            "schema_version": "m6-model-attribution-approval-v1",
            "release_scope_sha256": release.sha256,
            "action": APPROVAL_ACTION,
            "real_qlib_feature_or_price_read_authorized": True,
            "real_label_or_effect_read_authorized": True,
            "real_model_fit_authorized": True,
            "real_prediction_authorized": True,
            "real_backtest_authorized": True,
            "formal_effect_output_write_authorized": True,
            "independent_audit_authorized": True,
            "experiment_ledger_write_authorized": False,
            "external_network_authorized": False,
            "env_or_secret_read_authorized": False,
            "production_authorization": "none",
        }
        if set(document) != set(expected) | {"approved_at", "consumed"}:
            raise AttributionError("M6 approval fields differ from the exact authority")
        if any(document.get(key) != value for key, value in expected.items()):
            raise AttributionError("M6 approval does not match the exact release authority")
        if not isinstance(document.get("approved_at"), str) or not document["approved_at"]:
            raise AttributionError("M6 approval time is absent")
        if document.get("consumed") is not False:
            raise AttributionError("M6 approval is already consumed or malformed")
        return cls(path=path.resolve(), document=document, sha256=sha256_file(path.resolve()))
