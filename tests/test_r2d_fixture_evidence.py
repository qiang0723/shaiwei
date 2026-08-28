from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from shaiwei import daily_early_release_guard as base
from shaiwei.r2d_fixture_evidence import FixtureEvidence, validate_fixture


def _write(path: Path, document: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate() -> base.ReleaseIdentity:
    return base.ReleaseIdentity(
        image="shaiwei:scheduler-" + "1" * 16,
        image_id="sha256:" + "2" * 64,
        code_snapshot_sha256="3" * 64,
        git_head="4" * 40,
        lock_authority="docker-named-volume-v1",
    )


def _evidence(root: Path) -> tuple[FixtureEvidence, Path]:
    candidate = _candidate()
    scope = "5" * 64
    directory = root / ".release/r2d-r3a"
    report = {
        "schema_version": "shaiwei-r2d-r3a-health-convergence-fixture-v1",
        "action": "R2D_R3A_DOCKER_HEALTH_CONVERGENCE_FIXTURE_ONCE",
        "scope_sha256": scope,
        "verdict": "PASS",
        "error_type": "",
        "production_authorization": "none",
        "production_identity_unchanged": True,
        "production_evidence_before": {"release_state": "a" * 64},
        "production_evidence_after": {"release_state": "a" * 64},
        "candidate": {
            **candidate.model_dump(),
            "contract": {
                "image_id": candidate.image_id,
                "code_snapshot_sha256": candidate.code_snapshot_sha256,
                "git_head": candidate.git_head,
                "lock_authority": candidate.lock_authority,
                "health": "healthy",
                "read_only_rootfs": True,
                "mount_destinations": [
                    "/run/shaiwei-locks",
                    "/workspace/data",
                    "/workspace/ledger",
                    "/workspace/logs",
                ],
            },
        },
        "cases": [
            {"case": name, "status": "PASS"}
            for name in (
                "production_release_evidence_matches_scope",
                "candidate_image_labels",
                "docker_health_starting_observed",
                "shared_release_contract_converged",
                "guard_success_path_without_rollback",
                "production_release_evidence_unchanged",
            )
        ],
    }
    report_sha = _write(directory / "report.json", report)
    tree_content = "6" * 64
    tree_sha = _write(directory / "tree.json", {"tree_sha256": tree_content})
    receipt_sha = _write(
        directory / "receipt.json",
        {
            "action": report["action"],
            "scope_sha256": scope,
            "report_sha256": report_sha,
            "evidence_tree_sha256": tree_content,
            "status": "PASS",
        },
    )
    return FixtureEvidence(
        format="r3a",
        release_scope_sha256=scope,
        report_path=".release/r2d-r3a/report.json",
        report_sha256=report_sha,
        tree_path=".release/r2d-r3a/tree.json",
        tree_file_sha256=tree_sha,
        tree_content_sha256=tree_content,
        receipt_path=".release/r2d-r3a/receipt.json",
        receipt_sha256=receipt_sha,
    ), directory / "report.json"


def test_r3a_fixture_accepts_exact_sealed_evidence(tmp_path: Path) -> None:
    fixture, _report = _evidence(tmp_path)
    validate_fixture(fixture, candidate=_candidate(), project_root=tmp_path)


def test_r3a_fixture_rejects_report_mutation(tmp_path: Path) -> None:
    fixture, report = _evidence(tmp_path)
    document = json.loads(report.read_text(encoding="utf-8"))
    document["cases"][2]["status"] = "FAIL"
    report.write_text(json.dumps(document) + "\n", encoding="utf-8")
    with pytest.raises(base.GuardError, match="hash or schema"):
        validate_fixture(fixture, candidate=_candidate(), project_root=tmp_path)


def test_fixture_rejects_symlinked_evidence_path(tmp_path: Path) -> None:
    fixture, _report = _evidence(tmp_path)
    target = tmp_path / ".release/r2d-r3a"
    link = tmp_path / ".release/r2d-link"
    link.symlink_to(target, target_is_directory=True)
    linked = fixture.model_copy(
        update={
            "report_path": ".release/r2d-link/report.json",
            "tree_path": ".release/r2d-link/tree.json",
            "receipt_path": ".release/r2d-link/receipt.json",
        }
    )
    with pytest.raises(base.GuardError, match="hash or schema"):
        validate_fixture(linked, candidate=_candidate(), project_root=tmp_path)
