import json
from pathlib import Path
from types import SimpleNamespace

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


def test_image_verification_binds_runtime_snapshot_and_revision(monkeypatch):
    metadata = {
        "image": "shaiwei:scheduler-fixed",
        "image_id": "sha256:fixed",
        "code_snapshot_sha256": "a" * 64,
        "git_head": "b" * 40,
    }
    monkeypatch.setattr(release, "_image_metadata", lambda _image: metadata)
    monkeypatch.setattr(
        release,
        "_image_runtime_identity",
        lambda _image: {
            "code_snapshot_sha256": "a" * 64,
            "git_head": "b" * 40,
        },
    )
    assert release.verify_image("shaiwei:scheduler-fixed") == metadata

    monkeypatch.setattr(
        release,
        "_image_runtime_identity",
        lambda _image: {
            "code_snapshot_sha256": "a" * 64,
            "git_head": "c" * 40,
        },
    )
    with pytest.raises(release.ReleaseError, match="runtime identity differ"):
        release.verify_image("shaiwei:scheduler-fixed")


def test_container_contract_never_requests_environment(monkeypatch):
    expected = {
        "image_id": "sha256:fixed",
        "code_snapshot_sha256": "a" * 64,
        "git_head": "b" * 40,
    }
    requests = []

    def fake_run(argv, *, check=True):
        requests.append(argv)
        if argv[:3] == ["docker", "inspect", "--format"]:
            assert ".Config.Env" not in argv[3]
            mounts = json.dumps(
                [
                    {"Destination": "/workspace/data", "RW": True},
                    {"Destination": "/workspace/ledger", "RW": True},
                    {"Destination": "/workspace/logs", "RW": True},
                ]
            )
            return SimpleNamespace(stdout=f"sha256:fixed\ttrue\t{mounts}\n")
        return SimpleNamespace(
            stdout=json.dumps(
                {
                    "code_snapshot_sha256": "a" * 64,
                    "git_head": "b" * 40,
                }
            )
            + "\n"
        )

    monkeypatch.setattr(release, "_compose_container_id", lambda: "scheduler-id")
    monkeypatch.setattr(release, "_run", fake_run)

    contract = release._container_contract(expected)

    assert contract["read_only_rootfs"] is True
    assert contract["mount_destinations"] == [
        "/workspace/data",
        "/workspace/ledger",
        "/workspace/logs",
    ]
    assert all(".Config.Env" not in " ".join(request) for request in requests)


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


def _runtime_csv(path, header, rows):
    path.write_text(
        ",".join(header)
        + "\n"
        + "".join(",".join(row.get(field, "") for field in header) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_cross_snapshot_start_requires_a_newer_trade_date(tmp_path):
    paper = tmp_path / "paper_runs.csv"
    daily = tmp_path / "daily_runs.csv"
    _runtime_csv(
        paper,
        ["status", "execution_trade_date", "finished_at", "code_snapshot_sha256"],
        [
            {
                "status": "PASS",
                "execution_trade_date": "20260723",
                "finished_at": "2026-07-23T12:00:00+00:00",
                "code_snapshot_sha256": "a" * 64,
            }
        ],
    )
    _runtime_csv(
        daily,
        ["status", "target_trade_date", "finished_at"],
        [
            {
                "status": "PASS",
                "target_trade_date": "20260723",
                "finished_at": "2026-07-23T11:00:00+00:00",
            }
        ],
    )

    with pytest.raises(release.ReleaseError, match="unsafe before a newer"):
        release.release_start_readiness(
            "b" * 64,
            paper_runs_path=paper,
            daily_runs_path=daily,
            plan_loader=lambda: SimpleNamespace(missing_trade_dates=()),
        )
    evidence = release.release_start_readiness(
        "b" * 64,
        paper_runs_path=paper,
        daily_runs_path=daily,
        plan_loader=lambda: SimpleNamespace(missing_trade_dates=("20260724",)),
    )
    assert evidence["mode"] == "CROSS_SNAPSHOT_WITH_NEW_DATA"
    assert evidence["available_new_trade_dates"] == ["20260724"]


def test_cross_snapshot_restart_can_resume_after_daily_pass(tmp_path):
    paper = tmp_path / "paper_runs.csv"
    daily = tmp_path / "daily_runs.csv"
    _runtime_csv(
        paper,
        ["status", "execution_trade_date", "finished_at", "code_snapshot_sha256"],
        [
            {
                "status": "PASS",
                "execution_trade_date": "20260723",
                "finished_at": "2026-07-23T12:00:00+00:00",
                "code_snapshot_sha256": "a" * 64,
            }
        ],
    )
    _runtime_csv(
        daily,
        ["status", "target_trade_date", "finished_at"],
        [
            {
                "status": "PASS",
                "target_trade_date": "20260724",
                "finished_at": "2026-07-24T12:00:00+00:00",
            }
        ],
    )

    evidence = release.release_start_readiness(
        "b" * 64,
        paper_runs_path=paper,
        daily_runs_path=daily,
        plan_loader=lambda: SimpleNamespace(missing_trade_dates=()),
    )
    assert evidence["available_new_trade_dates"] == ["20260724"]


def test_same_release_restart_does_not_require_new_data(tmp_path):
    paper = tmp_path / "paper_runs.csv"
    daily = tmp_path / "daily_runs.csv"
    _runtime_csv(
        paper,
        ["status", "execution_trade_date", "finished_at", "code_snapshot_sha256"],
        [
            {
                "status": "PASS",
                "execution_trade_date": "20260723",
                "finished_at": "2026-07-23T12:00:00+00:00",
                "code_snapshot_sha256": "a" * 64,
            }
        ],
    )
    _runtime_csv(daily, ["status", "target_trade_date", "finished_at"], [])

    evidence = release.release_start_readiness(
        "a" * 64,
        paper_runs_path=paper,
        daily_runs_path=daily,
        plan_loader=lambda: (_ for _ in ()).throw(AssertionError("plan must not load")),
    )
    assert evidence["mode"] == "SAME_RELEASE_RESTART"
