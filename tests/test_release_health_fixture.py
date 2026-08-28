from pathlib import Path
import hashlib
import json
import subprocess

import pytest
import yaml

from shaiwei import release
from shaiwei import release_health_fixture as fixture


ROOT = Path(__file__).parents[1]
HEAD = "a" * 40
SNAPSHOT = "b" * 64
SCOPE = "c" * 64


def _spec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> fixture.FixtureSpec:
    prefix = tmp_path / "r2d-r3a-health-fixture"
    monkeypatch.setattr(fixture, "OUTPUT_PREFIX", prefix)
    return fixture.FixtureSpec(
        image=f"shaiwei:scheduler-{SNAPSHOT[:16]}",
        expected_head=HEAD,
        expected_snapshot=SNAPSHOT,
        scope_sha256=SCOPE,
        expected_release_state_sha256="e" * 64,
        expected_release_audit_sha256="f" * 64,
        output_root=prefix / SCOPE[:16],
    )


def _bind_production_evidence(
    spec: fixture.FixtureSpec,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> fixture.FixtureSpec:
    state = tmp_path / "scheduler_state.json"
    audit = tmp_path / "scheduler_releases.jsonl"
    state.write_text("{\"state\":\"old\"}\n", encoding="utf-8")
    audit.write_text("{\"audit\":\"old\"}\n", encoding="utf-8")
    monkeypatch.setattr(release, "STATE_PATH", state)
    monkeypatch.setattr(release, "AUDIT_PATH", audit)
    return fixture.FixtureSpec(
        **{
            **spec.__dict__,
            "expected_release_state_sha256": hashlib.sha256(state.read_bytes()).hexdigest(),
            "expected_release_audit_sha256": hashlib.sha256(audit.read_bytes()).hexdigest(),
        }
    )


def _contract() -> dict[str, object]:
    return {
        "container_id": "fixture-container",
        "image_id": "sha256:" + "d" * 64,
        "code_snapshot_sha256": SNAPSHOT,
        "git_head": HEAD,
        "health": "healthy",
        "read_only_rootfs": True,
        "lock_authority": "docker-named-volume-v1",
        "mount_destinations": [
            "/run/shaiwei-locks",
            "/workspace/data",
            "/workspace/ledger",
            "/workspace/logs",
        ],
    }


def test_fixture_compose_is_isolated_and_matches_production_health_contract() -> None:
    production = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))["services"][
        "scheduler"
    ]
    document = yaml.safe_load(
        (ROOT / "compose.r2d-r3a-health-fixture.yaml").read_text(encoding="utf-8")
    )
    service = document["services"]["scheduler"]

    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert service["healthcheck"]["test"] == production["healthcheck"]["test"]
    assert service["healthcheck"]["start_interval"] == production["healthcheck"]["start_interval"]
    assert service["healthcheck"]["start_period"] == production["healthcheck"]["start_period"]
    assert "env_file" not in service and "build" not in service
    assert {item["target"] for item in service["volumes"]} == {
        "/run/shaiwei-locks",
        "/workspace/data",
        "/workspace/ledger",
        "/workspace/logs",
    }
    rendered = json.dumps(document)
    assert ".env" not in rendered
    assert "docker.sock" not in rendered
    assert "shaiwei_runtime_locks_v1" in rendered


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("image", "shaiwei:scheduler-free-text"),
        ("expected_head", "short"),
        ("expected_snapshot", "z" * 64),
        ("scope_sha256", "0" * 63),
        ("expected_release_state_sha256", "0" * 63),
        ("expected_release_audit_sha256", "z" * 64),
    ],
)
def test_spec_identity_drift_fails_before_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
) -> None:
    spec = _spec(tmp_path, monkeypatch)
    changed = {**spec.__dict__, field: value}
    with pytest.raises(fixture.FixtureError):
        fixture.FixtureSpec(**changed).validate()
    assert not spec.output_root.exists()


def test_compose_command_disables_project_dotenv_and_uses_isolated_project() -> None:
    command = fixture._compose_command("shaiwei-r2d-r3a-fixed", "up", "-d", "scheduler")
    assert command[:4] == ["docker", "compose", "--env-file", "/dev/null"]
    assert "--project-name" in command
    assert "shaiwei-r2d-r3a-fixed" in command
    assert str(fixture.COMPOSE_PATH) in command


