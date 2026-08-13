from copy import deepcopy
from pathlib import Path

import yaml

from shaiwei.research.trend_swing.v5_models import Mechanism
from shaiwei.research.trend_swing.v5_projection_acceptance import minimal_proposal
from shaiwei.research.trend_swing.v5_r3d_diagnostic import diagnose_document


def rule_ids(result: dict[str, object]) -> set[str]:
    return {item["rule_id"] for item in result["visible_contract_findings"]}  # type: ignore[index]


def test_valid_independent_proposal_has_no_defect() -> None:
    result = diagnose_document(
        minimal_proposal(Mechanism.VOLATILITY_ADAPTIVE_PULLBACK),
        Mechanism.VOLATILITY_ADAPTIVE_PULLBACK,
    )
    assert result["visible_contract_pass"] is True
    assert result["compiler_status"] == "PASS"
    assert result["authority_binding_status"] == "PASS"
    assert result["local_implementation_defect"] is False


def test_adversarial_lineage_in_independent_slot_is_local_binding_defect() -> None:
    proposal = minimal_proposal(Mechanism.WEEKLY_STRUCTURE_QUANTILE)
    proposal["lineage"] = {
        "mode": "ADVERSARIAL_REVISION", "parent_candidate_fingerprints": ["a" * 64],
    }
    result = diagnose_document(proposal, Mechanism.WEEKLY_STRUCTURE_QUANTILE)
    assert result["visible_contract_pass"] is True
    assert result["compiler_status"] == "PASS"
    assert result["authority_binding_status"].startswith("FAIL_")
    assert result["local_implementation_defect"] is True


def test_search_product_and_missing_version_are_sanitized_visible_rules() -> None:
    proposal = deepcopy(minimal_proposal(Mechanism.BREAKOUT_RETEST))
    proposal.pop("schema_version")
    for slot in proposal["parameter_slots"]:
        slot["search_points_maximum"] = 7
    proposal["parameter_slots"].append({
        "parameter_id": "MAXIMUM_WAIT_DAYS", "value_type": "INTEGER",
        "minimum": "2", "maximum": "10", "search_points_maximum": 7,
    })
    result = diagnose_document(proposal, Mechanism.BREAKOUT_RETEST)
    assert {"REQUIRED_FIELD_MISSING", "SEARCH_PRODUCT_LIMIT"}.issubset(rule_ids(result))
    assert "submitted" not in str(result).lower()


def test_forbidden_text_and_invalid_parent_hash_are_classified_without_values() -> None:
    proposal = minimal_proposal(Mechanism.CONTRACTION_EXPANSION)
    proposal["hypothesis"] = "该假设包含 python 代码字样，因此必须由可见文本安全门拒绝。"
    proposal["lineage"] = {
        "mode": "ADVERSARIAL_REVISION", "parent_candidate_fingerprints": ["invalid"],
    }
    result = diagnose_document(proposal, Mechanism.CONTRACTION_EXPANSION)
    assert {"TEXT_SAFETY", "LINEAGE_PARENT_HASH"}.issubset(rule_ids(result))
    assert "python" not in str(result).lower()
    assert "invalid" not in str(result).lower()


def test_r3d_modules_remain_narrow() -> None:
    root = Path(__file__).resolve().parents[1] / "src/shaiwei/research/trend_swing"
    assert len((root / "v5_r3d_diagnostic.py").read_text().splitlines()) <= 400
    assert len((root / "v5_r3d_audit.py").read_text().splitlines()) <= 120
    assert len((root / "v5_r3d_inputs.py").read_text().splitlines()) <= 140


def test_r3d_compose_is_offline_secret_free_and_narrow() -> None:
    root = Path(__file__).resolve().parents[1]
    compose = yaml.safe_load((root / "compose.ts-v5-r3d.yaml").read_text(encoding="utf-8"))
    for service in compose["services"].values():
        assert service.get("network_mode") == "none" or "extends" in service
        assert "DEEPSEEK_API_KEY" not in service.get("environment", [])
        assert service.get("read_only") is True or "extends" in service
        assert service.get("cap_drop") == ["ALL"] or "extends" in service
    live = compose["services"]["ts-v5-r3d"]
    mounts = {item["target"]: item for item in live["volumes"]}
    assert mounts["/workspace/data/research/trend_swing/ts-v5-r3c-canary-001"]["read_only"] is True
    assert mounts["/workspace/ledger/ts_v5_r3c_llm_attempts.csv"]["read_only"] is True
    assert "/workspace/data/raw" not in mounts
