import pytest

from shaiwei.research.alphagen_expression import (
    ExpressionSafetyError,
    audit_expression,
    normalize_expression_text,
)


def test_expression_audit_is_safe_deterministic_and_counts_complexity():
    first = audit_expression("Std(Med(close,20),30)")
    second = audit_expression("Std(Med(close,20),30)")
    assert first == second
    assert first.pit_sentinel_pass
    assert first.shift_sentinel_pass
    assert first.max_lookback_days == 30
    assert first.required_backtrack_days == 48
    assert first.expression_tokens == 5
    assert first.ast_nodes == 5
    assert first.compared_values > 1000


def test_expression_audit_normalizes_gp_open_terminal_without_eval():
    assert normalize_expression_text("Mean(open_,40)") == "Mean(open,40)"
    assert audit_expression("Mean(open_,40)").shift_sentinel_pass


def test_expression_audit_allocates_cumulative_nested_rolling_backtrack():
    audit = audit_expression("Mad(Sum(Sum(low,20),50),30)")
    assert audit.max_lookback_days == 50
    assert audit.required_backtrack_days == 97
    assert audit.shift_sentinel_pass


def test_expression_audit_rejects_future_reference():
    with pytest.raises(ExpressionSafetyError, match="lookback"):
        audit_expression("Ref(close,-10)")
