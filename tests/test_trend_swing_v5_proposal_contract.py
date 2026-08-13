from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_models import (
    ARCHETYPE_CONTRACT,
    COMMON_FEATURES,
    MECHANISM_FEATURES,
    PARAMETER_BOUNDS,
    Mechanism,
)
from shaiwei.research.trend_swing.v5_projection_acceptance import build_report
from shaiwei.research.trend_swing.v5_projection_audit import audit_report
from shaiwei.research.trend_swing.v5_proposal_contract import (
    MANDATORY_CANCELLATIONS,
    OPTIONAL_CANCELLATIONS,
    ProposalContract,
    allowed_parameter_ids,
    build_request_v3,
    compile_proposal,
    mechanism_projection,
    projection_bundle_identity,
    proposal_schema,
)


def proposal_document(mechanism: Mechanism) -> dict[str, object]:
    mandatory = sorted(ARCHETYPE_CONTRACT[mechanism][2], key=lambda item: item.value)
    slots = []
    for parameter in mandatory:
        minimum, maximum, value_type = PARAMETER_BOUNDS[parameter]
        slots.append({
            "parameter_id": parameter.value,
            "value_type": value_type,
            "minimum": str(minimum),
            "maximum": str(maximum),
            "search_points_maximum": 3,
        })
    return {
        "schema_version": "ts-v5-mechanism-proposal-v2",
        "hypothesis": "在冻结趋势与板块条件下，该机制可能提供更稳定且可证伪的入场事件。",
        "economic_rationale_draft": "该研究只比较机制与邻近参数的稳健性，不包含任何收益或生产结论。",
        "change_summary": "仅替换入场机制表达，保持全部产品和执行约束不变。",
        "recovery_confirmation": "CLOSE_RECLAIMS_REFERENCE",
        "optional_cancellation_rules": ["MAX_WAIT_EXPIRED"],
        "parameter_slots": slots,
        "falsification_conditions": [
            "事件无法覆盖多个自然年度或只集中在单一阶段。",
            "邻近参数的方向与成本敏感性无法保持一致。",
        ],
        "lineage": {"mode": "INDEPENDENT", "parent_candidate_fingerprints": []},
    }


@pytest.mark.parametrize("mechanism", list(Mechanism))
def test_all_six_proposals_compile_to_frozen_candidate_contract(mechanism: Mechanism) -> None:
    proposal = proposal_document(mechanism)
    candidate = compile_proposal(mechanism, proposal)
    projection = mechanism_projection(mechanism)

    assert candidate.primary_mechanism == mechanism
    assert candidate.entry_design.reference_frame.value == projection["deterministic_reference_frame"]
    assert candidate.entry_design.pullback_measure.value == projection["deterministic_pullback_measure"]
    assert [item.value for item in candidate.entry_design.cancellation_rules] == [
        *[item.value for item in MANDATORY_CANCELLATIONS], "MAX_WAIT_EXPIRED",
    ]
    assert {item.value for item in candidate.required_features} == {
        item.value for item in COMMON_FEATURES | MECHANISM_FEATURES[mechanism]
    }
    assert compile_proposal(mechanism, proposal).fingerprint() == candidate.fingerprint()


@pytest.mark.parametrize("mechanism", list(Mechanism))
def test_projection_exposes_every_allowed_parameter_and_exact_range(mechanism: Mechanism) -> None:
    projection = mechanism_projection(mechanism)
    rows = {item["parameter_id"]: item for item in projection["parameter_contracts"]}

    assert set(rows) == {item.value for item in allowed_parameter_ids(mechanism)}
    assert projection["mandatory_parameter_ids"] == sorted(
        item.value for item in ARCHETYPE_CONTRACT[mechanism][2]
    )
    assert projection["optional_cancellation_rule_enum"] == [
        item.value for item in OPTIONAL_CANCELLATIONS
    ]
    assert projection["maximum_search_evaluations"] == 196
    for parameter in allowed_parameter_ids(mechanism):
        minimum, maximum, value_type = PARAMETER_BOUNDS[parameter]
        assert rows[parameter.value] == {
            "parameter_id": parameter.value,
            "required": parameter in ARCHETYPE_CONTRACT[mechanism][2],
            "value_type": value_type,
            "minimum_inclusive": str(minimum),
            "maximum_inclusive": str(maximum),
            "search_points_minimum": 2,
            "search_points_maximum": 7,
        }


