from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from shaiwei.provenance import CONTROLLED_FILES, code_snapshot_sha256, git_head, write_release_manifest
from shaiwei.research.trend_swing.r3g2.contract import EffectProtocol, R3G2Error
from shaiwei.research.trend_swing.r3g2.effect_audit import audit
from shaiwei.research.trend_swing.r3g2.effect_authority import load_effect_authority
from shaiwei.research.trend_swing.r3g2.effect_fixture import SyntheticAdapter
from shaiwei.research.trend_swing.r3g2.effect_recovery_control import (
    RECOVERY_ACTION,
    RECOVERY_APPROVAL_PATH,
    RECOVERY_AUDIT_ROOT,
    RECOVERY_COMPOSE,
    RECOVERY_EFFECT_ROOT,
    RECOVERY_SCOPE_PATH,
    RecoveryProtocol,
    expected_recovery_approval,
    predecessor_record,
    recovery_mounts,
)
from shaiwei.research.trend_swing.r3g2.effect_recovery_release import (
    build_release_document,
    verify_predecessor_evidence,
)
from shaiwei.research.trend_swing.r3g2.effect_run import run


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / RECOVERY_COMPOSE


def _document(tmp_path: Path) -> tuple[dict, Path, SyntheticAdapter]:
    protocol, recovery = EffectProtocol.load(), RecoveryProtocol.load(EffectProtocol.load())
    adapter = SyntheticAdapter(protocol, tmp_path / "temporary")
    manifest = tmp_path / "release-manifest.json"
    write_release_manifest(manifest, root=ROOT)
    inputs = {
        "pre_effect_preflight_sha256": hashlib.sha256(
            json.dumps(
                adapter.preflight(), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest(),
        "bound_input_hashes": protocol.bound_input_contract(),
        "w7_recovery_manifest_sha256": (
            "fe7b7aeedc9d0d63d44ff56ad17046ff61290f81ca7f99e93888994bddf1579f"
        ),
    }
    document = build_release_document(
        protocol=protocol,
        recovery=recovery,
        predecessor=predecessor_record(recovery),
        inputs=inputs,
        created_at="2026-08-17T12:00:00+00:00",
        implementation_git_commit=git_head(),
        origin_main_commit=git_head(),
        code_snapshot=code_snapshot_sha256(),
        image_id="sha256:" + "a" * 64,
        image_platform="linux/arm64",
        image_git_commit=git_head(),
        image_release_manifest_path=manifest,
    )
    return document, manifest, adapter


def _control(tmp_path: Path) -> tuple[Path, Path, Path, SyntheticAdapter]:
    document, manifest, adapter = _document(tmp_path)
    release_path = tmp_path / "release.json"
    release_path.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(
        json.dumps(
            expected_recovery_approval(document["release_scope_sha256"]), sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    return release_path, approval_path, manifest, adapter


def test_recovery_binds_failure_and_original_scope_remains_consumed() -> None:
    protocol, recovery = EffectProtocol.load(), RecoveryProtocol.load(EffectProtocol.load())
    original_approval = ROOT / recovery.document["predecessor"]["original_approval"]["path"]
    if not original_approval.is_file():
        pytest.skip("host-only predecessor evidence is intentionally absent from clean image")
    predecessor = verify_predecessor_evidence(protocol, recovery)

    assert predecessor["original_release_scope_sha256"] == (
        "961b62f288f61a6ae19f88ef04c0697f93f27bf52390ddb48b7c49064e19db75"
    )
    assert predecessor["effect_read_started"] is False
    assert predecessor["strategy_effect_attempt_count"] == 0
    assert predecessor["original_effect_files"] == ["failure.json"]
    assert predecessor["original_audit_file_count"] == 0


def test_recovery_scope_requires_distinct_exact_approval(tmp_path: Path) -> None:
    document, _, _ = _document(tmp_path)
    release_path = tmp_path / "release.json"
    release_path.write_text(json.dumps(document), encoding="utf-8")
    approval_path = tmp_path / "approval.json"
    approval = expected_recovery_approval(document["release_scope_sha256"])
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    release, loaded = load_effect_authority(
        release_path, approval_path, EffectProtocol.load()
    )
    assert release.scope["execution"]["approval_action"] == RECOVERY_ACTION
    assert loaded.document == approval

    approval["schema_version"] = "ts-v5-r3g2-effect-explicit-approval-v1"
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    with pytest.raises(R3G2Error, match="explicit approval differs"):
        load_effect_authority(release_path, approval_path, EffectProtocol.load())


def test_recovery_synthetic_runner_and_auditor_reuse_frozen_effect_logic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release, approval, manifest, _ = _control(tmp_path)
    monkeypatch.setenv("SHAIWEI_RELEASE_GIT_HEAD", git_head())
    monkeypatch.setenv("SHAIWEI_RELEASE_MANIFEST", str(manifest))
    result = run(
        release_path=release,
        approval_path=approval,
        output_root=tmp_path / "effect",
        temporary_root=tmp_path / "temporary",
        adapter_factory=lambda protocol, temporary: SyntheticAdapter(protocol, temporary),
    )
    audited = audit(
        release_path=release,
        approval_path=approval,
        effect_root=tmp_path / "effect",
        audit_root=tmp_path / "audit",
    )
    assert result["strategy_effective"] == "PENDING_INDEPENDENT_AUDIT"
    assert audited["independent_audit"] == "PASS"
    assert audited["strategy_effective"] == "HISTORICAL_GO_NOT_PRODUCTION"
    with pytest.raises(R3G2Error, match="output exists"):
        run(
            release_path=release,
            approval_path=approval,
            output_root=tmp_path / "effect",
            temporary_root=tmp_path / "other",
            adapter_factory=lambda protocol, temporary: SyntheticAdapter(protocol, temporary),
        )


def test_recovery_compose_is_offline_minimal_and_exact() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    serialized = COMPOSE.read_text(encoding="utf-8")
    services = document["services"]
    assert "env_file" not in serialized and ".env" not in serialized
    assert "docker.sock" not in serialized
    for service in services.values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert service["restart"] == "no"
    runner = services["ts-v5-r3g2-effect-recovery-runner"]
    auditor = services["ts-v5-r3g2-effect-recovery-auditor"]

    def mounts(rows: list[dict]) -> list[dict[str, str]]:
        return [
            {
                "source": str(row["source"]).removeprefix("./"),
                "target": row["target"],
                "access": "read_only" if row.get("read_only") else "read_write",
            }
            for row in rows
        ]

    expected_runner, expected_auditor = recovery_mounts()
    assert mounts(runner["volumes"]) == expected_runner
    assert mounts(auditor["volumes"]) == expected_auditor
    assert runner["command"][2].endswith("effect_run")
    assert auditor["command"][2].endswith("effect_audit")
    assert all(row["target"] != "/workspace/data/raw" for row in auditor["volumes"])


def test_recovery_paths_are_controlled_and_separate() -> None:
    assert RECOVERY_COMPOSE in CONTROLLED_FILES
    assert RECOVERY_COMPOSE in (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert RECOVERY_SCOPE_PATH != "config/ts_v5_r3g2_effect_release_scope_v1.json"
    assert RECOVERY_APPROVAL_PATH != "data/control/ts-v5-r3g2-effect-v1/approval.json"
    assert RECOVERY_EFFECT_ROOT != "data/research/trend_swing/ts-v5-r3g2-effect-v1"
    assert RECOVERY_AUDIT_ROOT != "data/research/trend_swing/ts-v5-r3g2-effect-v1-audit"
