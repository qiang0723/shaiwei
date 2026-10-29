"""TP-F-1 第一段工程：冻结钉扎、候选合同（签名硬约束与身份拒绝）、冻结提示词与盲评包/裁决转录（全合成，不调 LLM）。"""

import hashlib
import json
import shutil

import pytest

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.tp_f_0b.signature import SignatureRule, signature
from shaiwei.research.tp_f_1.candidate import IdentityIndex, validate_candidate
from shaiwei.research.tp_f_1.contract import (
    ADDENDUM_DOCUMENT_RELATIVE,
    ADDENDUM_RELATIVE,
    DOCUMENT_RELATIVE,
    PROTOCOL_RELATIVE,
    TPF1Error,
    TPF1Scope,
    require_r2_1r1_latch,
    validate_bound_inputs,
)
from shaiwei.research.tp_f_1.prompt import PromptBundle, parse_response
from shaiwei.research.tp_f_1.review import blind_packet, parse_ruling, record_ruling, ruling_template

FROZEN = (PROTOCOL_RELATIVE, ADDENDUM_RELATIVE, DOCUMENT_RELATIVE, ADDENDUM_DOCUMENT_RELATIVE)
JOINT = "Mul(Div($close,Mean($close,30d)),Div(Sub($close,$low),Sub($high,$low)))"
RATIONALE = "中期趋势在上而当日收盘回到区间高位，说明回踩被吸收、趋势延续概率更高。"


@pytest.fixture(scope="module")
def scope() -> TPF1Scope:
    return TPF1Scope.load()


@pytest.fixture(scope="module")
def rule() -> SignatureRule:
    from shaiwei.research.tp_f_0b.contract import TPFScope

    return SignatureRule.from_protocol(TPFScope.load().document["identity_registry"]["joint_state_signature"])


def _index(**overrides) -> IdentityIndex:
    base = {"canonical": frozenset(), "sealed_raw_hashes": frozenset(), "d1_v2_joint_state": frozenset(), "source_counts": {}}
    return IdentityIndex(**{**base, **overrides})


@pytest.mark.parametrize("relative", FROZEN)
def test_frozen_files_are_pinned(tmp_path, relative):
    for name in FROZEN:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT_ROOT / name, tmp_path / name)
    TPF1Scope.load(tmp_path)
    (tmp_path / relative).write_text((tmp_path / relative).read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(TPF1Error):
        TPF1Scope.load(tmp_path)


def test_bound_inputs_and_the_r2_1r1_latch_gate(tmp_path, scope):
    checks = validate_bound_inputs(scope)
    assert "src/shaiwei/research/tp_f_0b/signature.py" in checks and len(checks) == 9
    with pytest.raises(TPF1Error, match="none exists"):
        require_r2_1r1_latch(tmp_path)
    report = tmp_path / "data/research/r2-1r1/r2-1r1-continuous-segment-checkpoint-v1/report.json"
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({"schema_version": "r2-1r1-descriptive-report-v1",
                                  "segment": {"latch_day": "20261118", "live_dual_days": 20, "rebalance_cycles": 2}}), encoding="utf-8")
    assert require_r2_1r1_latch(tmp_path)["latch_day"] == "20261118"


