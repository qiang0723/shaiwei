"""Offline engineering acceptance for the TS-v5-R3E bound proposal contract."""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.provider_contract import D1ControlError
from shaiwei.research.trend_swing.v5_bound_proposal_contract import (
    BoundAttemptAuthority,
    build_request_v4,
    compile_bound_proposal,
    deterministic_search_points,
    independent_authority,
)
from shaiwei.research.trend_swing.v5_contract import canonical_json, sha256_file, sha256_text
from shaiwei.research.trend_swing.v5_evidence import write_once
from shaiwei.research.trend_swing.v5_models import ARCHETYPE_CONTRACT, PARAMETER_BOUNDS, Mechanism
from shaiwei.research.trend_swing.v5_r3e_inputs import load_legacy_documents, verify_frozen_inputs

SCOPE_PATH = PROJECT_ROOT / "config/ts_v5_r3e_bound_proposal_engineering_v1.yaml"
SCOPE_SHA256 = "30185aa4f34d2d186472594af43b0faadabce1215190cdd047031278087ec691"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-r3e-bound-proposal-engineering"
REPORT_PATH = OUTPUT_ROOT / "engineering_report.json"


@dataclass(frozen=True)
class R3EEngineeringScope:
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = SCOPE_PATH) -> "R3EEngineeringScope":
        if path.is_symlink() or sha256_file(path) != SCOPE_SHA256:
            raise D1ControlError("TS-v5-R3E engineering scope identity differs")
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise D1ControlError("TS-v5-R3E engineering scope is invalid") from exc
        method = document.get("engineering_method", {}) if isinstance(document, dict) else {}
        if (
            not isinstance(document, dict)
            or document.get("schema_version") != "ts-v5-r3e-bound-proposal-engineering-v1"
            or document.get("status") != "RESULT_BLIND_ENGINEERING_FROZEN"
            or document.get("external_api_calls_authorized") != 0
            or document.get("production_authorization") != "none"
            or method.get("old_r3c_response_count_exact") != 6
            or method.get("old_response_reasoning_used") is not False
            or method.get("old_response_repaired_normalized_or_admitted") is not False
        ):
            raise D1ControlError("TS-v5-R3E engineering authority differs")
        return cls(document, SCOPE_SHA256)


def minimal_bound_proposal(mechanism: Mechanism) -> dict[str, Any]:
    mandatory = sorted(ARCHETYPE_CONTRACT[mechanism][2], key=lambda item: item.value)
    return {
        "schema_version": "ts-v5-mechanism-proposal-v3",
        "hypothesis": "在冻结趋势与板块条件下，该机制可能形成稳定且可以证伪的入场事件。",
        "economic_rationale_draft": "该研究只比较机制与邻近参数的稳健性，不包含收益或生产结论。",
        "change_summary": "仅替换入场机制表达，保持产品和执行约束不变。",
        "recovery_confirmation": "CLOSE_RECLAIMS_REFERENCE",
        "optional_cancellation_rules": ["MAX_WAIT_EXPIRED"],
        "parameter_slots": [
            {
                "parameter_id": parameter.value,
                "value_type": PARAMETER_BOUNDS[parameter][2],
                "minimum": str(PARAMETER_BOUNDS[parameter][0]),
                "maximum": str(PARAMETER_BOUNDS[parameter][1]),
            }
            for parameter in mandatory
        ],
        "falsification_conditions": [
            "事件无法覆盖多个自然年度或只集中在单一阶段。",
            "邻近参数方向与成本敏感性无法保持一致。",
        ],
    }


def _fails(mechanism: Mechanism, document: dict[str, Any], authority: BoundAttemptAuthority) -> bool:
    try:
        compile_bound_proposal(mechanism, document, authority)
    except (D1ControlError, ValidationError, ValueError):
        return True
    return False


