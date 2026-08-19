from pathlib import Path

import yaml

from shaiwei.provenance import CONTROLLED_FILES
from shaiwei.research.rf_0b.contract import PROTOCOL_SHA256, RFBScope


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.ts-rf-0b.yaml"


def test_protocol_freezes_zero_effect_authority_and_gates() -> None:
    scope = RFBScope.load()
    assert scope.sha256 == PROTOCOL_SHA256
    objective = scope.document["objective"]
    assert objective["candidate_generation"] is False
    assert objective["strategy_effect_evaluation"] is False
    gate = scope.document["field_quality_gate"]
    assert gate["open_coverage_minimum_of_member_days"] == 0.99
    assert gate["bse_row_maximum"] == 0
    assert gate["threshold_change_after_profile"] == "forbidden"
    execution = scope.document["execution_control"]
    assert execution["deepseek_or_any_llm_call"] is False
    assert execution["same_scope_rerun"] == "forbidden"
    assert scope.document["production_authorization"] == "none"


def test_forbidden_ledger_columns_are_named() -> None:
    forbidden = RFBScope.load().document["frozen_inputs"]["ledger_columns_forbidden"]
    assert "discovery_rank_ic" in forbidden
    assert "result_json" in forbidden
    assert "admitted" in forbidden


def test_docker_boundary_is_offline_read_only_and_secret_free() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    serialized = COMPOSE.read_text(encoding="utf-8")
    assert ".env" not in serialized and "docker.sock" not in serialized
    for service in document["services"].values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["restart"] == "no"
        assert service["cap_drop"] == ["ALL"]
    fixture = document["services"]["rf-0b-fixture"]
    assert fixture["build"]["network"] == "none"
    for name in ("rf-0b-profile", "rf-0b-auditor"):
        writable = [row for row in document["services"][name]["volumes"] if row["read_only"] is False]
        assert len(writable) == 1
        assert writable[0]["source"].endswith("rf-0b-field-identity-preflight-v1")
    assert "Dockerfile.ts-rf-0b" in CONTROLLED_FILES
    assert COMPOSE.name in CONTROLLED_FILES


def test_rf_0b_package_respects_module_size_and_no_generic_dumping_ground() -> None:
    package = ROOT / "src/shaiwei/research/rf_0b"
    sizes = {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in package.glob("*.py")}
    assert sizes and max(sizes.values()) <= 400
    assert not ({"utils.py", "helpers.py", "common.py"} & set(sizes))
