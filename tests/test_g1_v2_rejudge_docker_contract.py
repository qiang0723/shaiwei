"""g1-v2 重判容器合同：断网、只读根、无密钥；每个服务只有协议允许的写入点，v1 准入账本与 logs/g1 永不可写。"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.g1-v2-rejudge.yaml"
DOC = "./docs/G1_V2_HISTORICAL_REJUDGE_PROTOCOL_V2_20261025.md"
CONTROL = "./data/control/g1-v2-rejudge"
INPUTS = {"./data/qlib_bin", "./data/raw", "./data/research", "./ledger", "./vendor/alphagen", "./tools/__init__.py", "./tools/p1_moneyflow", DOC}
EXPECTED = {
    "g1-v2-rejudge-precheck": {"read_only": INPUTS, "writable": {"./logs/g1-v2/precheck"}},
    "g1-v2-rejudge-run": {
        "read_only": INPUTS | {CONTROL},
        "writable": {"./ledger/experiments.csv", "./ledger/factor_admissions_v2.csv", "./data/research/g1-v2-rejudge", "./logs/g1-v2"},
    },
    "g1-v2-rejudge-audit": {
        "read_only": {"./ledger", DOC, CONTROL, "./data/research/g1-v2-rejudge", "./logs/g1-v2"},
        "writable": {"./logs/g1-v2-audit"},
    },
}
_VARIABLE = re.compile(r"\$\{(\w+)(?::-([^}]*))?(?::\?[^}]*)?\}")


def _render(value: str) -> str:
    return _VARIABLE.sub(lambda match: match.group(2) or f"<{match.group(1)}>", value)


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
        assert all(volume["target"] == "/workspace/" + volume["source"].removeprefix("./") for volume in binds), name
        read_only = {volume["source"] for volume in binds if volume["read_only"]}
        writable = {volume["source"] for volume in binds if not volume["read_only"]}
        assert read_only == EXPECTED[name]["read_only"], name
        assert writable == EXPECTED[name]["writable"], name
        assert not writable & {"./ledger/factor_admissions.csv", "./logs/g1"}, name


def test_only_the_formal_run_shares_the_scheduler_lock_and_runs_as_root():
    document = _document()
    services = document["services"]
    run = services["g1-v2-rejudge-run"]
    assert run["user"] == "0:0"
    assert run["environment"]["SHAIWEI_LOCK_AUTHORITY"] == "docker-named-volume-v1"
    assert run["environment"]["SHAIWEI_LOCK_ROOT"] == "/run/shaiwei-locks"
    locks = [volume for volume in run["volumes"] if volume["type"] == "volume"]
    assert locks == [{"type": "volume", "source": "runtime-locks", "target": "/run/shaiwei-locks", "volume": {"nocopy": True}}]
    assert document["volumes"]["runtime-locks"] == {"external": True, "name": "shaiwei_runtime_locks_v1"}
    for name in ("g1-v2-rejudge-precheck", "g1-v2-rejudge-audit"):
        assert services[name]["user"] != "0:0"
        assert all(volume["type"] == "bind" for volume in services[name]["volumes"])
        assert "SHAIWEI_LOCK_AUTHORITY" not in services[name]["environment"]


def test_entrypoints_are_the_release_subcommands_and_the_light_audit():
    services = _document()["services"]
    commands = {name: [_render(part) for part in service["command"]] for name, service in services.items()}
    assert commands == {
        "g1-v2-rejudge-precheck": ["python", "-m", "shaiwei.research.g1_v2_rejudge.release", "precheck", "--output", "unused"],
        "g1-v2-rejudge-run": ["python", "-m", "shaiwei.research.g1_v2_rejudge.release", "execute", "--scope", "unused"],
        "g1-v2-rejudge-audit": ["python", "-m", "shaiwei.research.g1_v2_rejudge.audit", "--execution-id", "unused"],
    }
    assert _render(services["g1-v2-rejudge-run"]["image"]) == "<SHAIWEI_G1_REJUDGE_IMAGE>"
