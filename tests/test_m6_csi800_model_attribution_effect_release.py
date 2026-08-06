from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil

import pandas as pd
import pytest
import yaml

from shaiwei.provenance import code_snapshot_sha256, git_head, write_release_manifest
from shaiwei.research.model_attribution.contract import (
    AttributionError,
    canonical_sha256,
)
from shaiwei.research.model_attribution.effect_audit import audit
from shaiwei.research.model_attribution.effect_contract import (
    APPROVAL_ACTION,
    EffectApproval,
    EffectProtocol,
    EffectReleaseScope,
)
from shaiwei.research.model_attribution.effect_fixture import execute_fixture
from shaiwei.research.model_attribution.effect_metrics import (
    normalize_report,
    portfolio_evidence,
)
from shaiwei.research.model_attribution.effect_release import build_release_document
from shaiwei.research.model_attribution.effect_release import main as release_main
from shaiwei.research.model_attribution.effect_schema import ARMS, WINDOWS


ROOT = Path(__file__).parents[1]


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    return path


def _release_document(tmp_path: Path) -> tuple[EffectProtocol, dict]:
    protocol = EffectProtocol.load()
    snapshot = "b" * 64
    manifest = {
        "schema_version": "shaiwei-release-manifest-v1",
        "code_snapshot_sha256": snapshot,
        "file_count": 0,
        "files": [],
    }
    manifest_path = _write(tmp_path / "image-manifest.json", manifest)
    document = build_release_document(
        protocol=protocol,
        created_at="2026-08-06T00:00:00+00:00",
        implementation_git_commit="a" * 40,
        origin_main_commit="a" * 40,
        code_snapshot=snapshot,
        image_id="sha256:" + "c" * 64,
        image_platform="linux/arm64",
        image_git_commit="a" * 40,
        image_release_manifest_path=manifest_path,
    )
    return protocol, document


def test_release_scope_is_content_addressed_and_grants_no_execution(tmp_path: Path) -> None:
    protocol, document = _release_document(tmp_path)
    release = EffectReleaseScope.load(_write(tmp_path / "release.json", document), protocol)

    assert release.sha256 == canonical_sha256(document["scope"])
    assert release.scope["authority"]["release_ready"] is True
    assert release.scope["authority"]["execution_authorized"] is False
    assert release.scope["authority"]["real_label_or_effect_read_authorized"] is False
    assert release.scope["authority"]["production_authorization"] == "none"


@pytest.mark.parametrize("mutation", ["authority", "mount", "command", "resources", "image"])
def test_release_scope_rejects_rehashed_boundary_drift(tmp_path: Path, mutation: str) -> None:
    protocol, document = _release_document(tmp_path)
    changed = copy.deepcopy(document)
    if mutation == "authority":
        changed["scope"]["authority"]["execution_authorized"] = True
    elif mutation == "mount":
        changed["scope"]["container"]["runner"]["mounts"][0]["source"] = "."
    elif mutation == "command":
        changed["scope"]["container"]["runner"]["command"][-1] = "/other"
    elif mutation == "resources":
        changed["scope"]["container"]["runner"]["memory"] = "16g"
    else:
        changed["scope"]["image"]["git_commit"] = "d" * 40
    changed["release_scope_sha256"] = canonical_sha256(changed["scope"])

    with pytest.raises(AttributionError):
        EffectReleaseScope.load(_write(tmp_path / f"{mutation}.json", changed), protocol)


