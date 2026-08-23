"""Independent artifact-only audit for the M6-5C delisting-risk diagnostic."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from shaiwei.research.effect_attempt_claim import verify_effect_attempt_claim
from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import mapping, write_once_document

from .delisting_independent_audit import independently_evaluate
from .delisting_release_contract import Approval, ReleaseProtocol, ReleaseScope


EXPECTED_FILES = {
    "authorization.json", "effect_started.json", "first_pass/bundle.json",
    "replay/bundle.json", "report.json",
}


def _equivalent(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(
            _equivalent(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _equivalent(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def _target_checks(bundle: dict[str, Any]) -> bool:
    for window in bundle["windows"].values():
        for trace in window["risk_trace"]:
            targets = trace["target_codes"]
            eligible = trace["decision"]["eligible_target_codes"]
            if (
                len(targets) != 30
                or len(set(targets)) != 30
                or not set(eligible) <= set(targets)
                or any(str(code).endswith(".BJ") for code in targets)
            ):
                return False
    return True


def audit_loaded(
    *, release: ReleaseScope, approval: Approval, effect_root: Path,
    ledger_path: Path, receipt_path: Path, audit_root: Path,
) -> dict[str, Any]:
    runtime = release.verify_runtime_identity()
    actual = {
        path.relative_to(effect_root).as_posix()
        for path in effect_root.rglob("*") if path.is_file()
    }
    if actual != EXPECTED_FILES:
        raise ProtocolError("M6-5C effect artifact file set differs")
    claim = verify_effect_attempt_claim(ledger_path=ledger_path, receipt_path=receipt_path)
    audit_root.mkdir(parents=True, exist_ok=True)
    if any(path.name != "audit.json" for path in audit_root.iterdir()):
        raise ProtocolError("M6-5C audit root contains unexpected files")
    first_path = effect_root / "first_pass/bundle.json"
    replay_path = effect_root / "replay/bundle.json"
    first, replay = mapping(first_path), mapping(replay_path)
    report = mapping(effect_root / "report.json")
    authorization = mapping(effect_root / "authorization.json")
    started = mapping(effect_root / "effect_started.json")
    rebuilt_first = independently_evaluate(first)
    rebuilt_replay = independently_evaluate(replay)
    first_sha, replay_sha = sha256_file(first_path), sha256_file(replay_path)
    claim_sha = claim["receipt_sha256"]
    checks = {
        "release_and_approval_identity": (
            report.get("release_scope_sha256") == release.sha256
            and report.get("approval_sha256") == approval.sha256
        ),
        "runtime_identity": report.get("runtime_identity") == runtime,
        "claim_identity": (
            report.get("claim_receipt_sha256") == claim_sha
            and authorization.get("claim_receipt_sha256") == claim_sha
            and started.get("claim_receipt_sha256") == claim_sha
            and report.get("experiment_id") == claim.get("experiment_id")
        ),
        "artifact_file_set_exact": actual == EXPECTED_FILES,
        "first_pass_replay_physical_identity": first_sha == replay_sha,
        "first_pass_replay_semantic_identity": first == replay,
        "reported_bundle_identity": (
            report.get("first_pass_bundle_sha256") == first_sha
            and report.get("replay_bundle_sha256") == replay_sha
        ),
        "target_identity": _target_checks(first) and _target_checks(replay),
        "independent_first_reconstruction": _equivalent(rebuilt_first, first.get("result")),
        "independent_replay_reconstruction": _equivalent(rebuilt_replay, rebuilt_first),
        "reported_result_identity": (
            report.get("result_sha256") == canonical_sha256(rebuilt_first)
            and report.get("decision") == rebuilt_first["decision"]
        ),
        "attempt_count": (
            report.get("family_attempts_before_run") == 0
            and report.get("new_attempts_consumed") == 1
            and report.get("total_family_attempts") == 1
        ),
        "post_hoc_non_production": (
            report.get("strategy_effectiveness_authority") == "NOT_FOR_PRODUCTION_VERDICT"
            and report.get("production_authorization") == "none"
        ),
        "no_failure_artifact": not (effect_root / "failure.json").exists(),
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise ProtocolError(f"M6-5C independent audit failed: {failed}")
    document = {
        "schema_version": "m6-head30-500k-delisting-risk-independent-audit-v1",
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "claim_receipt_sha256": claim_sha,
        "report_sha256": sha256_file(effect_root / "report.json"),
        "bundle_sha256": first_sha,
        "checks": checks,
        "independent_result_sha256": canonical_sha256(rebuilt_first),
        "decision": rebuilt_first["decision"],
        "independent_audit": "PASS",
        "strategy_effectiveness_authority": "NOT_FOR_PRODUCTION_VERDICT",
        "production_authorization": "none",
    }
    digest, reused = write_once_document(audit_root / "audit.json", document)
    return {"audit_sha256": digest, "reused": reused, "decision": document["decision"]}


def audit(**paths: Path) -> dict[str, Any]:
    protocol = ReleaseProtocol.load()
    release = ReleaseScope.load(paths.pop("release_path"), protocol)
    approval = Approval.load(paths.pop("approval_path"), release)
    return audit_loaded(release=release, approval=approval, **paths)


def main(argv: list[str] | None = None, *, auditor: Any = audit) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("release", "approval", "effect-root", "ledger", "claim-receipt", "audit-root"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(argv)
    values = vars(args)
    result = auditor(
        release_path=values["release"], approval_path=values["approval"],
        effect_root=values["effect_root"], ledger_path=values["ledger"],
        receipt_path=values["claim_receipt"], audit_root=values["audit_root"],
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
