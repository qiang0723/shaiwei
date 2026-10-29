"""TP-F-1 容器合同：只读根、丢弃全部能力、无 env_file；只有生成段出网且只透传 DeepSeek 密钥；写账本的两段以 root 共用命名卷锁；每段写入点固定。"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.tp-f-1.yaml"
DOCS = {f"./docs/{name}" for name in (
    "TP_F_1_FORMAL_SMALL_BATCH_PROTOCOL_20261029.md", "TP_F_1_FORMAL_SMALL_BATCH_ADDENDUM_A1_20261029.md",
    "TP_F_0B_DATA_IDENTITY_PREFLIGHT_PROTOCOL_20261027.md", "TP_F_0B_DATA_IDENTITY_PREFLIGHT_ADDENDUM_A1_20261029.md",
    "TP_F_0A_TREND_PULLBACK_FACTOR_PREPARATION_20260820.md", "TP_F_0B_ACCEPTANCE_20261029.md")}
FIXTURE_DOCS = {path for path in DOCS if "TP_F_0A" not in path and "ACCEPTANCE" not in path}
COMMON = DOCS | {"./data/research", "./ledger", "./data/control/tp-f-1"}
EXPECTED = {
    "tp-f-1-fixture": {"read_only": FIXTURE_DOCS | {"./vendor/alphagen"}, "writable": {"./logs/tp-f-1/fixture"}},
    "tp-f-1-generate": {"read_only": COMMON | {"./vendor/alphagen", "./data/qlib_bin"},
                        "writable": {"./ledger/tp_f_1_llm_attempts.csv", "./ledger/tp_f_1_llm_transports.csv", "./data/research/tp-f-1"}},
    "tp-f-1-evaluate": {"read_only": COMMON | {"./vendor/alphagen", "./data/qlib_bin", "./data/raw"},
                        "writable": {"./ledger/experiments.csv", "./ledger/factor_admissions_v2.csv", "./data/research/tp-f-1", "./logs/tp-f-1"}},
    "tp-f-1-audit": {"read_only": COMMON | {"./logs/tp-f-1"}, "writable": {"./data/research/tp-f-1-audit"}},
}
_VARIABLE = re.compile(r"\$\{(\w+)(?::-([^}]*))?(?::\?[^}]*)?\}")


def _render(value: str) -> str:
    return _VARIABLE.sub(lambda match: match.group(2) or f"<{match.group(1)}>", value)


def _services() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]


def test_mounts_secrets_and_network_are_confined_per_stage():
    services = _services()
    assert set(services) == set(EXPECTED)
    assert ".env" not in COMPOSE.read_text(encoding="utf-8")
    for name, service in services.items():
        assert service["read_only"] is True and service["cap_drop"] == ["ALL"] and service["restart"] == "no", name
        assert service["security_opt"] == ["no-new-privileges:true"] and "env_file" not in service, name
        binds = [volume for volume in service["volumes"] if volume["type"] == "bind"]
        assert all(volume["bind"]["create_host_path"] is False for volume in binds), name
        assert all(volume["target"] == "/workspace/" + volume["source"].removeprefix("./") for volume in binds), name
        assert {v["source"] for v in binds if v["read_only"]} == EXPECTED[name]["read_only"], name
        assert {v["source"] for v in binds if not v["read_only"]} == EXPECTED[name]["writable"], name
        assert not {v["source"] for v in binds if not v["read_only"]} & {"./ledger/factor_admissions.csv", "./ledger/paper_runs.csv"}, name
        secrets = {key for key in service["environment"] if key.startswith(("DEEPSEEK", "TUSHARE", "FEISHU"))}
        if name == "tp-f-1-generate":
            assert "network_mode" not in service and secrets == {"DEEPSEEK_API_KEY"}
        else:
            assert service["network_mode"] == "none" and not secrets, name


def test_only_ledger_writers_run_as_root_with_the_shared_lock():
    services = _services()
    for name in ("tp-f-1-generate", "tp-f-1-evaluate"):
        assert services[name]["user"] == "0:0"
        assert services[name]["environment"]["SHAIWEI_LOCK_AUTHORITY"] == "docker-named-volume-v1"
        assert [v for v in services[name]["volumes"] if v["type"] == "volume"] == [
            {"type": "volume", "source": "runtime-locks", "target": "/run/shaiwei-locks", "volume": {"nocopy": True}}]
    for name in ("tp-f-1-fixture", "tp-f-1-audit"):
        assert _render(services[name]["user"]) == "10001:10001" and "SHAIWEI_LOCK_AUTHORITY" not in services[name]["environment"]


def test_entrypoints_are_the_release_subcommands():
    module = ["python", "-m", "shaiwei.research.tp_f_1.release"]
    commands = {name: [_render(part) for part in service["command"]] for name, service in _services().items()}
    assert commands == {
        "tp-f-1-fixture": [*module, "fixture", "--output", "unused"],
        "tp-f-1-generate": [*module, "generate", "--scope", "unused"],
        "tp-f-1-evaluate": [*module, "evaluate", "--scope", "unused"],
        "tp-f-1-audit": [*module, "audit", "--scope", "unused"],
    }
