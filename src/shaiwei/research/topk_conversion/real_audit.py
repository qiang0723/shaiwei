"""Independent M6-3C artifact audit without primary metric or execution imports."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from shaiwei.research.topk_conversion.artifacts import load_json, sha256_file
from shaiwei.research.topk_conversion.audit_statistics import independently_evaluate
from shaiwei.research.topk_conversion.contract import ConversionError
from shaiwei.research.topk_conversion.real_contract import (
    Approval,
    RealProtocol,
    ReleaseScope,
    write_once_document,
)


def _equivalent(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(_equivalent(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _equivalent(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def audit(
    *,
    release_path: Path,
    approval_path: Path,
    effect_root: Path,
    audit_root: Path,
) -> dict[str, Any]:
    protocol = RealProtocol.load()
    release = ReleaseScope.load(release_path, protocol)
    approval = Approval.load(approval_path, release)
    runtime = release.verify_runtime_identity()
    first_path = effect_root / "first_pass/bundle.json"
    replay_path = effect_root / "replay/bundle.json"
    report_path = effect_root / "report.json"
    authorization_path = effect_root / "authorization.json"
    marker_path = effect_root / "top20_effect_started.json"
    expected_files = {
        "authorization.json",
        "top20_effect_started.json",
        "first_pass/bundle.json",
        "replay/bundle.json",
        "report.json",
    }
    actual_files = {
        path.relative_to(effect_root).as_posix()
        for path in effect_root.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise ConversionError("M6-3C effect artifact file set differs")
    audit_root.mkdir(parents=True, exist_ok=True)
    if any(path.name != "audit.json" for path in audit_root.iterdir()):
        raise ConversionError("M6-3C independent audit root contains unexpected files")
    first, replay = load_json(first_path), load_json(replay_path)
    report = load_json(report_path)
    authorization, marker = load_json(authorization_path), load_json(marker_path)
    first_sha, replay_sha = sha256_file(first_path), sha256_file(replay_path)
    rebuilt_first = independently_evaluate(first.get("case", {}), protocol.result)
    rebuilt_replay = independently_evaluate(replay.get("case", {}), protocol.result)
    checks = {
        "release_and_approval_identity": report.get("release_scope_sha256") == release.sha256
        and report.get("approval_sha256") == approval.sha256,
        "runtime_identity": report.get("runtime_identity") == runtime,
        "protocol_identity": first.get("result_protocol_sha256") == protocol.result_sha256
        and first.get("real_release_protocol_sha256") == protocol.sha256
        and first.get("schedule_addendum_sha256") == protocol.addendum_sha256,
        "first_pass_replay_physical_identity": first_sha == replay_sha,
        "first_pass_replay_semantic_identity": first == replay,
        "reported_bundle_identity": report.get("first_pass_bundle_sha256") == first_sha
        and report.get("replay_bundle_sha256") == replay_sha,
        "independent_first_pass_reconstruction": _equivalent(
            rebuilt_first, report.get("result")
        ),
        "independent_replay_reconstruction": _equivalent(rebuilt_replay, rebuilt_first),
        "decision_identity": report.get("decision") == rebuilt_first.get("decision"),
        "authorization_identity": authorization.get("release_scope_sha256") == release.sha256
        and authorization.get("approval_sha256") == approval.sha256,
        "attempt_marker": marker == {
            "release_scope_sha256": release.sha256,
            "portfolio_attempts_consumed": 2,
            "same_release_retry_authorized": False,
        },
        "attempt_count": report.get("portfolio_attempts_consumed") == 2
        and report.get("model_attempt_increment") == 0,
        "non_production": report.get("strategy_effective") == "PENDING_INDEPENDENT_AUDIT"
        and report.get("production_authorization") == "none",
        "no_failure_artifact": not (effect_root / "failure.json").exists(),
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise ConversionError(f"M6-3C independent audit failed: {failed}")
    document = {
        "schema_version": "m6-topk20-conversion-real-audit-v1",
        "release_scope_sha256": release.sha256,
        "approval_sha256": approval.sha256,
        "report_sha256": sha256_file(report_path),
        "bundle_sha256": first_sha,
        "checks": checks,
        "independent_result": rebuilt_first,
        "decision": rebuilt_first["decision"],
        "independent_audit": "PASS",
        "strategy_effective": "NOT_EVALUATED_FOR_PRODUCTION",
        "production_authorization": "none",
    }
    digest, reused = write_once_document(audit_root / "audit.json", document)
    return {
        "audit_sha256": digest,
        "reused": reused,
        "decision": document["decision"],
        "independent_audit": "PASS",
        "strategy_effective": "NOT_EVALUATED_FOR_PRODUCTION",
        "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--effect-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(**vars(args)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
