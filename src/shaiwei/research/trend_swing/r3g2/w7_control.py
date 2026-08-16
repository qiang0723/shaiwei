"""Release and explicit-approval contracts for the one-shot W7 lineage run."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.model_attribution.contract import ProtocolBundle
from shaiwei.research.trend_swing.contract import canonical_sha256
from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error, sha256_file


ACTION = "TS_R3G2_W7_SCORE_LINEAGE_ONCE_WITH_REPLAY_AND_INDEPENDENT_AUDIT"
SCOPE_KIND = "W7_LINEAGE_RELEASE_READY_NOT_EXECUTION_APPROVAL"
RELEASE_PROTOCOL_PATH = PROJECT_ROOT / "config/ts_v5_r3g2_w7_release_v1.yaml"
RUNNER_COMMAND = [
    "python", "-m", "shaiwei.research.trend_swing.r3g2.w7_run",
    "--release", "/inputs/release.json", "--approval", "/inputs/approval.json",
    "--provider-root", "/qlib", "--output-root", "/outputs",
]
AUDITOR_COMMAND = [
    "python", "-m", "shaiwei.research.trend_swing.r3g2.w7_audit_run",
    "--release", "/inputs/release.json", "--approval", "/inputs/approval.json",
    "--lineage-root", "/outputs", "--audit-root", "/audit",
]


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise R3G2Error(f"R3G-2 W7 control document is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise R3G2Error(f"R3G-2 W7 control document is not a mapping: {path.name}")
    return value


def load_release_protocol(protocol: EffectProtocol) -> tuple[dict[str, Any], str]:
    try:
        document = yaml.safe_load(RELEASE_PROTOCOL_PATH.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise R3G2Error("R3G-2 W7 release protocol is invalid") from error
    if not isinstance(document, dict):
        raise R3G2Error("R3G-2 W7 release protocol is not a mapping")
    if (
        document.get("schema_version") != "ts-v5-r3g2-w7-release-protocol-v1"
        or document.get("status") != "RESULT_BLIND_W7_LINEAGE_RELEASE_PREPARATION_ONLY"
        or document.get("parent_effect_protocol", {}).get("sha256") != protocol.sha256
    ):
        raise R3G2Error("R3G-2 W7 release protocol binding differs")
    authority = document.get("authority_before_explicit_approval", {})
    enabled = {
        key for key, value in authority.items() if isinstance(value, bool) and value
    }
    if enabled != {"release_metadata_and_synthetic_fixture"}:
        raise R3G2Error("R3G-2 W7 preapproval authority was broadened")
    return document, sha256_file(RELEASE_PROTOCOL_PATH)


def _expected_mounts(release_protocol: dict[str, Any], role: str) -> list[dict[str, str]]:
    return [dict(row) for row in release_protocol["docker"][role]["mounts"]]


def _validate_scope(
    scope: dict[str, Any], protocol: EffectProtocol, release_protocol: dict[str, Any]
) -> None:
    if scope.get("scope_kind") != SCOPE_KIND or scope.get("protocol_sha256") != protocol.sha256:
        raise R3G2Error("R3G-2 W7 release protocol binding differs")
    if scope.get("release_protocol_sha256") != sha256_file(RELEASE_PROTOCOL_PATH):
        raise R3G2Error("R3G-2 W7 release preparation hash differs")
    implementation, image = scope.get("implementation", {}), scope.get("image", {})
    commit = implementation.get("git_commit")
    snapshot = implementation.get("code_snapshot_sha256")
    if not isinstance(commit, str) or len(commit) != 40:
        raise R3G2Error("R3G-2 W7 implementation commit is invalid")
    if implementation.get("origin_main_commit") != commit:
        raise R3G2Error("R3G-2 W7 implementation is not bound to origin/main")
    if image.get("git_commit") != commit or image.get("code_snapshot_sha256") != snapshot:
        raise R3G2Error("R3G-2 W7 image identity differs")
    if not str(image.get("image_id", "")).startswith("sha256:"):
        raise R3G2Error("R3G-2 W7 image content identity is invalid")
    if image.get("reference") != release_protocol["docker"]["image"]:
        raise R3G2Error("R3G-2 W7 image reference differs")
    expected_inputs = {
        "qlib_manifest_sha256": "62cae2f46b57020db202bee1748f072e7859e209663046747f76aaa008f605a9",
        "qlib_tree_sha256": "0532f6cd7c2c78f0936f92a986aef83a848175fe6f332274e06c7ed6e8c11778",
        "qlib_file_count": 54464,
        "calendar_sha256": "80ddefd8e3cce5137bb99f6b53dbe090de1b1bd234db1a19f31ef3ddb2bd8bdb",
        "calendar_row_count": 2557,
    }
    if scope.get("inputs") != expected_inputs:
        raise R3G2Error("R3G-2 W7 provider identity differs")
    if scope.get("execution") != {
        "approval_action": ACTION,
        "runner_invocation_count": 1,
        "complete_internal_passes": ["first_pass", "replay"],
        "independent_auditor_invocation_count": 1,
        "strategy_effect_attempt_count": 0,
        "same_release_retry_authorized": False,
    }:
        raise R3G2Error("R3G-2 W7 execution boundary differs")
    authority = scope.get("authority", {})
    if authority != {
        "w7_training_and_prediction_after_explicit_approval": True,
        "label_rankic_return_or_effect_read": False,
        "external_network": False,
        "env_or_secret_read": False,
        "experiment_ledger_write": False,
        "paper_web_scheduler_or_production_change": False,
        "production_authorization": "none",
    }:
        raise R3G2Error("R3G-2 W7 release authority differs")
    docker = release_protocol["docker"]
    container = scope.get("container", {})
    common = {
        "compose_path": docker["compose_file"],
        "compose_sha256": sha256_file(PROJECT_ROOT / docker["compose_file"]),
        "network_mode": "none",
        "read_only_root": True,
        "run_as_non_root": True,
        "env_file_mounted": False,
        "docker_socket_mounted": False,
        "full_project_root_mounted": False,
        "production_ledger_mounted": False,
    }
    if any(container.get(key) != value for key, value in common.items()):
        raise R3G2Error("R3G-2 W7 container boundary differs")
    runner, auditor = container.get("runner", {}), container.get("auditor", {})
    if runner != {
        "service": docker["runner"]["service"],
        "command": RUNNER_COMMAND,
        "mounts": _expected_mounts(release_protocol, "runner"),
        "cpus": 6,
        "memory": "12g",
        "pids_limit": 256,
    }:
        raise R3G2Error("R3G-2 W7 runner boundary differs")
    if auditor != {
        "service": docker["auditor"]["service"],
        "command": AUDITOR_COMMAND,
        "mounts": _expected_mounts(release_protocol, "auditor"),
        "cpus": 2,
        "memory": "4g",
        "pids_limit": 256,
    }:
        raise R3G2Error("R3G-2 W7 auditor boundary differs")
    if scope.get("outputs") != {
        "lineage_root": release_protocol["outputs"]["lineage_root"],
        "audit_root": release_protocol["outputs"]["audit_root"],
        "experiment_ledger_write_authorized": False,
    }:
        raise R3G2Error("R3G-2 W7 output boundary differs")


@dataclass(frozen=True)
class ReleaseScope:
    path: Path
    document: dict[str, Any]
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, protocol: EffectProtocol) -> "ReleaseScope":
        release_protocol, _release_protocol_sha = load_release_protocol(protocol)
        document = _json(path.resolve())
        if set(document) != {"schema_version", "release_scope_sha256", "scope"}:
            raise R3G2Error("R3G-2 W7 release fields differ")
        if document.get("schema_version") != "ts-v5-r3g2-w7-release-scope-v1":
            raise R3G2Error("R3G-2 W7 release schema differs")
        scope = document.get("scope")
        if not isinstance(scope, dict):
            raise R3G2Error("R3G-2 W7 release scope is absent")
        digest = canonical_sha256(scope)
        if document.get("release_scope_sha256") != digest:
            raise R3G2Error("R3G-2 W7 release scope hash differs")
        _validate_scope(scope, protocol, release_protocol)
        return cls(path=path.resolve(), document=document, scope=scope, sha256=digest)

    def verify_runtime_identity(self) -> dict[str, str]:
        observed = {"git_commit": git_head(), "code_snapshot_sha256": code_snapshot_sha256()}
        expected = self.scope["implementation"]
        if observed != {
            "git_commit": expected["git_commit"],
            "code_snapshot_sha256": expected["code_snapshot_sha256"],
        }:
            raise R3G2Error("R3G-2 W7 runtime identity differs")
        return observed

    def verify_provider(self, root: Path) -> dict[str, Any]:
        metadata = ProtocolBundle.load().verify_metadata_inputs(
            root / "_shaiwei_manifest.json", root / "calendars/day.txt"
        )
        observed = {
            "qlib_manifest_sha256": metadata["qlib_manifest_sha256"],
            "qlib_tree_sha256": metadata["qlib_tree_sha256"],
            "qlib_file_count": metadata["qlib_file_count"],
            "calendar_sha256": sha256_file(root / "calendars/day.txt"),
            "calendar_row_count": metadata["calendar_row_count"],
        }
        if observed != self.scope["inputs"]:
            raise R3G2Error("R3G-2 W7 runtime provider differs")
        return observed


@dataclass(frozen=True)
class Approval:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: ReleaseScope) -> "Approval":
        document = _json(path.resolve())
        if document != {
            "schema_version": "ts-v5-r3g2-w7-explicit-approval-v1",
            "release_scope_sha256": release.sha256,
            "action": ACTION,
            "approved": True,
        }:
            raise R3G2Error("R3G-2 W7 explicit approval differs")
        return cls(path=path.resolve(), document=document, sha256=sha256_file(path.resolve()))
