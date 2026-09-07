"""Secret-free metadata and final-mutation adapters, entirely synthetic."""
import csv
import json
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from shaiwei import config, release, release_metadata as metadata
from shaiwei.ingest import catalog
from shaiwei.pipeline import daily
from shaiwei.r2d_metadata_environment import SecureEnvironment
from shaiwei.storage.runtime_mount_contract import RuntimeMountContractError
from test_r2d_release_guard import local
from test_release import _runtime_csv


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def paper(tmp_path):
    row = {key: "synthetic" for key in metadata.FORWARD_FIELDS}
    row.update(account_id="model_baseline", execution_trade_date="20260826",
               finished_at="2026-08-26T09:00:00+00:00", operator="docker-scheduler",
               freshness_status="PASS", status="PASS", artifact_path="data/paper/model_baseline/runs/synthetic.json")
    document = {key: row[key] for key in metadata.FORWARD_FIELDS[:9]}
    document.update(mode="FORWARD", result={"nav": "effect-sentinel-do-not-project"})
    artifact = tmp_path / row["artifact_path"]
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps(document))
    row["artifact_sha256"] = metadata.sha256(artifact)
    write_rows(tmp_path / "ledger/paper_runs.csv", [row])
    return tmp_path, row, document


def test_forward_projection_excludes_effects(paper):
    result = metadata.latest_forward("model_baseline", paper[0])
    assert result["artifact_verified"] == "true"
    assert result["mode"] == "FORWARD"
    assert set(result) == set(metadata.FORWARD_FIELDS) | {"mode", "artifact_verified"}
    assert "effect-sentinel" not in json.dumps(result)


@pytest.mark.parametrize("kind", ["hash", "backfill", "identity", "operator", "freshness"])
def test_forward_fails_closed(paper, kind):
    root, row, document = paper
    if kind == "operator":
        row["operator"] = "manual"
    elif kind == "freshness":
        row["freshness_status"] = "FAIL"
    else:
        if kind == "backfill":
            document["mode"] = "BACKFILL"
        else:
            document["code_snapshot_sha256"] = "different"
        (root / row["artifact_path"]).write_text(json.dumps(document))
        if kind != "hash":
            row["artifact_sha256"] = metadata.sha256(root / row["artifact_path"])
    write_rows(root / "ledger/paper_runs.csv", [row])
    with pytest.raises(metadata.MetadataError):
        metadata.latest_forward("model_baseline", root)


@pytest.mark.parametrize("path", ["../outside", "/absolute", ""])
def test_confined_paths_reject_escape(tmp_path, path):
    with pytest.raises(metadata.MetadataError):
        metadata.confined(tmp_path, path)


def test_confined_paths_reject_symlink(tmp_path):
    (tmp_path / "target").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "target", target_is_directory=True)
    with pytest.raises(metadata.MetadataError):
        metadata.confined(tmp_path, "link/file")


