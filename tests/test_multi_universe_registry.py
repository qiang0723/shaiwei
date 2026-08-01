from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from shaiwei.research.universe_registry import (
    EXPECTED_EVALUATION_FIELDS,
    PROJECT_ROOT,
    UniverseRegistry,
    UniverseRegistryError,
    load_registry,
    registry_sha256,
    validate_evaluation_identity,
    validation_summary,
)


CONFIG_PATH = PROJECT_ROOT / "config/m1_multi_universe_v1.yaml"


def _document() -> dict[str, object]:
    document = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _universe(document: dict[str, object], universe_id: str) -> dict[str, object]:
    universes = document["universes"]
    assert isinstance(universes, list)
    return next(item for item in universes if item["universe_id"] == universe_id)


def _evaluation(universe_id: str = "star50-official-pit-v2") -> dict[str, object]:
    return {
        "factor_id": "a" * 64,
        "factor_version": "candidate-001",
        "universe_id": universe_id,
        "benchmark_id": "SH000688",
        "label_id": "next_open_to_t_plus_11_open",
        "horizon_id": "next_open_to_t_plus_11_open",
        "neutralization_id": "star_industry_log_market_cap_v1",
        "window_set_id": "m1-star50-windows-v1",
        "cost_policy_id": "star-open-cost-v1",
        "decision_rule_version": "g1-v1",
    }


def _write_config(tmp_path: Path, document: dict[str, object]) -> Path:
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def test_frozen_registry_loads_and_has_stable_summary():
    first = load_registry()
    second = load_registry()
    assert registry_sha256(first) == registry_sha256(second)
    assert registry_sha256(first) == "acece635101ca08303d303a2229b49f2405f5919aa65745b5590aa03f7da927f"
    assert validation_summary(first) == validation_summary(second)
    assert validation_summary(first)["factor_protocol_eligible"] == [
        "csi800-pit-v1",
        "star50-official-pit-v2",
    ]
    assert first.factor_results_inspected is False
    assert first.llm_execution_authorized is False
    assert first.new_production_authorized is False


def test_registry_keeps_only_csi800_existing_production_permission():
    registry = load_registry()
    production = [
        item.universe_id
        for item in registry.universes
        if "CONTINUE_EXISTING_PRODUCTION" in item.permissions
    ]
    assert production == ["csi800-pit-v1"]


def test_star50_evaluation_identity_is_complete_and_universe_specific():
    registry = load_registry()
    identity = validate_evaluation_identity(registry, _evaluation())
    assert tuple(identity.model_dump()) == EXPECTED_EVALUATION_FIELDS
    assert identity.universe_id == "star50-official-pit-v2"


@pytest.mark.parametrize(
    "universe_id",
    [
        "star100-official-pit-v1",
        "star200-official-pit-v1",
        "star-composite-official-v1",
        "star-board-all-pit-v1",
    ],
)
def test_non_ready_universe_cannot_enter_factor_evaluation(universe_id: str):
    with pytest.raises(UniverseRegistryError, match="not eligible"):
        validate_evaluation_identity(load_registry(), _evaluation(universe_id))


def test_unregistered_universe_fails_closed():
    with pytest.raises(UniverseRegistryError, match="unregistered universe"):
        validate_evaluation_identity(load_registry(), _evaluation("star300-unregistered-v1"))


def test_evaluation_identity_rejects_missing_or_unknown_fields():
    registry = load_registry()
    missing = _evaluation()
    del missing["cost_policy_id"]
    with pytest.raises(ValidationError):
        validate_evaluation_identity(registry, missing)
    with pytest.raises(ValidationError):
        validate_evaluation_identity(registry, {**_evaluation(), "alpha_score": 1.0})


def test_registry_rejects_unknown_top_level_field():
    document = _document()
    document["result_hint"] = "positive"
    with pytest.raises(ValidationError):
        UniverseRegistry.model_validate(document)


