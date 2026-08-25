from pathlib import Path
import json
import os
import subprocess
import sys

import pytest
import yaml

import shaiwei.runtime_lock_fixture as fixture
from shaiwei.runtime_lock_fixture_payloads import THREAD_NOOP_FLOCK


ROOT = Path(__file__).parents[1]
SCOPE = "a" * 64
HEAD = "b" * 40
SNAPSHOT = "c" * 64


def _spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> fixture.FixtureSpec:
    prefix = tmp_path / "runtime-lock-fixture-r2c"
    monkeypatch.setattr(fixture, "OUTPUT_PREFIX", prefix)
    return fixture.FixtureSpec(
        image=f"shaiwei:scheduler-{SNAPSHOT[:16]}",
        expected_head=HEAD,
        expected_snapshot=SNAPSHOT,
        scope_sha256=SCOPE,
        output_root=prefix / SCOPE[:16],
    )


def _contract() -> dict:
    return yaml.safe_load(
        (ROOT / "config/r2_1r0l_b_r2c_named_volume_fixture_v1.yaml").read_text(
            encoding="utf-8"
        )
    )


def _recovery_contract() -> dict:
    return yaml.safe_load(
        (ROOT / "config/r2_1r0l_b_r2c_r1_fixture_entry_recovery_v1.yaml").read_text(
            encoding="utf-8"
        )
    )


def test_frozen_contract_is_nonexecuting_and_complete():
    document = _contract()
    assert document["status"] == "FROZEN_RELEASE_ENGINEERING_NOT_EXECUTION_APPROVAL"
    assert document["fixture"]["execution_authorized"] is False
    assert document["fixture"]["same_scope_rerun_authorized"] is False
    assert document["fixture"]["network_mode"] == "none"
    assert document["source"]["candidate_build_count"] == 1
    assert document["authority"]["production_authorization"] == "none"
    assert document["authority"]["env_or_secret_read_authorized"] is False
    assert document["authority"]["real_business_run_or_backfill_authorized"] is False


def test_recovery_contract_changes_only_candidate_native_thread_entry():
    document = _recovery_contract()
    assert document["status"] == "FROZEN_ENGINEERING_NOT_EXECUTION_APPROVAL"
    assert document["predecessor"]["same_scope_rerun_authorized"] is False
    assert document["recovery"]["changed_case"] == "eight_threads_with_noop_flock"
    assert document["recovery"]["explicit_lock_root_argument_forbidden"] is True
    assert document["recovery"]["unchanged_case_count"] == 9
    assert document["engineering"]["docker_build_authorized"] is False
    assert document["engineering"]["docker_fixture_authorized"] is False
    assert document["successor"]["action"] == fixture.ACTION
    assert document["successor"]["exact_user_approval_required"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("image", "shaiwei:scheduler-free-text"),
        ("expected_head", "short"),
        ("expected_snapshot", "z" * 64),
        ("scope_sha256", "0" * 63),
        ("lock_volume", "other-volume"),
    ],
)
def test_spec_identity_drift_fails_before_output_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: str
):
    spec = _spec(tmp_path, monkeypatch)
    changed = {**spec.__dict__, field: value}
    with pytest.raises(fixture.FixtureError):
        fixture.FixtureSpec(**changed).validate()
    assert not spec.output_root.exists()


def test_fixture_claim_precedes_cases_and_report_matches_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    spec = _spec(tmp_path, monkeypatch)
    client = fixture.DockerClient(lambda *_args, **_kwargs: None)  # never called

    def identity(_client, current):
        assert (current.output_root / "claim.json").is_file()
        assert _client.command_count == 0
        return {
            "image_id": "sha256:" + "d" * 64,
            "snapshot": SNAPSHOT,
            "head": HEAD,
            "lock_authority": "docker-named-volume-v1",
        }

    monkeypatch.setattr(fixture, "_image_identity", identity)
    for name in (
        "_thread_concurrency",
        "_timeline_processes",
        "_container_matrix",
        "_sigkill_release",
        "_ledger_concurrency",
        "_missing_mount",
        "_readonly_mount",
        "_wrong_volume_metadata",
        "_resource_failures",
    ):
        monkeypatch.setattr(fixture, name, lambda *_args: None)

    report = fixture.execute(spec, client=client)

    assert report["verdict"] == "PASS"
    assert report["command_count"] == 0
    assert [row["case"] for row in report["cases"]] == _contract()["fixture"][
        "required_cases"
    ]
    assert all(row["status"] == "PASS" for row in report["cases"])
    assert len(report["report_sha256"]) == 64
    assert len(report["evidence_tree_sha256"]) == 64
    assert (spec.output_root / "tree.json").is_file()


