from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from shaiwei.research.capital_feasibility.delisting_risk_execution_contract import (
    load_execution_adapter,
)
from shaiwei.research.production_conversion.contract import ProtocolError


ROOT = Path(__file__).parents[1]


def test_m6_5c_b_contract_remains_result_sealed_and_claim_pending() -> None:
    document = load_execution_adapter()
    authority = document["authority"]
    recovery = document["recovery"]

    assert document["adapter_contract"]["parameter_default"] == []
    assert document["adapter_contract"]["paper_v1_default_semantics_change_authorized"] is False
    assert recovery["failure_ruling"]["full_regression_failure_count_before_recovery"] == 23
    assert recovery["compatibility_recovery"]["legacy_engine_mutation_authorized"] is False
    assert authority["paper_engine_refactor_authorized"] is False
    assert authority["real_target_read_authorized"] is False
    assert authority["real_price_read_authorized"] is False
    assert authority["real_effect_read_authorized"] is False
    assert authority["canonical_ledger_write_authorized"] is False
    assert authority["release_or_scope_build_authorized"] is False
    assert authority["production_authorization"] == "none"


def test_recovery_contract_rejects_authority_broadening(tmp_path: Path) -> None:
    source = ROOT / (
        "config/"
        "m6_csi800_production_head30_delisting_risk_execution_adapter_recovery_v1.yaml"
    )
    document = yaml.safe_load(source.read_text(encoding="utf-8"))
    document["authority"]["real_effect_read_authorized"] = True
    changed = tmp_path / "changed.yaml"
    changed.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(ProtocolError, match="broadened"):
        load_execution_adapter(changed)


def test_execution_modules_are_bounded_and_do_not_depend_on_research_or_runtime() -> None:
    engine = ROOT / "src/shaiwei/paper/engine.py"
    assert len(engine.read_text(encoding="utf-8").splitlines()) == 860
    assert hashlib.sha256(engine.read_bytes()).hexdigest() == (
        "44e64d1a776973b0eb5b9ba5ce6d8a7d103a7e8a20aaeb172929c7ca4b1d6b94"
    )
    paths = [
        ROOT / "src/shaiwei/paper/sell_execution.py",
        ROOT / "src/shaiwei/paper/risk_exit_policy.py",
        ROOT / "src/shaiwei/paper/risk_exit_engine.py",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert len(text.splitlines()) <= 400
        for forbidden in (
            "shaiwei.research",
            "shaiwei.web",
            "shaiwei.pipeline",
            "docker",
            "qlib",
            "deepseek",
            "shaiwei.ledger",
        ):
            assert forbidden not in text.lower()
