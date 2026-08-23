from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from shaiwei.build_identity.web_release_build import (
    CANDIDATE_SCHEMA,
    canonical_candidate_sha256,
)
from shaiwei.build_identity.web_release_config import WebReleaseError
from shaiwei.build_identity.web_release_state import STATE_SCHEMA, write_release_state
from shaiwei.build_identity import web_release_successor


def _candidate() -> dict[str, object]:
    document: dict[str, object] = {
        "schema_version": CANDIDATE_SCHEMA,
        "candidate_sha256": "",
        "fixture": "deployed",
    }
    document["candidate_sha256"] = canonical_candidate_sha256(document)
    return document


def _prepare_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict[str, object]]:
    config = SimpleNamespace(
        state_path=".release/web_component_state.json",
        candidate_path=".release/web_component_candidate.json",
    )
    monkeypatch.setattr(web_release_successor, "load_web_release_config", lambda root: config)
    monkeypatch.setattr(web_release_successor, "pushed_git_identity", lambda root: "a" * 40)
    candidate = _candidate()
    state = {
        "schema_version": STATE_SCHEMA,
        "current_candidate_sha256": candidate["candidate_sha256"],
        "current_images": {
            "research-control": {"reference": "control:fixed", "image_id": f"sha256:{'b' * 64}"},
            "web-runtime": {"reference": "web:fixed", "image_id": f"sha256:{'c' * 64}"},
        },
        "scheduler_identity": {"container_id": "scheduler"},
    }
    write_release_state(tmp_path / config.state_path, state)
    candidate_path = tmp_path / config.candidate_path
    candidate_path.write_text(json.dumps(candidate, sort_keys=True), encoding="utf-8")
    return candidate_path, candidate


def test_prepare_successor_archives_exact_deployed_candidate_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_path, candidate = _prepare_root(tmp_path, monkeypatch)

    first = web_release_successor.prepare_successor_candidate(root=tmp_path)
    second = web_release_successor.prepare_successor_candidate(root=tmp_path)

    archive = candidate_path.parent / "web_component_candidates" / (
        f"{candidate['candidate_sha256']}.json"
    )
    assert first == second == {
        "status": "PASS",
        "archived_candidate_sha256": candidate["candidate_sha256"],
    }
    assert not candidate_path.exists()
    assert json.loads(archive.read_text(encoding="utf-8")) == candidate


def test_prepare_successor_rejects_corrupted_existing_archive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_path, candidate = _prepare_root(tmp_path, monkeypatch)
    web_release_successor.prepare_successor_candidate(root=tmp_path)
    archive = candidate_path.parent / "web_component_candidates" / (
        f"{candidate['candidate_sha256']}.json"
    )
    archive.write_text("{}\n", encoding="utf-8")

    with pytest.raises(WebReleaseError, match="does not match deployed state"):
        web_release_successor.prepare_successor_candidate(root=tmp_path)