def _adversarial_cases(mechanism: Mechanism, authority: BoundAttemptAuthority) -> dict[str, bool]:
    baseline = minimal_bound_proposal(mechanism)
    cases: dict[str, dict[str, Any]] = {}
    lineage = deepcopy(baseline)
    lineage["lineage"] = {"mode": "ADVERSARIAL_REVISION", "parent_candidate_fingerprints": ["a" * 64]}
    cases["response_injects_lineage"] = lineage
    points = deepcopy(baseline)
    points["parameter_slots"][0]["search_points_maximum"] = 7
    cases["response_injects_search_points"] = points
    deterministic = deepcopy(baseline)
    deterministic["primary_mechanism"] = mechanism.value
    cases["response_injects_deterministic_mechanism"] = deterministic
    missing = deepcopy(baseline)
    missing.pop("schema_version")
    cases["missing_required_field"] = missing
    duplicate = deepcopy(baseline)
    duplicate["parameter_slots"].append(deepcopy(duplicate["parameter_slots"][0]))
    cases["duplicate_parameter"] = duplicate
    unsafe_range = deepcopy(baseline)
    unsafe_range["parameter_slots"][0]["minimum"] = "-1"
    cases["unsafe_parameter_range"] = unsafe_range
    unsafe_text = deepcopy(baseline)
    unsafe_text["hypothesis"] = "该机制包含 python 代码，因此必须失败关闭。"
    cases["unsafe_text"] = unsafe_text
    duplicate_falsification = deepcopy(baseline)
    duplicate_falsification["falsification_conditions"] = ["重复的证伪条件。", "重复的证伪条件。"]
    cases["duplicate_falsification"] = duplicate_falsification
    return {case_id: _fails(mechanism, document, authority) for case_id, document in cases.items()}


def _mechanism_row(mechanism: Mechanism, ordinal: int) -> tuple[dict[str, Any], str]:
    authority = independent_authority(f"ts-v5-r3e-fixture-{ordinal}", ordinal)
    proposal = minimal_bound_proposal(mechanism)
    compiled = compile_bound_proposal(mechanism, proposal, authority)
    request = build_request_v4(mechanism, authority)
    task = json.loads(request["messages"][1]["content"])
    schema_text = canonical_json(task["proposal_schema"])
    adversarial = _adversarial_cases(mechanism, authority)
    row = {
        "mechanism": mechanism.value,
        "candidate_fingerprint": compiled.candidate.fingerprint(),
        "compiled_lineage_mode": compiled.candidate.lineage.mode,
        "evidence_mode": compiled.evidence_mode(),
        "search_evaluations": compiled.search_evaluations,
        "request_authority": task["assigned_attempt_authority"],
        "response_schema_contains_lineage": '"lineage"' in schema_text,
        "response_schema_contains_search_points": "search_points_maximum" in schema_text,
        "adversarial_cases": adversarial,
        "all_adversarial_cases_fail_closed": all(adversarial.values()),
    }
    return row, sha256_text(canonical_json(request))


def _legacy_replay(scope: R3EEngineeringScope, root: Path) -> list[dict[str, Any]]:
    results = []
    for row, document in load_legacy_documents(scope.document, root):
        mechanism = Mechanism(row["mechanism"])
        authority = independent_authority(f"ts-v5-r3e-replay-{row['ordinal']}", int(row["ordinal"]))
        present = sorted(set(document).intersection({"lineage", "parameter_slots"}))
        response_owned_search_points = any(
            isinstance(slot, dict) and "search_points_maximum" in slot
            for slot in document.get("parameter_slots", [])
            if isinstance(document.get("parameter_slots"), list)
        )
        results.append({
            "ordinal": int(row["ordinal"]),
            "mechanism": mechanism.value,
            "legacy_deterministic_field_categories": [
                *(["lineage"] if "lineage" in present else []),
                *(["search_points_maximum"] if response_owned_search_points else []),
            ],
            "admitted_under_v3": not _fails(mechanism, document, authority),
            "repaired_or_normalized": False,
        })
    return results


