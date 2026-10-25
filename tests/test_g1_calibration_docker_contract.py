"""G1 正控容器合同：断网、只读根、无密钥；每个服务在 v1、v2 两种协议取值下都只有协议允许的写入点。"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.g1-calibration.yaml"
ENVIRONMENTS = {
    "v1": {},  # 默认值即 v1
    "v2": {
        "SHAIWEI_G1_PROTOCOL": "config/g1_positive_control_v2.yaml",
        "SHAIWEI_G1_FAMILY": "g1-calibration-v2",
        "SHAIWEI_G1_REPORTS": "logs/g1-calibration-v2",
        "SHAIWEI_G1_PROTOCOL_DOC": "docs/G1_POSITIVE_CONTROL_V2_PROTOCOL_20261025.md",
    },
}
_VARIABLE = re.compile(r"\$\{(\w+)(?::-([^}]*))?(?::\?[^}]*)?\}")


def _render(value: str, env: dict[str, str]) -> str:
    return _VARIABLE.sub(lambda match: env.get(match.group(1), match.group(2) or f"<{match.group(1)}>"), value)


def _expected(version: str) -> dict[str, dict[str, set[str]]]:
    family = "g1-calibration-v2" if version == "v2" else "g1-calibration-v1"
    reports = "./logs/g1-calibration-v2" if version == "v2" else "./logs/g1-calibration"
    doc = "./docs/G1_POSITIVE_CONTROL_V2_PROTOCOL_20261025.md" if version == "v2" else "./docs/G1_POSITIVE_CONTROL_PROTOCOL_20261024.md"
    data, control = f"./data/research/{family}", f"./data/control/{family}"
    market = {"./data/qlib_bin", "./data/raw", "./ledger", "./vendor/alphagen"}
    return {
        "g1-calibration-pilot": {"read_only": market | {doc}, "writable": {data}},
        "g1-calibration-run": {
            "read_only": market | {doc, control},
            "writable": {"./ledger/experiments.csv", "./ledger/g1_calibration_runs.csv", data, reports},
        },
        "g1-calibration-audit": {"read_only": {"./ledger", doc, control, data, reports}, "writable": {f"{reports}-audit"}},
        "g1-calibration-devset": {
            "read_only": market | {"./docs/G1_POSITIVE_CONTROL_V2_PROTOCOL_20261025.md", "./data/research/g1-calibration-v1", "./logs/g1-calibration"},
            "writable": {"./logs/g1-calibration-v2/dev-set"},
        },
    }


def _document() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_every_service_is_offline_read_only_secret_free_and_writes_only_where_allowed():
    services = _document()["services"]
    for version, env in ENVIRONMENTS.items():
        expected = _expected(version)
        assert set(services) == set(expected)
        for name, service in services.items():
            assert service["network_mode"] == "none", name
            assert service["read_only"] is True and service["cap_drop"] == ["ALL"], name
            assert service["security_opt"] == ["no-new-privileges:true"], name
            assert service["pull_policy"] == "never" and service["restart"] == "no", name
            assert "env_file" not in service and "secrets" not in service, name
            assert not any(key.startswith(("FEISHU", "TUSHARE", "DEEPSEEK")) for key in service["environment"]), name
            binds = [volume for volume in service["volumes"] if volume["type"] == "bind"]
            assert all(volume["bind"]["create_host_path"] is False for volume in binds), name
            assert all(_render(volume["target"], env) == "/workspace/" + _render(volume["source"], env).removeprefix("./") for volume in binds), name
            read_only = {_render(volume["source"], env) for volume in binds if volume["read_only"]}
            writable = {_render(volume["source"], env) for volume in binds if not volume["read_only"]}
            assert read_only == expected[name]["read_only"], (version, name)
            assert writable == expected[name]["writable"], (version, name)


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
    for name in ("g1-calibration-pilot", "g1-calibration-audit", "g1-calibration-devset"):
        assert services[name]["user"] != "0:0"
        assert all(volume["type"] == "bind" for volume in services[name]["volumes"])
        assert "SHAIWEI_LOCK_AUTHORITY" not in services[name]["environment"]


def test_entrypoints_take_the_protocol_and_default_to_v1():
    services = _document()["services"]
    modules = {name: service["command"][2] for name, service in services.items()}
    assert modules == {
        "g1-calibration-pilot": "shaiwei.research.g1_calibration.pilot",
        "g1-calibration-run": "shaiwei.research.g1_calibration.execute",
        "g1-calibration-audit": "shaiwei.research.g1_calibration.audit",
        "g1-calibration-devset": "shaiwei.research.g1_calibration.devset",
    }
    for name in ("g1-calibration-pilot", "g1-calibration-run", "g1-calibration-audit"):
        command = services[name]["command"]
        protocol = command[command.index("--protocol") + 1]
        assert _render(protocol, {}) == "config/g1_positive_control_v1.yaml"
        assert _render(protocol, ENVIRONMENTS["v2"]) == "config/g1_positive_control_v2.yaml"
