from shaiwei.research.rf_0c.cli import main
from shaiwei.research.rf_0c.contract import RFCScope
from shaiwei.research.rf_0c.fixture import fixture
from shaiwei.research.rf_0c.registry import build_registry_with_reproduction_check


def test_classifier_supplementary_suspension_layer() -> None:
    assert fixture()["fixture_pass"] is True


def test_registry_reproduces_sealed_rf_0b_registry() -> None:
    registry = build_registry_with_reproduction_check(RFCScope.load())
    assert registry["sections"]["alpha158_family"]["expression_count"] == 158


def test_cli_fixture_is_stable(capsys) -> None:
    assert main(["fixture"]) == 0
    assert '"fixture_pass": true' in capsys.readouterr().out
