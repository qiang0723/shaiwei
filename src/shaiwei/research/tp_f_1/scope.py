"""TP-F-1 exact scope, verbatim approval and blind-review transcription, drift checks. The tool never fabricates either."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.tp_f_1.contract import TPF1Error, TPF1Scope

CONTROL_ROOT = PROJECT_ROOT / "data/control/tp-f-1"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/tp-f-1"
AUDIT_ROOT = PROJECT_ROOT / "data/research/tp-f-1-audit"
REPORTS_ROOT = PROJECT_ROOT / "logs/tp-f-1"
FIXTURE_ROOT = REPORTS_ROOT / "fixture"
ATTEMPTS = PROJECT_ROOT / "ledger/tp_f_1_llm_attempts.csv"
TRANSPORTS = PROJECT_ROOT / "ledger/tp_f_1_llm_transports.csv"
_HEX64 = r"^[0-9a-f]{64}$"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PriceBinding(_Frozen):
    input_cache_hit_per_million_usd: str
    input_cache_miss_per_million_usd: str
    output_per_million_usd: str
    rechecked_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_url: str


class LedgerBaseline(_Frozen):
    tp_f_1_attempt_rows: Literal[0]
    tp_f_1_transport_rows: Literal[0]
    tp_f_1_family_experiment_rows: Literal[0]
    admissions_v2_rows: int = Field(ge=0)


class Scope(_Frozen):
    schema_version: Literal["tp-f-1-scope-v1"]
    protocol_id: Literal["tp-f-1-trend-pullback-joint-state-001"]
    protocol_sha256: str = Field(pattern=_HEX64)
    addendum_sha256: str = Field(pattern=_HEX64)
    prompt_sha256: str = Field(pattern=_HEX64)
    transport_protocol_sha256: str = Field(pattern=_HEX64)
    execution_id: str = Field(pattern=r"^tpf1-[0-9a-f]{12}-\d{8}T\d{6}Z$")
    git_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    image: str = Field(pattern=r"^shaiwei:tp-f-1-[0-9a-f]{12}$")
    image_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    code_snapshot_sha256: str = Field(pattern=_HEX64)
    bound_inputs: dict[str, str]
    r2_1r1_report_sha256: str = Field(pattern=_HEX64)
    r2_1r1_latch_day: str = Field(pattern=r"^\d{8}$")
    prices: PriceBinding
    single_batch_ceiling_usd: Literal["1.00"]
    qlib_directory_fingerprint: str = Field(pattern=_HEX64)
    fixture_report_path: str
    fixture_report_sha256: str = Field(pattern=_HEX64)
    ledgers: LedgerBaseline
    prepared_at: str


class Envelope(_Frozen):
    scope_sha256: str = Field(pattern=_HEX64)
    scope: Scope


def scope_hash(scope: Scope) -> str:
    payload = json.dumps(scope.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def approval_text(envelope: Envelope) -> str:
    scope = envelope.scope
    return (
        f"批准 TP-F-1 趋势回踩联合状态正式小批：以 scope {envelope.scope_sha256} 对镜像 {scope.image} 仅执行一次 {scope.protocol_id}"
        "（含补遗 A1）——生成段至多 8 个 deepseek-v4-pro 完成响应、单批费用上限 1.00 美元，经我逐字盲评后一次离线评估与 g1-v2 判定，"
        "并做一次独立审计；结果只记 TP-F-1 专用账本、实验总账与 factor_admissions_v2，不入因子库，不写 v1 准入账本，"
        "不授权模拟仓、生产或其他研究动作。"
    )


def write_once(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        raise TPF1Error(f"TP-F-1 control record already exists: {path.name}") from exc
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def load_envelope(scope_sha: str, control: Path = CONTROL_ROOT) -> Envelope:
    envelope = Envelope.model_validate_json((control / "scopes" / f"{scope_sha}.scope.json").read_text(encoding="utf-8"))
    if envelope.scope_sha256 != scope_sha or scope_hash(envelope.scope) != scope_sha:
        raise TPF1Error("scope file does not hash to its declared identity")
    return envelope


def record_approval(scope_sha: str, text: str, control: Path = CONTROL_ROOT) -> dict[str, str]:
    envelope = load_envelope(scope_sha, control)
    if text != approval_text(envelope):
        raise TPF1Error("approval text is not the exact verbatim text for this scope")
    write_once(control / "approvals" / f"{scope_sha}.approval.json", {"scope_sha256": scope_sha, "approval_text": text})
    return {"status": "APPROVAL_RECORDED", "scope_sha256": scope_sha}


def load_approved(scope_sha: str, control: Path = CONTROL_ROOT) -> Envelope:
    envelope = load_envelope(scope_sha, control)
    path = control / "approvals" / f"{scope_sha}.approval.json"
    if not path.is_file() or json.loads(path.read_text(encoding="utf-8")) != {"scope_sha256": scope_sha, "approval_text": approval_text(envelope)}:
        raise TPF1Error("approval does not match this scope verbatim")
    return envelope


def verify(envelope: Envelope, contract: TPF1Scope, *, code: str, prompt_sha256: str, transport_sha256: str,
           bound: dict[str, str], qlib_fingerprint: str, r2_1r1_report_sha256: str) -> None:
    scope = envelope.scope
    checks = {
        "protocol": (contract.sha256, scope.protocol_sha256), "addendum A1": (contract.addendum_sha256, scope.addendum_sha256),
        "prompt": (prompt_sha256, scope.prompt_sha256), "transport": (transport_sha256, scope.transport_protocol_sha256),
        "code": (code, scope.code_snapshot_sha256), "bound inputs": (bound, scope.bound_inputs),
        "qlib directory": (qlib_fingerprint, scope.qlib_directory_fingerprint), "R2-1R1 report": (r2_1r1_report_sha256, scope.r2_1r1_report_sha256),
    }
    if drift := [name for name, (actual, expected) in checks.items() if actual != expected]:
        raise TPF1Error(f"execution preconditions drifted from the approved scope: {drift}")


def review_path(scope_sha: str, control: Path = CONTROL_ROOT) -> Path:
    return control / "reviews" / f"{scope_sha}.ruling.json"


def scope_attempts(scope_sha: str, path: Path = ATTEMPTS) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if row["scope_sha256"] == scope_sha]