def test_approval_must_bind_every_exact_authority_field(tmp_path: Path) -> None:
    protocol, document = _release_document(tmp_path)
    release = EffectReleaseScope.load(_write(tmp_path / "release.json", document), protocol)
    approval = {
        "schema_version": "m6-model-attribution-approval-v1",
        "release_scope_sha256": release.sha256,
        "action": APPROVAL_ACTION,
        "approved_at": "2026-08-06T00:01:00+00:00",
        "consumed": False,
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
    EffectApproval.load(_write(tmp_path / "approval.json", approval), release)
    approval["release_scope_sha256"] = "0" * 64
    with pytest.raises(AttributionError, match="exact release authority"):
        EffectApproval.load(_write(tmp_path / "wrong.json", approval), release)


def test_normalized_report_is_idempotent_and_benchmark_drift_fails() -> None:
    dates = pd.bdate_range("2024-01-02", periods=20)
    normalized = pd.DataFrame(
        {
            "gross_return": [0.001] * 20,
            "benchmark_return": [0.0005] * 20,
            "recorded_cost": [0.0001] * 20,
            "turnover": [0.02] * 20,
        },
        index=dates,
    )
    assert normalize_report(normalized).equals(normalized)
    reports = {window: {arm: normalized.copy() for arm in ARMS} for window in WINDOWS}
    reports["W1"][ARMS[1]].loc[dates[0], "benchmark_return"] = 0.0006
    stress = {arm: normalized.copy() for arm in ARMS}
    with pytest.raises(AttributionError, match="benchmark returns differ"):
        portfolio_evidence(reports, stress, EffectProtocol.load().result)


def test_compose_matches_frozen_commands_mounts_and_isolation() -> None:
    protocol = EffectProtocol.load()
    compose = yaml.safe_load((ROOT / "compose.m6-attribution.yaml").read_text())
    services = compose["services"]
    roles = {
        "runner": services["m6-effect-runner"],
        "auditor": services["m6-effect-auditor"],
    }
    for role, service in roles.items():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert "env_file" not in service
        actual_mounts = [
            {
                "source": row["source"].removeprefix("./"),
                "target": row["target"],
                "mode": "ro" if row["read_only"] else "rw",
            }
            for row in service["volumes"]
        ]
        assert actual_mounts == protocol.document["docker"][f"{role}_mounts"]
        assert all("ledger" not in row["source"] for row in actual_mounts)
    assert roles["runner"]["command"][-4:] == [
        "--provider-root",
        "/qlib",
        "--output-root",
        "/outputs",
    ]
    assert "/qlib" not in [row["target"] for row in roles["auditor"]["volumes"]]


def test_release_cli_passes_the_manifest_argument_to_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_build(**kwargs):
        captured.update(kwargs)
        return {"release_ready": True}

    monkeypatch.setattr("shaiwei.research.model_attribution.effect_release.build", fake_build)
    monkeypatch.setattr(
        "sys.argv",
        [
            "effect-release",
            "--image-id",
            "sha256:" + "1" * 64,
            "--image-platform",
            "linux/arm64",
            "--image-git-commit",
            "a" * 40,
            "--image-release-manifest",
            "manifest.json",
            "--output",
            "scope.json",
        ],
    )
    assert release_main() == 0
    assert captured["image_release_manifest"] == Path("manifest.json")


def test_synthetic_one_shot_runner_independent_audit_and_tamper_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = tmp_path / "release-manifest.json"
    write_release_manifest(manifest_path, root=ROOT)
    monkeypatch.setenv("SHAIWEI_RELEASE_MANIFEST", str(manifest_path))
    monkeypatch.setenv("SHAIWEI_RELEASE_GIT_HEAD", git_head())
    assert code_snapshot_sha256() == json.loads(manifest_path.read_text())["code_snapshot_sha256"]

    root = tmp_path / "fixture"
    result = execute_fixture(root)
    assert result["real_data_read"] is False
    assert result["runner"]["strategy_effective"] == "PENDING_INDEPENDENT_AUDIT"
    assert result["auditor"]["independent_audit"] == "PASS"

    source = (ROOT / "src/shaiwei/research/model_attribution/effect_audit.py").read_text()
    assert ".effect_metrics" not in source
    assert ".inference" not in source
    assert ".effect_artifacts" not in source
    assert ".effect_execution" not in source

    shutil.rmtree(root / "audit")
    target = root / "effect/first_pass/W1/models/clean_lgbm_control_v1.txt"
    target.write_bytes(target.read_bytes() + b"tampered\n")
    with pytest.raises(AttributionError, match="artifact hash differs"):
        audit(
            release_path=root / "control/release.json",
            approval_path=root / "control/approval.json",
            effect_root=root / "effect",
            audit_root=root / "audit",
        )


def test_fixture_does_not_replace_existing_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest_path = tmp_path / "release-manifest.json"
    write_release_manifest(manifest_path, root=ROOT)
    monkeypatch.setenv("SHAIWEI_RELEASE_MANIFEST", str(manifest_path))
    monkeypatch.setenv("SHAIWEI_RELEASE_GIT_HEAD", git_head())
    output = tmp_path / "fixture"
    output.mkdir()
    (output / "effect").mkdir()
    (output / "effect/existing.json").write_text("{}\n")
    with pytest.raises(AttributionError, match="output exists"):
        execute_fixture(output)


def test_no_test_leaks_environment_changes() -> None:
    assert "M6_TEST_SECRET" not in os.environ
