from copy import deepcopy
import json
from pathlib import Path

import pytest
import yaml

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_bound_proposal_contract import (
    BoundCompilation,
    BoundProposalContract,
    build_request_v4,
    compile_bound_proposal,
    deterministic_search_points,
    independent_authority,
    proposal_schema,
)
from shaiwei.research.trend_swing.v5_models import Mechanism, MechanismCandidate
from shaiwei.research.trend_swing.v5_r3e_acceptance import minimal_bound_proposal


@pytest.mark.parametrize("mechanism", list(Mechanism))
def test_all_six_bound_proposals_compile_with_local_authority(mechanism: Mechanism) -> None:
    ordinal = list(Mechanism).index(mechanism) + 1
    authority = independent_authority(f"fixture-{ordinal}", ordinal)
    compiled = compile_bound_proposal(mechanism, minimal_bound_proposal(mechanism), authority)

    assert compiled.candidate.primary_mechanism == mechanism
    assert compiled.candidate.lineage.mode == "INDEPENDENT"
    assert compiled.candidate.lineage.parent_candidate_fingerprints == []
    assert compiled.evidence_mode() == "INDEPENDENT"
    assert compiled.search_evaluations <= 196


@pytest.mark.parametrize(
    ("slot_count", "points", "product"),
    [(1, 7, 7), (2, 7, 49), (3, 5, 125), (4, 3, 81), (5, 2, 32)],
)
def test_search_budget_is_local_and_within_frozen_limit(
    slot_count: int, points: int, product: int
) -> None:
    assert deterministic_search_points(slot_count) == points
    assert points**slot_count == product <= 196


@pytest.mark.parametrize("slot_count", [0, 6, 99])
def test_unregistered_slot_count_fails_closed(slot_count: int) -> None:
    with pytest.raises(D1ControlError, match="no frozen search budget"):
        deterministic_search_points(slot_count)


def test_request_binds_authority_but_response_schema_cannot_override_it() -> None:
    mechanism = Mechanism.BREAKOUT_RETEST
    authority = independent_authority("fixture-breakout", 3)
    request = build_request_v4(mechanism, authority)
    task = json.loads(request["messages"][1]["content"])
    schema_text = json.dumps(task["proposal_schema"], sort_keys=True)

    assert task["assigned_attempt_authority"] == authority.model_dump(mode="json")
    assert '"lineage"' not in schema_text
    assert "search_points_maximum" not in schema_text
    assert task["mechanism_projection"]["response_lineage_field_allowed"] is False
    assert task["mechanism_projection"]["response_search_points_field_allowed"] is False
    assert task["mechanism_projection"]["deterministic_required_features"]
    assert task["mechanism_projection"]["deterministic_mandatory_cancellation_rules"] == [
        "STRUCTURE_LOW_BROKEN",
        "MARKET_OR_SECTOR_GATE_LOST",
    ]
    assert task["proposal_schema"]["x-ts-text-contract"]["forbidden_pattern"]


@pytest.mark.parametrize("field", ["lineage", "search_points_maximum"])
def test_response_owned_authority_or_budget_field_fails_closed(field: str) -> None:
    mechanism = Mechanism.VOLATILITY_ADAPTIVE_PULLBACK
    document = minimal_bound_proposal(mechanism)
    if field == "lineage":
        document[field] = {
            "mode": "ADVERSARIAL_REVISION",
            "parent_candidate_fingerprints": ["a" * 64],
        }
    else:
        document["parameter_slots"][0][field] = 7
    with pytest.raises(D1ControlError, match="bound mechanism contract"):
        compile_bound_proposal(mechanism, document, independent_authority("fixture-one", 1))


def test_conflicting_evidence_mode_cannot_be_derived() -> None:
    mechanism = Mechanism.WEEKLY_STRUCTURE_QUANTILE
    authority = independent_authority("fixture-two", 2)
    compiled = compile_bound_proposal(mechanism, minimal_bound_proposal(mechanism), authority)
    payload = compiled.candidate.model_dump(mode="json")
    payload["lineage"] = {
        "mode": "ADVERSARIAL_REVISION",
        "parent_candidate_fingerprints": ["a" * 64],
    }
    tampered = BoundCompilation(
        authority=authority,
        candidate=MechanismCandidate.model_validate(payload),
        search_evaluations=compiled.search_evaluations,
    )
    with pytest.raises(D1ControlError, match="evidence mode differs"):
        tampered.evidence_mode()


@pytest.mark.parametrize(
    "mutator",
    [
        lambda document: document.update({"primary_mechanism": "BREAKOUT_RETEST"}),
        lambda document: document.pop("schema_version"),
        lambda document: document["parameter_slots"].append(
            deepcopy(document["parameter_slots"][0])
        ),
        lambda document: document["parameter_slots"][0].update({"minimum": "-1"}),
        lambda document: document.update({"hypothesis": "包含 python 代码的非法研究文本。"}),
        lambda document: document.update(
            {"falsification_conditions": ["重复证伪条件。", "重复证伪条件。"]}
        ),
    ],
)
def test_adversarial_documents_fail_closed(mutator: object) -> None:
    mechanism = Mechanism.CONTRACTION_EXPANSION
    document = minimal_bound_proposal(mechanism)
    mutator(document)  # type: ignore[operator]
    with pytest.raises(D1ControlError):
        compile_bound_proposal(mechanism, document, independent_authority("fixture-five", 5))


def test_v3_schema_and_contract_are_stable() -> None:
    contract = BoundProposalContract.load()
    schema = proposal_schema(Mechanism.RELATIVE_STRENGTH_PULLBACK)

    assert contract.sha256 == "c46ee09cf6d1039e85f797e8510284533e0b8980cda255bfb827c30e69942dc8"
    assert schema["properties"]["schema_version"]["const"] == "ts-v5-mechanism-proposal-v3"
    assert "CandidateLineage" not in schema.get("$defs", {})


def test_r3e_modules_are_narrow_and_compose_is_offline() -> None:
    root = Path(__file__).resolve().parents[1]
    module_root = root / "src/shaiwei/research/trend_swing"
    assert len((module_root / "v5_bound_proposal_contract.py").read_text().splitlines()) <= 400
    assert len((module_root / "v5_r3e_acceptance.py").read_text().splitlines()) <= 320
    assert len((module_root / "v5_r3e_inputs.py").read_text().splitlines()) <= 100
    assert len((module_root / "v5_r3e_audit.py").read_text().splitlines()) <= 120

    compose = yaml.safe_load((root / "compose.ts-v5-r3e.yaml").read_text(encoding="utf-8"))
    for service in compose["services"].values():
        assert service.get("network_mode") == "none" or "extends" in service
        assert "DEEPSEEK_API_KEY" not in service.get("environment", [])
        assert service.get("read_only") is True or "extends" in service
        assert service.get("cap_drop") == ["ALL"] or "extends" in service
    live = compose["services"]["ts-v5-r3e"]
    mounts = {item["target"]: item for item in live["volumes"]}
    assert mounts["/workspace/data/research/trend_swing/ts-v5-r3c-canary-001"]["read_only"] is True
    assert mounts["/workspace/data/research/trend_swing/ts-v5-r3d-offline-proposal-diagnostic"][
        "read_only"
    ] is True
    assert "/workspace/data/raw" not in mounts