def test_plan_reuses_daily_without_credentials(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    daily_settings = dict(poll_seconds=60, ready_hour=16, ready_minute=0,
        source_deadline_hour=19, source_deadline_minute=0, max_catchup_trade_days=5,
        min_market_rows=1000, health_stale_seconds=3600)
    (tmp_path / "config/settings.yaml").write_text(yaml.safe_dump({"daily": daily_settings}))
    rows = [{"source_api": api, "params_json": '{"end_date":"20260825"}'}
            for api in daily.REQUIRED_BOOTSTRAP_APIS]
    write_rows(tmp_path / "ledger/ingest_batches.csv", rows)
    write_rows(tmp_path / "ledger/daily_runs.csv",
               [{"status": "PASS", "target_trade_date": "20260826"}])
    calendar = pd.DataFrame({"cal_date": ["20260826", "20260827"], "is_open": ["1", "1"]})
    calls = []
    def calendar_only(api, **kwargs):
        calls.append((api, kwargs))
        return calendar
    monkeypatch.setattr(catalog, "load_latest_api", calendar_only)
    def forbidden(*args, **kwargs):
        pytest.fail("credential loader used")
    monkeypatch.setattr(config, "load", forbidden)
    monkeypatch.setattr(config, "load_dotenv", forbidden)
    plan = metadata.load_plan(local(27, 16, 5), tmp_path)
    assert plan.missing_trade_dates == ("20260827",)
    assert calls == [("tushare.trade_cal",
                      {"ledger_path": tmp_path / "ledger/ingest_batches.csv"})]


def test_default_readiness_uses_secret_free_loader(tmp_path, monkeypatch):
    paper, daily_path = tmp_path / "paper.csv", tmp_path / "daily.csv"
    _runtime_csv(paper, ["status", "execution_trade_date", "finished_at",
                        "code_snapshot_sha256"],
                 [{"status": "PASS", "execution_trade_date": "20260826",
                   "finished_at": "x", "code_snapshot_sha256": "a" * 64}])
    _runtime_csv(daily_path, ["status", "target_trade_date", "finished_at"], [])
    def forbidden(*args, **kwargs):
        pytest.fail("credential loader used")
    monkeypatch.setattr(config, "load", forbidden)
    monkeypatch.setattr(config, "load_dotenv", forbidden)
    monkeypatch.setattr(metadata, "load_plan",
                        lambda _: SimpleNamespace(missing_trade_dates=("20260827",)))
    result = release.release_start_readiness("b" * 64,
                                             paper_runs_path=paper, daily_runs_path=daily_path)
    assert result["available_new_trade_dates"] == ["20260827"]


@pytest.fixture
def docker_metadata(tmp_path, monkeypatch):
    value = {"id": "c" * 64, "image": "sha256:" + "b" * 64, "running": True,
             "restart": 0, "health": "healthy", "readonly": True,
             "mounts": [{"Type": "bind", "Destination": "/workspace/" + name,
                         "Source": str(tmp_path / name), "RW": True}
                        for name in ("data", "ledger", "logs")] +
                       [{"Type": "volume", "Destination": "/run/shaiwei-locks",
                         "Name": "shaiwei_runtime_locks_v1", "RW": True}]}
    calls = []
    env = SecureEnvironment(tmp_path, "synthetic")
    def run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(stdout=value["id"] if argv[1] == "ps" else json.dumps(value))
    env._run = run
    monkeypatch.setattr(release, "_image_metadata", lambda _: {
        "code_snapshot_sha256": "a" * 64, "git_head": "b" * 40})
    return env, value, calls


def test_targeted_inspect_has_no_env_or_compose(docker_metadata):
    env, _, calls = docker_metadata
    observed = env.running_scheduler()
    assert observed.restart_count == 0
    assert len(observed.mount_destinations) == 4
    assert "Config.Env" not in str(calls) and "compose" not in calls[0]
    assert "label=com.docker.compose.project=synthetic" in calls[0]


@pytest.mark.parametrize("kind", ["source", "lock", "duplicate", "readonly", "type"])
def test_exact_mount_sources_and_identity(docker_metadata, kind):
    env, value, _ = docker_metadata
    if kind == "source":
        value["mounts"][0]["Source"] += "-other"
    elif kind == "lock":
        value["mounts"][-1]["Name"] = "other-volume"
    elif kind == "duplicate":
        value["mounts"].append(value["mounts"][0])
    elif kind == "readonly":
        value["mounts"][0]["RW"] = False
    else:
        value["mounts"][0]["Type"] = "volume"
    with pytest.raises((RuntimeError, ValueError, RuntimeMountContractError)):
        env.running_scheduler()


def test_image_metadata_requests_only_three_labels(monkeypatch):
    calls = []
    def run(argv):
        calls.append(argv)
        return SimpleNamespace(stdout='[{"Id":"synthetic","Config":{"Labels":{}}}]')
    monkeypatch.setattr(release, "_run", run)
    release._image_document("synthetic")
    assert "--format" in calls[0]
    assert "{{json .Config.Labels}}" not in calls[0][-2]
    assert "Config.Env" not in str(calls)
    for label in (release.SNAPSHOT_LABEL, release.REVISION_LABEL, release.LOCK_AUTHORITY_LABEL):
        assert label in calls[0][-2]


@pytest.mark.parametrize("fail_on", [1, 2])
def test_low_level_checks_immediately_before_each_mutation(monkeypatch, fail_on):
    calls, checks = [], []
    monkeypatch.setattr(release, "_load_state", lambda: {"current": {
        "image": "synthetic", "code_snapshot_sha256": "a" * 64}})
    monkeypatch.setattr(release, "release_start_readiness", lambda _: {})
    monkeypatch.setattr(release, "_tag", lambda *_: calls.append("tag"))
    monkeypatch.setattr(release, "_run", lambda *_: pytest.fail("Docker dispatched"))
    def check():
        checks.append(True)
        if len(checks) == fail_on:
            raise ValueError("deadline crossed")
    with pytest.raises(ValueError, match="deadline crossed"):
        release.start_current(before_mutation=check, compose_project="synthetic")
    assert calls == ([] if fail_on == 1 else ["tag"])


def test_start_pins_compose_project_and_wait_container(monkeypatch):
    calls = []
    monkeypatch.setattr(release, "_load_state", lambda: {"current": {
        "image": "synthetic", "code_snapshot_sha256": "a" * 64}})
    monkeypatch.setattr(release, "release_start_readiness", lambda _: {})
    monkeypatch.setattr(release, "_tag", lambda *_: None)
    def run(argv):
        calls.append(argv)
        return SimpleNamespace(stdout="c" * 64)
    monkeypatch.setattr(release, "_run", run)
    def wait(expected, **kwargs):
        assert kwargs == {"container_id": "c" * 64}
        return {}
    monkeypatch.setattr(release, "_wait_scheduler_contract", wait)
    monkeypatch.setattr(release, "_append_audit", lambda *_: {"record_sha256": "a" * 64})
    release.start_current(before_mutation=lambda: None, compose_project="synthetic")
    assert all(call[:4] == ["docker", "compose", "-p", "synthetic"] for call in calls)


def test_legacy_image_missing_lock_label_remains_legacy(monkeypatch):
    monkeypatch.setattr(release, "_image_document", lambda _: {
        "Id": "sha256:" + "a" * 64, "Config": {"Labels": {
            release.SNAPSHOT_LABEL: "a" * 64, release.REVISION_LABEL: "b" * 40,
            release.LOCK_AUTHORITY_LABEL: None}}})
    assert "lock_authority" not in release._image_metadata("synthetic")


def test_forward_rejects_secret_path_before_read(paper):
    root, row, _ = paper
    row["artifact_path"] = ".env"
    write_rows(root / "ledger/paper_runs.csv", [row])
    with pytest.raises(metadata.MetadataError, match="account run boundary"):
        metadata.latest_forward("model_baseline", root)
