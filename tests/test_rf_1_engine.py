import hashlib

import pytest

from shaiwei.research.rf_1.candidate_contract import _sealed_expression_hashes, validate_candidate
from shaiwei.research.rf_1.cli import main
from shaiwei.research.rf_1.contract import RF1Error, RF1Scope
from shaiwei.research.rf_1.fixture import fixture
from shaiwei.research.rf_1.release import load_execution_release


def test_candidate_contract_and_fixture() -> None:
    assert fixture()["fixture_pass"] is True
    scope = RF1Scope.load()
    valid = validate_candidate(
        scope,
        "Sub(Div($open, Ref($close,1)), Div($close,$open))",
        "隔夜与日内分量的方向差异刻画信息吸收效率。",
    )
    assert valid["max_lookback_days"] == 1
    with pytest.raises(RF1Error, match="both \\$open and \\$close"):
        validate_candidate(scope, "Sub($close, Ref($close,1))", "缺少 open 的纯收盘动量候选。")


def test_registry_hash_membership_detects_known_ledger_expression() -> None:
    known = "Sub(EMA($close,10d),EMA($close,50d))"
    digest = hashlib.sha256(known.encode()).hexdigest()
    assert digest in _sealed_expression_hashes()


def test_release_gate_fails_closed_without_frozen_release(tmp_path) -> None:
    with pytest.raises(RF1Error, match="RELEASE_NOT_AUTHORIZED"):
        load_execution_release(RF1Scope.load(), tmp_path / "absent.yaml")


def test_cli_fixture_is_stable(capsys) -> None:
    assert main(["fixture"]) == 0
    assert '"fixture_pass": true' in capsys.readouterr().out
