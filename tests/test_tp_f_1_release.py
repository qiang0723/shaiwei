"""TP-F-1 scope/逐字批准/漂移拒绝，以及 G→R→E→A 全段合成演练：生成、逐字盲评、评估判定、独立审计 PASS，篡改后 FAIL（不联网、不写真实账本）。"""

from contextlib import contextmanager
from decimal import Decimal
import json

import pytest
from pydantic import ValidationError

from shaiwei.ledger import EXPERIMENTS
from shaiwei.research.g1_v2 import load_spec
from shaiwei.research.g1_v2_rejudge.judge import RejudgeRoots
from shaiwei.research.g1_v2_rejudge.protocol import FACTOR_ADMISSIONS_V2
from shaiwei.research.provider_contract import ProviderResponse
from shaiwei.research.tp_f_0b.contract import TPFScope
from shaiwei.research.tp_f_0b.signature import SignatureRule
from shaiwei.research.tp_f_1 import audit as audit_module
from shaiwei.research.tp_f_1 import evaluate
from shaiwei.research.tp_f_1.candidate import IdentityIndex
from shaiwei.research.tp_f_1.contract import TPF1Error, TPF1Scope
from shaiwei.research.tp_f_1.generate import ATTEMPT_HEADER, run_generation
from shaiwei.research.tp_f_1.prompt import PromptBundle
from shaiwei.research.tp_f_1.review import record_ruling
from shaiwei.research.tp_f_1.scope import (
    Envelope, LedgerBaseline, PriceBinding, Scope, approval_text, load_approved, record_approval, review_path, scope_attempts,
    scope_hash, verify,
)
from shaiwei.research.tp_f_1.transport import Prices
from tests.test_g1_calibration import _fake_backtest, _series, baselines, research, settings  # noqa: F401

EXECUTION = "tpf1-0123456789ab-20261119T100000Z"
RATIONALE = "中期趋势向上而短期回踩被吸收，收盘回到区间高位，延续概率更高。"
EXPRESSIONS = ["Mul(Div($close,Mean($close,30d)),Div(Sub($close,$low),Sub($high,$low)))",
               "Sub(Div($close,Mean($close,40d)),Div($close,Mean($close,5d)))",
               "Mul(Div($close,Ref($close,20d)),Div(Mean($volume,5d),Mean($volume,20d)))"]
PRICES = PriceBinding(input_cache_hit_per_million_usd="0.003625", input_cache_miss_per_million_usd="0.435", output_per_million_usd="0.87",
                      rechecked_on="2026-11-18", source_url="https://api-docs.deepseek.com/quick_start/pricing/")


def _envelope(contract: TPF1Scope, control) -> Envelope:
    scope = Scope(
        schema_version="tp-f-1-scope-v1", protocol_id="tp-f-1-trend-pullback-joint-state-001", protocol_sha256=contract.sha256,
        addendum_sha256=contract.addendum_sha256, prompt_sha256="1" * 64, transport_protocol_sha256="2" * 64, execution_id=EXECUTION,
        git_head="3" * 40, image="shaiwei:tp-f-1-0123456789ab", image_id="sha256:" + "4" * 64, code_snapshot_sha256="5" * 64,
        bound_inputs={"a": "6" * 64}, r2_1r1_report_sha256="7" * 64, r2_1r1_latch_day="20261118", prices=PRICES,
        single_batch_ceiling_usd="1.00", qlib_directory_fingerprint="8" * 64, fixture_report_path="logs/tp-f-1/fixture/x.json",
        fixture_report_sha256="9" * 64,
        ledgers=LedgerBaseline(tp_f_1_attempt_rows=0, tp_f_1_transport_rows=0, tp_f_1_family_experiment_rows=0, admissions_v2_rows=21),
        prepared_at="2026-11-19T00:00:00+00:00",
    )
    envelope = Envelope(scope_sha256=scope_hash(scope), scope=scope)
    path = control / "scopes" / f"{envelope.scope_sha256}.scope.json"
    path.parent.mkdir(parents=True)
    path.write_text(envelope.model_dump_json(), encoding="utf-8")
    return envelope


def test_scope_approval_is_verbatim_and_drift_is_refused(tmp_path):
    contract = TPF1Scope.load()
    envelope = _envelope(contract, tmp_path)
    sha = envelope.scope_sha256
    assert "单批费用上限 1.00 美元" in approval_text(envelope) and "经我逐字盲评" in approval_text(envelope)
    with pytest.raises(TPF1Error, match="verbatim"):
        record_approval(sha, "批准", tmp_path)
    record_approval(sha, approval_text(envelope), tmp_path)
    with pytest.raises(TPF1Error, match="already exists"):
        record_approval(sha, approval_text(envelope), tmp_path)
    approved = load_approved(sha, tmp_path)
    facts = dict(code="5" * 64, prompt_sha256="1" * 64, transport_sha256="2" * 64, bound={"a": "6" * 64},
                 qlib_fingerprint="8" * 64, r2_1r1_report_sha256="7" * 64)
    verify(approved, contract, **facts)
    for key, value in (("prompt_sha256", "0" * 64), ("r2_1r1_report_sha256", "0" * 64), ("bound", {})):
        with pytest.raises(TPF1Error, match="drifted"):
            verify(approved, contract, **{**facts, key: value})
    with pytest.raises(ValidationError):
        LedgerBaseline(tp_f_1_attempt_rows=1, tp_f_1_transport_rows=0, tp_f_1_family_experiment_rows=0, admissions_v2_rows=0)


