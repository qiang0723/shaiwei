import json
from pathlib import Path

import pytest
import yaml

from shaiwei import release


def test_release_audit_is_hash_chained_and_detects_tampering(monkeypatch, tmp_path):
    audit = tmp_path / "scheduler_releases.jsonl"
    monkeypatch.setattr(release, "AUDIT_PATH", audit)
    monkeypatch.setattr(release, "git_head", lambda: "a" * 40)

    first = release._append_audit("BUILD_PASS", {"image_id": "sha256:first"})
    second = release._append_audit("PROMOTE_PASS", {"image_id": "sha256:second"})
    records = release._validate_audit_chain()

    assert len(records) == 2
    assert second["previous_record_sha256"] == first["record_sha256"]
    lines = audit.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[0])
    tampered["details"]["image_id"] = "sha256:tampered"
    lines[0] = json.dumps(tampered, sort_keys=True)
    audit.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(release.ReleaseError, match="hash differs"):
        release._validate_audit_chain()


def test_release_state_roundtrip(monkeypatch, tmp_path):
    state_path = tmp_path / "scheduler_state.json"
    monkeypatch.setattr(release, "STATE_PATH", state_path)
    current = {
        "image": "shaiwei:scheduler-current-hash",
        "image_id": "sha256:current",
        "code_snapshot_sha256": "a" * 64,
    }
    previous = {
        "image": "shaiwei:scheduler-previous-hash",
        "image_id": "sha256:previous",
        "code_snapshot_sha256": "b" * 64,
    }
    document = release._state_for(current, previous)
    release._write_json_atomic(state_path, document)

    assert release._load_state() == document


def test_scheduler_compose_has_no_development_tree_or_docker_socket():
    compose = yaml.safe_load((Path(__file__).parents[1] / "compose.yaml").read_text(encoding="utf-8"))
    scheduler = compose["services"]["scheduler"]
    assert scheduler["image"] == release.CURRENT_ALIAS
    assert "build" not in scheduler
    assert scheduler["read_only"] is True
    assert scheduler["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in scheduler["security_opt"]
    destinations = {volume["target"] for volume in scheduler["volumes"]}
    assert destinations == {
        "/workspace/data",
        "/workspace/ledger",
        "/workspace/logs",
    }
    assert "/workspace" not in destinations
    assert all("docker.sock" not in json.dumps(volume) for volume in scheduler["volumes"])


def test_no_start_promote_and_rollback_swap_distinct_content_images(monkeypatch, tmp_path):
    monkeypatch.setattr(release, "STATE_PATH", tmp_path / "scheduler_state.json")
    monkeypatch.setattr(release, "AUDIT_PATH", tmp_path / "scheduler_releases.jsonl")
    monkeypatch.setattr(release, "git_head", lambda: "c" * 40)
    tagged = []
    monkeypatch.setattr(release, "_tag", lambda source, target: tagged.append((source, target)))
    images = {
        "shaiwei:scheduler-a": {
            "image": "shaiwei:scheduler-a",
            "image_id": "sha256:a",
            "code_snapshot_sha256": "a" * 64,
        },
        "shaiwei:scheduler-b": {
            "image": "shaiwei:scheduler-b",
            "image_id": "sha256:b",
            "code_snapshot_sha256": "b" * 64,
        },
    }
    monkeypatch.setattr(release, "verify_image", lambda image: images[image])

    release.promote("shaiwei:scheduler-a", start=False)
    release.promote("shaiwei:scheduler-b", start=False)
    promoted = release._load_state()
    assert promoted["current"] == images["shaiwei:scheduler-b"]
    assert promoted["previous"] == images["shaiwei:scheduler-a"]

    release.rollback(start=False)
    rolled_back = release._load_state()
    assert rolled_back["current"] == images["shaiwei:scheduler-a"]
    assert rolled_back["previous"] == images["shaiwei:scheduler-b"]
    assert tagged[-2:] == [
        ("shaiwei:scheduler-a", release.CURRENT_ALIAS),
        ("shaiwei:scheduler-b", release.PREVIOUS_ALIAS),
    ]
    assert [record["event"] for record in release._validate_audit_chain()] == [
        "PROMOTE_PASS",
        "PROMOTE_PASS",
        "ROLLBACK_PASS",
    ]