@pytest.mark.parametrize("mechanism", list(Mechanism))
def test_every_projected_parameter_accepts_exact_safe_boundaries(mechanism: Mechanism) -> None:
    document = proposal_document(mechanism)
    present = {slot["parameter_id"] for slot in document["parameter_slots"]}
    for parameter in allowed_parameter_ids(mechanism):
        if parameter.value in present:
            continue
        minimum, maximum, value_type = PARAMETER_BOUNDS[parameter]
        document["parameter_slots"].append({
            "parameter_id": parameter.value,
            "value_type": value_type,
            "minimum": str(minimum),
            "maximum": str(maximum),
            "search_points_maximum": 2,
        })
    points = [slot["search_points_maximum"] for slot in document["parameter_slots"]]
    product = 1
    for value in points:
        product *= value
    assert product <= 196
    candidate = compile_proposal(mechanism, document)
    assert {item.parameter_id for item in candidate.parameter_slots} == set(
        allowed_parameter_ids(mechanism)
    )


def test_schema_and_request_are_mechanism_specific_and_safe() -> None:
    mechanism = Mechanism.BREAKOUT_RETEST
    schema = proposal_schema(mechanism)
    request = build_request_v3(mechanism, attempt_id="fixture-attempt", ordinal=1)
    task = json.loads(request["messages"][1]["content"])

    parameter_enum = schema["$defs"]["ProposalParameterSlot"]["properties"]["parameter_id"]["enum"]
    assert set(parameter_enum) == {item.value for item in allowed_parameter_ids(mechanism)}
    assert task["mechanism_projection"] == mechanism_projection(mechanism)
    assert task["proposal_schema"] == schema
    assert request["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in request
    assert request["tools"] == []
    for forbidden in ("000001.SZ", "/Users/", "api_key", "sealed_validation"):
        assert forbidden not in json.dumps(request, ensure_ascii=False)


def test_compiler_rejects_cross_mechanism_range_duplicates_and_search_explosion() -> None:
    mechanism = Mechanism.VOLATILITY_ADAPTIVE_PULLBACK
    cross = proposal_document(mechanism)
    cross["parameter_slots"].append({
        "parameter_id": "BREAKOUT_LOOKBACK_WEEKS", "value_type": "INTEGER",
        "minimum": "4", "maximum": "26", "search_points_maximum": 2,
    })
    with pytest.raises(D1ControlError, match="mechanism-specific"):
        compile_proposal(mechanism, cross)

    unsafe = proposal_document(mechanism)
    unsafe["parameter_slots"][0]["minimum"] = "5"
    with pytest.raises(D1ControlError, match="safe range"):
        compile_proposal(mechanism, unsafe)

    duplicate = proposal_document(mechanism)
    duplicate["parameter_slots"].append(deepcopy(duplicate["parameter_slots"][0]))
    with pytest.raises(D1ControlError, match="mechanism-specific"):
        compile_proposal(mechanism, duplicate)

    explosion = proposal_document(Mechanism.CONTRACTION_EXPANSION)
    for slot in explosion["parameter_slots"]:
        slot["search_points_maximum"] = 7
    with pytest.raises(D1ControlError, match="mechanism-specific"):
        compile_proposal(Mechanism.CONTRACTION_EXPANSION, explosion)


def test_compiler_rejects_deterministic_fields_and_unsafe_optional_cancellation() -> None:
    document = proposal_document(Mechanism.WEEKLY_STRUCTURE_QUANTILE)
    document["required_features"] = ["WEEKLY_RANGE"]
    with pytest.raises(D1ControlError, match="mechanism-specific"):
        compile_proposal(Mechanism.WEEKLY_STRUCTURE_QUANTILE, document)

    unsafe = proposal_document(Mechanism.WEEKLY_STRUCTURE_QUANTILE)
    unsafe["optional_cancellation_rules"] = ["STRUCTURE_LOW_BROKEN"]
    with pytest.raises(D1ControlError, match="mechanism-specific"):
        compile_proposal(Mechanism.WEEKLY_STRUCTURE_QUANTILE, unsafe)

    unsafe_text = proposal_document(Mechanism.WEEKLY_STRUCTURE_QUANTILE)
    unsafe_text["hypothesis"] = "正常研究文字" * 5 + "\x00"
    with pytest.raises(D1ControlError, match="mechanism-specific"):
        compile_proposal(Mechanism.WEEKLY_STRUCTURE_QUANTILE, unsafe_text)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("optional_cancellation_rules", ["MAX_WAIT_EXPIRED", "MAX_WAIT_EXPIRED"]),
        ("falsification_conditions", ["同一个可证伪条件。", "同一个可证伪条件。"]),
        (
            "lineage",
            {"mode": "INDEPENDENT", "parent_candidate_fingerprints": ["a" * 64]},
        ),
    ],
)
def test_compiler_rejects_duplicate_or_invalid_semantic_contract(
    field: str, value: object
) -> None:
    document = proposal_document(Mechanism.MOVING_AVERAGE_RESUMPTION)
    document[field] = value
    with pytest.raises(D1ControlError, match="mechanism-specific"):
        compile_proposal(Mechanism.MOVING_AVERAGE_RESUMPTION, document)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("value_type", "DECIMAL"),
        ("minimum", "3"),
        ("maximum", "2"),
        ("minimum", "2.5"),
    ],
)
def test_compiler_rejects_parameter_type_order_and_integrality(
    field: str, value: str
) -> None:
    mechanism = Mechanism.BREAKOUT_RETEST
    document = proposal_document(mechanism)
    document["parameter_slots"][0][field] = value
    with pytest.raises(D1ControlError):
        compile_proposal(mechanism, document)


