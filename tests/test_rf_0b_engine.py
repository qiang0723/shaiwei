from shaiwei.research.rf_0b.cli import main
from shaiwei.research.rf_0b.contract import RFBScope
from shaiwei.research.rf_0b.fields import evaluate_field_gate
from shaiwei.research.rf_0b.fixture import fixture
from shaiwei.research.rf_0b.registry import build_identity_registry


def test_registry_counts_and_no_outcome_columns() -> None:
    registry = build_identity_registry(RFBScope.load())
    attempts = (
        registry["sections"]["attempt_ledger_d1_v2"]["attempt_rows"]
        + registry["sections"]["attempt_ledger_m1"]["attempt_rows"]
        + registry["sections"]["attempt_ledger_m3"]["attempt_rows"]
    )
    assert attempts == 104
    assert registry["sections"]["alpha158_family"]["expression_count"] == 158
    assert registry["sections"]["g1_admission_ledger"]["outcome_fields_read"] is False
    assert registry["total_unique_expression_hashes"] >= 158


def test_classifier_covers_all_adversarial_classes() -> None:
    assert fixture()["fixture_pass"] is True


def test_field_gate_is_fail_closed() -> None:
    gate = {
        "open_coverage_minimum_of_member_days": 0.99,
        "prev_close_join_minimum_of_member_days": 0.99,
        "bse_row_maximum": 0,
        "unclassified_missing_field_rows_maximum": 0,
    }
    passing = {
        "open_coverage": 0.995,
        "prev_close_coverage": 0.992,
        "class_counts": {"BSE_ROW": 0, "NO_BAR_UNEXPLAINED": 0},
    }
    assert evaluate_field_gate(passing, gate)["pass"] is True
    failing = {
        "open_coverage": 0.98,
        "prev_close_coverage": 0.992,
        "class_counts": {"BSE_ROW": 0, "NO_BAR_UNEXPLAINED": 0},
    }
    assert evaluate_field_gate(failing, gate)["pass"] is False
    bse = {
        "open_coverage": 1.0,
        "prev_close_coverage": 1.0,
        "class_counts": {"BSE_ROW": 1, "NO_BAR_UNEXPLAINED": 0},
    }
    assert evaluate_field_gate(bse, gate)["pass"] is False


def test_cli_fixture_is_stable(capsys) -> None:
    assert main(["fixture"]) == 0
    assert '"fixture_pass": true' in capsys.readouterr().out
