"""TP-F-1 评估段（E）：每个完成响应恰一行总账（N=全部响应，含失败与否决），保留候选算完整 g1-v2 证据，按发现期 |RankIC| 机械选 Top1/Top2 并判定（合成数据，不读真实研究数据、不写真实账本）。"""

import csv
import json
from pathlib import Path

import pytest

from shaiwei.ledger import EXPERIMENTS
from shaiwei.research.g1_v2 import load_spec
from shaiwei.research.g1_v2_rejudge.judge import RejudgeRoots
from shaiwei.research.g1_v2_rejudge.protocol import FACTOR_ADMISSIONS_V2
from shaiwei.research.tp_f_1 import evaluate
from shaiwei.research.tp_f_1.contract import FAMILY, TPF1Error, TPF1Scope
from tests.test_g1_calibration import _fake_backtest, _series, baselines, research, settings  # noqa: F401

SCOPE_SHA = "e" * 64
RATIONALE = "中期趋势向上而短期回踩被吸收，收盘回到区间高位，延续概率更高。"


def _attempt(ordinal: int, status: str, cid: str = "") -> dict[str, str]:
    return {"attempt_id": f"{ordinal:016x}", "ordinal": str(ordinal), "status": status, "candidate_id": cid,
            "canonical_expression": f"canonical-{ordinal}" if status != "RESPONSE_SCHEMA" else "", "prompt_sha256": "p" * 64}


@pytest.fixture()
def staged(tmp_path, settings, research, baselines, monkeypatch):  # noqa: F811
    monkeypatch.setattr(evaluate, "_max_library_correlation", lambda *_args: 0.0)
    experiments = tmp_path / "experiments.csv"
    experiments.write_text(EXPERIMENTS.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
    admissions = tmp_path / "factor_admissions_v2.csv"
    admissions.write_text(FACTOR_ADMISSIONS_V2.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
    roots = RejudgeRoots(data=tmp_path / "data", reports=tmp_path / "logs", experiments=experiments, admissions=admissions)
    spec = load_spec(settings)
    seeds = {"aaaaaaaaaaaa": 301, "bbbbbbbbbbbb": 302, "cccccccccccc": 303}
    ctx = evaluate.EvaluationContext(
        settings=settings, scope=TPF1Scope.load(), spec=spec.spec, spec_sha256=spec.sha256, research=research, baselines=baselines,
        code_hash="c" * 64, data_hash="d" * 64, scope_sha256=SCOPE_SHA, backtest=_fake_backtest(research.labels),
        expression_values=lambda formula, _data: _series(seeds[formula[-12:]]),
    )
    attempts = [_attempt(1, "RESPONSE_SCHEMA"), _attempt(2, "NOT_JOINT_STATE"), _attempt(3, "QUALIFIED", "aaaaaaaaaaaa"),
                _attempt(4, "QUALIFIED", "bbbbbbbbbbbb"), _attempt(5, "QUALIFIED", "cccccccccccc")]
    candidates = {cid: {"candidate_id": cid, "normalized_expression": f"expr-{cid}", "economic_rationale": RATIONALE,
                        "canonical_sha256": cid * 5 + "abcd"} for cid in seeds}
    audits = {cid: {"expression_tokens": 14, "ast_nodes": 15, "pit_sentinel_pass": True, "shift_sentinel_pass": True} for cid in seeds}
    return ctx, roots, attempts, candidates, audits


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_every_response_counts_vetoes_count_and_top_two_are_judged(staged):
    ctx, roots, attempts, candidates, audits = staged
    decisions = {"aaaaaaaaaaaa": "RETAIN", "bbbbbbbbbbbb": "RETAIN", "cccccccccccc": "DISGUISED_DUPLICATE"}
    summary = evaluate.run_evaluation(ctx, roots, attempts=attempts, candidates=candidates, audits=audits, decisions=decisions)
    rows = _rows(roots.experiments)
    assert len(rows) == 5 and all(json.loads(row["params_json"])["g1_research_family"] == FAMILY for row in rows)
    statuses = [json.loads(row["result_json"])["status"] for row in rows]
    assert statuses == ["RESPONSE_SCHEMA", "NOT_JOINT_STATE", "EVALUATED", "EVALUATED", "VETOED_DISGUISED_DUPLICATE"]
    evaluated = {item["candidate_id"]: item["discovery_abs_rank_ic"] for item in summary["evaluated"]}
    assert summary["selected"] == sorted(evaluated, key=lambda cid: -evaluated[cid])
    assert [item["rank"] for item in summary["judged"]] == [1, 2] and len(_rows(roots.admissions)) == 2
    report = json.loads((Path(summary["judged"][0]["report_path"]) if Path(summary["judged"][0]["report_path"]).is_absolute()
                         else Path.cwd() / summary["judged"][0]["report_path"]).read_text())
    assert report["statistics"]["increment_trial_count"] == 5 and report["statistics"]["valid_trial_increment_irs"] == 2
    assert summary["verdict"] in {"GO_SEPARATE_ADMISSION_OR_PAPER_PROTOCOL_PROPOSAL_ONLY", "REJECT_TP_F_AND_CLOSE"}
    assert summary["verdict"] == ("GO_SEPARATE_ADMISSION_OR_PAPER_PROTOCOL_PROPOSAL_ONLY"
                                  if any(item["status"] == "PASS" for item in summary["judged"]) else "REJECT_TP_F_AND_CLOSE")


def test_selection_is_in_sample_and_ties_break_by_canonical_sha():
    items = [{"status": "EVALUATED", "discovery_abs_rank_ic": 0.02, "canonical_sha256": "b", "candidate_id": "x"},
             {"status": "EVALUATED", "discovery_abs_rank_ic": 0.02, "canonical_sha256": "a", "candidate_id": "y"},
             {"status": "EVALUATED", "discovery_abs_rank_ic": 0.05, "canonical_sha256": "c", "candidate_id": "z"},
             {"status": "EVIDENCE_ERROR", "candidate_id": "w"}]
    assert [item["candidate_id"] for item in evaluate.select_top_two(items)] == ["z", "y"]


def test_decisions_must_cover_exactly_the_qualified_candidates(staged):
    ctx, roots, attempts, candidates, audits = staged
    with pytest.raises(TPF1Error, match="exactly the qualified"):
        evaluate.run_evaluation(ctx, roots, attempts=attempts, candidates=candidates, audits=audits, decisions={"aaaaaaaaaaaa": "RETAIN"})
