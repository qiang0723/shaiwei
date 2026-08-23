"""Versioned local state and archive helpers for Web component releases."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import uuid
from typing import Mapping

from shaiwei.build_identity.web_release_config import WebReleaseError


STATE_SCHEMA_V1 = "shaiwei-web-component-release-state-v1"
STATE_SCHEMA = "shaiwei-web-component-release-state-v2"
STATE_SCHEMAS = {STATE_SCHEMA_V1, STATE_SCHEMA}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ROLES = {"research-control", "web-runtime"}


def write_release_state(path: Path, document: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def load_release_state(path: Path, *, required: bool = True) -> dict[str, object] | None:
    if not path.is_file() and not required:
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WebReleaseError("Web release state is missing or invalid") from error
    if not isinstance(document, dict) or document.get("schema_version") not in STATE_SCHEMAS:
        raise WebReleaseError("Web release state schema differs")
    candidate = document.get("current_candidate_sha256")
    if not isinstance(candidate, str) or not _SHA256.fullmatch(candidate):
        raise WebReleaseError("Web release state candidate identity is invalid")
    release_images(document)
    if not isinstance(document.get("scheduler_identity"), dict):
        raise WebReleaseError("Web release state scheduler identity is invalid")
    return document


def release_images(state: Mapping[str, object]) -> dict[str, dict[str, str]]:
    raw = state.get("current_images")
    if not isinstance(raw, dict) or set(raw) != _ROLES:
        raise WebReleaseError("Web release state image roles differ")
    images: dict[str, dict[str, str]] = {}
    for role, row in raw.items():
        if not isinstance(role, str) or not isinstance(row, dict):
            raise WebReleaseError("Web release state image record is invalid")
        reference, image_id = row.get("reference"), row.get("image_id")
        if (
            not isinstance(reference, str)
            or not reference
            or not isinstance(image_id, str)
            or not _IMAGE_ID.fullmatch(image_id)
        ):
            raise WebReleaseError("Web release state image identity is invalid")
        images[role] = {"reference": reference, "image_id": image_id}
    return images


def archive_release_state(path: Path, state: Mapping[str, object]) -> Path:
    candidate = str(state["current_candidate_sha256"])
    archive = path.parent / "web_component_states" / f"{candidate}.json"
    if archive.exists():
        try:
            current = json.loads(archive.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise WebReleaseError("Web previous-state archive is invalid") from error
        if current != state:
            raise WebReleaseError("Web previous-state archive differs")
    else:
        write_release_state(archive, state)
    return archive
