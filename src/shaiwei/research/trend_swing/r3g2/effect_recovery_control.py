"""Result-blind controls for the R3G-2 effect entrypoint recovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping, TypeVar

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error, sha256_file
from shaiwei.research.trend_swing.r3g2.effect_control import (
    AUDITOR_COMMAND,
    RUNNER_COMMAND,
    _mapping,
    canonical_sha256,
    expected_scope_authority,
)


RECOVERY_PROTOCOL_PATH = (
    PROJECT_ROOT / "config/ts_v5_r3g2_effect_entrypoint_recovery_v1.yaml"
)
RECOVERY_SCOPE_KIND = "REAL_EFFECT_ENTRYPOINT_RECOVERY_READY_NOT_EXECUTION_APPROVAL"
RECOVERY_ACTION = (
    "TS_R3G2_BREAKOUT_RETEST_EFFECT_ENTRYPOINT_RECOVERY_ONCE_WITH_"
    "DISCOVERY_FIREWALL_REPLAY_AND_INDEPENDENT_AUDIT"
)
RECOVERY_SCOPE_SCHEMA = "ts-v5-r3g2-effect-entrypoint-recovery-scope-v1"
RECOVERY_APPROVAL_SCHEMA = (
    "ts-v5-r3g2-effect-entrypoint-recovery-explicit-approval-v1"
)
RECOVERY_COMPOSE = "compose.ts-v5-r3g2-effect-recovery.yaml"
RECOVERY_IMAGE = "shaiwei:ts-v5-r3g2-effect-entrypoint-recovery-v1"
RECOVERY_EFFECT_ROOT = "data/research/trend_swing/ts-v5-r3g2-effect-entrypoint-recovery-v1"
RECOVERY_AUDIT_ROOT = (
    "data/research/trend_swing/ts-v5-r3g2-effect-entrypoint-recovery-v1-audit"
)
RECOVERY_APPROVAL_PATH = (
    "data/control/ts-v5-r3g2-effect-entrypoint-recovery-v1/approval.json"
)
RECOVERY_SCOPE_PATH = "config/ts_v5_r3g2_effect_entrypoint_recovery_scope_v1.json"


_Release = TypeVar("_Release")


@dataclass(frozen=True)
class RecoveryProtocol:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, protocol: EffectProtocol) -> "RecoveryProtocol":
        document = _mapping(RECOVERY_PROTOCOL_PATH)
        predecessor = document.get("predecessor", {})
        original = predecessor.get("original_release", {})
        failure = predecessor.get("failure_receipt", {})
        if (
            document.get("schema_version")
            != "ts-v5-r3g2-effect-entrypoint-recovery-protocol-v1"
            or document.get("status") != "RESULT_BLIND_ENTRYPOINT_RECOVERY_ONLY"
            or document.get("production_authorization") != "none"
            or predecessor.get("effect_protocol", {}).get("sha256") != protocol.sha256
            or original.get("scope_sha256")
            != "961b62f288f61a6ae19f88ef04c0697f93f27bf52390ddb48b7c49064e19db75"
            or original.get("runner_invocation_consumed") is not True
            or original.get("same_scope_retry_authorized") is not False
            or failure.get("frozen_facts", {}).get("effect_read_started") is not False
            or failure.get("frozen_facts", {}).get("strategy_effect_attempt_count") != 0
            or document.get("release", {}).get("approval_action") != RECOVERY_ACTION
            or document.get("execution", {}).get(
                "effect_attempts_consumed_at_first_recovery_value_read"
            ) != 3
        ):
            raise R3G2Error("R3G-2 effect recovery protocol identity differs")
        return cls(document=document, sha256=sha256_file(RECOVERY_PROTOCOL_PATH))


def expected_recovery_approval(scope_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": RECOVERY_APPROVAL_SCHEMA,
        "release_scope_sha256": scope_sha256,
        "action": RECOVERY_ACTION,
        "approved": True,
        "real_event_score_value_or_rank_read": True,
        "real_post_entry_price_or_benchmark_value_read": True,
        "strategy_effect_or_backtest": True,
        "strategy_effect_attempt_count": 3,
        "discovery_first_holdout_firewall": True,
        "complete_internal_passes": ["first_pass", "replay"],
        "independent_audit": True,
        "same_release_retry_authorized": False,
        "original_release_retry_authorized": False,
        "experiment_ledger_write": False,
        "external_network": False,
        "env_or_secret_read": False,
        "paper_web_scheduler_or_production_change": False,
        "production_authorization": "none",
    }


def _source_mounts() -> list[dict[str, str]]:
    sources = [
        ("data/raw", "/workspace/data/raw"),
        ("data/research/trend_swing/ts-v3-data-gate-r3", "/workspace/data/research/trend_swing/ts-v3-data-gate-r3"),
        ("data/research/trend_swing/ts-v5-r3g-executable-semantics", "/workspace/data/research/trend_swing/ts-v5-r3g-executable-semantics"),
        ("data/research/trend_swing/ts-v5-r3f-canary-001", "/workspace/data/research/trend_swing/ts-v5-r3f-canary-001"),
        ("ledger/ts_v5_r3f_llm_attempts.csv", "/workspace/ledger/ts_v5_r3f_llm_attempts.csv"),
        ("ledger/ts_v5_r3f_llm_transports.csv", "/workspace/ledger/ts_v5_r3f_llm_transports.csv"),
        ("data/research/trend_swing/ts-v5-r3g1-recent-density-r2", "/workspace/data/research/trend_swing/ts-v5-r3g1-recent-density-r2"),
        ("data/research/trend_swing/ts-v5-r3g2-benchmark-lineage-v1", "/workspace/data/research/trend_swing/ts-v5-r3g2-benchmark-lineage-v1"),
        ("data/research/m6_csi800_model_attribution_v1/effect/first_pass", "/workspace/data/research/m6_csi800_model_attribution_v1/effect/first_pass"),
        ("data/research/trend_swing/ts-v5-r3g2-w7-lineage-recovery", "/workspace/data/research/trend_swing/ts-v5-r3g2-w7-lineage-recovery"),
        ("data/research/trend_swing/ts-v5-r3g2-w7-lineage-recovery-audit", "/workspace/data/research/trend_swing/ts-v5-r3g2-w7-lineage-recovery-audit"),
    ]
    return [
        {"source": source, "target": target, "access": "read_only"}
        for source, target in sources
    ]


def recovery_mounts() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    runner = _source_mounts()
    runner.extend(
        [
            {"source": RECOVERY_SCOPE_PATH, "target": "/inputs/release.json", "access": "read_only"},
            {"source": RECOVERY_APPROVAL_PATH, "target": "/inputs/approval.json", "access": "read_only"},
            {"source": RECOVERY_EFFECT_ROOT, "target": "/outputs", "access": "read_write"},
        ]
    )
    auditor = [
        {"source": RECOVERY_SCOPE_PATH, "target": "/inputs/release.json", "access": "read_only"},
        {"source": RECOVERY_APPROVAL_PATH, "target": "/inputs/approval.json", "access": "read_only"},
        {"source": RECOVERY_EFFECT_ROOT, "target": "/outputs", "access": "read_only"},
        {"source": RECOVERY_AUDIT_ROOT, "target": "/audit", "access": "read_write"},
    ]
    return runner, auditor


def predecessor_record(protocol: RecoveryProtocol) -> dict[str, Any]:
    predecessor = protocol.document["predecessor"]
    return {
        "original_release_scope_sha256": predecessor["original_release"]["scope_sha256"],
        "original_release_document_sha256": predecessor["original_release"]["document_sha256"],
        "original_approval_sha256": predecessor["original_approval"]["sha256"],
        "failure_receipt_sha256": predecessor["failure_receipt"]["sha256"],
        "original_effect_files": predecessor["preserved_original_outputs"]["expected_files"],
        "original_audit_file_count": predecessor["preserved_original_outputs"][
            "expected_audit_file_count"
        ],
        **predecessor["failure_receipt"]["frozen_facts"],
    }


def validate_recovery_scope(
    scope: Mapping[str, Any], protocol: EffectProtocol, recovery: RecoveryProtocol
) -> None:
    execution = scope.get("execution", {})
    if (
        scope.get("scope_kind") != RECOVERY_SCOPE_KIND
        or scope.get("effect_protocol_sha256") != protocol.sha256
        or scope.get("release_protocol_sha256") != recovery.sha256
        or scope.get("predecessor_failure") != predecessor_record(recovery)
        or scope.get("authority") != expected_scope_authority()
        or execution.get("approval_action") != RECOVERY_ACTION
        or execution.get("strategy_effect_attempt_count") != 3
        or execution.get("same_release_retry_authorized") is not False
        or execution.get("original_release_retry_authorized") is not False
    ):
        raise R3G2Error("R3G-2 effect recovery scope authority differs")
    container, outputs = scope.get("container", {}), scope.get("outputs", {})
    implementation, image = scope.get("implementation", {}), scope.get("image", {})
    runner_mounts, auditor_mounts = recovery_mounts()
    expected_runner = {
        "service": "ts-v5-r3g2-effect-recovery-runner",
        "command": RUNNER_COMMAND,
        "mounts": runner_mounts,
        "cpus": 6,
        "memory": "14g",
        "pids_limit": 256,
    }
    expected_auditor = {
        "service": "ts-v5-r3g2-effect-recovery-auditor",
        "command": AUDITOR_COMMAND,
        "mounts": auditor_mounts,
        "cpus": 2,
        "memory": "4g",
        "pids_limit": 256,
    }
    if (
        container.get("compose_path") != RECOVERY_COMPOSE
        or container.get("compose_sha256")
        != sha256_file(PROJECT_ROOT / RECOVERY_COMPOSE)
        or container.get("network_mode") != "none"
        or container.get("read_only_root") is not True
        or container.get("run_as_non_root") is not True
        or container.get("cap_drop_all") is not True
        or container.get("no_new_privileges") is not True
        or container.get("env_file_mounted") is not False
        or container.get("docker_socket_mounted") is not False
        or container.get("production_ledger_mounted") is not False
        or container.get("full_project_root_mounted") is not False
        or container.get("frozen_research_lineage_ledgers_mounted") is not True
        or container.get("runner") != expected_runner
        or container.get("auditor") != expected_auditor
        or image.get("reference") != RECOVERY_IMAGE
        or image.get("git_commit") != implementation.get("git_commit")
        or outputs.get("effect_root") != RECOVERY_EFFECT_ROOT
        or outputs.get("audit_root") != RECOVERY_AUDIT_ROOT
        or outputs.get("empty_at_scope_freeze") is not True
        or outputs.get("approval_file_exists_at_scope_freeze") is not False
    ):
        raise R3G2Error("R3G-2 effect recovery container boundary differs")
    hashes = (
        implementation.get("code_snapshot_sha256"),
        image.get("release_manifest_sha256"),
        scope.get("inputs", {}).get("pre_effect_preflight_sha256"),
    )
    inputs = scope.get("inputs", {})
    if (
        inputs.get("bound_input_hashes") != protocol.bound_input_contract()
        or inputs.get("w7_recovery_manifest_sha256")
        != "fe7b7aeedc9d0d63d44ff56ad17046ff61290f81ca7f99e93888994bddf1579f"
    ):
        raise R3G2Error("R3G-2 effect recovery inputs differ")
    commits = (
        implementation.get("git_commit"),
        implementation.get("origin_main_commit"),
        image.get("git_commit"),
    )
    if any(re.fullmatch(r"[0-9a-f]{64}", str(value)) is None for value in hashes) or any(
        re.fullmatch(r"[0-9a-f]{40}", str(value)) is None for value in commits
    ):
        raise R3G2Error("R3G-2 effect recovery identity format differs")


def load_recovery_release(
    path: Path, protocol: EffectProtocol, release_type: type[_Release]
) -> _Release:
    document = _mapping(path)
    if document.get("schema_version") != RECOVERY_SCOPE_SCHEMA:
        raise R3G2Error("R3G-2 effect recovery scope schema differs")
    scope = document.get("scope")
    if not isinstance(scope, dict):
        raise R3G2Error("R3G-2 effect recovery scope payload is missing")
    digest = canonical_sha256(scope)
    if document.get("release_scope_sha256") != digest:
        raise R3G2Error("R3G-2 effect recovery scope self-hash differs")
    validate_recovery_scope(scope, protocol, RecoveryProtocol.load(protocol))
    return release_type(document, scope, digest)
