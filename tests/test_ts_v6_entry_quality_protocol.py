from pathlib import Path

import yaml

from shaiwei.provenance import CONTROLLED_FILES
from shaiwei.research.trend_swing.v6.contract import ADDENDUM_SHA256, PROTOCOL_SHA256, V6Scope


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.ts-v6-entry-quality.yaml"


def test_protocol_freezes_one_mechanism_and_keeps_all_effect_authority_closed() -> None:
    scope = V6Scope.load()
    assert scope.sha256 == PROTOCOL_SHA256
    assert scope.addendum_sha256 == ADDENDUM_SHA256
    assert scope.roles == (
        ("selectable_discovery", "20210104", "20231229"),
        ("frozen_stability_holdout", "20240102", "20251231"),
    )
    assert scope.document["entry_quality_mechanism"]["one_primary_mechanism_change_only"] is True
    assert scope.document["inherited_parent_semantics"]["exit_rules_changed"] is False
    assert scope.document["inherited_parent_semantics"]["sizing_or_risk_rules_changed"] is False
    assert scope.document["result_firewall"]["forbidden"]
    assert scope.document["execution_control"]["env_or_secret_read"] is False
    assert scope.document["production_authorization"] == "none"


def test_operationalization_forbids_rearm_and_new_child_events() -> None:
    addendum = V6Scope.load().addendum
    parent = addendum["authoritative_parent_event_set"]
    semantics = addendum["candidate_filter_semantics"]
    assert parent["child_may_create_new_parent_episode_or_event"] is False
    assert parent["exact_key_reconciliation_required_before_candidate_profile"] is True
    assert semantics["rearm_or_retry_inside_same_parent_episode"] == "forbidden"
    assert semantics["rescan_to_create_alternative_signal_date"] == "forbidden"
    assert semantics["child_event_key_must_equal_surviving_parent_event_key"] is True


def test_docker_boundary_is_offline_read_only_and_secret_free() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    serialized = COMPOSE.read_text(encoding="utf-8")
    assert ".env" not in serialized and "docker.sock" not in serialized
    for service in document["services"].values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["restart"] == "no"
        assert service["cap_drop"] == ["ALL"]
    profile = document["services"]["ts-v6-entry-quality-profile"]
    fixture = document["services"]["ts-v6-entry-quality-fixture"]
    assert fixture["build"]["network"] == "none"
    writable = [row for row in profile["volumes"] if row["read_only"] is False]
    assert len(writable) == 1
    assert writable[0]["source"].endswith("ts-v6-entry-quality-preflight-v1")
    assert "Dockerfile.ts-v6-entry-quality" in CONTROLLED_FILES
    assert COMPOSE.name in CONTROLLED_FILES


def test_v6_package_respects_module_size_and_no_generic_dumping_ground() -> None:
    package = ROOT / "src/shaiwei/research/trend_swing/v6"
    sizes = {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in package.glob("*.py")}
    assert sizes and max(sizes.values()) <= 400
    assert not ({"utils.py", "helpers.py", "common.py"} & set(sizes))