def test_registry_rejects_duplicate_universe_or_official_code():
    duplicate_id = _document()
    _universe(duplicate_id, "star100-official-pit-v1")["universe_id"] = (
        "star50-official-pit-v2"
    )
    with pytest.raises(ValidationError, match="duplicate universe IDs"):
        UniverseRegistry.model_validate(duplicate_id)

    duplicate_code = _document()
    _universe(duplicate_code, "star100-official-pit-v1")["official_index_code"] = "000688.SH"
    with pytest.raises(ValidationError, match="duplicate official index codes"):
        UniverseRegistry.model_validate(duplicate_code)


def test_custom_universe_cannot_claim_official_identity():
    document = _document()
    custom = _universe(document, "star-board-midcap-pit-v1")
    custom["official_index_code"] = "000777.SH"
    with pytest.raises(ValidationError, match="cannot claim an official index code"):
        UniverseRegistry.model_validate(document)

    document = _document()
    _universe(document, "star-board-midcap-pit-v1")["display_name"] = "自建科创300指数"
    with pytest.raises(ValidationError, match="cannot use an official index label"):
        UniverseRegistry.model_validate(document)


def test_pit_status_cannot_grant_factor_or_production_permission():
    factor_escalation = _document()
    _universe(factor_escalation, "star100-official-pit-v1")["permissions"] = [
        "FREEZE_NEW_FACTOR_PROTOCOL"
    ]
    with pytest.raises(ValidationError, match="do not match PIT status"):
        UniverseRegistry.model_validate(factor_escalation)

    production_escalation = _document()
    _universe(production_escalation, "star50-official-pit-v2")["permissions"] = [
        "FREEZE_NEW_FACTOR_PROTOCOL",
        "CONTINUE_EXISTING_PRODUCTION",
    ]
    with pytest.raises(ValidationError, match="do not match PIT status"):
        UniverseRegistry.model_validate(production_escalation)


def test_bse_inclusion_and_frozen_identity_set_fail_closed():
    bse = _document()
    _universe(bse, "csi800-pit-v1")["bse_included"] = True
    with pytest.raises(ValidationError):
        UniverseRegistry.model_validate(bse)

    extra = _document()
    universes = extra["universes"]
    assert isinstance(universes, list)
    added = deepcopy(_universe(extra, "star-board-all-pit-v1"))
    added["universe_id"] = "star300-unregistered-v1"
    universes.append(added)
    with pytest.raises(ValidationError, match="frozen M1-0 identity set"):
        UniverseRegistry.model_validate(extra)


def test_evaluation_contract_order_and_gates_are_immutable():
    reordered = _document()
    fields = reordered["evaluation_contract"]["identity_fields"]
    fields[0], fields[1] = fields[1], fields[0]
    with pytest.raises(ValidationError, match="ordered contract"):
        UniverseRegistry.model_validate(reordered)

    missing_gate = _document()
    missing_gate["evaluation_contract"]["required_gate_families"].pop()
    with pytest.raises(ValidationError, match="gate families"):
        UniverseRegistry.model_validate(missing_gate)


def test_protocol_hash_missing_evidence_and_path_escape_fail_closed(tmp_path: Path):
    wrong_hash = _document()
    wrong_hash["protocol_sha256"] = "0" * 64
    with pytest.raises(UniverseRegistryError, match="protocol hash differs"):
        load_registry(_write_config(tmp_path, wrong_hash), project_root=PROJECT_ROOT)

    missing = _document()
    _universe(missing, "star200-official-pit-v1")["evidence_documents"] = [
        "docs/DOES_NOT_EXIST.md"
    ]
    with pytest.raises(UniverseRegistryError, match="evidence file is missing"):
        load_registry(_write_config(tmp_path, missing), project_root=PROJECT_ROOT)

    escaped = _document()
    _universe(escaped, "star200-official-pit-v1")["evidence_documents"] = ["../secret"]
    with pytest.raises(UniverseRegistryError, match="not project-relative"):
        load_registry(_write_config(tmp_path, escaped), project_root=PROJECT_ROOT)


def test_registry_module_stays_small_and_does_not_pull_runtime_or_network():
    source_path = PROJECT_ROOT / "src/shaiwei/research/universe_registry.py"
    source = source_path.read_text(encoding="utf-8")
    assert len(source.splitlines()) <= 400
    assert "from shaiwei.config" not in source
    assert "import httpx" not in source
    assert "import requests" not in source
    assert "dotenv" not in source
