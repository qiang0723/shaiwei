from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.capital_feasibility import entrypoint_recovery_audit
from shaiwei.research.capital_feasibility import entrypoint_recovery_run
from shaiwei.research.capital_feasibility.entrypoint_recovery_contract import (
    ACTION,
    EntrypointRecoveryProtocol,
)
from shaiwei.research.capital_feasibility.entrypoint_recovery_fixture import build_fixture
from shaiwei.research.capital_feasibility import release_audit, release_run
from shaiwei.research.production_conversion.contract import ProtocolError


ROOT = PROJECT_ROOT


def _runner_args() -> list[str]:
    return [
        "--release", "/a/release", "--approval", "/a/approval",
        "--r2-root", "/a/r2", "--r7-audit", "/a/r7",
        "--raw-manifest", "/a/raw", "--project-root", "/a/project",
        "--output-root", "/a/output",
    ]


def _audit_args() -> list[str]:
    return [
        "--release", "/a/release", "--approval", "/a/approval",
        "--effect-root", "/a/effect", "--audit-root", "/a/audit",
    ]


@pytest.mark.parametrize("main", [release_run.main, entrypoint_recovery_run.main])
def test_runner_cli_explicitly_maps_public_names(main, capsys: pytest.CaptureFixture[str]) -> None:
    captured: dict[str, Path] = {}

    def executor(**kwargs: Path) -> dict[str, str]:
        captured.update(kwargs)
        return {"status": "PASS"}

    assert main(_runner_args(), executor=executor) == 0
    assert set(captured) == {
        "release_path", "approval_path", "r2_root", "r7_audit", "raw_manifest",
        "project_root", "output_root",
    }
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"


@pytest.mark.parametrize("main", [release_audit.main, entrypoint_recovery_audit.main])
def test_auditor_cli_explicitly_maps_public_names(main, capsys: pytest.CaptureFixture[str]) -> None:
    captured: dict[str, Path] = {}

    def auditor(**kwargs: Path) -> dict[str, str]:
        captured.update(kwargs)
        return {"status": "PASS"}

    assert main(_audit_args(), auditor=auditor) == 0
    assert set(captured) == {"release_path", "approval_path", "effect_root", "audit_root"}
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"


def test_protocol_closes_failed_scope_without_consuming_semantic_attempt() -> None:
    protocol = EntrypointRecoveryProtocol.load()
    ruling = protocol.document["failure_ruling"]
    assert ruling["failed_scope_permanently_closed"] is True
    assert ruling["new_semantic_attempts_consumed"] == 0
    assert ruling["family_attempts_before_future_authorized_run"] == 1
    assert ruling["total_family_attempts_after_future_authorized_run"] == 2
    assert protocol.document["release_and_approval"]["approval_action"] == ACTION


def test_failure_evidence_mutation_fails_closed(tmp_path: Path) -> None:
    protocol = yaml.safe_load(
        (ROOT / "config/m6_csi800_production_head30_500k_entrypoint_recovery_v1.yaml").read_text()
    )
    protocol["failure_ruling"]["failed_scope_permanently_closed"] = False
    path = tmp_path / "protocol.yaml"
    path.write_text(yaml.safe_dump(protocol), encoding="utf-8")
    with pytest.raises(ProtocolError, match="attempt ruling"):
        EntrypointRecoveryProtocol.load(path)


def test_daemon_fixture_covers_both_cli_mappings_and_domain_replay() -> None:
    evidence = build_fixture()
    assert evidence["status"] == "PASS"
    assert evidence["runner_cli_mapping_pass"] is True
    assert evidence["auditor_cli_mapping_pass"] is True
    assert evidence["internal_replay_pass"] is True
    assert evidence["independent_reconstruction_pass"] is True
    assert evidence["real_target_read"] is False


def test_recovery_compose_keeps_auditor_artifact_only() -> None:
    compose = yaml.safe_load(
        (ROOT / "compose.m6-head30-500k-entrypoint-recovery.yaml").read_text()
    )
    services = compose["services"]
    runner = services["m6-head30-500k-entrypoint-recovery-runner"]
    auditor = services["m6-head30-500k-entrypoint-recovery-auditor"]
    for service in services.values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert len(service["tmpfs"]) == 1
    runner_targets = {item["target"] for item in runner["volumes"]}
    auditor_targets = {item["target"] for item in auditor["volumes"]}
    assert "/workspace/data/raw" in runner_targets and "/inputs/r2" in runner_targets
    assert "/workspace/data/raw" not in auditor_targets and "/inputs/r2" not in auditor_targets
    assert "/outputs" in auditor_targets and "/audit" in auditor_targets


def test_recovery_modules_remain_bounded() -> None:
    root = ROOT / "src/shaiwei/research/capital_feasibility"
    names = [
        "entrypoint_recovery_contract.py", "entrypoint_recovery_run.py",
        "entrypoint_recovery_audit.py", "entrypoint_recovery_fixture.py",
        "entrypoint_recovery_builder.py", "release_run.py", "release_audit.py",
    ]
    for name in names:
        assert len((root / name).read_text().splitlines()) <= 400, name
