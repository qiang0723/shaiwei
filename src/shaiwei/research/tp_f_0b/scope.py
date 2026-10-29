"""TP-F-0B exact scope, verbatim approval transcription and drift checks. The tool never fabricates approval."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.g1_calibration.scope import directory_fingerprint
from shaiwei.research.tp_f_0b.contract import (
    CONTROL_ROOT,
    TPFError,
    TPFScope,
    validate_bound_inputs,
    validate_qlib_cache,
    validate_raw_artifacts,
)

_HEX64 = r"^[0-9a-f]{64}$"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Scope(_Frozen):
    schema_version: Literal["tp-f-0b-scope-v1"]
    protocol_id: Literal["tp-f-0b-data-identity-preflight-001"]
    protocol_sha256: str = Field(pattern=_HEX64)
    protocol_document_sha256: str = Field(pattern=_HEX64)
    addendum_sha256: str = Field(pattern=_HEX64)
    addendum_document_sha256: str = Field(pattern=_HEX64)
    execution_id: str = Field(pattern=r"^tpf0b-[0-9a-f]{12}-\d{8}T\d{6}Z$")
    git_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    image: str = Field(pattern=r"^shaiwei:tp-f-0b-[0-9a-f]{12}$")
    image_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    code_snapshot_sha256: str = Field(pattern=_HEX64)
    bound_inputs: dict[str, str]
    raw_artifact_bundle_sha256: str = Field(pattern=_HEX64)
    qlib_artifact_sha256: str = Field(pattern=_HEX64)
    qlib_directory_fingerprint: str = Field(pattern=_HEX64)
    fixture_report_path: str
    fixture_report_sha256: str = Field(pattern=_HEX64)
    prepared_at: str


class Envelope(_Frozen):
    scope_sha256: str = Field(pattern=_HEX64)
    scope: Scope


def scope_hash(scope: Scope) -> str:
    payload = json.dumps(scope.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def approval_text(envelope: Envelope) -> str:
    return (
        f"批准 TP-F-0B 结果盲数据与身份预检正式画像：以 scope {envelope.scope_sha256} 对镜像 {envelope.scope.image} "
        f"仅执行一次 {envelope.scope.protocol_id}（含补遗 A1）字段画像与身份普查，并做一次独立审计；只输出计数与比例，"
        "不计算任何候选值、分布或收益，不调用任何 LLM，不写账本，不授权 TP-F 正式小批或其他生产、研究动作。"
    )


def data_facts(contract: TPFScope, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Re-hash every frozen input on whichever side runs it (host before approval, container before reading)."""
    manifest = json.loads((root / contract.manifest_relative).read_text(encoding="utf-8"))
    required = contract.document["frozen_inputs"]["raw_market_store"]["required_layers"]
    return {
        "bound_inputs": validate_bound_inputs(contract, root),
        "raw_artifact_bundle_sha256": validate_raw_artifacts(manifest, required, root),
        "qlib_artifact_sha256": validate_qlib_cache(contract, root)["artifact_sha256"],
        "qlib_directory_fingerprint": directory_fingerprint(root / contract.qlib_root_relative),
    }


def _write_once(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def load_envelope(scope_sha: str, control: Path = CONTROL_ROOT) -> Envelope:
    envelope = Envelope.model_validate_json((control / "scopes" / f"{scope_sha}.scope.json").read_text(encoding="utf-8"))
    if envelope.scope_sha256 != scope_sha or scope_hash(envelope.scope) != scope_sha:
        raise TPFError("scope file does not hash to its declared identity")
    return envelope


def record_approval(scope_sha: str, text: str, control: Path = CONTROL_ROOT) -> dict[str, str]:
    envelope = load_envelope(scope_sha, control)
    if text != approval_text(envelope):
        raise TPFError("approval text is not the exact verbatim text for this scope")
    try:
        _write_once(control / "approvals" / f"{scope_sha}.approval.json", {"scope_sha256": scope_sha, "approval_text": text})
    except FileExistsError as exc:
        raise TPFError("approval already recorded for this scope") from exc
    return {"status": "APPROVAL_RECORDED", "scope_sha256": scope_sha}


def load_approved(scope_sha: str, control: Path = CONTROL_ROOT) -> Envelope:
    envelope = load_envelope(scope_sha, control)
    approval = json.loads((control / "approvals" / f"{scope_sha}.approval.json").read_text(encoding="utf-8"))
    if approval != {"scope_sha256": scope_sha, "approval_text": approval_text(envelope)}:
        raise TPFError("approval does not match this scope verbatim")
    return envelope


def verify(envelope: Envelope, contract: TPFScope, *, code: str, facts: dict[str, Any]) -> None:
    scope = envelope.scope
    checks = {
        "protocol": (contract.sha256, scope.protocol_sha256), "addendum A1": (contract.addendum_sha256, scope.addendum_sha256),
        "code": (code, scope.code_snapshot_sha256), "bound inputs": (facts["bound_inputs"], scope.bound_inputs),
        "raw artifacts": (facts["raw_artifact_bundle_sha256"], scope.raw_artifact_bundle_sha256),
        "qlib artifact": (facts["qlib_artifact_sha256"], scope.qlib_artifact_sha256),
        "qlib directory": (facts["qlib_directory_fingerprint"], scope.qlib_directory_fingerprint),
    }
    if drift := [name for name, (actual, expected) in checks.items() if actual != expected]:
        raise TPFError(f"execution preconditions drifted from the approved scope: {drift}")


