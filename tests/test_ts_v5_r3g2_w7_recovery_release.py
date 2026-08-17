from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from shaiwei.provenance import CONTROLLED_FILES
from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error
from shaiwei.research.trend_swing.r3g2.w7_control import (
    Approval,
    RECOVERY_ACTION,
    RECOVERY_PROTOCOL_PATH,
    RECOVERY_SCOPE_KIND,
    ReleaseScope,
    load_recovery_protocol,
    recovery_predecessor_record,
)
from shaiwei.research.trend_swing.r3g2.w7_release import build_release_document


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / "compose.ts-v5-r3g2-w7-recovery.yaml"
ORIGINAL_SCOPE = ROOT / "config/ts_v5_r3g2_w7_release_scope_v1.json"
COMMIT = "a" * 40
SNAPSHOT = "b" * 64


def _document() -> dict[str, object]:
    protocol = EffectProtocol.load()
    recovery, recovery_sha = load_recovery_protocol(protocol)
    return build_release_document(
        protocol=protocol,
        release_protocol=recovery,
        release_protocol_sha256=recovery_sha,
        created_at="2026-08-17T00:00:00+00:00",
        implementation_git_commit=COMMIT,
        origin_main_commit=COMMIT,
        code_snapshot=SNAPSHOT,
        image_id=f"sha256:{'c' * 64}",
        image_platform="linux/arm64",
        image_git_commit=COMMIT,
        image_release_manifest_sha256="d" * 64,
        image_release_manifest_file_count=1,
        inputs=recovery["frozen_provider"],
        document_schema="ts-v5-r3g2-w7-entrypoint-recovery-scope-v1",
        scope_kind=RECOVERY_SCOPE_KIND,
        action=RECOVERY_ACTION,
        release_protocol_path=RECOVERY_PROTOCOL_PATH,
        predecessor_failure=recovery_predecessor_record(recovery),
    )


def test_recovery_protocol_is_result_blind_and_binds_consumed_scope() -> None:
    protocol = EffectProtocol.load()
    recovery, digest = load_recovery_protocol(protocol)
    predecessor = recovery["predecessor"]

    assert len(digest) == 64
    assert recovery["status"] == "RESULT_BLIND_W7_ENTRYPOINT_RECOVERY_PREPARATION_ONLY"
    assert predecessor["original_release"]["scope_sha256"] == (
        "5d2389429aa4ba272371d60214fd04866405372f61b7d3933db67e8a7b7838ad"
    )
    assert predecessor["failure_receipt"]["frozen_facts"]["runner_invocation_count"] == 1
    assert predecessor["failure_receipt"]["frozen_facts"]["real_qlib_read_started"] is False
    assert recovery["execution_after_exact_approval"]["strategy_effect_attempt_count"] == 0
    assert recovery["execution_after_exact_approval"]["original_release_retry_authorized"] is False


def test_recovery_compose_is_offline_minimal_and_auditor_has_no_qlib() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    serialized = COMPOSE.read_text(encoding="utf-8")
    services = document["services"]

    assert "env_file" not in serialized
    assert ".env" not in serialized
    assert "docker.sock" not in serialized
    assert "ledger/" not in serialized
    for service in services.values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert service["restart"] == "no"
    assert "volumes" not in services["ts-v5-r3g2-w7-recovery-fixture"]
    auditor = services["ts-v5-r3g2-w7-recovery-auditor"]
    assert all(volume["target"] != "/qlib" for volume in auditor["volumes"])
    runner_targets = {
        volume["target"]
        for volume in services["ts-v5-r3g2-w7-recovery-runner"]["volumes"]
    }
    assert runner_targets == {"/qlib", "/inputs/release.json", "/inputs/approval.json", "/outputs"}


def test_recovery_compose_is_a_controlled_image_input() -> None:
    assert COMPOSE.name in CONTROLLED_FILES
    assert COMPOSE.name in (ROOT / "Dockerfile").read_text(encoding="utf-8")


def test_recovery_scope_and_approval_are_distinct_from_original(tmp_path: Path) -> None:
    document = _document()
    release_path = tmp_path / "release.json"
    release_path.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")
    release = ReleaseScope.load(release_path, EffectProtocol.load())

    assert release.scope["execution"]["approval_action"] == RECOVERY_ACTION
    assert release.scope["predecessor_failure"]["runner_invocation_count"] == 1
    assert release.scope["predecessor_failure"]["original_lineage_file_count"] == 0
    approval_path = tmp_path / "approval.json"
    approval = {
        "schema_version": "ts-v5-r3g2-w7-entrypoint-recovery-explicit-approval-v1",
        "release_scope_sha256": release.sha256,
        "action": RECOVERY_ACTION,
        "approved": True,
    }
    approval_path.write_text(json.dumps(approval, sort_keys=True) + "\n", encoding="utf-8")
    assert Approval.load(approval_path, release).document == approval

    approval["schema_version"] = "ts-v5-r3g2-w7-explicit-approval-v1"
    approval_path.write_text(json.dumps(approval, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(R3G2Error, match="explicit approval differs"):
        Approval.load(approval_path, release)


def test_original_scope_remains_loadable_and_is_not_rewritten() -> None:
    release = ReleaseScope.load(ORIGINAL_SCOPE, EffectProtocol.load())

    assert release.sha256 == "5d2389429aa4ba272371d60214fd04866405372f61b7d3933db67e8a7b7838ad"
    assert release.scope["execution"]["approval_action"] != RECOVERY_ACTION


def test_recovery_builder_rejects_a_changed_predecessor() -> None:
    protocol = EffectProtocol.load()
    recovery, recovery_sha = load_recovery_protocol(protocol)
    predecessor = recovery_predecessor_record(recovery)
    predecessor["real_qlib_read_started"] = True

    with pytest.raises(R3G2Error, match="predecessor failure differs"):
        build_release_document(
            protocol=protocol,
            release_protocol=recovery,
            release_protocol_sha256=recovery_sha,
            created_at="2026-08-17T00:00:00+00:00",
            implementation_git_commit=COMMIT,
            origin_main_commit=COMMIT,
            code_snapshot=SNAPSHOT,
            image_id=f"sha256:{'c' * 64}",
            image_platform="linux/arm64",
            image_git_commit=COMMIT,
            image_release_manifest_sha256="d" * 64,
            image_release_manifest_file_count=1,
            inputs=recovery["frozen_provider"],
            document_schema="ts-v5-r3g2-w7-entrypoint-recovery-scope-v1",
            scope_kind=RECOVERY_SCOPE_KIND,
            action=RECOVERY_ACTION,
            release_protocol_path=RECOVERY_PROTOCOL_PATH,
            predecessor_failure=predecessor,
        )