@pytest.fixture()
def full_run(tmp_path, settings, research, baselines, monkeypatch):  # noqa: F811
    monkeypatch.setattr(evaluate, "_max_library_correlation", lambda *_args: 0.0)
    contract, control = TPF1Scope.load(), tmp_path / "control"
    envelope = _envelope(contract, control)
    sha = envelope.scope_sha256
    record_approval(sha, approval_text(envelope), control)
    prompt = PromptBundle.load(contract)
    rule = SignatureRule.from_protocol(TPFScope.load().document["identity_registry"]["joint_state_signature"])
    attempts = tmp_path / "attempts.csv"
    attempts.write_text(",".join(ATTEMPT_HEADER) + "\n", encoding="utf-8")
    answers = iter(EXPRESSIONS)

    class Fake:
        def complete(self, _request):
            content = json.dumps({"expression": next(answers), "economic_rationale": RATIONALE})
            return ProviderResponse("deepseek-v4-pro", content, "", "stop", {"prompt_cache_miss_tokens": 900, "completion_tokens": 900},
                                    "2026-11-19T10:00:00+00:00", False, "0" * 64)

    @contextmanager
    def provider_for(_attempt):
        yield Fake()

    root = tmp_path / "output" / EXECUTION
    generation = run_generation(contract, prompt, IdentityIndex(frozenset(), frozenset(), frozenset(), {}), rule, scope_sha256=sha,
                                provider_for=provider_for, prices=Prices.from_mapping(PRICES.model_dump()),
                                output_dir=root / "generation", attempt_ledger=attempts)
    packet = json.loads((root / "generation/blind_review_packet.json").read_text())
    ids = generation["qualified_candidates"]
    text = f"盲评 TP-F-1 scope {sha}：{ids[0]} 保留；{ids[1]} 保留；{ids[2]} 否决（不是这个机制）。"
    ruling = record_ruling(review_path(sha, control), packet, text)
    experiments, admissions = tmp_path / "experiments.csv", tmp_path / "admissions_v2.csv"
    experiments.write_text(EXPERIMENTS.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
    admissions.write_text(FACTOR_ADMISSIONS_V2.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
    candidates = {item["candidate_id"]: item for item in json.loads((root / "generation/qualified_candidates.json").read_text())["candidates"]}
    rows = scope_attempts(sha, attempts)
    for cid, item in candidates.items():
        item["canonical_sha256"] = next(row["canonical_sha256"] for row in rows if row["candidate_id"] == cid)
    seeds = {item["normalized_expression"]: 400 + position for position, item in enumerate(candidates.values())}
    spec = load_spec(settings)
    ctx = evaluate.EvaluationContext(settings=settings, scope=contract, spec=spec.spec, spec_sha256=spec.sha256, research=research,
                                     baselines=baselines, code_hash="c" * 64, data_hash="d" * 64, scope_sha256=sha,
                                     backtest=_fake_backtest(research.labels), expression_values=lambda formula, _data: _series(seeds[formula]))
    reports = tmp_path / "logs"
    roots = RejudgeRoots(data=root / "evaluation", reports=reports / EXECUTION, experiments=experiments, admissions=admissions)
    audits = {cid: {"expression_tokens": 14, "ast_nodes": 15, "pit_sentinel_pass": True, "shift_sentinel_pass": True} for cid in candidates}
    summary = evaluate.run_evaluation(ctx, roots, attempts=rows, candidates=candidates, audits=audits, decisions=ruling["decisions"])
    paths = dict(control=control, output_root=tmp_path / "output", reports_root=reports, attempts_path=attempts,
                 experiments=experiments, admissions=admissions, settings=settings)
    return {"sha": sha, "summary": summary, "paths": paths, "root": root, "tmp": tmp_path, "generation": generation}


def test_full_g_r_e_a_rehearsal_audits_pass_and_tampering_fails(full_run):
    sha, paths, tmp = full_run["sha"], full_run["paths"], full_run["tmp"]
    assert full_run["generation"]["completed_responses"] == 3 and len(full_run["summary"]["judged"]) == 2
    report = audit_module.audit_once(sha, audit_root=tmp / "audit", **paths)
    assert report["independent_audit"] == "PASS" and report["completed_responses"] == 3
    assert Decimal(report["spent_usd"]) <= Decimal("1.00")
    with pytest.raises(TPF1Error, match="same-scope audit rerun"):
        audit_module.audit_once(sha, audit_root=tmp / "audit", **paths)
    summary_path = tmp / "logs" / EXECUTION / "evaluation_summary.json"
    tampered = json.loads(summary_path.read_text())
    tampered["selected"] = list(reversed(tampered["selected"]))
    summary_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(TPF1Error, match="selection_recomputed"):
        audit_module.audit_once(sha, audit_root=tmp / "audit2", **paths)
