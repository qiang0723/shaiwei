"""G1 正控容器合同：断网、只读根、无密钥；每个服务只有协议允许的写入点（协议 §8、§10）。"""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.g1-calibration.yaml"
PROTOCOL_DOC = "./docs/G1_POSITIVE_CONTROL_PROTOCOL_20261024.md"
CALIBRATION_DATA = "./data/research/g1-calibration-v1"
EXPECTED = {
    "g1-calibration-pilot": {
        "read_only": {"./data/qlib_bin", "./data/raw", "./ledger", "./vendor/alphagen", PROTOCOL_DOC},
        "writable": {CALIBRATION_DATA},
    },
    "g1-calibration-run": {
        "read_only": {"./data/qlib_bin", "./data/raw", "./ledger", "./vendor/alphagen", PROTOCOL_DOC, "./data/control/g1-calibration-v1"},
        "writable": {"./ledger/experiments.csv", "./ledger/g1_calibration_runs.csv", CALIBRATION_DATA, "./logs/g1-calibration"},
    },
    "g1-calibration-audit": {
        "read_only": {"./ledger", PROTOCOL_DOC, "./data/control/g1-calibration-v1", CALIBRATION_DATA, "./logs/g1-calibration"},
        "writable": {"./logs/g1-calibration-audit"},
    },
}


def _document() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_every_service_is_offline_read_only_secret_free_and_writes_only_where_allowed():
    services = _document()["services"]
    assert set(services) == set(EXPECTED)
    for name, service in services.items():
        assert service["network_mode"] == "none", name
        assert service["read_only"] is True and service["cap_drop"] == ["ALL"], name
        assert service["security_opt"] == ["no-new-privileges:true"], name
        assert service["pull_policy"] == "never" and service["restart"] == "no", name
        assert "env_file" not in service and "secrets" not in service, name
        assert not any(key.startswith(("FEISHU", "TUSHARE", "DEEPSEEK")) for key in service["environment"]), name
        binds = [volume for volume in service["volumes"] if volume["type"] == "bind"]
        assert all(volume["bind"]["create_host_path"] is False for volume in binds), name
        read_only = {volume["source"] for volume in binds if volume["read_only"]}
        writable = {volume["source"] for volume in binds if not volume["read_only"]}
        assert read_only == EXPECTED[name]["read_only"], name
        assert writable == EXPECTED[name]["writable"], name


def test_only_the_formal_run_shares_the_scheduler_lock_and_runs_as_root():
    document = _document()
    services = document["services"]
    run = services["g1-calibration-run"]
    assert run["user"] == "0:0"
    assert run["environment"]["SHAIWEI_LOCK_AUTHORITY"] == "docker-named-volume-v1"
    assert run["environment"]["SHAIWEI_LOCK_ROOT"] == "/run/shaiwei-locks"
    locks = [volume for volume in run["volumes"] if volume["type"] == "volume"]
    assert locks == [{"type": "volume", "source": "runtime-locks", "target": "/run/shaiwei-locks", "volume": {"nocopy": True}}]
    assert document["volumes"]["runtime-locks"] == {"external": True, "name": "shaiwei_runtime_locks_v1"}
    for name in ("g1-calibration-pilot", "g1-calibration-audit"):
        assert services[name]["user"] != "0:0"
        assert all(volume["type"] == "bind" for volume in services[name]["volumes"])
        assert "SHAIWEI_LOCK_AUTHORITY" not in services[name]["environment"]


def test_entrypoints_are_pilot_execute_and_audit():
    services = _document()["services"]
    modules = {name: service["command"][2] for name, service in services.items()}
    assert modules == {
        "g1-calibration-pilot": "shaiwei.research.g1_calibration.pilot",
        "g1-calibration-run": "shaiwei.research.g1_calibration.execute",
        "g1-calibration-audit": "shaiwei.research.g1_calibration.audit",
    }
    assert services["g1-calibration-run"]["command"][3] == "--scope"
