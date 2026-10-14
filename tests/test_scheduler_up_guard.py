import json
from pathlib import Path

from shaiwei import scheduler_up_guard as guard

RUNNING = "sha256:" + "7" * 64
CANDIDATE = "sha256:" + "b" * 64


def _audit(tmp_path: Path, *events: tuple[str, str]) -> Path:
    path = tmp_path / "audit.jsonl"
    lines = [json.dumps({"event": event, "details": {"image_id": image}}) for event, image in events]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_allow_when_alias_matches_running_container():
    verdict = guard.decide(tag_image=RUNNING, container_images=[RUNNING], last_started=RUNNING)
    assert verdict["decision"] == "ALLOW"


def test_refuse_when_alias_drifted_to_unstarted_candidate():
    verdict = guard.decide(tag_image=CANDIDATE, container_images=[RUNNING], last_started=RUNNING)
    assert verdict["decision"] == "REFUSE"
    assert "replace production" in verdict["reason"]
    assert verdict["current_image_id"] == CANDIDATE[:19]


def test_without_container_only_last_start_pass_image_is_allowed():
    assert guard.decide(tag_image=RUNNING, container_images=[], last_started=RUNNING)["decision"] == "ALLOW"
    assert guard.decide(tag_image=CANDIDATE, container_images=[], last_started=RUNNING)["decision"] == "REFUSE"
    assert guard.decide(tag_image=CANDIDATE, container_images=[], last_started=None)["decision"] == "REFUSE"
    assert guard.decide(tag_image=None, container_images=[], last_started=RUNNING)["decision"] == "REFUSE"


def test_last_start_pass_is_taken_from_audit_chain(tmp_path: Path):
    path = _audit(tmp_path, ("BUILD_PASS", CANDIDATE), ("START_PASS", RUNNING), ("PROMOTE_PASS", CANDIDATE))
    assert guard.last_started_image_id(path) == RUNNING
    assert guard.last_started_image_id(tmp_path / "missing.jsonl") is None


def test_main_refuses_current_production_drift(monkeypatch, tmp_path: Path, capsys):
    def fake_docker(args):
        if args[:2] == ["image", "inspect"]:
            return CANDIDATE
        if args[0] == "ps":
            return "abc123"
        return RUNNING

    monkeypatch.setattr(guard, "docker_query", fake_docker)
    code = guard.main(["--audit", str(_audit(tmp_path, ("START_PASS", RUNNING)))])
    out = json.loads(capsys.readouterr().out)
    assert code == 2
    assert out["decision"] == "REFUSE"
    assert out["container_image_ids"] == [RUNNING[:19]]


def test_main_allows_consistent_state(monkeypatch, tmp_path: Path, capsys):
    def fake_docker(args):
        if args[:2] == ["image", "inspect"]:
            return RUNNING
        if args[0] == "ps":
            return "abc123"
        return RUNNING

    monkeypatch.setattr(guard, "docker_query", fake_docker)
    assert guard.main(["--audit", str(_audit(tmp_path, ("START_PASS", RUNNING)))]) == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "ALLOW"
