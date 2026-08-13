"""Offline audit for the TS-v5 first-batch response-contract failure."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError, ProviderResponse
from shaiwei.research.trend_swing.v5_contract import canonical_json, sha256_file, sha256_text
from shaiwei.research.trend_swing.v5_evidence import write_once
from shaiwei.research.trend_swing.v5_response_contract import V5ResponseContract

DEFAULT_RAW_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-llm-batch-001/artifacts/raw"
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "data/research/trend_swing/ts-v5-llm-batch-001/ts_v5_response_recovery_audit.json"
)


def _response(document: dict[str, Any]) -> ProviderResponse:
    try:
        model = document["model"]
        content = document["content"]
        reasoning = document["reasoning_content"]
        finish_reason = document["finish_reason"]
        usage = document["usage"]
        completed_at = document["completed_at"]
        sensitive = document["sensitive_output_detected"]
        response_sha = document["source_response_sha256"]
        if (
            any(
                not isinstance(value, str)
                for value in (model, content, reasoning, finish_reason, completed_at, response_sha)
            )
            or not isinstance(usage, dict)
            or not isinstance(sensitive, bool)
        ):
            raise TypeError
        return ProviderResponse(
            model=model,
            content=content,
            reasoning_content=reasoning,
            finish_reason=finish_reason,
            usage=usage,
            completed_at=completed_at,
            sensitive_output_detected=sensitive,
            source_response_sha256=response_sha,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise D1ControlError("TS-v5 legacy response envelope is invalid") from exc


def audit_legacy_responses(
    raw_root: Path,
    *,
    contract: V5ResponseContract | None = None,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    try:
        resolved = raw_root.resolve(strict=True)
        resolved.relative_to(project_root.resolve(strict=True))
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise D1ControlError("TS-v5 legacy response root is missing or outside the project") from exc
    if raw_root.is_symlink() or not resolved.is_dir():
        raise D1ControlError("TS-v5 legacy response root is not an ordinary directory")
    selected = contract or V5ResponseContract.load()
    paths = sorted(resolved.glob("*.json"))
    responses, evidence = [], []
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise D1ControlError("TS-v5 legacy response evidence contains an invalid file")
        document = json.loads(path.read_text(encoding="utf-8"))
        responses.append(_response(document))
        evidence.append({"name": path.name, "sha256": sha256_file(path)})
    failures = Counter(selected.terminal_failure(item) or "NONE" for item in responses)
    checks = {
        "response_count_exact": len(responses) == 12,
        "finish_reason_length_exact": sum(item.finish_reason == "length" for item in responses) == 12,
        "completion_tokens_at_limit_exact": sum(
            isinstance(item.usage, dict)
            and item.usage.get("completion_tokens") == selected.max_tokens
            for item in responses
        ) == 12,
        "empty_final_content_exact": sum(not item.content for item in responses) == 12,
        "nonempty_reasoning_exact": sum(bool(item.reasoning_content) for item in responses) == 12,
        "failure_class_exact": failures == {"OUTPUT_BUDGET_EXHAUSTED_IN_REASONING": 12},
        "sensitive_output_zero": not any(item.sensitive_output_detected for item in responses),
    }
    return {
        "schema_version": "ts-v5-response-contract-recovery-audit-v1",
        "response_contract_sha256": selected.sha256,
        "legacy_response_count": len(responses),
        "checks": checks,
        "failure_class_counts": dict(sorted(failures.items())),
        "legacy_envelope_bundle_sha256": sha256_text(canonical_json(evidence)),
        "external_api_calls": 0,
        "secret_read": False,
        "market_or_effect_read": False,
        "candidate_content_admitted": False,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        report = audit_legacy_responses(args.raw_root)
        write_once(args.output, json.dumps(report, indent=2, sort_keys=True) + "\n")
    except (D1ControlError, OSError, TypeError, ValueError, json.JSONDecodeError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5ResponseRecoveryError"}))
        return 2
    print(canonical_json(report))
    return 0 if report["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
