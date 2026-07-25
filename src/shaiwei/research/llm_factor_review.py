"""D1-3A result-blind adversarial review runner for the frozen D1 Top2."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import append_llm_factor_review, sha256_file
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.alphagen_expression import audit_expression
from shaiwei.research.deepseek_client import (
    TRANSPORT_LEDGER_HEADER_V2,
    create_live_deepseek_provider,
)
from shaiwei.research.llm_factor import (
    D1ControlError,
    _has_sensitive_output,
    _response_envelope,
    _validate_usage,
)
from shaiwei.research.llm_factor_live import tls_hostname_probe


REVIEW_LEDGER_HEADER = (
    "review_id",
    "protocol_id",
    "execution_release_id",
    "execution_release_sha256",
    "candidate_id",
    "global_ordinal",
    "role",
    "completed_at",
    "provider",
    "requested_model",
    "returned_model",
    "protocol_sha256",
    "prompt_sha256",
    "request_sha256",
    "response_sha256",
    "code_snapshot_sha256",
    "prompt_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "completion_tokens",
    "estimated_cost_usd",
    "parse_status",
    "schema_status",
    "role_verdict",
    "critical_findings",
    "major_findings",
    "minor_findings",
    "failure_class",
    "raw_artifact_path",
    "raw_artifact_sha256",
    "manifest_path",
    "manifest_sha256",
    "operator",
)
ROLES = (
    "construct_validity",
    "economic_sign",
    "pit_execution",
    "redundancy_falsifiability",
)
CANDIDATE_IDS = ("6ade2d0f6d103613", "3bf9d418202afc20")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _project_path(value: str | Path, *, label: str) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        raise D1ControlError(f"D1-3 {label} path must be project-relative")
    candidate = (PROJECT_ROOT / relative).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT.resolve())
    except ValueError as error:
        raise D1ControlError(f"D1-3 {label} path escapes the project") from error
    return candidate


def _write_once(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_text(encoding="utf-8") != payload:
            raise D1ControlError(f"immutable D1-3 review artifact differs: {path.name}")
        return
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _initialize_ledger(path: Path, header: tuple[str, ...]) -> None:
    serialized = ",".join(header) + "\n"
    if path.is_file():
        if path.read_text(encoding="utf-8").splitlines()[:1] != [serialized.rstrip("\n")]:
            raise D1ControlError(f"D1-3 review ledger header differs: {path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")


def _rows(path: Path, header: tuple[str, ...]) -> list[dict[str, str]]:
    _initialize_ledger(path, header)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != header:
            raise D1ControlError(f"D1-3 review ledger schema differs: {path.name}")
        rows = list(reader)
    ids = [row["review_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise D1ControlError("D1-3 review ledger contains duplicate ids")
    return rows


class ReviewFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    severity: Literal["critical", "major", "minor"]
    category: str = Field(min_length=3, max_length=80)
    statement: str = Field(min_length=20, max_length=1000)
    falsification_or_resolution: str = Field(min_length=20, max_length=1000)


class AdversarialReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["d1-adversarial-review-response-v1"]
    candidate_id: str = Field(min_length=16, max_length=16)
    role: Literal[
        "construct_validity",
        "economic_sign",
        "pit_execution",
        "redundancy_falsifiability",
    ]
    role_verdict: Literal["NO_BLOCKER_FOUND", "BLOCKER_FOUND"]
    summary: str = Field(min_length=40, max_length=1500)
    findings: list[ReviewFinding] = Field(max_length=6)
    formula_change_or_new_candidate_proposed: Literal[False]
    performance_claim_made: Literal[False]

    @model_validator(mode="after")
    def verdict_matches_findings(self) -> "AdversarialReviewResponse":
        has_blocker = any(item.severity in {"critical", "major"} for item in self.findings)
        if has_blocker != (self.role_verdict == "BLOCKER_FOUND"):
            raise ValueError("review role verdict differs from critical/major findings")
        return self


@dataclass(frozen=True)
class CandidateBinding:
    candidate_id: str
    global_ordinal: int
    topic: str
    formula: str
    expression_sha256: str
    expression_tokens: int
    ast_nodes: int
    max_lookback_days: int
    expected_direction: str
    original_hypothesis: str
    original_rationale: str


@dataclass(frozen=True)
class ReviewPlan:
    review_id: str
    global_ordinal: int
    candidate: CandidateBinding
    role: str


@dataclass(frozen=True)
class D1ReviewProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    prompt_document: dict[str, Any]
    prompt_sha256: str
    candidates: tuple[CandidateBinding, ...]

    @property
    def provider_name(self) -> str:
        return str(self.document["provider"]["provider"])

    @property
    def requested_model(self) -> str:
        return str(self.document["provider"]["model"])

    @property
    def maximum_output_tokens(self) -> int:
        return int(self.document["provider"]["maximum_output_tokens"])

    @classmethod
    def load(cls, path: Path) -> "D1ReviewProtocol":
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise D1ControlError("D1-3 review protocol is missing") from error
        if not isinstance(document, dict):
            raise D1ControlError("D1-3 review protocol must be a YAML object")
        if (
            document.get("schema_version") != "d1-llm-factor-review-protocol-v1"
            or document.get("status") != "D1_3A_RESULT_BLIND_PROTOCOL_FROZEN"
            or document.get("production_authorization") != "none"
        ):
            raise D1ControlError("D1-3 review protocol identity or status differs")
        source = document.get("source_binding", {})
        manifest_path = _project_path(
            str(source.get("execution_manifest_path", "")), label="source manifest"
        )
        report_path = _project_path(
            str(source.get("run_report_path", "")), label="source report"
        )
        if (
            sha256_file(manifest_path) != source.get("execution_manifest_sha256")
            or sha256_file(report_path) != source.get("run_report_sha256")
        ):
            raise D1ControlError("D1-3 source execution evidence differs")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest.get("completed_response_count") != 40
            or manifest.get("selected_count") != 2
            or manifest.get("production_authorization") != "none"
        ):
            raise D1ControlError("D1-3 source execution manifest is ineligible")
        selected = {
            item["attempt_id"]: item for item in manifest.get("mechanical_top2", [])
        }
        prompt = document.get("prompt", {})
        prompt_path = _project_path(str(prompt.get("path", "")), label="prompt")
        if sha256_file(prompt_path) != prompt.get("sha256"):
            raise D1ControlError("D1-3 review prompt differs")
        prompt_document = yaml.safe_load(prompt_path.read_text(encoding="utf-8"))
        if (
            prompt_document.get("schema_version") != prompt.get("schema_version")
            or prompt_document.get("prompt_id") != prompt.get("prompt_id")
        ):
            raise D1ControlError("D1-3 review prompt identity differs")
        raw_candidates = document.get("candidates", [])
        if [item.get("candidate_id") for item in raw_candidates] != list(CANDIDATE_IDS):
            raise D1ControlError("D1-3 candidate order differs from frozen Top2")
        bindings: list[CandidateBinding] = []
        artifact_root = _project_path(
            "data/research/d1/d1-llm-dsl-v1/artifacts", label="source artifact root"
        )
        for item in raw_candidates:
            candidate_id = str(item["candidate_id"])
            source_item = selected.get(candidate_id)
            if source_item is None or any(
                source_item.get(key) != item.get(target)
                for key, target in (
                    ("global_ordinal", "global_ordinal"),
                    ("topic", "topic"),
                    ("expression_sha256", "expression_sha256"),
                )
            ):
                raise D1ControlError("D1-3 candidate differs from mechanical Top2")
            manifest_file = artifact_root / "manifests" / f"{candidate_id}.json"
            raw_file = artifact_root / "raw" / (
                f"{candidate_id}-{str(item['raw_response_sha256'])[:12]}.json"
            )
            if (
                sha256_file(manifest_file) != item.get("manifest_sha256")
                or sha256_file(raw_file) != item.get("raw_response_sha256")
            ):
                raise D1ControlError("D1-3 selected candidate artifact differs")
            raw_response = json.loads(raw_file.read_text(encoding="utf-8"))
            try:
                source_candidate = json.loads(raw_response["content"])
                source_expression = str(source_candidate["expression"])
                source_direction = str(source_candidate["expected_direction"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise D1ControlError("D1-3 selected raw response is invalid") from error
            audit = audit_expression(source_expression)
            if (
                audit.normalized_expression != item["formula"]
                or _sha256_text(audit.normalized_expression) != item["expression_sha256"]
                or audit.expression_tokens != int(item["expression_tokens"])
                or audit.ast_nodes != int(item["ast_nodes"])
                or audit.max_lookback_days != int(item["max_lookback_days"])
                or source_direction != item["expected_direction"]
                or audit.pit_sentinel_pass is not True
                or audit.shift_sentinel_pass is not True
            ):
                raise D1ControlError("D1-3 formula identity or complexity differs")
            bindings.append(
                CandidateBinding(
                    candidate_id=candidate_id,
                    global_ordinal=int(item["global_ordinal"]),
                    topic=str(item["topic"]),
                    formula=str(item["formula"]),
                    expression_sha256=str(item["expression_sha256"]),
                    expression_tokens=int(item["expression_tokens"]),
                    ast_nodes=int(item["ast_nodes"]),
                    max_lookback_days=int(item["max_lookback_days"]),
                    expected_direction=str(item["expected_direction"]),
                    original_hypothesis=str(item["original_hypothesis"]),
                    original_rationale=str(item["original_rationale"]),
                )
            )
        schedule = document.get("review_schedule", {})
        if (
            schedule.get("candidate_order") != list(CANDIDATE_IDS)
            or schedule.get("role_order") != list(ROLES)
            or int(schedule.get("completed_responses_exact", 0)) != 8
            or schedule.get("early_stop") is not False
            or schedule.get("invalid_response_replacement") is not False
        ):
            raise D1ControlError("D1-3 review schedule differs")
        blindness = document.get("blindness", {})
        if any(
            blindness.get(key) is not False
            for key in (
                "discovery_rank_ic_visible",
                "discovery_coverage_visible",
                "discovery_ordering_score_visible",
                "W1_W6_visible",
                "stress_results_visible",
                "g1_results_visible",
                "forward_results_visible",
                "production_results_visible",
            )
        ):
            raise D1ControlError("D1-3 review blindness differs")
        contamination = blindness.get("primary_window_contamination", {})
        if (
            blindness.get("deepseek_payloads_are_result_blind") is not True
            or blindness.get("primary_window_may_adjudicate_human_gate") is not False
            or blindness.get("independent_result_blind_adjudicator_required") is not True
            or blindness.get("independent_adjudicator_authorization_deferred_to_D1_3B")
            is not True
            or contamination
            != {
                "occurred_before_protocol_freeze": True,
                "candidate_id": "6ade2d0f6d103613",
                "exposed_fields": ["discovery_rank_ic", "discovery_coverage"],
                "exposed_values_must_not_be_repeated_or_exported": True,
                "W1_W6_or_stress_or_g1_exposed": False,
            }
        ):
            raise D1ControlError("D1-3 primary-window contamination record differs")
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            prompt_document=prompt_document,
            prompt_sha256=sha256_file(prompt_path),
            candidates=tuple(bindings),
        )


@dataclass(frozen=True)
class D1ReviewRelease:
    path: Path
    document: dict[str, Any]
    sha256: str
    release_id: str
    protocol_sha256: str
    batch_hard_ceiling_usd: float
    response_model_identity: str

    @classmethod
    def load(cls, path: Path, protocol: D1ReviewProtocol) -> "D1ReviewRelease":
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise D1ControlError("D1-3 review execution release is missing") from error
        if not isinstance(document, dict):
            raise D1ControlError("D1-3 review execution release must be a YAML object")
        if (
            document.get("schema_version")
            != "d1-llm-factor-review-execution-release-v1"
            or document.get("status") != "D1_3A_RESULT_BLIND_EXECUTION_FROZEN"
            or document.get("execution_authorized") is not True
            or document.get("production_authorization") != "none"
        ):
            raise D1ControlError("D1-3 review execution release differs")
        contract = document.get("frozen_contract", {})
        source = protocol.document["source_binding"]
        if (
            contract.get("protocol_sha256") != protocol.sha256
            or contract.get("prompt_sha256") != protocol.prompt_sha256
            or contract.get("d1_2b_execution_manifest_sha256")
            != source["execution_manifest_sha256"]
            or contract.get("d1_2b_run_report_sha256") != source["run_report_sha256"]
            or contract.get("candidate_ids") != list(CANDIDATE_IDS)
            or contract.get("selection_and_candidate_identity_immutable") is not True
        ):
            raise D1ControlError("D1-3 review release does not bind the frozen inputs")
        authorization = document.get("authorization", {})
        batch = float(authorization.get("d1_3a_review_hard_ceiling_usd", -1))
        if (
            int(authorization.get("completed_responses_exact", 0)) != 8
            or batch != 0.25
            or float(authorization.get("d1_total_authorization_usd", -1)) != 10.0
            or authorization.get("unused_budget_is_not_automatic_authority") is not True
        ):
            raise D1ControlError("D1-3 review budget or response count differs")
        scope = document.get("scope", {})
        if any(value is not False for value in scope.values()):
            raise D1ControlError("D1-3 review execution scope expands beyond blind review")
        if document.get("egress") != {
            "scheme": "https",
            "host": "api.deepseek.com",
            "port": 443,
            "path": "/chat/completions",
            "trust_environment_proxy": False,
        }:
            raise D1ControlError("D1-3 review egress allowlist differs")
        provider = protocol.document["provider"]
        prices = protocol.document["cost_budget"]
        expected_provider = {
            "model": provider["model"],
            "response_model_field": provider["response_model_field"],
            "thinking": provider["thinking"],
            "reasoning_effort": provider["reasoning_effort"],
            "input_cache_hit_per_million_usd": float(
                prices["pro_input_cache_hit_per_million"]
            ),
            "input_cache_miss_per_million_usd": float(
                prices["pro_input_cache_miss_per_million"]
            ),
            "output_per_million_usd": float(prices["pro_output_per_million"]),
            "price_change_policy": "fail_closed_before_first_request",
        }
        if document.get("provider_contract") != expected_provider:
            raise D1ControlError("D1-3 official provider contract differs")
        if document.get("ledgers") != {
            "review": "ledger/llm_factor_reviews.csv",
            "transport": "ledger/llm_factor_review_transports.csv",
            "d1_2b_ledgers_are_read_only": True,
        }:
            raise D1ControlError("D1-3 review ledger boundary differs")
        pre_execution = document.get("pre_execution_gates", {})
        if (
            pre_execution.get("independent_human_gate_not_run_in_this_release")
            is not True
            or pre_execution.get("primary_window_not_used_as_human_adjudicator")
            is not True
        ):
            raise D1ControlError("D1-3 independent adjudication boundary differs")
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            release_id=str(document["release_id"]),
            protocol_sha256=protocol.sha256,
            batch_hard_ceiling_usd=batch,
            response_model_identity=str(provider["response_model_field"]),
        )


def plan_review(protocol: D1ReviewProtocol, global_ordinal: int) -> ReviewPlan:
    if not 1 <= global_ordinal <= 8:
        raise D1ControlError("D1-3 review ordinal must be 1..8")
    candidate = protocol.candidates[(global_ordinal - 1) // len(ROLES)]
    role = ROLES[(global_ordinal - 1) % len(ROLES)]
    identity = f"{protocol.document['protocol_id']}:{candidate.candidate_id}:{role}"
    return ReviewPlan(
        review_id=_sha256_text(identity)[:20],
        global_ordinal=global_ordinal,
        candidate=candidate,
        role=role,
    )


def _forbidden_outbound_scan(request: dict[str, Any]) -> None:
    forbidden_keys = {
        "discovery_rank_ic",
        "discovery_coverage",
        "discovery_rank",
        "stress_result",
        "g1_result",
        "forward_result",
        "holdings",
        "api_key",
    }

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in forbidden_keys:
                    raise D1ControlError(f"D1-3 request contains forbidden field: {key}")
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            lowered = value.lower()
            if any(token in lowered for token in ("rankic=", "rank_ic=", "w1:", "w2:", "w3:", "w4:", "w5:", "w6:")):
                raise D1ControlError("D1-3 request contains forbidden result text")

    visit(request)


def build_review_request(protocol: D1ReviewProtocol, plan: ReviewPlan) -> dict[str, Any]:
    peer = next(item for item in protocol.candidates if item.candidate_id != plan.candidate.candidate_id)
    task = {
        "candidate": {
            "candidate_id": plan.candidate.candidate_id,
            "topic": plan.candidate.topic,
            "frozen_formula": plan.candidate.formula,
            "frozen_expected_direction": plan.candidate.expected_direction,
            "non_authoritative_original_hypothesis": plan.candidate.original_hypothesis,
            "non_authoritative_original_rationale": plan.candidate.original_rationale,
            "expression_tokens": plan.candidate.expression_tokens,
            "ast_nodes": plan.candidate.ast_nodes,
            "max_lookback_days": plan.candidate.max_lookback_days,
        },
        "peer_context_for_redundancy_only": {
            "candidate_id": peer.candidate_id,
            "frozen_formula": peer.formula,
            "expression_tokens": peer.expression_tokens,
            "ast_nodes": peer.ast_nodes,
        },
        "assigned_role": plan.role,
        "role_instruction": protocol.prompt_document["roles"][plan.role],
        "execution_clock": "signal-day high/low/close available after close; earliest trade is next official open",
        "response_schema": AdversarialReviewResponse.model_json_schema(),
        "response_contract": protocol.prompt_document["response_contract"],
        "constraints": {
            "no_formula_or_direction_change": True,
            "no_new_candidate_or_variant": True,
            "no_performance_inference": True,
            "no_admission_or_production_decision": True,
        },
    }
    request = {
        "model": protocol.requested_model,
        "messages": [
            {"role": "system", "content": protocol.prompt_document["system_prompt"]},
            {"role": "user", "content": _canonical_json(task)},
        ],
        "thinking": {"type": protocol.document["provider"]["thinking"]},
        "reasoning_effort": protocol.document["provider"]["reasoning_effort"],
        "response_format": {"type": protocol.document["provider"]["response_format"]},
        "max_tokens": protocol.maximum_output_tokens,
        "tools": [],
        "stream": False,
    }
    _forbidden_outbound_scan(request)
    if len(_canonical_json(request).encode("utf-8")) + 1024 > int(
        protocol.document["provider"]["maximum_prompt_tokens_per_attempt"]
    ):
        raise D1ControlError("D1-3 review request exceeds its conservative input bound")
    return request


def _count_findings(review: AdversarialReviewResponse | None) -> dict[str, int]:
    return {
        severity: (
            sum(item.severity == severity for item in review.findings) if review is not None else 0
        )
        for severity in ("critical", "major", "minor")
    }


def _worst_case_cost(protocol: D1ReviewProtocol) -> float:
    provider = protocol.document["provider"]
    prices = protocol.document["cost_budget"]
    return (
        int(provider["maximum_prompt_tokens_per_attempt"])
        * float(prices["pro_input_cache_miss_per_million"])
        + int(provider["maximum_output_tokens"])
        * float(prices["pro_output_per_million"])
    ) / 1_000_000


def _static_evidence(
    *,
    rows: list[dict[str, str]],
    transport_path: Path,
    output_root: Path,
    release: D1ReviewRelease,
) -> dict[str, int]:
    if len(rows) != 8:
        raise D1ControlError("D1-3 static evidence requires exactly eight review rows")
    if [int(row["global_ordinal"]) for row in rows] != list(range(1, 9)):
        raise D1ControlError("D1-3 review ordinals are incomplete")
    request_count = raw_count = manifest_count = 0
    for row in rows:
        if (
            row["execution_release_id"] != release.release_id
            or row["execution_release_sha256"] != release.sha256
        ):
            raise D1ControlError("D1-3 review row release identity differs")
        request_path = output_root / "artifacts/requests" / (
            f"{row['review_id']}-{row['request_sha256'][:12]}.json"
        )
        raw_path = _project_path(row["raw_artifact_path"], label="raw review artifact")
        manifest_path = _project_path(row["manifest_path"], label="review manifest")
        if sha256_file(request_path) != row["request_sha256"]:
            raise D1ControlError("D1-3 request artifact differs")
        if sha256_file(raw_path) != row["raw_artifact_sha256"]:
            raise D1ControlError("D1-3 raw response artifact differs")
        if sha256_file(manifest_path) != row["manifest_sha256"]:
            raise D1ControlError("D1-3 review manifest differs")
        request_count += 1
        raw_count += 1
        manifest_count += 1
    with transport_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != TRANSPORT_LEDGER_HEADER_V2:
            raise D1ControlError("D1-3 transport ledger schema differs")
        events = list(reader)
    completed = [row for row in events if row["event_type"] == "COMPLETED"]
    if len(events) < 16 or len(events) > 48 or len(completed) != 8:
        raise D1ControlError("D1-3 transport completion evidence differs")
    if any(
        event["event_type"] not in {"STARTED", "RETRYABLE_ERROR", "COMPLETED"}
        for event in events
    ):
        raise D1ControlError("D1-3 transport contains a non-recoverable terminal event")
    if any(
        event["execution_release_id"] != release.release_id
        or event["execution_release_sha256"] != release.sha256
        for event in events
    ):
        raise D1ControlError("D1-3 transport release identity differs")
    provider_count = 0
    provider_root = (output_root / "artifacts/provider").resolve()
    for event in completed:
        relative = Path(event["response_artifact_path"])
        if relative.is_absolute():
            raise D1ControlError("D1-3 provider artifact path must be relative")
        candidate = (provider_root / relative).resolve()
        try:
            candidate.relative_to(provider_root)
        except ValueError as error:
            raise D1ControlError("D1-3 provider artifact escapes its root") from error
        if sha256_file(candidate) != event["response_artifact_sha256"]:
            raise D1ControlError("D1-3 provider response artifact differs")
        provider_count += 1
    return {
        "review_rows": len(rows),
        "request_artifacts": request_count,
        "raw_response_artifacts": raw_count,
        "review_manifests": manifest_count,
        "provider_response_artifacts": provider_count,
        "transport_events": len(events),
        "transport_completions": len(completed),
    }


def run_reviews(
    *, protocol_path: Path, release_path: Path, output_root: Path
) -> dict[str, Any]:
    output_root = output_root.resolve()
    try:
        output_root.relative_to(PROJECT_ROOT.resolve())
    except ValueError as error:
        raise D1ControlError("D1-3 output root escapes the project") from error
    protocol = D1ReviewProtocol.load(protocol_path)
    release = D1ReviewRelease.load(release_path, protocol)
    review_path = PROJECT_ROOT / release.document["ledgers"]["review"]
    transport_path = PROJECT_ROOT / release.document["ledgers"]["transport"]
    rows = _rows(review_path, REVIEW_LEDGER_HEADER)
    release_rows = [row for row in rows if row["execution_release_id"] == release.release_id]
    if [int(row["global_ordinal"]) for row in release_rows] != list(
        range(1, len(release_rows) + 1)
    ):
        raise D1ControlError("D1-3 partial reviews are not a contiguous prefix")
    report_path = output_root / "d1_3a_review_report.json"
    if len(release_rows) == 8 and report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        static = _static_evidence(
            rows=release_rows,
            transport_path=transport_path,
            output_root=output_root,
            release=release,
        )
        if report.get("static_evidence") != static:
            raise D1ControlError("D1-3 report differs from re-hashed static evidence")
        return {**report, "idempotent_reuse": True, "external_api_calls_this_run": 0}

    tls_certificate_sha256 = tls_hostname_probe(release)
    code_sha = code_snapshot_sha256()
    external_calls = 0
    reserve = _worst_case_cost(protocol)
    for ordinal in range(len(release_rows) + 1, 9):
        current = _rows(review_path, REVIEW_LEDGER_HEADER)
        cumulative = sum(float(row["estimated_cost_usd"]) for row in current)
        if cumulative + reserve > release.batch_hard_ceiling_usd + 1e-12:
            raise D1ControlError("D1-3 review cost reserve reaches the hard ceiling")
        plan = plan_review(protocol, ordinal)
        request = build_review_request(protocol, plan)
        request_payload = _canonical_json(request) + "\n"
        request_sha = hashlib.sha256(request_payload.encode("utf-8")).hexdigest()
        request_path = output_root / "artifacts/requests" / (
            f"{plan.review_id}-{request_sha[:12]}.json"
        )
        _write_once(request_path, request_payload)
        with create_live_deepseek_provider(
            protocol,  # type: ignore[arg-type]
            execution_release=release,  # type: ignore[arg-type]
            attempt_id=plan.review_id,
            transport_ledger_path=transport_path,
            artifact_root=output_root / "artifacts/provider",
            operator="docker-d1-review",
        ) as provider:
            response = provider.complete(request)
            external_calls += provider.external_api_calls
        usage, cost = _validate_usage(protocol, response.usage)  # type: ignore[arg-type]
        raw_payload = _canonical_json(_response_envelope(response)) + "\n"
        raw_path = output_root / "artifacts/raw" / (
            f"{plan.review_id}-{response.source_response_sha256[:12]}.json"
        )
        _write_once(raw_path, raw_payload)
        review: AdversarialReviewResponse | None = None
        failure_class = ""
        parse_status = "PASS"
        schema_status = "PASS"
        try:
            if response.model != release.response_model_identity:
                raise D1ControlError("D1-3 provider returned a different model")
            if _has_sensitive_output(response):
                raise D1ControlError("D1-3 provider response contains sensitive output")
            document = json.loads(response.content)
            review = AdversarialReviewResponse.model_validate(document)
            if review.candidate_id != plan.candidate.candidate_id or review.role != plan.role:
                raise ValueError("review response identity differs")
        except json.JSONDecodeError:
            parse_status = "FAIL"
            schema_status = "NOT_EVALUATED"
            failure_class = "json_invalid"
        except (TypeError, ValueError):
            schema_status = "FAIL"
            failure_class = "schema_invalid"
        counts = _count_findings(review)
        manifest = {
            "schema_version": "d1-review-artifact-manifest-v1",
            "review_id": plan.review_id,
            "candidate_id": plan.candidate.candidate_id,
            "global_ordinal": ordinal,
            "role": plan.role,
            "request_sha256": request_sha,
            "response_sha256": response.source_response_sha256,
            "raw_artifact_sha256": sha256_file(raw_path),
            "parse_status": parse_status,
            "schema_status": schema_status,
            "role_verdict": review.role_verdict if review is not None else "",
            "finding_counts": counts,
            "failure_class": failure_class,
            "protocol_sha256": protocol.sha256,
            "execution_release_sha256": release.sha256,
        }
        manifest_payload = json.dumps(
            manifest, ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"
        manifest_path = output_root / "artifacts/manifests" / f"{plan.review_id}.json"
        _write_once(manifest_path, manifest_payload)
        row = {
            "review_id": plan.review_id,
            "protocol_id": protocol.document["protocol_id"],
            "execution_release_id": release.release_id,
            "execution_release_sha256": release.sha256,
            "candidate_id": plan.candidate.candidate_id,
            "global_ordinal": str(ordinal),
            "role": plan.role,
            "completed_at": response.completed_at,
            "provider": protocol.provider_name,
            "requested_model": protocol.requested_model,
            "returned_model": response.model,
            "protocol_sha256": protocol.sha256,
            "prompt_sha256": protocol.prompt_sha256,
            "request_sha256": request_sha,
            "response_sha256": response.source_response_sha256,
            "code_snapshot_sha256": code_sha,
            "prompt_tokens": str(usage["prompt_tokens"]),
            "prompt_cache_hit_tokens": str(usage["prompt_cache_hit_tokens"]),
            "prompt_cache_miss_tokens": str(usage["prompt_cache_miss_tokens"]),
            "completion_tokens": str(usage["completion_tokens"]),
            "estimated_cost_usd": f"{cost:.12f}",
            "parse_status": parse_status,
            "schema_status": schema_status,
            "role_verdict": review.role_verdict if review is not None else "",
            "critical_findings": str(counts["critical"]),
            "major_findings": str(counts["major"]),
            "minor_findings": str(counts["minor"]),
            "failure_class": failure_class,
            "raw_artifact_path": raw_path.relative_to(PROJECT_ROOT).as_posix(),
            "raw_artifact_sha256": sha256_file(raw_path),
            "manifest_path": manifest_path.relative_to(PROJECT_ROOT).as_posix(),
            "manifest_sha256": sha256_file(manifest_path),
            "operator": "docker-d1-review",
        }
        if not append_llm_factor_review(path=review_path, **row):
            raise D1ControlError("D1-3 review row unexpectedly already exists")
        print(
            _canonical_json(
                {
                    "global_ordinal": ordinal,
                    "candidate_id": plan.candidate.candidate_id,
                    "role": plan.role,
                    "completed": True,
                    "schema_status": schema_status,
                    "role_verdict": row["role_verdict"] or "INVALID",
                    "cumulative_cost_usd": round(
                        sum(
                            float(item["estimated_cost_usd"])
                            for item in _rows(review_path, REVIEW_LEDGER_HEADER)
                        ),
                        9,
                    ),
                }
            ),
            flush=True,
        )
        if response.model != release.response_model_identity or _has_sensitive_output(response):
            raise D1ControlError("D1-3 review stopped at a fatal completed-response gate")

    final_rows = [
        row
        for row in _rows(review_path, REVIEW_LEDGER_HEADER)
        if row["execution_release_id"] == release.release_id
    ]
    static = _static_evidence(
        rows=final_rows,
        transport_path=transport_path,
        output_root=output_root,
        release=release,
    )
    total_cost = sum(float(row["estimated_cost_usd"]) for row in final_rows)
    valid = sum(row["schema_status"] == "PASS" for row in final_rows)
    report = {
        "schema_version": "d1-review-live-run-report-v1",
        "protocol_id": protocol.document["protocol_id"],
        "protocol_sha256": protocol.sha256,
        "prompt_sha256": protocol.prompt_sha256,
        "execution_release_id": release.release_id,
        "execution_release_sha256": release.sha256,
        "release_git_head": git_head(),
        "code_snapshot_sha256": code_sha,
        "completed_response_count": len(final_rows),
        "completed_response_exact_gate": len(final_rows) == 8,
        "valid_review_count": valid,
        "all_8_valid_reviews_required_for_human_gate": True,
        "human_gate_ready": valid == 8,
        "primary_window_may_adjudicate_human_gate": False,
        "independent_result_blind_adjudicator_required": True,
        "role_verdict_counts": {
            verdict: sum(row["role_verdict"] == verdict for row in final_rows)
            for verdict in ("NO_BLOCKER_FOUND", "BLOCKER_FOUND")
        },
        "failure_class_counts": {
            failure or "NONE": sum(row["failure_class"] == failure for row in final_rows)
            for failure in sorted({row["failure_class"] for row in final_rows})
        },
        "actual_cost_usd": total_cost,
        "review_hard_ceiling_usd": release.batch_hard_ceiling_usd,
        "cost_gate_pass": total_cost <= release.batch_hard_ceiling_usd,
        "new_candidates_generated": False,
        "discovery_metrics_read_or_sent": False,
        "W1_W6_read_or_sent": False,
        "stress_or_g1_read_or_sent": False,
        "human_adjudication_complete": False,
        "review_execution_gate": (
            "GO_INDEPENDENT_HUMAN_GATE" if valid == 8 else "STOP_INVALID_REVIEW_RESPONSE"
        ),
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "tls_certificate_sha256": tls_certificate_sha256,
        "static_evidence": static,
    }
    _write_once(report_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {**report, "idempotent_reuse": False, "external_api_calls_this_run": external_calls}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=PROJECT_ROOT / "config/d1_llm_factor_review_v1.yaml",
    )
    parser.add_argument(
        "--execution-release",
        type=Path,
        default=PROJECT_ROOT / "config/d1_llm_factor_review_execution_v1.yaml",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "data/research/d1/d1-llm-dsl-v1/d1_3_reviews",
    )
    args = parser.parse_args(argv)
    try:
        report = run_reviews(
            protocol_path=args.protocol,
            release_path=args.execution_release,
            output_root=args.output_root,
        )
    except (D1ControlError, OSError, RuntimeError, TypeError, ValueError):
        print(_canonical_json({"status": "FAIL", "error_class": "D1ReviewError"}))
        return 2
    print(_canonical_json(report))
    return 0 if report["review_execution_gate"] == "GO_INDEPENDENT_HUMAN_GATE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
