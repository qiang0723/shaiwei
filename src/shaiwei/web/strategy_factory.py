"""Read and verify the immutable M5-0 strategy-factory snapshot."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from pydantic import ValidationError

from shaiwei.web.query import WebQueryError
from shaiwei.web.strategy_factory_contract import StrategyFactoryPointer


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = Path("data/web/research_snapshots/strategy_factory_v2")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _contains_bse(value: object) -> bool:
    if isinstance(value, str):
        return value.upper().endswith(".BJ")
    if isinstance(value, dict):
        return any(_contains_bse(key) or _contains_bse(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_bse(item) for item in value)
    return False


@dataclass(frozen=True)
class StrategyFactoryBundle:
    snapshot_id: str
    generated_at: str
    protocol_id: str
    catalog_id: str
    data: dict[str, Any]
    document_sha256: str
    source_identity: dict[str, Any]

    @property
    def meta(self) -> dict[str, object]:
        return {
            "as_of": self.generated_at[:10],
            "generated_at": self.generated_at,
            "timezone": "Asia/Shanghai",
            "freshness_status": "PASS",
            "snapshot_id": self.snapshot_id,
            "source_refs": [f"strategy_factory:{self.snapshot_id}"],
            "evidence_hashes": {
                "strategy_factory_snapshot": self.document_sha256,
                "strategy_factory_catalog": str(self.source_identity["catalog_sha256"]),
                "strategy_factory_authority_addendum": str(
                    self.source_identity["authority_addendum_sha256"]
                ),
                "strategy_factory_builder": str(self.source_identity["builder_sha256"]),
            },
            "protocol_id": self.protocol_id,
            "catalog_id": self.catalog_id,
        }


def _projection_root(project_root: Path | None, output_root: Path | None) -> Path:
    root = (project_root or PROJECT_ROOT).resolve()
    output = (
        (root / DEFAULT_OUTPUT).resolve()
        if output_root is None
        else (root / output_root).resolve()
        if not output_root.is_absolute()
        else output_root.resolve()
    )
    try:
        output.relative_to(root)
    except ValueError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "策略工厂投影读取目录越界") from error
    if output.is_symlink() or not output.is_dir():
        raise WebQueryError("NOT_READY", "策略工厂投影尚未构建", status_code=503)
    return output


def load_strategy_factory(
    project_root: Path | None = None,
    *,
    output_root: Path | None = None,
) -> StrategyFactoryBundle:
    output = _projection_root(project_root, output_root)
    pointer_path = output / "latest.json"
    if pointer_path.is_symlink() or not pointer_path.is_file():
        raise WebQueryError("NOT_READY", "策略工厂指针尚未构建", status_code=503)
    try:
        pointer = StrategyFactoryPointer.model_validate_json(pointer_path.read_bytes())
    except (OSError, ValidationError) as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "策略工厂指针无效") from error
    snapshot_path = output / pointer.snapshot_path
    try:
        snapshot_path.resolve().relative_to(output)
    except ValueError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "策略工厂快照路径越界") from error
    if snapshot_path.is_symlink() or not snapshot_path.is_file():
        raise WebQueryError("EVIDENCE_MISMATCH", "策略工厂快照缺失或为符号链接")
    payload = snapshot_path.read_bytes()
    if _sha256(payload) != pointer.snapshot_sha256:
        raise WebQueryError("EVIDENCE_MISMATCH", "策略工厂快照哈希不匹配")
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "策略工厂快照JSON无效") from error
    if not isinstance(document, dict):
        raise WebQueryError("EVIDENCE_MISMATCH", "策略工厂快照必须为对象")
    required = {
        "schema_version",
        "protocol_id",
        "catalog_id",
        "snapshot_id",
        "generated_at",
        "timezone",
        "source_identity",
        "data",
    }
    if set(document) != required:
        raise WebQueryError("EVIDENCE_MISMATCH", "策略工厂快照字段集合无效")
    identity = {
        "protocol_id": document["protocol_id"],
        "catalog_id": document["catalog_id"],
        "published_at": document["generated_at"],
        "source_identity": document["source_identity"],
        "data": document["data"],
    }
    calculated_id = _sha256(_canonical(identity))
    if (
        document["schema_version"] != "m5-strategy-factory-snapshot-v1"
        or document["protocol_id"] != pointer.protocol_id
        or document["snapshot_id"] != pointer.snapshot_id
        or calculated_id != pointer.snapshot_id
        or document["timezone"] != "Asia/Shanghai"
        or not SHA256_RE.fullmatch(str(document["snapshot_id"]))
    ):
        raise WebQueryError("EVIDENCE_MISMATCH", "策略工厂快照身份绑定无效")
    data = document["data"]
    source_identity = document["source_identity"]
    if (
        not isinstance(source_identity, dict)
        or not SHA256_RE.fullmatch(str(source_identity.get("catalog_sha256", "")))
        or not SHA256_RE.fullmatch(str(source_identity.get("authority_addendum_sha256", "")))
        or not SHA256_RE.fullmatch(str(source_identity.get("builder_sha256", "")))
        or not isinstance(source_identity.get("evidence_hashes"), dict)
    ):
        raise WebQueryError("EVIDENCE_MISMATCH", "策略工厂来源身份无效")
    if not isinstance(data, dict) or _contains_bse(data):
        raise WebQueryError("EVIDENCE_MISMATCH", "策略工厂数据无效或包含北交所身份")
    summary = data.get("summary")
    invariants = data.get("invariants")
    if not isinstance(summary, dict) or not isinstance(invariants, dict):
        raise WebQueryError("EVIDENCE_MISMATCH", "策略工厂摘要或不变量缺失")
    frozen_counts = {
        "registered_universe_count": 8,
        "research_eligible_universe_count": 5,
        "blocked_universe_count": 3,
        "existing_production_strategy_count": 1,
        "admitted_factor_count": 0,
        "active_authorized_task_count": 0,
        "registered_program_count": 8,
    }
    if any(summary.get(key) != value for key, value in frozen_counts.items()):
        raise WebQueryError("EVIDENCE_MISMATCH", "策略工厂冻结计数不一致")
    if (
        invariants.get("web_read_only") is not True
        or invariants.get("external_calls_made") != 0
        or invariants.get("real_research_runs") != 0
        or invariants.get("bse_count") != 0
        or invariants.get("production_authorization") != "none"
    ):
        raise WebQueryError("EVIDENCE_MISMATCH", "策略工厂只读或生产边界失效")
    return StrategyFactoryBundle(
        snapshot_id=pointer.snapshot_id,
        generated_at=str(document["generated_at"]),
        protocol_id=str(document["protocol_id"]),
        catalog_id=str(document["catalog_id"]),
        data=data,
        document_sha256=pointer.snapshot_sha256,
        source_identity=dict(source_identity),
    )
