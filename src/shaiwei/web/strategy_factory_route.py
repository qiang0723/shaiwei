"""Hash-bound current-route overlay for the immutable strategy-factory catalog."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from shaiwei.web.query_evidence import SHA256_PATTERN, WebQueryError


ROUTE_PATH = Path("config/web_route_status_v1.yaml")
BASE_POINTER_PATH = "data/web/research_snapshots/strategy_factory_v3/latest.json"
BASE_SNAPSHOT_PATH = (
    "data/web/research_snapshots/strategy_factory_v3/snapshots/"
    "80498300f2b2c0933eed163fe214115c59babae0f3a609b12191d11d54340840.json"
)


def _source(root: Path, relative: str, expected: str) -> bytes:
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "策略路线证据路径越界") from error
    if path.is_symlink() or not path.is_file():
        raise WebQueryError("EVIDENCE_MISMATCH", "策略路线证据缺失或为符号链接")
    payload = path.read_bytes()
    if not SHA256_PATTERN.fullmatch(expected) or hashlib.sha256(payload).hexdigest() != expected:
        raise WebQueryError("EVIDENCE_MISMATCH", "策略路线证据哈希漂移")
    return payload


def load_strategy_route(
    root: Path,
    *,
    pointer_payload: bytes,
    snapshot_payload: bytes,
) -> tuple[dict[str, Any], str, tuple[str, ...], dict[str, str]]:
    route_path = (root / ROUTE_PATH).resolve()
    if route_path.is_symlink() or not route_path.is_file():
        raise WebQueryError("EVIDENCE_MISMATCH", "当前策略路线合同缺失")
    payload = route_path.read_bytes()
    try:
        document = yaml.safe_load(payload)
    except yaml.YAMLError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "当前策略路线合同格式无效") from error
    if not isinstance(document, dict) or document.get("schema_version") != "web-route-status-v1":
        raise WebQueryError("EVIDENCE_MISMATCH", "当前策略路线合同版本无效")
    base = dict(document.get("base_strategy_factory", {}))
    if (
        base.get("pointer_path") != BASE_POINTER_PATH
        or base.get("snapshot_path") != BASE_SNAPSHOT_PATH
        or hashlib.sha256(pointer_payload).hexdigest() != base.get("pointer_sha256")
        or hashlib.sha256(snapshot_payload).hexdigest() != base.get("snapshot_sha256")
    ):
        raise WebQueryError("EVIDENCE_MISMATCH", "策略路线未绑定当前工厂基线")
    refs = [str(ROUTE_PATH)]
    hashes = {str(ROUTE_PATH): hashlib.sha256(payload).hexdigest()}
    for item in list(document.get("evidence", [])):
        source = dict(item)
        relative = str(source.get("path", ""))
        digest = str(source.get("sha256", ""))
        if not relative.startswith("docs/") or relative in refs:
            raise WebQueryError("EVIDENCE_MISMATCH", "策略路线来源集合无效")
        _source(root, relative, digest)
        refs.append(relative)
        hashes[relative] = digest
    primary = dict(document.get("primary_goal", {}))
    m7 = dict(document.get("m7", {}))
    expected = {
        "status": "COURSE_CORRECTION_AND_OBSERVE",
        "active_authorized_task_count": 0,
        "production_authorization": "none",
    }
    if any(document.get(key) != value for key, value in expected.items()):
        raise WebQueryError("EVIDENCE_MISMATCH", "策略路线当前裁决漂移")
    if (
        primary.get("goal_id") != "R2-1_FORWARD_EVIDENCE_CHECKPOINT"
        or primary.get("state") != "NOT_DUE"
        or primary.get("live_dual_days_at_freeze") != 5
        or primary.get("minimum_live_dual_days") != 20
        or primary.get("live_dual_rebalances_at_freeze") != 0
        or primary.get("minimum_live_dual_rebalances") != 2
        or primary.get("dates_are_planning_only") is not True
        or m7.get("verdict") != "NO_GO_M7_EVIDENCE_RECOVERY_INCOMPLETE"
        or m7.get("strategy_effective") != "NOT_EVALUATED"
        or m7.get("candidate_count") != 0
        or m7.get("effect_read_count") != 0
        or m7.get("production_authorization") != "none"
    ):
        raise WebQueryError("EVIDENCE_MISMATCH", "策略路线主目标或M7事实漂移")
    route = {
        "route_id": str(document["route_id"]),
        "published_at": str(document["published_at"]),
        "status": str(document["status"]),
        "headline": str(document["headline"]),
        "summary": str(document["summary"]),
        "primary_goal": primary,
        "m7": m7,
        "paused_work": list(document.get("paused_work", [])),
        "capability_note": str(document["capability_note"]),
        "active_authorized_task_count": int(document["active_authorized_task_count"]),
        "production_authorization": str(document["production_authorization"]),
    }
    return route, hashes[str(ROUTE_PATH)], tuple(refs), hashes