def test_failure_is_persisted_and_same_scope_cannot_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    spec = _spec(tmp_path, monkeypatch)
    monkeypatch.setattr(
        fixture,
        "_image_identity",
        lambda *_args: {
            "image_id": "sha256:" + "d" * 64,
            "snapshot": SNAPSHOT,
            "head": HEAD,
            "lock_authority": "docker-named-volume-v1",
        },
    )
    monkeypatch.setattr(
        fixture,
        "_thread_concurrency",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("synthetic failure")),
    )
    with pytest.raises(fixture.FixtureError, match="failed closed"):
        fixture.execute(spec, client=fixture.DockerClient())
    report = yaml.safe_load((spec.output_root / "report.json").read_text(encoding="utf-8"))
    assert report["verdict"] == "FAIL"
    assert report["error_type"] == "RuntimeError"
    with pytest.raises(fixture.FixtureError, match="cannot be rerun"):
        spec.validate()


def test_candidate_command_has_only_frozen_security_and_synthetic_mounts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    spec = _spec(tmp_path, monkeypatch)
    spec.output_root.mkdir(parents=True)
    seen = []

    def runner(argv, **_kwargs):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    fixture._candidate_run(fixture.DockerClient(runner), spec, ["python", "-V"])
    command = seen[0]
    rendered = " ".join(command)
    assert command[:3] == ["docker", "run", "--rm"]
    assert "--network none" in rendered
    assert "--read-only" in command
    assert "--cap-drop ALL" in rendered
    assert "no-new-privileges" in rendered
    assert "shaiwei_runtime_locks_v1" in rendered
    assert "/run/shaiwei-locks" in rendered and "/fixture" in rendered
    assert ",rw" not in rendered
    assert ".env" not in rendered and "docker.sock" not in rendered
    assert "/workspace/data" not in rendered and "/workspace/logs" not in rendered

    readonly = " ".join(fixture._runtime_args(spec, lock_mode="ro"))
    assert "readonly" in readonly
    with pytest.raises(fixture.FixtureError, match="unknown fixture lock mount mode"):
        fixture._runtime_args(spec, lock_mode="invalid")


def test_candidate_native_thread_payload_runs_without_explicit_root(tmp_path: Path):
    assert "lock_root" not in THREAD_NOOP_FLOCK
    assert "logical_lock(DAILY_CYCLE)" in THREAD_NOOP_FLOCK
    assert "ThreadPoolExecutor(max_workers=8)" in THREAD_NOOP_FLOCK
    assert "backend.fcntl.flock=lambda" in THREAD_NOOP_FLOCK
    env = os.environ.copy()
    env.pop("SHAIWEI_LOCK_AUTHORITY", None)
    env.pop("SHAIWEI_RELEASE_MANIFEST", None)
    env["SHAIWEI_LOCK_ROOT"] = str(tmp_path / "locks")
    result = subprocess.run(
        [sys.executable, "-c", THREAD_NOOP_FLOCK],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert json.loads(result.stdout) == {
        "explicit_root": False,
        "maximum_active": 1,
        "threads": 8,
    }


def test_thread_case_uses_candidate_native_payload_and_real_volume_command_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    spec = _spec(tmp_path, monkeypatch)
    spec.output_root.mkdir(parents=True)
    seen = []

    def runner(argv, **_kwargs):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    fixture._thread_concurrency(fixture.DockerClient(runner), spec)
    assert len(seen) == 1
    command = seen[0]
    rendered = " ".join(command)
    assert command[-3:] == ["python", "-c", THREAD_NOOP_FLOCK]
    assert "pytest" not in command and "test_interprocess_lock" not in rendered
    assert "SHAIWEI_LOCK_AUTHORITY=docker-named-volume-v1" in command
    assert "type=volume,src=shaiwei_runtime_locks_v1,dst=/run/shaiwei-locks" in command
    assert "--network none" in rendered and "--read-only" in command


def test_preexisting_container_is_rejected_without_cleanup():
    seen = []

    def runner(argv, **_kwargs):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="existing-id\n", stderr="")

    with pytest.raises(fixture.FixtureError, match="already exists"):
        fixture._require_container_absent(fixture.DockerClient(runner), "scope-holder")
    assert seen == [
        ["docker", "container", "inspect", "--format", "{{.Id}}", "scope-holder"]
    ]
    assert all(command[:3] != ["docker", "rm", "-f"] for command in seen)


def test_fixture_modules_stay_within_normal_file_budget():
    paths = [
        ROOT / "src/shaiwei/runtime_lock_fixture.py",
        ROOT / "src/shaiwei/runtime_lock_fixture_payloads.py",
    ]
    lines = {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in paths}
    assert lines["runtime_lock_fixture.py"] <= 400
    assert lines["runtime_lock_fixture_payloads.py"] <= 100
