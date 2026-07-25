"""Restricted DeepSeek adapter for D1.

D1-2A validates this module only with ``httpx.MockTransport`` and a project-
scoped temporary ledger. The live factory fails before reading the environment
while the frozen protocol keeps execution unauthorized.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

from shaiwei.ledger import append_llm_factor_transport, sha256_file
from shaiwei.research.llm_factor import (
    D1ControlError,
    D1Protocol,
    ProviderResponse,
    SENSITIVE_OUTPUT_PATTERNS,
    build_request,
    plan_attempt,
)


TRANSPORT_LEDGER_HEADER_V1 = (
    "event_id",
    "attempt_id",
    "request_sha256",
    "sequence",
    "event_type",
    "recorded_at",
    "http_status",
    "completed_response",
    "billing_status",
    "response_id_sha256",
    "response_artifact_path",
    "response_artifact_sha256",
    "source_response_sha256",
    "error_class",
    "provider",
    "model",
    "operator",
)
TRANSPORT_LEDGER_HEADER = TRANSPORT_LEDGER_HEADER_V1
TRANSPORT_LEDGER_HEADER_V2 = (
    "event_id",
    "attempt_id",
    "request_sha256",
    "sequence",
    "event_type",
    "recorded_at",
    "http_status",
    "completed_response",
    "billing_status",
    "response_id_sha256",
    "response_artifact_path",
    "response_artifact_sha256",
    "source_response_sha256",
    "error_class",
    "provider",
    "model",
    "execution_release_id",
    "execution_release_sha256",
    "operator",
)
RETRYABLE_HTTP_STATUS = {429, 500, 503}
TERMINAL_EVENT_TYPES = {
    "COMPLETED",
    "RETRYABLE_ERROR",
    "TERMINAL_ERROR",
    "BILLING_UNCERTAIN",
}


@dataclass(frozen=True)
class D1ExecutionRelease:
    """Result-before execution authorization layered over the immutable D1-2A protocol."""

    path: Path
    document: dict[str, Any]
    sha256: str
    release_id: str
    protocol_sha256: str
    total_authorization_usd: float
    batch_hard_ceiling_usd: float
    response_model_identity: str

    @classmethod
    def load(cls, path: Path, protocol: D1Protocol) -> "D1ExecutionRelease":
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise D1ControlError("D1 execution release is missing") from error
        if not isinstance(document, dict):
            raise D1ControlError("D1 execution release must be a YAML object")
        try:
            authorization = document["authorization"]
            contract = document["frozen_contract"]
            egress = document["egress"]
            scope = document["scope"]
            official = document["official_contract_recheck"]
            ledgers = document["ledgers"]
        except (KeyError, TypeError) as error:
            raise D1ControlError("D1 execution release is incomplete") from error
        if document.get("schema_version") != "d1-llm-factor-execution-release-v1":
            raise D1ControlError("D1 execution release schema differs")
        if document.get("status") != "D1_2B_RESULT_BEFORE_EXECUTION_FROZEN":
            raise D1ControlError("D1 execution release is not frozen")
        if document.get("execution_authorized") is not True:
            raise D1ControlError("D1 live execution is not authorized")
        if document.get("production_authorization") != "none":
            raise D1ControlError("D1 execution release cannot authorize production")
        release_id = str(document.get("release_id", ""))
        if re.fullmatch(r"d1-llm-dsl-v1-batch-[0-9]{3}", release_id) is None:
            raise D1ControlError("D1 execution release id is invalid")
        if contract.get("protocol_path") != "config/d1_llm_factor_research_v1.yaml":
            raise D1ControlError("D1 execution release protocol path differs")
        if contract.get("protocol_sha256") != protocol.sha256:
            raise D1ControlError("D1 execution release protocol hash differs")
        if contract.get("prompt_sha256") != protocol.prompt_bundle.sha256:
            raise D1ControlError("D1 execution release prompt hash differs")
        if contract.get("knowledge_manifest_sha256") != protocol.knowledge_manifest.sha256:
            raise D1ControlError("D1 execution release knowledge hash differs")
        if float(contract.get("original_d1_2a_hard_ceiling_usd", -1)) != 0.75:
            raise D1ControlError("D1 execution release does not preserve the original budget record")
        if contract.get("original_d1_2a_record_is_immutable") is not True:
            raise D1ControlError("D1 execution release could rewrite the D1-2A record")
        if ledgers != {
            "attempt": "ledger/llm_factor_attempts_v2.csv",
            "transport": "ledger/llm_factor_transports_v2.csv",
            "experiment": "ledger/experiments.csv",
            "v1_attempt_and_transport_ledgers_remain_byte_immutable": True,
        }:
            raise D1ControlError("D1 execution release ledger boundary differs")
        if int(authorization.get("completed_responses_exact", 0)) != 40:
            raise D1ControlError("D1 execution release must authorize exactly 40 responses")
        total = float(authorization.get("d1_total_authorization_usd", -1))
        batch = float(authorization.get("batch_hard_ceiling_usd", -1))
        if total != 10.0 or batch != 1.0 or batch > total:
            raise D1ControlError("D1 execution release budget differs from user authorization")
        if authorization.get("future_batches_require_new_protocol_and_instruction") is not True:
            raise D1ControlError("D1 execution release must not authorize future batches")
        expected_scope = {
            "discovery_period_only": ["2016-06-01", "2018-12-31"],
            "W1_W6_access": False,
            "stress_period_access": False,
            "g1_run": False,
            "forward_access": False,
            "scheduler_changes": False,
        }
        if any(scope.get(key) != value for key, value in expected_scope.items()):
            raise D1ControlError("D1 execution release scope differs")
        if any(
            scope.get(key) is not False
            for key in ("web_changes", "guanxiang_access", "new_market_collection")
        ):
            raise D1ControlError("D1 execution release expands forbidden scope")
        if egress != {
            "scheme": "https",
            "host": "api.deepseek.com",
            "port": 443,
            "path": "/chat/completions",
            "trust_environment_proxy": False,
        }:
            raise D1ControlError("D1 execution release egress allowlist differs")
        provider = protocol.document["provider"]
        prices = protocol.document["cost_budget"]
        expected_official = {
            "rechecked_on": "2026-07-25",
            "model": provider["model"],
            "model_version": protocol.returned_model_identity,
            "response_model_field": provider["model"],
            "thinking": provider["thinking"],
            "reasoning_effort": provider["reasoning_effort"],
            "input_cache_hit_per_million_usd": float(
                prices["pro_input_cache_hit_per_million"]
            ),
            "input_cache_miss_per_million_usd": float(
                prices["pro_input_cache_miss_per_million"]
            ),
            "output_per_million_usd": float(prices["pro_output_per_million"]),
        }
        if any(official.get(key) != value for key, value in expected_official.items()):
            raise D1ControlError("D1 official contract recheck differs from the frozen provider")
        if official.get("d1_2a_conflated_version_and_response_field") is not True or official.get(
            "correction_frozen_before_any_paid_response"
        ) is not True:
            raise D1ControlError("D1 response-model correction is not explicitly frozen")
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            release_id=release_id,
            protocol_sha256=protocol.sha256,
            total_authorization_usd=total,
            batch_hard_ceiling_usd=batch,
            response_model_identity=str(official["response_model_field"]),
        )


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_once(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        if path.read_text(encoding="utf-8") != payload:
            raise D1ControlError(f"immutable D1 transport artifact differs: {path.name}")
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def initialize_transport_ledger(
    path: Path, *, header: tuple[str, ...] = TRANSPORT_LEDGER_HEADER_V1
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized_header = ",".join(header) + "\n"
    if path.is_file():
        if path.read_text(encoding="utf-8").splitlines()[:1] != [
            serialized_header.rstrip("\n")
        ]:
            raise D1ControlError(f"D1 transport ledger header differs: {path}")
        return
    path.write_text(serialized_header, encoding="utf-8")


def _read_events(path: Path, *, attempt_id: str, request_sha256: str) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        all_rows = list(csv.DictReader(handle))
    event_ids = [row["event_id"] for row in all_rows]
    if len(event_ids) != len(set(event_ids)):
        raise D1ControlError("D1 transport ledger contains duplicate event ids")
    rows = [row for row in all_rows if row["attempt_id"] == attempt_id]
    if any(row["request_sha256"] != request_sha256 for row in rows):
        raise D1ControlError("D1 transport attempt collides with a different request")
    per_sequence: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        sequence = int(row["sequence"])
        per_sequence.setdefault(sequence, []).append(row)
    for sequence, events in per_sequence.items():
        started = [row for row in events if row["event_type"] == "STARTED"]
        terminal = [row for row in events if row["event_type"] in TERMINAL_EVENT_TYPES]
        if len(started) != 1 or len(terminal) > 1:
            raise D1ControlError(f"D1 transport event sequence is invalid: {sequence}")
        if any(row["event_type"] not in TERMINAL_EVENT_TYPES | {"STARTED"} for row in events):
            raise D1ControlError(f"D1 transport event type is invalid: {sequence}")
    if per_sequence and sorted(per_sequence) != list(range(1, max(per_sequence) + 1)):
        raise D1ControlError("D1 transport sequences are not contiguous")
    return rows


class DeepSeekProvider:
    """OpenAI-compatible DeepSeek provider with fail-closed billing recovery."""

    mode = "deepseek-http"

    def __init__(
        self,
        protocol: D1Protocol,
        *,
        attempt_id: str,
        api_key: str,
        transport_ledger_path: Path,
        artifact_root: Path,
        transport: httpx.BaseTransport,
        execution_release: D1ExecutionRelease | None = None,
        operator: str = "docker-d1-research",
        clock: Callable[[], str] = _now,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if not api_key:
            raise D1ControlError("DeepSeek API key is missing")
        if not isinstance(transport, httpx.MockTransport) and execution_release is None:
            raise D1ControlError(
                "D1 live transport requires a frozen execution release; only MockTransport is allowed"
            )
        if execution_release is not None and execution_release.protocol_sha256 != protocol.sha256:
            raise D1ControlError("D1 execution release does not bind the active protocol")
        self.protocol = protocol
        self.attempt_id = attempt_id
        self.transport_ledger_path = transport_ledger_path
        self.artifact_root = artifact_root
        self.operator = operator
        self.clock = clock
        self.sleeper = sleeper
        self.execution_release = execution_release
        self.external_api_calls = 0
        provider = protocol.document["provider"]
        self._client = httpx.Client(
            base_url=str(provider["base_url"]).rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=httpx.Timeout(float(provider["request_timeout_seconds"])),
            transport=transport,
            trust_env=False,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "DeepSeekProvider":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _event_id(self, request_sha256: str, sequence: int, event_type: str) -> str:
        return _sha256_text(
            f"{self.attempt_id}:{request_sha256}:{sequence}:{event_type}"
        )[:20]

    def _append_event(
        self,
        *,
        request_sha256: str,
        sequence: int,
        event_type: str,
        http_status: str = "",
        completed_response: bool = False,
        billing_status: str,
        response_id_sha256: str = "",
        response_artifact_path: str = "",
        response_artifact_sha256: str = "",
        source_response_sha256: str = "",
        error_class: str = "",
    ) -> None:
        full_row = {
            "event_id": self._event_id(request_sha256, sequence, event_type),
            "attempt_id": self.attempt_id,
            "request_sha256": request_sha256,
            "sequence": str(sequence),
            "event_type": event_type,
            "recorded_at": self.clock(),
            "http_status": http_status,
            "completed_response": str(completed_response).lower(),
            "billing_status": billing_status,
            "response_id_sha256": response_id_sha256,
            "response_artifact_path": response_artifact_path,
            "response_artifact_sha256": response_artifact_sha256,
            "source_response_sha256": source_response_sha256,
            "error_class": error_class,
            "provider": self.protocol.provider_name,
            "model": self.protocol.requested_model,
            "execution_release_id": (
                self.execution_release.release_id if self.execution_release is not None else ""
            ),
            "execution_release_sha256": (
                self.execution_release.sha256 if self.execution_release is not None else ""
            ),
            "operator": self.operator,
        }
        header = (
            TRANSPORT_LEDGER_HEADER_V2
            if self.execution_release is not None
            else TRANSPORT_LEDGER_HEADER_V1
        )
        row = {field: full_row[field] for field in header}
        if tuple(row) != header:
            raise D1ControlError("D1 transport event differs from the tracked schema")
        if not append_llm_factor_transport(path=self.transport_ledger_path, **row):
            raise D1ControlError("D1 transport event unexpectedly already exists")

    def _load_completed(self, event: dict[str, str]) -> ProviderResponse:
        relative = event["response_artifact_path"]
        if not relative:
            raise D1ControlError("completed D1 transport has no recoverable response artifact")
        relative_path = Path(relative)
        if relative_path.is_absolute():
            raise D1ControlError("completed D1 transport artifact path must be relative")
        artifact = (self.artifact_root / relative_path).resolve()
        try:
            artifact.relative_to(self.artifact_root.resolve())
        except ValueError as error:
            raise D1ControlError("completed D1 transport artifact path escapes its root") from error
        if not artifact.is_file() or sha256_file(artifact) != event["response_artifact_sha256"]:
            raise D1ControlError("completed D1 transport response artifact is missing or changed")
        document = json.loads(artifact.read_text(encoding="utf-8"))
        if document.get("source_response_sha256") != event["source_response_sha256"]:
            raise D1ControlError("completed D1 transport response identity differs")
        return ProviderResponse(
            model=str(document["model"]),
            content=str(document["content"]),
            reasoning_content=str(document["reasoning_content"]),
            finish_reason=str(document["finish_reason"]),
            usage=document["usage"],
            completed_at=str(document["completed_at"]),
            sensitive_output_detected=bool(document["sensitive_output_detected"]),
            source_response_sha256=str(document["source_response_sha256"]),
        )

    def _preflight(self, request_sha256: str) -> tuple[list[dict[str, str]], int]:
        initialize_transport_ledger(
            self.transport_ledger_path,
            header=(
                TRANSPORT_LEDGER_HEADER_V2
                if self.execution_release is not None
                else TRANSPORT_LEDGER_HEADER_V1
            ),
        )
        rows = _read_events(
            self.transport_ledger_path,
            attempt_id=self.attempt_id,
            request_sha256=request_sha256,
        )
        completed = [row for row in rows if row["event_type"] == "COMPLETED"]
        if len(completed) > 1:
            raise D1ControlError("D1 transport has multiple completed responses")
        if completed:
            return rows, -1
        if any(row["event_type"] == "BILLING_UNCERTAIN" for row in rows):
            raise D1ControlError("D1 transport billing is uncertain; automatic retry is forbidden")
        by_sequence: dict[int, set[str]] = {}
        for row in rows:
            by_sequence.setdefault(int(row["sequence"]), set()).add(row["event_type"])
        if any(types == {"STARTED"} for types in by_sequence.values()):
            raise D1ControlError("D1 transport has a dangling STARTED event; billing is uncertain")
        if any("TERMINAL_ERROR" in types for types in by_sequence.values()):
            raise D1ControlError("D1 transport previously ended with a terminal provider error")
        next_sequence = max(by_sequence, default=0) + 1
        maximum_sequences = (
            int(self.protocol.document["attempt_budget"]["maximum_transport_retries_per_attempt"])
            + 1
        )
        if next_sequence > maximum_sequences:
            raise D1ControlError("D1 transport retry budget is exhausted")
        return rows, next_sequence

    def _parse_completed_response(
        self, response: httpx.Response
    ) -> tuple[ProviderResponse, str, str, str]:
        raw = response.content
        source_sha256 = hashlib.sha256(raw).hexdigest()
        try:
            document = response.json()
            choices = document["choices"]
            choice = choices[0]
            message = choice["message"]
            created = document["created"]
            if (
                not isinstance(document, dict)
                or not isinstance(choices, list)
                or len(choices) != 1
                or isinstance(created, bool)
                or not isinstance(created, int)
            ):
                raise TypeError
            model = document["model"]
            finish_reason = choice["finish_reason"]
            content = message.get("content") or ""
            reasoning = message.get("reasoning_content") or ""
            usage = document["usage"]
            if not all(
                isinstance(value, str)
                for value in (model, finish_reason, content, reasoning)
            ) or not isinstance(usage, dict):
                raise TypeError
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise D1ControlError("DeepSeek completed response schema is invalid") from error
        completed_at = datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
        sensitive = any(pattern.search(raw.decode("utf-8", errors="replace")) for pattern in SENSITIVE_OUTPUT_PATTERNS)
        provider_response = ProviderResponse(
            model=model,
            content="" if sensitive else content,
            reasoning_content="" if sensitive else reasoning,
            finish_reason=finish_reason,
            usage=usage,
            completed_at=completed_at,
            sensitive_output_detected=sensitive,
            source_response_sha256=source_sha256,
        )
        response_id = document.get("id")
        response_id_sha256 = _sha256_text(response_id) if isinstance(response_id, str) else ""
        artifact = {
            "schema_version": "d1-provider-response-v1",
            "model": provider_response.model,
            "content": provider_response.content,
            "reasoning_content": provider_response.reasoning_content,
            "finish_reason": provider_response.finish_reason,
            "usage": provider_response.usage,
            "completed_at": provider_response.completed_at,
            "sensitive_output_detected": provider_response.sensitive_output_detected,
            "source_response_sha256": source_sha256,
        }
        return provider_response, _canonical_json(artifact) + "\n", response_id_sha256, source_sha256

    def complete(self, request: dict[str, Any]) -> ProviderResponse:
        request_sha256 = _sha256_text(_canonical_json(request))
        rows, sequence = self._preflight(request_sha256)
        completed = [row for row in rows if row["event_type"] == "COMPLETED"]
        if completed:
            return self._load_completed(completed[0])

        maximum_sequences = (
            int(self.protocol.document["attempt_budget"]["maximum_transport_retries_per_attempt"])
            + 1
        )
        while sequence <= maximum_sequences:
            self._append_event(
                request_sha256=request_sha256,
                sequence=sequence,
                event_type="STARTED",
                billing_status="UNKNOWN_UNTIL_TERMINAL",
            )
            try:
                self.external_api_calls += 1
                response = self._client.post("/chat/completions", json=request)
            except (httpx.ConnectError, httpx.ConnectTimeout) as error:
                self._append_event(
                    request_sha256=request_sha256,
                    sequence=sequence,
                    event_type="RETRYABLE_ERROR",
                    billing_status="NO_COMPLETED_RESPONSE",
                    error_class=type(error).__name__,
                )
                if sequence >= maximum_sequences:
                    raise D1ControlError("DeepSeek transport retry budget is exhausted") from error
                self.sleeper(float(2 ** (sequence - 1)))
                sequence += 1
                continue
            except (httpx.ReadTimeout, httpx.WriteError, httpx.RemoteProtocolError) as error:
                self._append_event(
                    request_sha256=request_sha256,
                    sequence=sequence,
                    event_type="BILLING_UNCERTAIN",
                    billing_status="UNCERTAIN",
                    error_class=type(error).__name__,
                )
                raise D1ControlError(
                    "DeepSeek transport billing is uncertain; automatic retry is forbidden"
                ) from error
            except httpx.HTTPError as error:
                self._append_event(
                    request_sha256=request_sha256,
                    sequence=sequence,
                    event_type="BILLING_UNCERTAIN",
                    billing_status="UNCERTAIN",
                    error_class=type(error).__name__,
                )
                raise D1ControlError(
                    "DeepSeek transport outcome is uncertain; automatic retry is forbidden"
                ) from error

            status = response.status_code
            if status in RETRYABLE_HTTP_STATUS:
                self._append_event(
                    request_sha256=request_sha256,
                    sequence=sequence,
                    event_type="RETRYABLE_ERROR",
                    http_status=str(status),
                    billing_status="NO_COMPLETED_RESPONSE",
                    error_class=f"HTTP_{status}",
                )
                if sequence >= maximum_sequences:
                    raise D1ControlError("DeepSeek transport retry budget is exhausted")
                self.sleeper(float(2 ** (sequence - 1)))
                sequence += 1
                continue
            if status != 200:
                self._append_event(
                    request_sha256=request_sha256,
                    sequence=sequence,
                    event_type="TERMINAL_ERROR",
                    http_status=str(status),
                    billing_status="NO_COMPLETED_RESPONSE",
                    error_class=f"HTTP_{status}",
                )
                raise D1ControlError(f"DeepSeek request failed with terminal HTTP status {status}")

            try:
                parsed, artifact_payload, response_id_sha, source_sha = (
                    self._parse_completed_response(response)
                )
            except D1ControlError:
                self._append_event(
                    request_sha256=request_sha256,
                    sequence=sequence,
                    event_type="BILLING_UNCERTAIN",
                    http_status=str(status),
                    billing_status="COMPLETED_UNPARSEABLE",
                    completed_response=True,
                    source_response_sha256=hashlib.sha256(response.content).hexdigest(),
                    error_class="completed_response_schema_invalid",
                )
                raise
            relative = f"responses/{self.attempt_id}-{request_sha256[:12]}.json"
            artifact_path = self.artifact_root / relative
            _write_once(artifact_path, artifact_payload)
            artifact_sha256 = sha256_file(artifact_path)
            self._append_event(
                request_sha256=request_sha256,
                sequence=sequence,
                event_type="COMPLETED",
                http_status=str(status),
                completed_response=True,
                billing_status="COMPLETED_USAGE_RECORDED",
                response_id_sha256=response_id_sha,
                response_artifact_path=relative,
                response_artifact_sha256=artifact_sha256,
                source_response_sha256=source_sha,
            )
            return parsed
        raise D1ControlError("DeepSeek transport retry budget is exhausted")


def create_live_deepseek_provider(
    protocol: D1Protocol,
    *,
    execution_release: D1ExecutionRelease | None = None,
    attempt_id: str,
    transport_ledger_path: Path,
    artifact_root: Path,
    operator: str = "docker-d1-research",
) -> DeepSeekProvider:
    """Create a live provider only after a distinct result-before release authorizes it."""
    if execution_release is None or execution_release.protocol_sha256 != protocol.sha256:
        raise D1ControlError(
            "D1 live execution is not authorized; environment and network were not accessed"
        )
    variable = str(protocol.document["provider"]["api_key_environment_variable"])
    api_key = os.environ.get(variable, "")
    if not api_key:
        raise D1ControlError("DeepSeek API key is missing")
    return DeepSeekProvider(
        protocol,
        attempt_id=attempt_id,
        api_key=api_key,
        transport_ledger_path=transport_ledger_path,
        artifact_root=artifact_root,
        transport=httpx.HTTPTransport(retries=0),
        execution_release=execution_release,
        operator=operator,
    )


def run_mock_transport_fixture(protocol: D1Protocol, output_dir: Path) -> dict[str, Any]:
    """Exercise success, retry and uncertain-billing recovery without a network route."""
    fixed_time = "2026-07-25T14:30:00+00:00"
    request = build_request(protocol, plan_attempt(protocol, 1))

    def completion() -> dict[str, Any]:
        return {
            "id": "fixture-response-id",
            "object": "chat.completion",
            "created": 1784989800,
            "model": protocol.returned_model_identity,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "{}",
                        "reasoning_content": "synthetic transport fixture",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 800,
                "prompt_cache_hit_tokens": 200,
                "prompt_cache_miss_tokens": 600,
                "completion_tokens": 120,
                "total_tokens": 920,
            },
        }

    success_calls = 0

    def success_handler(http_request: httpx.Request) -> httpx.Response:
        nonlocal success_calls
        success_calls += 1
        return httpx.Response(200, json=completion(), request=http_request)

    success = DeepSeekProvider(
        protocol,
        attempt_id="fixture-success",
        api_key="fixture-key-never-logged",
        transport_ledger_path=output_dir / "success/ledger.csv",
        artifact_root=output_dir / "success/artifacts",
        transport=httpx.MockTransport(success_handler),
        clock=lambda: fixed_time,
        sleeper=lambda _: None,
        operator="docker-d1-fixture",
    )
    first = success.complete(request)
    replay = success.complete(request)
    success.close()

    retry_calls = 0

    def retry_handler(http_request: httpx.Request) -> httpx.Response:
        nonlocal retry_calls
        retry_calls += 1
        if retry_calls == 1:
            return httpx.Response(429, json={"error": "synthetic"}, request=http_request)
        return httpx.Response(200, json=completion(), request=http_request)

    retry = DeepSeekProvider(
        protocol,
        attempt_id="fixture-retry",
        api_key="fixture-key-never-logged",
        transport_ledger_path=output_dir / "retry/ledger.csv",
        artifact_root=output_dir / "retry/artifacts",
        transport=httpx.MockTransport(retry_handler),
        clock=lambda: fixed_time,
        sleeper=lambda _: None,
        operator="docker-d1-fixture",
    )
    retried = retry.complete(request)
    retry.close()

    uncertain_calls = 0

    def uncertain_handler(http_request: httpx.Request) -> httpx.Response:
        nonlocal uncertain_calls
        uncertain_calls += 1
        raise httpx.ReadTimeout("synthetic read timeout", request=http_request)

    uncertain = DeepSeekProvider(
        protocol,
        attempt_id="fixture-uncertain",
        api_key="fixture-key-never-logged",
        transport_ledger_path=output_dir / "uncertain/ledger.csv",
        artifact_root=output_dir / "uncertain/artifacts",
        transport=httpx.MockTransport(uncertain_handler),
        clock=lambda: fixed_time,
        sleeper=lambda _: None,
        operator="docker-d1-fixture",
    )
    uncertain_blocked = False
    resume_blocked = False
    try:
        uncertain.complete(request)
    except D1ControlError:
        uncertain_blocked = True
    try:
        uncertain.complete(request)
    except D1ControlError:
        resume_blocked = True
    uncertain.close()

    success_events = _read_events(
        output_dir / "success/ledger.csv",
        attempt_id="fixture-success",
        request_sha256=_sha256_text(_canonical_json(request)),
    )
    retry_events = _read_events(
        output_dir / "retry/ledger.csv",
        attempt_id="fixture-retry",
        request_sha256=_sha256_text(_canonical_json(request)),
    )
    uncertain_events = _read_events(
        output_dir / "uncertain/ledger.csv",
        attempt_id="fixture-uncertain",
        request_sha256=_sha256_text(_canonical_json(request)),
    )
    fixture_pass = bool(
        first == replay
        and first.source_response_sha256
        and retried.source_response_sha256
        and success_calls == 1
        and retry_calls == 2
        and uncertain_calls == 1
        and uncertain_blocked
        and resume_blocked
        and [row["event_type"] for row in success_events] == ["STARTED", "COMPLETED"]
        and [row["event_type"] for row in retry_events]
        == ["STARTED", "RETRYABLE_ERROR", "STARTED", "COMPLETED"]
        and [row["event_type"] for row in uncertain_events]
        == ["STARTED", "BILLING_UNCERTAIN"]
    )
    return {
        "fixture_pass": fixture_pass,
        "transport": "httpx.MockTransport",
        "network_route_required": False,
        "live_external_api_calls": 0,
        "success_mock_requests": success_calls,
        "retry_mock_requests": retry_calls,
        "uncertain_mock_requests": uncertain_calls,
        "success_reused_without_request": success_calls == 1,
        "billing_uncertain_resume_blocked": uncertain_blocked and resume_blocked,
        "transport_event_rows": len(success_events) + len(retry_events) + len(uncertain_events),
    }
