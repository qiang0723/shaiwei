from pathlib import Path

import yaml

from shaiwei.provenance import CONTROLLED_FILES
from shaiwei.research.trend_swing.ts_c.contract import PROTOCOL_SHA256, TQCScope


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.ts-c-qualification.yaml"


def test_protocol_freezes_three_arms_and_density_gates() -> None:
    scope = TQCScope.load()
    assert scope.sha256 == PROTOCOL_SHA256
    arms = [row["trigger_id"] for row in scope.document["trigger_arms"]]
    assert arms == ["VWAP_ANCHOR_PULLBACK", "HIGH20_DRAWDOWN", "MA20_PULLBACK"]
    gate = scope.document["density_gate"]
    assert gate["per_trigger_minimum_confirmed_events"] == 120
    assert gate["threshold_change_after_profile"] == "forbidden"
    assert scope.document["objective"]["post_entry_outcomes_allowed"] is False
    assert scope.document["production_authorization"] == "none"


def test_docker_boundary_is_offline_read_only_and_secret_free() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    serialized = COMPOSE.read_text(encoding="utf-8")
    assert ".env" not in serialized and "docker.sock" not in serialized
    for service in document["services"].values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["restart"] == "no"
        assert service["cap_drop"] == ["ALL"]
    fixture = document["services"]["ts-c-fixture"]
    assert fixture["build"]["network"] == "none"
    for name in ("ts-c-profile", "ts-c-auditor"):
        writable = [row for row in document["services"][name]["volumes"] if row["read_only"] is False]
        assert len(writable) == 1
        assert writable[0]["source"].endswith("ts-c-trigger-qualification-v1")
    assert "Dockerfile.ts-c-qualification" in CONTROLLED_FILES
    assert COMPOSE.name in CONTROLLED_FILES


def test_ts_c_package_respects_module_size_and_no_generic_dumping_ground() -> None:
    package = ROOT / "src/shaiwei/research/trend_swing/ts_c"
    sizes = {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in package.glob("*.py")}
    assert sizes and max(sizes.values()) <= 400
    assert not ({"utils.py", "helpers.py", "common.py"} & set(sizes))