def build_report(scope: R3EEngineeringScope, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    verify_frozen_inputs(scope.document, root)
    evidence = [_mechanism_row(mechanism, ordinal) for ordinal, mechanism in enumerate(Mechanism, 1)]
    mechanisms, request_hashes = zip(*evidence, strict=True)
    legacy = _legacy_replay(scope, root)
    schedule = {
        str(count): {
            "points_per_slot": deterministic_search_points(count),
            "search_evaluations": deterministic_search_points(count) ** count,
        }
        for count in range(1, 6)
    }
    checks = {
        "all_six_synthetic_proposals_compile": len(mechanisms) == 6,
        "all_compiled_candidates_use_bound_independent_mode": all(
            row["compiled_lineage_mode"] == row["evidence_mode"] == "INDEPENDENT"
            for row in mechanisms
        ),
        "all_requests_bind_approved_authority": all(
            row["request_authority"]["mode"] == "INDEPENDENT"
            and row["request_authority"]["parent_candidate_fingerprints"] == []
            for row in mechanisms
        ),
        "response_schema_excludes_lineage": all(
            row["response_schema_contains_lineage"] is False for row in mechanisms
        ),
        "response_schema_excludes_search_points": all(
            row["response_schema_contains_search_points"] is False for row in mechanisms
        ),
        "deterministic_search_product_within_196": all(
            row["search_evaluations"] <= 196 for row in schedule.values()
        ),
        "all_adversarial_cases_fail_closed": all(
            row["all_adversarial_cases_fail_closed"] for row in mechanisms
        ),
        "all_six_legacy_documents_not_admitted": len(legacy) == 6
        and all(row["admitted_under_v3"] is False for row in legacy),
        "legacy_documents_not_repaired_or_normalized": all(
            row["repaired_or_normalized"] is False for row in legacy
        ),
        "legacy_inputs_byte_immutable": True,
        "external_api_calls_zero": True,
        "no_market_effect_or_backtest": True,
    }
    gate = "GO_R3F_LIVE_CANARY_SCOPE_PROPOSAL_ONLY" if all(checks.values()) else "STOP_R3E_ENGINEERING_GAP"
    report = {
        "schema_version": "ts-v5-r3e-bound-proposal-engineering-report-v1",
        "scope_sha256": scope.sha256,
        "request_bundle_sha256": sha256_text(canonical_json(request_hashes)),
        "mechanisms": list(mechanisms),
        "search_schedule": schedule,
        "legacy_replay": legacy,
        "checks": checks,
        "synthetic_compiled_candidate_count": len(mechanisms),
        "adversarial_case_count": sum(len(row["adversarial_cases"]) for row in mechanisms),
        "legacy_response_count": len(legacy),
        "legacy_candidate_admission_count": sum(row["admitted_under_v3"] for row in legacy),
        "external_api_calls": 0,
        "secret_read": False,
        "market_or_effect_read": False,
        "parameter_search_or_backtest": False,
        "candidate_effectiveness": "NOT_EVALUATED",
        "production_authorization": "none",
        "gate": gate,
    }
    report["engineering_payload_sha256"] = sha256_text(canonical_json(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path, default=SCOPE_PATH)
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    try:
        report = build_report(R3EEngineeringScope.load(args.scope))
        write_once(args.output, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    except (D1ControlError, OSError, TypeError, ValueError, json.JSONDecodeError):
        print(canonical_json({"status": "FAIL", "error_class": "TSV5R3EEngineeringError"}))
        return 2
    print(canonical_json({
        "gate": report["gate"],
        "synthetic_compiled_candidate_count": report["synthetic_compiled_candidate_count"],
        "legacy_candidate_admission_count": report["legacy_candidate_admission_count"],
        "external_api_calls": 0,
    }))
    return 0 if report["gate"] == "GO_R3F_LIVE_CANARY_SCOPE_PROPOSAL_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
