from __future__ import annotations

import json
from pathlib import Path

import pytest

from shaiwei.build_identity.web_release_config import WebReleaseError
from shaiwei.build_identity.web_release_state import (
    STATE_SCHEMA,
    STATE_SCHEMA_V1,
    archive_release_state,
    load_release_state,
    release_images,
)


CANDIDATE = "a" * 64
IMAGE_ID = f"sha256:{'b' * 64}"


def _state(schema: str = STATE_SCHEMA) -> dict[str, object]:
    return {
        "schema_version": schema,
        "current_candidate_sha256": CANDIDATE,
        "current_images": {
            "research-control": {"reference": "control:fixed", "image_id": IMAGE_ID},
            "web-runtime": {"reference": "web:fixed", "image_id": IMAGE_ID},
        },
        "scheduler_identity": {"container_id": "scheduler"},
    }


@pytest.mark.parametrize("schema", [STATE_SCHEMA_V1, STATE_SCHEMA])
def test_release_state_accepts_frozen_v1_and_successor_v2(tmp_path: Path, schema: str) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps(_state(schema)), encoding="utf-8")

    loaded = load_release_state(path)

    assert loaded == _state(schema)
    assert release_images(loaded) == _state(schema)["current_images"]


def test_release_state_requires_exact_image_roles_and_content_ids(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    document = _state()
    document["current_images"]["unexpected"] = {  # type: ignore[index]
        "reference": "extra:fixed",
        "image_id": IMAGE_ID,
    }
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(WebReleaseError, match="image roles differ"):
        load_release_state(path)


def test_release_state_archive_is_idempotent_but_tamper_evident(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    document = _state()

    first = archive_release_state(path, document)
    second = archive_release_state(path, document)

    assert first == second
    assert json.loads(first.read_text(encoding="utf-8")) == document
    first.write_text(json.dumps({**document, "scheduler_identity": {}}), encoding="utf-8")
    with pytest.raises(WebReleaseError, match="archive differs"):
        archive_release_state(path, document)


def test_optional_release_state_is_absent_without_creating_files(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"
    assert load_release_state(path, required=False) is None
    assert not path.exists()
