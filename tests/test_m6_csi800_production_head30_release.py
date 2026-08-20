import ast
import json
from pathlib import Path

from shaiwei.config import PROJECT_ROOT
from shaiwei.provenance import CONTROLLED_FILES, RELEASE_MANIFEST_SCHEMA
from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.production_conversion.audit_statistics import independently_evaluate
from shaiwei.research.production_conversion.fixture import build_bundle
from shaiwei.research.production_conversion.real_contract import (
    APPROVAL_ACTION,
    IMAGE,
    ReleaseProtocol,
    expected_authority,
)
from shaiwei.research.production_conversion.real_release import build_release_document
from shaiwei.research.production_conversion import real_release


def test_release_protocol_is_result_blind_and_single_attempt() -> None:
    protocol = ReleaseProtocol.load()
    authority = protocol.document["authority_before_exact_user_approval"]
    assert authority["sealed_effect_semantic_read_authorized"] is False
    assert authority["real_treatment_backtest_authorized"] is False
    assert protocol.document["execution_counting"] == {
        "runner_invocation_count": 1,
        "complete_internal_passes": ["first_pass", "replay"],
        "independent_auditor_invocation_count": 1,
        "new_portfolio_attempts_consumed_at_first_treatment_effect_read": 1,
        "model_attempt_increment": 0,
        "same_release_retry_authorized": False,
    }
    assert protocol.document["release_and_approval"]["approval_action"] == APPROVAL_ACTION


def test_fixture_is_deterministic_and_independently_reconstructed() -> None:
    first = build_bundle()
    replay = build_bundle()
    assert canonical_sha256(first) == canonical_sha256(replay)
    assert canonical_sha256(independently_evaluate(first)) == canonical_sha256(first["result"])
    assert first["result"]["g0"]["window_count"] == 6


def test_auditor_has_no_primary_execution_or_metric_import() -> None:
    path = PROJECT_ROOT / "src/shaiwei/research/production_conversion/real_audit.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    forbidden = {
        "shaiwei.research.production_conversion.execution",
        "shaiwei.research.production_conversion.metrics",
        "shaiwei.research.production_conversion.real_run",
    }
    assert imports.isdisjoint(forbidden)


def test_compose_is_controlled_and_contains_no_secret_or_production_mount() -> None:
    name = "compose.m6-production-head30-release.yaml"
    assert name in CONTROLLED_FILES
    text = (PROJECT_ROOT / name).read_text(encoding="utf-8")
    assert "network_mode: none" in text
    assert ".env" not in text
    assert "ledger" not in text
    assert "/var/run/docker.sock" not in text
    assert "read_only: true" in text
    assert (
        "docs/M6_CSI800_MODEL_ATTRIBUTION_AUDIT_RECOVERY_ACCEPTANCE_20260807.md"
        in CONTROLLED_FILES
    )
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert (
        "!docs/M6_CSI800_MODEL_ATTRIBUTION_AUDIT_RECOVERY_ACCEPTANCE_20260807.md"
        in dockerignore
    )


def test_release_document_binds_image_and_stays_non_authoritative(tmp_path: Path) -> None:
    protocol = ReleaseProtocol.load()
    snapshot = "a" * 64
    manifest = {
        "schema_version": RELEASE_MANIFEST_SCHEMA,
        "code_snapshot_sha256": snapshot,
        "file_count": 1,
        "files": [{"path": "x", "sha256": "b" * 64}],
    }
    manifest_path = tmp_path / "release-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    qlib = json.loads(
        (PROJECT_ROOT / "config/m6_csi800_model_attribution_release_scope_v1.json").read_text(
            encoding="utf-8"
        )
    )["scope"]["inputs"]
    inputs = {
        "qlib": qlib,
        "sealed_m6_effect": {
            "file_count": 1,
            "total_bytes": 1,
            "tree_sha256": "c" * 64,
            "report_sha256": "d" * 64,
            "first_pass_bundle_sha256": "e" * 64,
            "replay_bundle_sha256": "e" * 64,
        },
        "sealed_m6_audit": {
            "path": "data/example/audit.json",
            "sha256": "f" * 64,
            "independent_audit": "PASS",
        },
    }
    commit = "1" * 40
    document = build_release_document(
        protocol=protocol,
        created_at="2026-08-20T00:00:00+00:00",
        implementation_git_commit=commit,
        origin_main_commit=commit,
        code_snapshot=snapshot,
        image_id="sha256:" + "2" * 64,
        image_platform="linux/arm64",
        image_git_commit=commit,
        image_release_manifest_path=manifest_path,
        inputs=inputs,
    )
    assert document["scope"]["image"]["reference"] == IMAGE
    assert document["scope"]["authority"] == expected_authority()
    assert document["scope"]["authority"]["execution_authorized"] is False


def test_sealed_input_metadata_accepts_relative_project_paths(
    tmp_path: Path, monkeypatch
) -> None:
    effect = tmp_path / "effect"
    for name in ("first_pass", "replay"):
        directory = effect / name
        directory.mkdir(parents=True)
        (directory / "manifest.json").write_text(
            json.dumps({"bundle_sha256": name + "-bundle"}), encoding="utf-8"
        )
    (effect / "report.json").write_text("{}", encoding="utf-8")
    audit = tmp_path / "audit.json"
    audit.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(real_release, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        real_release,
        "effect_tree_identity",
        lambda _: {"file_count": 3, "total_bytes": 3, "tree_sha256": "a" * 64},
    )
    monkeypatch.chdir(tmp_path)
    result = real_release._sealed_inputs(Path("effect"), Path("audit.json"))
    assert result["sealed_m6_audit"]["path"] == "audit.json"
    assert result["sealed_m6_effect"]["first_pass_bundle_sha256"] == "first_pass-bundle"
