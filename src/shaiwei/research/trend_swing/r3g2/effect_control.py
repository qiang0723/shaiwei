"""Exact release, approval, and runtime identity controls for R3G-2 effect."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error, sha256_file
from shaiwei.research.trend_swing.r3g2.evidence import canonical_json


RELEASE_PROTOCOL_PATH = PROJECT_ROOT / "config/ts_v5_r3g2_effect_release_v1.yaml"
SCOPE_KIND = "REAL_EFFECT_RELEASE_READY_NOT_EXECUTION_APPROVAL"
ACTION = (
    "TS_R3G2_BREAKOUT_RETEST_EFFECT_ONCE_WITH_DISCOVERY_FIREWALL_"
    "REPLAY_AND_INDEPENDENT_AUDIT"
)
RUNNER_COMMAND = [
    "python", "-m", "shaiwei.research.trend_swing.r3g2.effect_run",
    "--release", "/inputs/release.json", "--approval", "/inputs/approval.json",
    "--output-root", "/outputs", "--temporary-root", "/tmp/r3g2",
]
AUDITOR_COMMAND = [
    "python", "-m", "shaiwei.research.trend_swing.r3g2.effect_audit",
    "--release", "/inputs/release.json", "--approval", "/inputs/approval.json",
    "--effect-root", "/outputs", "--audit-root", "/audit",
]


def canonical_sha256(value: Any) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(value)).hexdigest()


def _mapping(path: Path) -> dict[str, Any]:
    try:
        if path.suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
        else:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as error:
        raise R3G2Error(f"R3G-2 control document is invalid: {path.name}") from error
    if not isinstance(value, dict):
        raise R3G2Error(f"R3G-2 control document is not a mapping: {path.name}")
    return value


@dataclass(frozen=True)
class ReleaseProtocol:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls) -> "ReleaseProtocol":
        document = _mapping(RELEASE_PROTOCOL_PATH)
        if (
            document.get("schema_version") != "ts-v5-r3g2-effect-release-protocol-v1"
            or document.get("status")
            != "RESULT_BLIND_EFFECT_ENGINEERING_AND_RELEASE_PREPARATION_ONLY"
            or document.get("production_authorization") != "none"
            or document.get("release", {}).get("approval_action") != ACTION
        ):
            raise R3G2Error("R3G-2 release protocol identity differs")
        for row in document["predecessors"].values():
            if not isinstance(row, dict) or not {"path", "sha256"} <= set(row):
                continue
            path = PROJECT_ROOT / row["path"]
            if not path.is_file() or sha256_file(path) != row["sha256"]:
                raise R3G2Error(f"R3G-2 release predecessor differs: {path.name}")
        return cls(document, sha256_file(RELEASE_PROTOCOL_PATH))


def expected_scope_authority() -> dict[str, Any]:
    return {
        "release_ready": True,
        "execution_authorized": False,
        "real_event_score_value_or_rank_read": False,
        "real_post_entry_price_or_benchmark_value_read": False,
        "strategy_effect_or_backtest": False,
        "experiment_ledger_write": False,
        "external_network": False,
        "env_or_secret_read": False,
        "paper_web_scheduler_or_production_change": False,
        "production_authorization": "none",
    }


def _validate_scope(scope: Mapping[str, Any], protocol: EffectProtocol, release: ReleaseProtocol) -> None:
    if (
        scope.get("scope_kind") != SCOPE_KIND
        or scope.get("effect_protocol_sha256") != protocol.sha256
        or scope.get("release_protocol_sha256") != release.sha256
        or scope.get("authority") != expected_scope_authority()
        or scope.get("execution", {}).get("approval_action") != ACTION
        or scope.get("execution", {}).get("strategy_effect_attempt_count") != 3
        or scope.get("execution", {}).get("same_release_retry_authorized") is not False
    ):
        raise R3G2Error("R3G-2 release scope authority differs")
    container = scope.get("container", {})
    implementation, image = scope.get("implementation", {}), scope.get("image", {})
    outputs = scope.get("outputs", {})
    if (
        container.get("network_mode") != "none"
        or container.get("read_only_root") is not True
        or container.get("env_file_mounted") is not False
        or container.get("docker_socket_mounted") is not False
        or container.get("production_ledger_mounted") is not False
        or container.get("full_project_root_mounted") is not False
        or container.get("runner", {}).get("command") != RUNNER_COMMAND
        or container.get("auditor", {}).get("command") != AUDITOR_COMMAND
        or image.get("reference") != release.document["docker"]["image"]
        or image.get("git_commit") != implementation.get("git_commit")
        or outputs.get("effect_root")
        != "data/research/trend_swing/ts-v5-r3g2-effect-v1"
        or outputs.get("audit_root")
        != "data/research/trend_swing/ts-v5-r3g2-effect-v1-audit"
        or outputs.get("empty_at_scope_freeze") is not True
        or outputs.get("approval_file_exists_at_scope_freeze") is not False
    ):
        raise R3G2Error("R3G-2 release container boundary differs")
    hashes = (
        implementation.get("code_snapshot_sha256"),
        image.get("release_manifest_sha256"),
        scope.get("inputs", {}).get("pre_effect_preflight_sha256"),
    )
    commits = (
        implementation.get("git_commit"), implementation.get("origin_main_commit"),
        image.get("git_commit"),
    )
    if any(re.fullmatch(r"[0-9a-f]{64}", str(value)) is None for value in hashes) or any(
        re.fullmatch(r"[0-9a-f]{40}", str(value)) is None for value in commits
    ):
        raise R3G2Error("R3G-2 release identity format differs")


@dataclass(frozen=True)
class EffectReleaseScope:
    document: dict[str, Any]
    scope: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, protocol: EffectProtocol) -> "EffectReleaseScope":
        document = _mapping(path)
        if document.get("schema_version") != "ts-v5-r3g2-effect-release-scope-v1":
            raise R3G2Error("R3G-2 release scope schema differs")
        scope = document.get("scope")
        if not isinstance(scope, dict):
            raise R3G2Error("R3G-2 release scope payload is missing")
        digest = canonical_sha256(scope)
        if document.get("release_scope_sha256") != digest:
            raise R3G2Error("R3G-2 release scope self-hash differs")
        release = ReleaseProtocol.load()
        _validate_scope(scope, protocol, release)
        return cls(document, scope, digest)

    def verify_runtime(self) -> dict[str, str]:
        embedded = os.getenv("SHAIWEI_RELEASE_GIT_HEAD", "").strip().lower()
        implementation = self.scope["implementation"]
        manifest_path = os.getenv("SHAIWEI_RELEASE_MANIFEST", "").strip()
        if (
            re.fullmatch(r"[0-9a-f]{40}", embedded) is None
            or git_head() != embedded
            or embedded != implementation["git_commit"]
            or code_snapshot_sha256() != implementation["code_snapshot_sha256"]
            or not manifest_path
            or sha256_file(Path(manifest_path)) != self.scope["image"]["release_manifest_sha256"]
        ):
            raise R3G2Error("R3G-2 runtime code identity differs")
        return {
            "git_commit": embedded,
            "code_snapshot_sha256": implementation["code_snapshot_sha256"],
        }


def expected_approval(scope_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": "ts-v5-r3g2-effect-explicit-approval-v1",
        "release_scope_sha256": scope_sha256,
        "action": ACTION,
        "approved": True,
        "real_event_score_value_or_rank_read": True,
        "real_post_entry_price_or_benchmark_value_read": True,
        "strategy_effect_or_backtest": True,
        "strategy_effect_attempt_count": 3,
        "discovery_first_holdout_firewall": True,
        "complete_internal_passes": ["first_pass", "replay"],
        "independent_audit": True,
        "same_release_retry_authorized": False,
        "experiment_ledger_write": False,
        "external_network": False,
        "env_or_secret_read": False,
        "paper_web_scheduler_or_production_change": False,
        "production_authorization": "none",
    }


@dataclass(frozen=True)
class EffectApproval:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path, release: EffectReleaseScope) -> "EffectApproval":
        document = _mapping(path)
        if document != expected_approval(release.sha256):
            raise R3G2Error("R3G-2 explicit approval differs from the exact release scope")
        return cls(document, sha256_file(path))