def test_execute_claims_first_converges_and_never_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _bind_production_evidence(_spec(tmp_path, monkeypatch), tmp_path, monkeypatch)

    def metadata(_image):
        assert (spec.output_root / "claim.json").is_file()
        return {
            "image": spec.image,
            "image_id": "sha256:" + "d" * 64,
            "code_snapshot_sha256": SNAPSHOT,
            "git_head": HEAD,
            "lock_authority": "docker-named-volume-v1",
        }

    monkeypatch.setattr(release, "_image_metadata", metadata)
    monkeypatch.setattr(release, "_wait_scheduler_contract", lambda *_args, **_kwargs: _contract())
    monkeypatch.setattr(fixture, "_docker_health", lambda *_args: "starting")

    seen: list[tuple[list[str], dict[str, str] | None]] = []

    def runner(argv, **kwargs):
        seen.append((argv, kwargs.get("env")))
        if "ps" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout="fixture-container\n", stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    report = fixture.execute(spec, client=fixture.DockerClient(runner))

    assert report["verdict"] == "PASS"
    assert report["production_identity_unchanged"] is True
    assert [row["case"] for row in report["cases"]] == [
        "production_release_evidence_matches_scope",
        "candidate_image_labels",
        "docker_health_starting_observed",
        "shared_release_contract_converged",
        "guard_success_path_without_rollback",
        "production_release_evidence_unchanged",
    ]
    assert (spec.output_root / "claim.json").is_file()
    assert (spec.output_root / "report.json").is_file()
    assert (spec.output_root / "tree.json").is_file()
    assert (spec.output_root / "receipt.json").is_file()
    assert any("up" in command for command, _env in seen)
    assert any("down" in command for command, _env in seen)
    assert any("--pull" in command and "never" in command for command, _env in seen)
    for command, environment in seen:
        if command[:2] == ["docker", "compose"]:
            assert environment is not None
            assert "TUSHARE_TOKEN" not in environment
            assert ".env" not in " ".join(command)


def test_production_evidence_drift_fails_before_docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _spec(tmp_path, monkeypatch)
    state = tmp_path / "scheduler_state.json"
    audit = tmp_path / "scheduler_releases.jsonl"
    state.write_text("current-state\n", encoding="utf-8")
    audit.write_text("current-audit\n", encoding="utf-8")
    monkeypatch.setattr(release, "STATE_PATH", state)
    monkeypatch.setattr(release, "AUDIT_PATH", audit)
    monkeypatch.setattr(
        release,
        "_image_metadata",
        lambda _image: pytest.fail("image metadata must not be read after scope drift"),
    )

    def runner(_argv, **_kwargs):
        pytest.fail("Docker must not run after production evidence scope drift")

    client = fixture.DockerClient(runner)
    with pytest.raises(fixture.FixtureError, match="failed closed"):
        fixture.execute(spec, client=client)

    report = json.loads((spec.output_root / "report.json").read_text(encoding="utf-8"))
    assert report["error_type"] == "FixtureError"
    assert report["production_identity_unchanged"] is True
    assert client.command_count == 0


def test_failure_is_persisted_and_same_scope_cannot_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _bind_production_evidence(_spec(tmp_path, monkeypatch), tmp_path, monkeypatch)
    monkeypatch.setattr(
        release,
        "_image_metadata",
        lambda _image: (_ for _ in ()).throw(release.ReleaseError("synthetic identity failure")),
    )
    with pytest.raises(fixture.FixtureError, match="failed closed"):
        fixture.execute(spec, client=fixture.DockerClient())

    report = json.loads((spec.output_root / "report.json").read_text(encoding="utf-8"))
    assert report["verdict"] == "FAIL"
    assert report["error_type"] == "ReleaseError"
    with pytest.raises(fixture.FixtureError, match="cannot be rerun"):
        spec.validate()


def test_frozen_protocol_is_nonexecuting_and_complete() -> None:
    document = yaml.safe_load(
        (ROOT / "config/r2d_r3a_health_convergence_fixture_v1.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert document["status"] == "FROZEN_ENGINEERING_NOT_EXECUTION_APPROVAL"
    assert document["predecessor"]["same_scope_rerun_authorized"] is False
    assert document["fixture"]["candidate_build_count"] == 1
    assert document["fixture"]["suite_invocation_count"] == 1
    assert document["fixture"]["project_dotenv_forbidden"] is True
    assert document["fixture"]["implicit_image_pull_forbidden"] is True
    assert document["fixture"]["external_network_authorized"] is False
    assert document["fixture"]["env_or_secret_read_authorized"] is False
    assert document["fixture"]["production_release_evidence_hashes_required"] is True
    assert document["engineering"]["docker_build_authorized"] is False
    assert document["engineering"]["docker_fixture_authorized"] is False
    assert document["engineering"]["production_authorization"] == "none"
    assert document["successor"]["exact_user_approval_required"] is True


def test_compose_up_failure_still_cleans_isolated_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _bind_production_evidence(_spec(tmp_path, monkeypatch), tmp_path, monkeypatch)
    monkeypatch.setattr(
        release,
        "_image_metadata",
        lambda _image: {
            "image": spec.image,
            "image_id": "sha256:" + "d" * 64,
            "code_snapshot_sha256": SNAPSHOT,
            "git_head": HEAD,
            "lock_authority": "docker-named-volume-v1",
        },
    )
    seen: list[list[str]] = []

    def runner(argv, **_kwargs):
        seen.append(argv)
        if "up" in argv:
            raise subprocess.CalledProcessError(1, argv, stderr="synthetic up failure")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    with pytest.raises(fixture.FixtureError, match="failed closed"):
        fixture.execute(spec, client=fixture.DockerClient(runner))

    assert any("up" in command for command in seen)
    assert any("down" in command for command in seen)
    report = json.loads((spec.output_root / "report.json").read_text(encoding="utf-8"))
    assert report["verdict"] == "FAIL"
    assert report["production_identity_unchanged"] is True


def test_fixture_module_stays_within_file_budget() -> None:
    assert len((ROOT / "src/shaiwei/release_health_fixture.py").read_text().splitlines()) <= 400
