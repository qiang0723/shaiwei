"""Result-before M3-3 preexecution release with live authority kept closed."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from shaiwei.ledger import sha256_file
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.m3_multi_pool_review_contract import (
    CANDIDATE_IDS,
    DEFAULT_RELEASE_PATH,
    M3ReviewProtocol,
    canonical_json,
    project_path,
    sha256_text,
)
from shaiwei.research.m3_multi_pool_review_request import preflight


def code_bundle_sha256(paths: list[str]) -> str:
    if not paths or len(paths) != len(set(paths)):
        raise D1ControlError("M3-3 code bundle paths are missing or duplicated")
    bindings = {path: sha256_file(project_path(path, label="code bundle")) for path in paths}
    return sha256_text(canonical_json(bindings))


@dataclass(frozen=True)
class M3ReviewRelease:
    path: Path
    document: dict[str, Any]
    sha256: str
    release_id: str
    protocol_sha256: str
    request_bundle_sha256: str
    code_bundle_sha256: str
    image_tag: str

    @classmethod
    def load(
        cls, path: Path = DEFAULT_RELEASE_PATH, protocol: M3ReviewProtocol | None = None
    ) -> "M3ReviewRelease":
        active_protocol = protocol or M3ReviewProtocol.load()
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise D1ControlError("M3-3 preexecution release is missing") from error
        if not isinstance(document, dict):
            raise D1ControlError("M3-3 preexecution release must be an object")
        if (
            document.get("schema_version")
            != "m3-multi-pool-factor-review-execution-release-v1"
            or document.get("status") != "M3_3_PREEXECUTION_FROZEN_LIVE_NOT_AUTHORIZED"
            or document.get("execution_authorized") is not False
            or document.get("strategy_effective") != "NOT_EVALUATED"
            or document.get("production_authorization") != "none"
        ):
            raise D1ControlError("M3-3 preexecution authority differs")
        release_id = str(document.get("release_id", ""))
        if re.fullmatch(r"m3-star-three-pool-review-v1-preexecution-[0-9]{3}", release_id) is None:
            raise D1ControlError("M3-3 preexecution release id differs")
        request_sha, code_sha = _validate_contract(document, active_protocol)
        _validate_authorization_and_scope(document)
        return cls(
            path=path,
            document=document,
            sha256=sha256_file(path),
            release_id=release_id,
            protocol_sha256=active_protocol.sha256,
            request_bundle_sha256=request_sha,
            code_bundle_sha256=code_sha,
            image_tag=str(document["container_contract"]["image_tag"]),
        )

    def assert_live_authorized(self) -> None:
        raise D1ControlError(
            "M3-3 live review requires a separate immutable user-authorized live release"
        )


def _validate_contract(
    document: dict[str, Any], protocol: M3ReviewProtocol
) -> tuple[str, str]:
    frozen = document.get("frozen_contract", {})
    source = protocol.document["source_binding"]
    request_sha = str(frozen.get("request_bundle_sha256", ""))
    code_paths = frozen.get("code_paths", [])
    code_sha = str(frozen.get("code_bundle_sha256", ""))
    if (
        frozen.get("protocol_path") != "config/m3_multi_pool_factor_review_v1.yaml"
        or frozen.get("protocol_sha256") != protocol.sha256
        or frozen.get("prompt_sha256") != protocol.prompt_sha256
        or frozen.get("semantic_protocol_sha256") != protocol.semantic_protocol.sha256
        or frozen.get("discovery_manifest_sha256") != source["discovery_manifest_sha256"]
        or frozen.get("discovery_report_sha256") != source["discovery_report_sha256"]
        or frozen.get("discovery_live_context_sha256")
        != source["discovery_live_context_sha256"]
        or frozen.get("discovery_attempt_ledger_sha256")
        != source["discovery_attempt_ledger_sha256"]
        or frozen.get("discovery_evidence_tree_sha256")
        != source["discovery_evidence_tree_sha256"]
        or frozen.get("knowledge_sha256") != protocol.document["knowledge_binding"]["sha256"]
        or frozen.get("candidate_ids") != list(CANDIDATE_IDS)
        or frozen.get("selection_formula_and_order_immutable") is not True
        or request_sha != preflight(protocol.path)["request_bundle_sha256"]
        or not isinstance(code_paths, list)
        or code_sha != code_bundle_sha256(list(map(str, code_paths)))
    ):
        raise D1ControlError("M3-3 release does not bind frozen inputs and code")
    return request_sha, code_sha


def _validate_authorization_and_scope(document: dict[str, Any]) -> None:
    authorization = document.get("authorization", {})
    if (
        authorization.get("source") != "primary_thread_goal_authorizes_preexecution_only"
        or authorization.get("authorized_on") != "2026-08-02"
        or authorization.get("provider_calls_authorized_now") != 0
        or authorization.get("completed_responses_if_later_authorized_exact") != 8
        or float(authorization.get("future_live_hard_ceiling_usd", -1)) != 0.25
        or authorization.get("future_live_requires_new_explicit_user_authority") is not True
        or authorization.get("future_live_requires_separate_immutable_release") is not True
    ):
        raise D1ControlError("M3-3 preexecution authorization differs")
    scope = document.get("scope", {})
    if (
        scope.get("result_blind_contract_preexecution") is not True
        or any(value is not False for key, value in scope.items() if key != "result_blind_contract_preexecution")
    ):
        raise D1ControlError("M3-3 preexecution scope expands")
    if document.get("ledgers") != {
        "review": "ledger/m3_multi_pool_factor_reviews.csv",
        "transport": "ledger/m3_multi_pool_factor_review_transports.csv",
        "must_be_header_only_before_live_authorization": True,
        "prior_ledgers_remain_byte_immutable": True,
    }:
        raise D1ControlError("M3-3 ledger boundary differs")
    if document.get("container_contract") != {
        "image_tag": "shaiwei:m3-multi-pool-review-preexecution-v1",
        "network_mode": "none",
        "read_only_root": True,
        "non_root": True,
        "docker_socket": False,
        "host_ports": False,
        "secret_environment": False,
    }:
        raise D1ControlError("M3-3 container boundary differs")
