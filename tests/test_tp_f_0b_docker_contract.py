"""TP-F-0B 容器合同：断网、只读根、无密钥、宿主 UID；fixture 不挂真实数据；每个服务只有一个写入点，账本永不可写。"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.tp-f-0b.yaml"
DOCS = {"./docs/TP_F_0B_DATA_IDENTITY_PREFLIGHT_PROTOCOL_20261027.md", "./docs/TP_F_0B_DATA_IDENTITY_PREFLIGHT_ADDENDUM_A1_20261029.md"}
INPUTS = DOCS | {
    "./data/raw",
    "./data/research/trend_swing/ts-v3-data-gate-r3/input_manifest.json",
    "./data/qlib_bin",
    "./ledger",
    "./data/research/rf/rf-0b-field-identity-preflight-v1-r2/identity_registry.json",
    "./data/control/tp-f-0b",
}
EVIDENCE = "./data/research/tp-f/tp-f-0b-data-identity-preflight-v1"
EXPECTED = {
    "tp-f-0b-fixture": {"read_only": DOCS, "writable": {"./logs/tp-f-0b/fixture"}},
    "tp-f-0b-profile": {"read_only": INPUTS, "writable": {EVIDENCE}},
    "tp-f-0b-audit": {"read_only": INPUTS | {EVIDENCE}, "writable": {"./data/research/tp-f/tp-f-0b-audit"}},
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
        assert _render(service["user"]) == "10001:10001", name
        assert "env_file" not in service and "secrets" not in service, name
        assert not any(key.startswith(("FEISHU", "TUSHARE", "DEEPSEEK", "SHAIWEI_LOCK")) for key in service["environment"]), name
        assert all(volume["type"] == "bind" for volume in service["volumes"]), name
        assert all(volume["bind"]["create_host_path"] is False for volume in service["volumes"]), name
        assert all(volume["target"] == "/workspace/" + volume["source"].removeprefix("./") for volume in service["volumes"]), name
        read_only = {volume["source"] for volume in service["volumes"] if volume["read_only"]}
        writable = {volume["source"] for volume in service["volumes"] if not volume["read_only"]}
        assert read_only == EXPECTED[name]["read_only"], name
        assert writable == EXPECTED[name]["writable"], name
        assert not any(path.startswith("./ledger") for path in writable), name
    assert ".env" not in COMPOSE.read_text(encoding="utf-8")


def test_entrypoints_are_the_release_subcommands():
    services = _document()["services"]
    commands = {name: [_render(part) for part in service["command"]] for name, service in services.items()}
    module = ["python", "-m", "shaiwei.research.tp_f_0b.release"]
    assert commands == {
        "tp-f-0b-fixture": [*module, "fixture", "--output", "unused"],
        "tp-f-0b-profile": [*module, "profile", "--scope", "unused"],
        "tp-f-0b-audit": [*module, "audit", "--scope", "unused"],
    }
    assert _render(services["tp-f-0b-profile"]["image"]) == "<SHAIWEI_TP_F_0B_IMAGE>"
