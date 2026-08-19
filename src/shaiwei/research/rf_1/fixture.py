"""Synthetic fixtures for the RF-1 candidate contract and release gate."""

from __future__ import annotations

from typing import Any

from shaiwei.research.rf_1.candidate_contract import validate_candidate
from shaiwei.research.rf_1.contract import RF1Error, RF1Scope
from shaiwei.research.rf_1.release import load_execution_release


def fixture() -> dict[str, Any]:
    scope = RF1Scope.load()
    valid = validate_candidate(
        scope,
        "Sub(Div($open, Ref($close,1)), Div($close,$open))",
        "隔夜跳空与日内吸收的方向差异刻画信息吸收效率，负相关状态预期反转延续。",
    )
    if not valid["references_open_and_close"] or valid["registry_dedup"] != "PASS":
        raise RF1Error("RF-1 fixture valid candidate must pass the contract")
    rejected = 0
    for expression, rationale in (
        ("Sub(EMA($close,10d),EMA($close,50d))", "纯双均线动量，无隔夜分量。"),
        ("Div($close,$open)", ""),  # placeholder rationale
        ("Sub($close, Ref($close,1))", "缺少 open 引用。"),
        ("Sub(EMA($open,60d),$close)", "回看超过 50 日上限。"),
    ):
        try:
            validate_candidate(scope, expression, rationale)
        except RF1Error:
            rejected += 1
    if rejected != 4:
        raise RF1Error("RF-1 fixture rejection count differs")
    try:
        load_execution_release(scope)
    except RF1Error as error:
        if "RELEASE_NOT_AUTHORIZED" not in str(error):
            raise
    else:
        raise RF1Error("RF-1 release gate must fail closed without a frozen release")
    return {
        "fixture_pass": True,
        "valid_candidate": valid["normalized_expression"],
        "rejected_candidates": rejected,
        "release_gate_fail_closed": True,
    }