def test_projection_and_request_are_content_addressed_and_legacy_contracts_unchanged() -> None:
    root = Path(__file__).resolve().parents[1]
    identity = projection_bundle_identity()
    requests = [
        build_request_v3(mechanism, attempt_id=f"fixture-{ordinal}", ordinal=ordinal)
        for ordinal, mechanism in enumerate(Mechanism, start=1)
    ]
    assert identity == projection_bundle_identity()
    assert len({sha256(json.dumps(item, sort_keys=True).encode()).hexdigest() for item in requests}) == 6
    assert ProposalContract.load().sha256 == identity["proposal_contract_sha256"]
    assert sha256((root / "src/shaiwei/research/trend_swing/v5_models.py").read_bytes()).hexdigest() == (
        "dc3a19b7cbc07ae6cca44b4c814c1c34c283caf90359b8d81e8f1a68cb54b37b"
    )
    assert sha256((root / "src/shaiwei/research/trend_swing/v5_prompt.py").read_bytes()).hexdigest() == (
        "4dfabdac2e82868c0c710b62866943e2b805c50bdf8242af55f7f6e546e9ce77"
    )


def test_proposal_contract_module_stays_below_architecture_limit() -> None:
    root = Path(__file__).resolve().parents[1]
    assert len((root / "src/shaiwei/research/trend_swing/v5_proposal_contract.py").read_text().splitlines()) <= 400


def test_engineering_report_and_independent_audit_recompute(tmp_path: Path) -> None:
    report = build_report()
    report_path = tmp_path / "engineering_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

    assert report["gate"] == "GO_NEW_LIVE_CANARY_SCOPE_PROPOSAL_ONLY"
    assert report["compiled_candidate_count"] == 6
    assert report["adversarial_case_count"] == 42
    assert all(report["checks"].values())
    assert audit_report(report_path)["verdict"] == "PASS"
