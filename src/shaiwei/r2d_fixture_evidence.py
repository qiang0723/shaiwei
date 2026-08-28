"""Validate immutable R2D fixture evidence without invoking Docker."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from shaiwei import daily_early_release_guard as base


R3A_SCHEMA = "shaiwei-r2d-r3a-health-convergence-fixture-v1"
R3A_ACTION = "R2D_R3A_DOCKER_HEALTH_CONVERGENCE_FIXTURE_ONCE"
R3A_CASES = (
    "production_release_evidence_matches_scope",
    "candidate_image_labels",
    "docker_health_starting_observed",
    "shared_release_contract_converged",
    "guard_success_path_without_rollback",
    "production_release_evidence_unchanged",
)
R3A_MOUNTS = {
    "/run/shaiwei-locks",
    "/workspace/data",
    "/workspace/ledger",
    "/workspace/logs",
}


class FixtureEvidence(base.FrozenModel):
    format: Literal["legacy-r2c", "r3a"] = "legacy-r2c"
    release_scope_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_path: str = Field(pattern=r"^\.release/[A-Za-z0-9_./-]+\.json$")
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tree_path: str = Field(pattern=r"^\.release/[A-Za-z0-9_./-]+\.json$")
    tree_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tree_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_path: str = Field(pattern=r"^\.release/[A-Za-z0-9_./-]+\.json$")
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fixture_json(root: Path, path_text: str, expected_sha256: str) -> dict[str, object]:
    unresolved = root / path_text
    path = unresolved.resolve()
    try:
        path.relative_to(root.resolve())
        relative = unresolved.relative_to(root)
        cursor = root
        if any((cursor := cursor / part).is_symlink() for part in relative.parts) or (
            _file_sha256(path) != expected_sha256
        ):
            raise base.GuardError("fixture evidence hash or schema differs")
        document = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise base.GuardError("fixture evidence escapes the project") from error
    except (OSError, json.JSONDecodeError) as error:
        raise base.GuardError("fixture evidence is unreadable") from error
    if not isinstance(document, dict):
        raise base.GuardError("fixture evidence hash or schema differs")
    return document


def _legacy_passes(
    fixture: FixtureEvidence,
    candidate: base.ReleaseIdentity,
    report: dict[str, object],
    tree: dict[str, object],
    receipt: dict[str, object],
) -> bool:
    return bool(
        report.get("scope_sha256") == fixture.release_scope_sha256
        and report.get("verdict") == "PASS"
        and tree.get("tree_sha256") == fixture.tree_content_sha256
        and receipt.get("release_scope_sha256") == fixture.release_scope_sha256
        and receipt.get("report_sha256") == fixture.report_sha256
        and receipt.get("evidence_tree_file_sha256") == fixture.tree_file_sha256
        and receipt.get("evidence_tree_sha256") == fixture.tree_content_sha256
        and receipt.get("status") == "PASS"
        and receipt.get("candidate") == candidate.image
        and receipt.get("image_id") == candidate.image_id
    )


def _r3a_candidate_passes(
    candidate: base.ReleaseIdentity,
    report: dict[str, object],
) -> bool:
    actual = report.get("candidate")
    if not isinstance(actual, dict):
        return False
    expected = candidate.model_dump(exclude_none=True)
    if any(actual.get(key) != value for key, value in expected.items()):
        return False
    contract = actual.get("contract")
    return bool(
        isinstance(contract, dict)
        and contract.get("health") == "healthy"
        and contract.get("read_only_rootfs") is True
        and set(contract.get("mount_destinations", ())) == R3A_MOUNTS
        and all(contract.get(key) == value for key, value in expected.items() if key != "image")
    )


def _r3a_passes(
    fixture: FixtureEvidence,
    candidate: base.ReleaseIdentity,
    report: dict[str, object],
    tree: dict[str, object],
    receipt: dict[str, object],
) -> bool:
    cases = report.get("cases")
    case_names = [row.get("case") for row in cases] if isinstance(cases, list) else []
    case_statuses = [row.get("status") for row in cases] if isinstance(cases, list) else []
    return bool(
        report.get("schema_version") == R3A_SCHEMA
        and report.get("action") == R3A_ACTION
        and report.get("scope_sha256") == fixture.release_scope_sha256
        and report.get("verdict") == "PASS"
        and report.get("error_type") == ""
        and report.get("production_authorization") == "none"
        and report.get("production_identity_unchanged") is True
        and report.get("production_evidence_before") == report.get("production_evidence_after")
        and case_names == list(R3A_CASES)
        and case_statuses == ["PASS"] * len(R3A_CASES)
        and _r3a_candidate_passes(candidate, report)
        and tree.get("tree_sha256") == fixture.tree_content_sha256
        and receipt.get("action") == R3A_ACTION
        and receipt.get("scope_sha256") == fixture.release_scope_sha256
        and receipt.get("report_sha256") == fixture.report_sha256
        and receipt.get("evidence_tree_sha256") == fixture.tree_content_sha256
        and receipt.get("status") == "PASS"
    )


def validate_fixture(
    fixture: FixtureEvidence,
    *,
    candidate: base.ReleaseIdentity,
    project_root: Path,
) -> None:
    report = _fixture_json(project_root, fixture.report_path, fixture.report_sha256)
    tree = _fixture_json(project_root, fixture.tree_path, fixture.tree_file_sha256)
    receipt = _fixture_json(project_root, fixture.receipt_path, fixture.receipt_sha256)
    valid = (
        _legacy_passes(fixture, candidate, report, tree, receipt)
        if fixture.format == "legacy-r2c"
        else _r3a_passes(fixture, candidate, report, tree, receipt)
    )
    if not valid:
        raise base.GuardError("fixture evidence differs from the frozen R2D boundary")