def test_candidate_contract_failure_classes(scope, rule):
    index = _index()
    assert validate_candidate(scope, index, rule, JOINT, RATIONALE)["status"] == "QUALIFIED"
    cases = {
        "EMPTY_EXPRESSION": ("  ", RATIONALE),
        "RATIONALE_MISSING_OR_PLACEHOLDER": (JOINT, "啊" * 25),
        "UNSAFE_AST": ("Div($close,Mean($close,60d))", RATIONALE),
        "BACKTRACK_CEILING": ("Div($close,Mean(Ref(Ref($close,50d),50d),20d))", RATIONALE),
        "NOT_JOINT_STATE": ("Div($close,Mean($close,20d))", RATIONALE),
        "TOKEN_CEILING": ("Mul(Mul(Div($close,Mean($close,30d)),Div(Sub($close,$low),Sub($high,$low))),"
                          "Mul(Div($open,Mean($open,40d)),Div($vwap,Mean($vwap,5d))))", RATIONALE),
    }
    for expected, (expression, rationale) in cases.items():
        assert validate_candidate(scope, index, rule, expression, rationale)["status"] == expected, expected
    canonical = signature(JOINT, rule).canonical_sha256
    assert validate_candidate(scope, _index(canonical=frozenset({canonical})), rule, JOINT, RATIONALE)["status"] == "DUPLICATE_CANONICAL_IDENTITY"
    assert validate_candidate(scope, index, rule, JOINT, RATIONALE, seen_in_batch=frozenset({canonical}))["status"] == "DUPLICATE_WITHIN_BATCH"
    normalized = validate_candidate(scope, index, rule, JOINT, RATIONALE)["normalized_expression"]
    sealed = _index(sealed_raw_hashes=frozenset({hashlib.sha256(normalized.encode()).hexdigest()}))
    assert validate_candidate(scope, sealed, rule, JOINT, RATIONALE)["status"] == "DUPLICATE_SEALED_REGISTRY"
    assert validate_candidate(scope, index, rule, None, RATIONALE)["status"] == "EMPTY_EXPRESSION"


def test_real_identity_index_covers_every_frozen_source(rule):
    index = IdentityIndex.build(rule)
    assert index.source_counts["alpha158"] == 158 and index.source_counts["public_routes"] == 3
    assert len(index.d1_v2_joint_state) == 1 and len(index.sealed_raw_hashes) == 221


def test_prompt_is_frozen_consistent_and_carries_no_results(scope):
    bundle = PromptBundle.load(scope)
    request = bundle.build_request(ordinal=3, already_proposed=["Div($close,$open)"])
    task = json.loads(request["messages"][1]["content"])
    assert request["model"] == "deepseek-v4-pro" and request["response_format"] == {"type": "json_object"}
    assert task["already_proposed_in_this_batch"] == ["Div($close,$open)"] and task["prompt_sha256"] == bundle.sha256
    assert not any(word in json.dumps(task) for word in ("RankIC", "rank_ic", "sharpe", "return_", "discovery"))
    assert parse_response(json.dumps({"expression": JOINT, "economic_rationale": RATIONALE})) == (JOINT, RATIONALE)
    for bad in ("not json", json.dumps({"expression": JOINT}), json.dumps({"expression": 1, "economic_rationale": "x"}),
                json.dumps({"expression": JOINT, "economic_rationale": RATIONALE, "extra": 1})):
        assert parse_response(bad) is None


def test_blind_review_packet_and_verbatim_ruling(tmp_path):
    scope_sha = "a" * 64
    candidates = [{"candidate_id": f"{i:012x}", "canonical_expression": JOINT, "economic_rationale": RATIONALE, "rank_ic": 0.05}
                  for i in (1, 2, 3)]
    packet = blind_packet(scope_sha, candidates)
    assert "rank_ic" not in json.dumps(packet) and packet["contains_market_numbers"] is False
    assert ruling_template(packet).startswith(f"盲评 TP-F-1 scope {scope_sha}：")
    text = f"盲评 TP-F-1 scope {scope_sha}：000000000001 保留；000000000002 否决（换皮重复）；000000000003 否决（不是这个机制）。"
    assert parse_ruling(packet, text) == {"000000000001": "RETAIN", "000000000002": "DISGUISED_DUPLICATE",
                                          "000000000003": "NOT_THIS_MECHANISM"}
    for bad in (text.replace("；000000000003 否决（不是这个机制）", ""), text.replace("换皮重复", "不好看"), "批准"):
        with pytest.raises(TPF1Error):
            parse_ruling(packet, bad)
    recorded = record_ruling(tmp_path / "ruling.json", packet, text)
    assert recorded["retained"] == ["000000000001"] and recorded["verbatim_user_text"] == text
    with pytest.raises(TPF1Error, match="already recorded"):
        record_ruling(tmp_path / "ruling.json", packet, text)
