from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).parents[1]
RELEASE_PATH = (
    ROOT / "config/m5_dynamic_fundamental_data_gate_release_scope_v4.json"
)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_recovery_release_v4_is_canonical_content_addressed_and_unapproved() -> None:
    serialized = RELEASE_PATH.read_text(encoding="utf-8")
    document = json.loads(serialized)
    scope = document["scope"]

    assert serialized == json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ) + "\n"
    assert document["schema_version"] == "m5-data-gate-release-scope-v2"
    assert document["release_scope_sha256"] == _canonical_sha256(scope)
    assert document["release_scope_sha256"] == (
        "8858912f14577a8911e47f0ec338cde82208fe818b4c7a921578e42aeeed6f65"
    )
    assert scope["protocol_scope_sha256"] == (
        "6f99c0dfdc5cd75df9bf769fb65318feb4e8e7140082a9dfb924a88a3bb0dc49"
    )
    assert scope["case_id"] == (
        "a2539149d588a0c19f9cb73331f19a66df63e301df03f56fbb2c8e5c74672068"
    )
    assert scope["build_protocol_id"] == (
        "m5-dynamic-fundamental-data-gate-build-v2"
    )
    assert datetime.fromisoformat(scope["scope_created_at"]) < datetime.fromisoformat(
        scope["source_proposal"]["expires_at"]
    )


def test_recovery_release_binds_pushed_code_image_and_metadata_only_input() -> None:
    scope = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))["scope"]

    assert scope["implementation"] == {
        "auditor_code_sha256": "2030d2f68e328f303790c07e50609b3495f199363b375eba00d8a53464343356",
        "code_bundle_sha256": "afdc4f2b402fedba8a91969d5a03c86a50f124c74fe2ff2c1d82803fc182093f",
        "commit_pushed_before_scope": True,
        "compose_sha256": "2e691b3543bd976d255438c39c3a455ab80636bcde455b2bf90efa6548fe16a1",
        "dockerfile_sha256": "06ad76c1b238c5370de925cfbf6c483234a3a16d4705fb035e2e3d21ad600852",
        "git_commit": "18e7502b74919641e02689720dd31b1e36b276a7",
        "origin_main_commit": "18e7502b74919641e02689720dd31b1e36b276a7",
        "requirements_lock_sha256": "3f0bc07912efd5d05dd47794f2e26dbc523f1b25c0698022620a25714992a3e3",
    }
    assert scope["image"] == {
        "base_image": "python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93",
        "image_id": "sha256:acb7c6c2828dd3b8a40f599f934f3059904ec27835c19e3847bbb416897d1ea7",
        "platform": "linux/arm64",
        "repo_digest": "shaiwei@sha256:acb7c6c2828dd3b8a40f599f934f3059904ec27835c19e3847bbb416897d1ea7",
    }
    assert scope["input_manifest_sha256"] == (
        "f4aeb411af00ea2f5ad096983859f50a587ed9ad6cee1f384268e14d1ef9399b"
    )
    assert scope["input_manifest_physical_sha256"] == (
        "683bed3adda638ab890a30cbadca77a07b1d39fd58b8347dcdb65c5b6053f020"
    )
    assert scope["authority"]["data_gate_release_ready"] is True
    assert scope["authority"]["data_gate_approval_recorded"] is False
    assert scope["authority"]["data_gate_execution_authorized"] is False
    assert scope["authority"]["real_data_read_authorized"] is False
    assert scope["authority"]["production_authorization"] == "none"
