"""In-image TP-F-1 fixture: candidate contract, mock-route generation and blind-review grammar; synthetic only, no network."""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
import json
from pathlib import Path
import tempfile
from typing import Any, Iterator

from shaiwei.research.provider_contract import ProviderResponse
from shaiwei.research.tp_f_0b.contract import TPFScope
from shaiwei.research.tp_f_0b.signature import SignatureRule
from shaiwei.research.tp_f_1.candidate import IdentityIndex, validate_candidate
from shaiwei.research.tp_f_1.contract import TPF1Error, TPF1Scope
from shaiwei.research.tp_f_1.generate import ATTEMPT_HEADER, run_generation
from shaiwei.research.tp_f_1.prompt import PromptBundle
from shaiwei.research.tp_f_1.review import blind_packet, parse_ruling
from shaiwei.research.tp_f_1.scope import write_once
from shaiwei.research.tp_f_1.transport import Prices

RATIONALE = "中期趋势向上而短期回踩被吸收，收盘回到区间高位，延续概率更高。"
CASES = {
    "QUALIFIED": "Mul(Div($close,Mean($close,30d)),Div(Sub($close,$low),Sub($high,$low)))",
    "NOT_JOINT_STATE": "Div($close,Mean($close,20d))",
    "UNSAFE_AST": "Div($close,Mean($close,60d))",
    "BACKTRACK_CEILING": "Div($close,Mean(Ref(Ref($close,50d),50d),20d))",
}
GENERATED = [
    "Sub(Div($close,Mean($close,40d)),Div($close,Mean($close,5d)))",
    "Sub(Div($close,Mean($close,40d)),Div($close,Mean($close,5d)))",
    "Mul(Div($close,Ref($close,20d)),Div(Mean($volume,5d),Mean($volume,20d)))",
    "Mul(Div($close,Mean($close,30d)),Div(Sub($close,$low),Sub($high,$low)))",
]


def fixture() -> dict[str, Any]:
    scope = TPF1Scope.load()
    prompt = PromptBundle.load(scope)
    rule = SignatureRule.from_protocol(TPFScope.load().document["identity_registry"]["joint_state_signature"])
    index = IdentityIndex(frozenset(), frozenset(), frozenset(), {"synthetic": 0})
    failed = [name for name, expression in CASES.items() if validate_candidate(scope, index, rule, expression, RATIONALE)["status"] != name]

    class Fake:
        calls = 0

        def complete(self, _request: dict[str, Any]) -> ProviderResponse:
            Fake.calls += 1
            content = json.dumps({"expression": GENERATED[Fake.calls - 1], "economic_rationale": RATIONALE})
            usage = {"prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 1000, "completion_tokens": 1000}
            return ProviderResponse("deepseek-v4-pro", content, "", "stop", usage, "2026-11-19T00:00:00+00:00", False, "0" * 64)

    @contextmanager
    def provider_for(_attempt: str) -> Iterator[Fake]:
        yield Fake()

    recorded: list[dict[str, Any]] = []

    def record(*, path: Path, **row: Any) -> bool:  # 已发布运行时拒绝非正式账本路径的锁，fixture 只校验行与表头逐列一致
        if tuple(row) != ATTEMPT_HEADER:
            raise TPF1Error("TP-F-1 fixture attempt row differs from the frozen ledger header")
        recorded.append(row)
        return True

    with tempfile.TemporaryDirectory(prefix="tp-f-1-fixture-") as directory:
        ledger = Path(directory) / "attempts.csv"
        ledger.write_text(",".join(ATTEMPT_HEADER) + "\n", encoding="utf-8")
        summary = run_generation(scope, prompt, index, rule, scope_sha256="f" * 64, provider_for=provider_for,
                                 prices=Prices(Decimal("0.003625"), Decimal("0.435"), Decimal("0.87")),
                                 output_dir=Path(directory) / "out", attempt_ledger=ledger, append_attempt=record)
    if [row["ordinal"] for row in recorded] != ["1", "2", "3", "4"]:
        failed.append("attempt_rows_recorded")
    if (summary["status_counts"] != {"DUPLICATE_WITHIN_BATCH": 1, "QUALIFIED": 3} or summary["completed_responses"] != 4
            or summary["stop_reason"] != "QUALIFIED_CANDIDATE_MAXIMUM"):
        failed.append("generation_dedup_and_accounting")
    packet = blind_packet("f" * 64, [{"candidate_id": cid, "canonical_expression": "x", "economic_rationale": RATIONALE}
                                     for cid in summary["qualified_candidates"]])
    first, second, third = summary["qualified_candidates"]
    text = f"盲评 TP-F-1 scope {'f' * 64}：{first} 保留；{second} 否决（换皮重复）；{third} 否决（不是这个机制）。"
    if parse_ruling(packet, text) != {first: "RETAIN", second: "DISGUISED_DUPLICATE", third: "NOT_THIS_MECHANISM"}:
        failed.append("blind_review_grammar")
    try:
        parse_ruling(packet, "批准")
        failed.append("blind_review_refuses_bare_approval")
    except TPF1Error:
        pass
    if failed:
        raise TPF1Error(f"TP-F-1 fixture cases failed: {failed}")
    return {"fixture_pass": True, "candidate_cases": len(CASES), "generation_responses": summary["completed_responses"],
            "synthetic_only": True, "network": False}


def fixture_report(output: Path) -> dict[str, Any]:
    from shaiwei.provenance import code_snapshot_sha256

    contract = TPF1Scope.load()
    report = {"schema_version": "tp-f-1-fixture-report-v1", "protocol_sha256": contract.sha256, "addendum_sha256": contract.addendum_sha256,
              "code_snapshot_sha256": code_snapshot_sha256(), **fixture()}
    write_once(output, report)
    return report
