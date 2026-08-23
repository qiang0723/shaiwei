"""Explicit archival step before building a successor Web release candidate."""

from __future__ import annotations

import json
from pathlib import Path

from shaiwei.build_identity.registry import PROJECT_ROOT
from shaiwei.build_identity.web_release_build import (
    CANDIDATE_SCHEMA,
    canonical_candidate_sha256,
    pushed_git_identity,
)
from shaiwei.build_identity.web_release_config import WebReleaseError, load_web_release_config
from shaiwei.build_identity.web_release_state import load_release_state


def _verified_archival_candidate(path: Path, expected_sha256: str) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WebReleaseError("Web current candidate is missing or invalid") from error
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != CANDIDATE_SCHEMA
        or document.get("candidate_sha256") != expected_sha256
        or canonical_candidate_sha256(document) != expected_sha256
    ):
        raise WebReleaseError("Web current candidate does not match deployed state")
    return document


def prepare_successor_candidate(*, root: Path | None = None) -> dict[str, object]:
    """Archive the deployed candidate pointer without rewriting its evidence."""
    project_root = (root or PROJECT_ROOT).resolve()
    config = load_web_release_config(root=project_root)
    pushed_git_identity(project_root)
    state = load_release_state(project_root / config.state_path)
    if state is None:
        raise WebReleaseError("Web successor preparation requires a deployed state")
    current_sha = str(state["current_candidate_sha256"])
    candidate_path = project_root / config.candidate_path
    archive = candidate_path.parent / "web_component_candidates" / f"{current_sha}.json"
    if archive.is_file() and not candidate_path.exists():
        _verified_archival_candidate(archive, current_sha)
        return {"status": "PASS", "archived_candidate_sha256": current_sha}
    _verified_archival_candidate(candidate_path, current_sha)
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        _verified_archival_candidate(archive, current_sha)
        if archive.read_bytes() != candidate_path.read_bytes():
            raise WebReleaseError("Web successor candidate archive differs")
        candidate_path.unlink()
    else:
        candidate_path.replace(archive)
    return {"status": "PASS", "archived_candidate_sha256": current_sha}
