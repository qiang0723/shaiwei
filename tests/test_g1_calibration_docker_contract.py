"""G1 正控容器合同：断网、只读、无密钥，唯一可写目录是标定数据目录（协议 §8、§10）。"""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.g1-calibration.yaml"
WRITABLE = "./data/research/g1-calibration-v1"
READ_ONLY = {"./data/qlib_bin", "./data/raw", "./ledger", "./vendor/alphagen"}


def _services() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]


def test_every_service_is_offline_read_only_and_secret_free():
    services = _services()
    assert set(services) == {"g1-calibration-pilot"}
    for name, service in services.items():
        assert service["network_mode"] == "none", name
        assert service["read_only"] is True and service["cap_drop"] == ["ALL"], name
        assert service["pull_policy"] == "never" and service["restart"] == "no", name
        assert "env_file" not in service and "secrets" not in service, name
        assert not any(key.startswith(("FEISHU", "TUSHARE", "DEEPSEEK")) for key in service["environment"]), name
        mounts = {volume["source"]: volume for volume in service["volumes"]}
        assert set(mounts) == READ_ONLY | {WRITABLE}, name
        assert all(mounts[source]["read_only"] is True for source in READ_ONLY), name
        assert mounts[WRITABLE]["read_only"] is False, name
        assert mounts[WRITABLE]["target"] == "/workspace/data/research/g1-calibration-v1", name
        assert all(volume["bind"]["create_host_path"] is False for volume in service["volumes"]), name


def test_pilot_command_is_the_result_blind_timing_entrypoint():
    command = _services()["g1-calibration-pilot"]["command"]
    assert command[:5] == ["python", "-m", "shaiwei.research.g1_calibration.pilot", "--pilot", "--output"]
