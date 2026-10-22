"""ADR 0019：Web 发布门按 scheduler 发布审计 START_PASS 重设基线。"""

from __future__ import annotations

import pytest

from shaiwei.build_identity import web_release_deploy as deploy
from shaiwei.build_identity.web_release_config import WebReleaseError
from shaiwei.build_identity.web_release_runtime import scheduler_rebaseline

OLD = {"container_id": "183b8c6c", "image_id": "sha256:722f", "health": "healthy", "snapshot": "4e52", "revision": "210a"}
NEW = {"container_id": "98d1f84c", "image_id": "sha256:ce1a", "health": "healthy", "snapshot": "8b5b", "revision": "f6d3"}


def _start_pass(identity, sha, recorded_at="2026-10-22T09:12:24+00:00"):
    return {
        "event": "START_PASS",
        "record_sha256": sha,
        "recorded_at": recorded_at,
        "details": {
            "container_id": identity["container_id"],
            "image_id": identity["image_id"],
            "code_snapshot_sha256": identity["snapshot"],
            "git_head": identity["revision"],
        },
    }


def test_unchanged_scheduler_needs_no_rebaseline():
    assert scheduler_rebaseline(OLD, dict(OLD), []) is None


def test_released_scheduler_change_rebaselines_with_latest_start_pass():
    records = [
        _start_pass(OLD, "a" * 64),
        {"event": "PROMOTE_PASS", "details": {}},
        _start_pass(NEW, "b" * 64, "2026-10-22T09:00:00+00:00"),
        _start_pass(NEW, "c" * 64),
    ]
    evidence = scheduler_rebaseline(OLD, NEW, records)
    assert evidence == {
        "from_container_id": "183b8c6c",
        "to_container_id": "98d1f84c",
        "start_pass_record_sha256": "c" * 64,
        "start_pass_recorded_at": "2026-10-22T09:12:24+00:00",
    }


@pytest.mark.parametrize("field", ["container_id", "image_id", "snapshot", "revision"])
def test_unreleased_or_mismatched_scheduler_change_fails_closed(field):
    released = dict(NEW, **{field: "other"})
    with pytest.raises(WebReleaseError, match="lacks a START_PASS"):
        scheduler_rebaseline(OLD, NEW, [_start_pass(released, "d" * 64)])
    with pytest.raises(WebReleaseError, match="lacks a START_PASS"):
        scheduler_rebaseline(OLD, NEW, [])


def test_non_start_events_do_not_authorize_a_change():
    record = _start_pass(NEW, "e" * 64)
    record["event"] = "PROMOTE_PASS"
    with pytest.raises(WebReleaseError, match="lacks a START_PASS"):
        scheduler_rebaseline(OLD, NEW, [record])


def test_deployed_baseline_uses_audit_backed_rebaseline(monkeypatch, tmp_path):
    images = {"web-runtime": {"reference": "r", "image_id": "sha256:1"}, "research-control": {"reference": "c", "image_id": "sha256:2"}}
    monkeypatch.setattr(deploy, "release_images", lambda _state: images)
    monkeypatch.setattr(
        deploy,
        "wait_and_verify_runtime",
        lambda *_a, **_k: {"web-ui": {"container_id": "u"}, "web-query": {"container_id": "q"}},
    )
    monkeypatch.setattr(deploy, "verify_read_only_http", lambda *_a, **_k: None)
    monkeypatch.setattr(deploy, "scheduler_identity", lambda _root: NEW)
    monkeypatch.setattr(deploy, "_scheduler_release_records", lambda: [_start_pass(NEW, "f" * 64)])
    got_images, containers, rebaseline = deploy._deployed_baseline(tmp_path, object(), {"scheduler_identity": OLD})
    assert got_images is images
    assert containers == {"web-ui": "u", "web-query": "q"}
    assert rebaseline["to_container_id"] == "98d1f84c"

    monkeypatch.setattr(deploy, "_scheduler_release_records", lambda: [])
    with pytest.raises(WebReleaseError, match="lacks a START_PASS"):
        deploy._deployed_baseline(tmp_path, object(), {"scheduler_identity": OLD})


def test_real_scheduler_audit_backs_the_current_production_container():
    """只读：真实发布审计哈希链有效，且含 10-22 新候选容器的 START_PASS。"""
    records = deploy._scheduler_release_records()
    starts = [r for r in records if r.get("event") == "START_PASS"]
    assert any(str(r["details"].get("container_id", "")).startswith("98d1f84c") for r in starts)
