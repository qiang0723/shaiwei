"""TP-F-1 stage orchestration and CLI: prepare scope → verbatim approval → G generation → R blind review → E evaluation.

Each stage re-verifies the approved scope inside its container and runs once; the tool never fabricates an approval
or a review ruling.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterator

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ledger import EXPERIMENTS, sha256_file
from shaiwei.research.g1_calibration.ledger_view import complete_rows
from shaiwei.research.g1_calibration.scope import SNAPSHOT_PY, _run, directory_fingerprint
from shaiwei.research.g1_v2_rejudge.protocol import FACTOR_ADMISSIONS_V2
from shaiwei.research.tp_f_1.contract import FAMILY, TPF1Error, TPF1Scope, require_r2_1r1_latch, validate_bound_inputs
from shaiwei.research.tp_f_1.prompt import PromptBundle
from shaiwei.research.tp_f_1.review import blind_packet, record_ruling, ruling_template
from shaiwei.research.tp_f_1.audit import audit_once
from shaiwei.research.tp_f_1.scope import (
    ATTEMPTS, CONTROL_ROOT, FIXTURE_ROOT, OUTPUT_ROOT, REPORTS_ROOT, TRANSPORTS, Envelope, LedgerBaseline, PriceBinding, Scope,
    approval_text, load_approved, record_approval, review_path, scope_attempts, scope_hash, verify, write_once,
)
from shaiwei.research.tp_f_1.transport import Prices, TPF1ExecutionRelease, TPF1TransportProtocol, create_live_provider


def _parts() -> tuple[TPF1Scope, PromptBundle, TPF1TransportProtocol]:
    contract = TPF1Scope.load()
    prompt = PromptBundle.load(contract)
    return contract, prompt, TPF1TransportProtocol.load(contract, prompt)


def ledger_baseline() -> dict[str, int]:
    family = sum(json.loads(row["params_json"]).get("g1_research_family") == FAMILY for row in complete_rows(EXPERIMENTS))
    return {"tp_f_1_attempt_rows": len(complete_rows(ATTEMPTS)), "tp_f_1_transport_rows": len(complete_rows(TRANSPORTS)),
            "tp_f_1_family_experiment_rows": family, "admissions_v2_rows": len(complete_rows(FACTOR_ADMISSIONS_V2))}


def live_facts(contract: TPF1Scope) -> dict[str, Any]:
    settings = load()
    return {"bound": validate_bound_inputs(contract), "qlib_fingerprint": directory_fingerprint(settings.runtime.data_root / "qlib_bin"),
            "r2_1r1_report_sha256": require_r2_1r1_latch()["report_sha256"]}


def prepare(*, image: str, fixture: Path, prices: PriceBinding) -> dict[str, str]:
    from shaiwei.provenance import code_snapshot_sha256

    if _run(["git", "status", "--porcelain", "--untracked-files=no"]):
        raise TPF1Error("tracked worktree is dirty")
    head = _run(["git", "rev-parse", "HEAD"])
    if head != _run(["git", "rev-parse", "origin/main"]):
        raise TPF1Error("HEAD differs from origin/main")
    image_id = _run(["docker", "image", "inspect", "--format", "{{.Id}}", image])
    snapshot = _run(["docker", "run", "--rm", "--network", "none", image, "python", "-c", SNAPSHOT_PY]).splitlines()[-1]
    if snapshot != code_snapshot_sha256() or not image.endswith(snapshot[:12]):
        raise TPF1Error("image code snapshot differs from the pushed worktree")
    contract, prompt, transport = _parts()
    latch = require_r2_1r1_latch()
    report = json.loads(fixture.read_text(encoding="utf-8"))
    if not fixture.resolve().is_relative_to(FIXTURE_ROOT.resolve()) or report.get("fixture_pass") is not True \
            or report.get("code_snapshot_sha256") != snapshot:
        raise TPF1Error("fixture report is not a passing in-image report for this code snapshot")
    facts = live_facts(contract)
    scope = Scope(
        schema_version="tp-f-1-scope-v1", protocol_id=contract.document["protocol_id"], protocol_sha256=contract.sha256,
        addendum_sha256=contract.addendum_sha256, prompt_sha256=prompt.sha256, transport_protocol_sha256=transport.sha256,
        execution_id=f"tpf1-{head[:12]}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}", git_head=head, image=image, image_id=image_id,
        code_snapshot_sha256=snapshot, bound_inputs=facts["bound"], r2_1r1_report_sha256=latch["report_sha256"],
        r2_1r1_latch_day=latch["latch_day"], prices=prices, single_batch_ceiling_usd="1.00",
        qlib_directory_fingerprint=facts["qlib_fingerprint"], fixture_report_path=fixture.resolve().relative_to(PROJECT_ROOT).as_posix(),
        fixture_report_sha256=sha256_file(fixture), ledgers=LedgerBaseline.model_validate(ledger_baseline()),
        prepared_at=datetime.now(timezone.utc).isoformat(),
    )
    envelope = Envelope(scope_sha256=scope_hash(scope), scope=scope)
    write_once(CONTROL_ROOT / "scopes" / f"{envelope.scope_sha256}.scope.json", envelope.model_dump(mode="json"))
    return {"status": "SCOPE_PREPARED_NOT_APPROVED", "scope_sha256": envelope.scope_sha256, "approval_text": approval_text(envelope)}


def _verified(scope_sha: str) -> tuple[Envelope, TPF1Scope, PromptBundle, TPF1TransportProtocol]:
    from shaiwei.provenance import code_snapshot_sha256

    envelope = load_approved(scope_sha)
    contract, prompt, transport = _parts()
    facts = live_facts(contract)
    verify(envelope, contract, code=code_snapshot_sha256(), prompt_sha256=prompt.sha256, transport_sha256=transport.sha256,
           bound=facts["bound"], qlib_fingerprint=facts["qlib_fingerprint"], r2_1r1_report_sha256=facts["r2_1r1_report_sha256"])
    return envelope, contract, prompt, transport


def generate(scope_sha: str) -> dict[str, Any]:
    from shaiwei.research.tp_f_0b.contract import TPFScope
    from shaiwei.research.tp_f_0b.signature import SignatureRule
    from shaiwei.research.tp_f_1.candidate import IdentityIndex
    from shaiwei.research.tp_f_1.generate import run_generation

    envelope, contract, prompt, transport = _verified(scope_sha)
    if ledger_baseline() != envelope.scope.ledgers.model_dump():
        raise TPF1Error("TP-F-1 ledgers are no longer pristine; generation refused")
    rule = SignatureRule.from_protocol(TPFScope.load().document["identity_registry"]["joint_state_signature"])
    release = TPF1ExecutionRelease(release_id=envelope.scope.execution_id, sha256=scope_sha, protocol_sha256=transport.sha256)
    root = OUTPUT_ROOT / envelope.scope.execution_id

    @contextmanager
    def provider_for(attempt_id: str) -> Iterator[Any]:
        provider = create_live_provider(transport, release, attempt_id=attempt_id, transport_ledger_path=TRANSPORTS,
                                        artifact_root=root / "responses")
        try:
            yield provider
        finally:
            provider.close()

    return run_generation(contract, prompt, IdentityIndex.build(rule), rule, scope_sha256=scope_sha, provider_for=provider_for,
                          prices=Prices.from_mapping(envelope.scope.prices.model_dump()), output_dir=root / "generation",
                          attempt_ledger=ATTEMPTS)


def review_packet(scope_sha: str) -> dict[str, Any]:
    envelope = load_approved(scope_sha)
    packet = json.loads((OUTPUT_ROOT / envelope.scope.execution_id / "generation/blind_review_packet.json").read_text(encoding="utf-8"))
    if packet != blind_packet(scope_sha, packet["candidates"]):
        raise TPF1Error("TP-F-1 blind review packet differs from its frozen form")
    return {"packet": packet, "ruling_grammar": ruling_template(packet)}


def record_review(scope_sha: str, text: str) -> dict[str, Any]:
    return record_ruling(review_path(scope_sha), review_packet(scope_sha)["packet"], text)


def evaluate(scope_sha: str) -> dict[str, Any]:
    from shaiwei.ledger import ingest_snapshot_sha256
    from shaiwei.provenance import code_snapshot_sha256
    from shaiwei.research.alphagen_expression import audit_expression
    from shaiwei.research.g1_pipeline import build_baseline_windows, load_research_data
    from shaiwei.research.g1_v2 import load_spec
    from shaiwei.research.g1_v2_rejudge.judge import RejudgeRoots
    from shaiwei.research.tp_f_1.evaluate import EvaluationContext, run_evaluation

    envelope, contract, _, _ = _verified(scope_sha)
    ruling = json.loads(review_path(scope_sha).read_text(encoding="utf-8"))
    root = OUTPUT_ROOT / envelope.scope.execution_id
    candidates = {item["candidate_id"]: item for item in
                  json.loads((root / "generation/qualified_candidates.json").read_text(encoding="utf-8"))["candidates"]}
    attempts = scope_attempts(scope_sha)
    canonical = {row["candidate_id"]: row["canonical_sha256"] for row in attempts if row["candidate_id"]}
    audits = {}
    for cid, item in candidates.items():
        audit = audit_expression(item["normalized_expression"])  # 确定性重算复杂度与泄漏哨兵，供证据绑定
        audits[cid] = {"expression_tokens": audit.expression_tokens, "ast_nodes": audit.ast_nodes,
                       "pit_sentinel_pass": audit.pit_sentinel_pass, "shift_sentinel_pass": audit.shift_sentinel_pass}
        item["canonical_sha256"] = canonical[cid]
    settings = load()
    spec = load_spec(settings)
    research = load_research_data(settings)
    roots = RejudgeRoots(data=root / "evaluation", reports=REPORTS_ROOT / envelope.scope.execution_id, experiments=EXPERIMENTS,
                         admissions=FACTOR_ADMISSIONS_V2)
    ctx = EvaluationContext(settings=settings, scope=contract, spec=spec.spec, spec_sha256=spec.sha256, research=research,
                            baselines=build_baseline_windows(settings, research.labels), code_hash=code_snapshot_sha256(),
                            data_hash=ingest_snapshot_sha256(), scope_sha256=scope_sha)
    return run_evaluation(ctx, roots, attempts=attempts, candidates=candidates, audits=audits,
                          decisions=ruling["decisions"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fixture").add_argument("--output", type=Path, required=True)
    prep = commands.add_parser("prepare")
    for name in ("image", "fixture", "price-hit", "price-miss", "price-output", "price-checked-on", "price-source-url"):
        prep.add_argument(f"--{name}", required=True)
    for name in ("record-approval", "record-review"):
        sub = commands.add_parser(name)
        sub.add_argument("--scope", required=True)
        sub.add_argument("--text", required=True)
    for name in ("check-image", "generate", "review-packet", "evaluate", "audit"):
        commands.add_parser(name).add_argument("--scope", required=True)
    args = parser.parse_args(argv)
    if args.command == "fixture":
        from shaiwei.research.tp_f_1.fixture import fixture_report

        if not args.output.resolve().is_relative_to(FIXTURE_ROOT.resolve()) or args.output.exists():
            raise SystemExit(f"fixture output must be a new file under {FIXTURE_ROOT}")
        result: object = fixture_report(args.output)
    elif args.command == "prepare":
        prices = PriceBinding(input_cache_hit_per_million_usd=args.price_hit, input_cache_miss_per_million_usd=args.price_miss,
                              output_per_million_usd=args.price_output, rechecked_on=args.price_checked_on, source_url=args.price_source_url)
        result = prepare(image=args.image, fixture=Path(args.fixture), prices=prices)
    elif args.command == "record-approval":
        result = record_approval(args.scope, args.text)
    elif args.command == "record-review":
        result = record_review(args.scope, args.text)
    elif args.command == "check-image":
        envelope = load_approved(args.scope)
        if _run(["docker", "image", "inspect", "--format", "{{.Id}}", envelope.scope.image]) != envelope.scope.image_id:
            raise SystemExit("local image id differs from the approved scope")
        print(envelope.scope.image)
        return 0
    elif args.command == "audit":
        result = audit_once(args.scope)
    else:
        result = {"generate": generate, "review-packet": review_packet, "evaluate": evaluate}[args.command](args.scope)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

