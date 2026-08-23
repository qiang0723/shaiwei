"""Fail-closed read-only projections for P3-2A operational evidence."""

from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import re

from shaiwei.web.query import (
    SCHEMA_VERSION,
    TIMEZONE,
    WebQueryError,
    build_snapshot,
)
from shaiwei.web.notification_evidence import (
    MESSAGE_ID_PATTERN,
    notification_records,
)


DATE_PATTERN = re.compile(r"^\d{4}-?\d{2}-?\d{2}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
IMAGE_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
FIXED_LEDGER_PATHS = (
    "ledger/daily_runs.csv",
    "ledger/ingest_batches.csv",
    "ledger/shadow_runs.csv",
    "ledger/shadow_reconciliations.csv",
    "ledger/paper_runs.csv",
)
OPTIONAL_FIXED_PATHS = (
    "logs/releases/scheduler_releases.jsonl",
    "logs/scheduler/health.json",
)
MAX_STAGE_ATTEMPTS = 64
MAX_INCREMENTAL_BATCHES = 32
MAX_SENTINEL_METRIC_BYTES = 65_536
RELEASE_SCHEMA = "shaiwei-scheduler-release-audit-v1"
HEALTH_STATUSES = {
    "starting",
    "running",
    "shadow",
    "paper",
    "noop",
    "waiting",
    "degraded",
    "stopped",
    "idle",
}
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{0,128}$")


class _EvidenceChanged(RuntimeError):
    pass


@dataclass(frozen=True)
class _Source:
    relative_path: str
    payload: bytes
    size: int
    mtime_ns: int

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


@dataclass(frozen=True)
class OperationsBundle:
    snapshot_id: str
    as_of: str
    generated_at: str
    source_refs: tuple[str, ...]
    evidence_hashes: dict[str, str]
    data_quality: dict[str, object]
    system_run: dict[str, object]
    notifications: dict[str, dict[str, object]]

    @property
    def meta(self) -> dict[str, object]:
        return {
            "as_of": self.as_of,
            "generated_at": self.generated_at,
            "timezone": TIMEZONE,
            "freshness_status": self.data_quality["status"],
            "snapshot_id": self.snapshot_id,
            "source_refs": list(self.source_refs),
            "evidence_hashes": dict(self.evidence_hashes),
        }


def _default_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _require_sha256(value: object, label: str = "证据") -> str:
    text = str(value)
    if not SHA256_PATTERN.fullmatch(text):
        raise WebQueryError("EVIDENCE_MISMATCH", f"{label}哈希格式无效")
    return text


def _parse_timestamp(value: object, label: str = "证据") -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", f"{label}时间格式无效") from error
    if parsed.tzinfo is None:
        raise WebQueryError("EVIDENCE_MISMATCH", f"{label}时间缺少时区")
    return parsed.astimezone(timezone.utc)


def _normalize_as_of(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not DATE_PATTERN.fullmatch(stripped):
        raise WebQueryError(
            "INVALID_ARGUMENT",
            "as_of 必须使用 YYYY-MM-DD 或 YYYYMMDD",
            status_code=422,
        )
    compact = stripped.replace("-", "")
    try:
        datetime.strptime(compact, "%Y%m%d")
    except ValueError as error:
        raise WebQueryError("INVALID_ARGUMENT", "as_of 不是有效日期", status_code=422) from error
    return compact


def _display_date(compact: str) -> str:
    try:
        return datetime.strptime(compact, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "业务日期格式无效") from error


def _json_document(payload: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WebQueryError("EVIDENCE_MISMATCH", f"{label}格式无效") from error
    if not isinstance(value, dict):
        raise WebQueryError("EVIDENCE_MISMATCH", f"{label}格式无效")
    return value


class _OperationsCut:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.sources: dict[str, _Source] = {}
        self.notification_inventory: tuple[str, ...] = ()

    def _path(self, relative_path: str, *, prefixes: tuple[str, ...]) -> Path:
        relative = Path(relative_path)
        if (
            not relative_path
            or "\\" in relative_path
            or relative.is_absolute()
            or ".." in relative.parts
            or not relative_path.startswith(prefixes)
        ):
            raise WebQueryError("EVIDENCE_MISMATCH", "运维证据路径不在只读白名单")
        candidate = self.root / relative
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(self.root)
        except (FileNotFoundError, ValueError) as error:
            raise WebQueryError("EVIDENCE_MISMATCH", "已登记运维证据不存在或越界") from error
        current = candidate
        while current != self.root:
            if current.is_symlink():
                raise WebQueryError("EVIDENCE_MISMATCH", "运维证据路径不得经过符号链接")
            current = current.parent
        if not resolved.is_file():
            raise WebQueryError("EVIDENCE_MISMATCH", "已登记运维证据不是文件")
        return resolved

    def _read(self, relative_path: str, *, prefixes: tuple[str, ...]) -> bytes:
        if relative_path in self.sources:
            return self.sources[relative_path].payload
        path = self._path(relative_path, prefixes=prefixes)
        before = path.stat()
        payload = path.read_bytes()
        after = path.stat()
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or len(payload) != after.st_size
        ):
            raise _EvidenceChanged
        self.sources[relative_path] = _Source(
            relative_path=relative_path,
            payload=payload,
            size=after.st_size,
            mtime_ns=after.st_mtime_ns,
        )
        return payload

    def open(self) -> None:
        for relative_path in FIXED_LEDGER_PATHS:
            self._read(relative_path, prefixes=("ledger/",))
        for relative_path in OPTIONAL_FIXED_PATHS:
            candidate = self.root / relative_path
            if candidate.is_file() and not candidate.is_symlink():
                self._read(relative_path, prefixes=("logs/releases/", "logs/scheduler/"))
        notifications = self.root / "logs" / "notifications"
        if notifications.is_dir() and not notifications.is_symlink():
            self.notification_inventory = tuple(
                f"logs/notifications/{path.name}"
                for path in sorted(notifications.glob("feishu_*.jsonl"))
                if path.is_file() and not path.is_symlink()
            )
        for relative_path in self.notification_inventory:
            self._read(relative_path, prefixes=("logs/notifications/",))

    def artifact(self, relative_path: str, *, prefix: str) -> bytes:
        return self._read(relative_path, prefixes=(prefix,))

    def rows(self, relative_path: str) -> list[dict[str, str]]:
        try:
            text = self.sources[relative_path].payload.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            if not reader.fieldnames:
                raise ValueError("missing header")
            return list(reader)
        except (UnicodeDecodeError, csv.Error, ValueError) as error:
            raise WebQueryError("EVIDENCE_MISMATCH", "运维账本格式无效") from error

    def stable(self) -> bool:
        notifications = self.root / "logs" / "notifications"
        current_inventory: tuple[str, ...] = ()
        if notifications.is_dir() and not notifications.is_symlink():
            current_inventory = tuple(
                f"logs/notifications/{path.name}"
                for path in sorted(notifications.glob("feishu_*.jsonl"))
                if path.is_file() and not path.is_symlink()
            )
        if current_inventory != self.notification_inventory:
            return False
        for relative_path, source in self.sources.items():
            try:
                path = self._path(
                    relative_path,
                    prefixes=(
                        "ledger/",
                        "data/shadow/signals/",
                        "logs/sentinels/",
                        "logs/notifications/",
                        "logs/releases/",
                        "logs/scheduler/",
                    ),
                )
                stat = path.stat()
            except WebQueryError:
                return False
            if stat.st_size != source.size or stat.st_mtime_ns != source.mtime_ns:
                return False
        return True


def _attempts_for_latest_date(
    rows: list[dict[str, str]],
    *,
    date_field: str,
    requested_as_of: str | None,
    id_field: str,
) -> tuple[str, list[dict[str, str]]]:
    eligible = [
        row
        for row in rows
        if row.get(date_field)
        and (requested_as_of is None or row[date_field] <= requested_as_of)
    ]
    if not eligible:
        raise WebQueryError("NO_DATA", "没有已登记的日运行", status_code=404)
    actual = max(row[date_field] for row in eligible)
    _display_date(actual)
    attempts = sorted(
        [row for row in eligible if row[date_field] == actual],
        key=lambda row: _parse_timestamp(row.get("finished_at"), "运行"),
    )
    ids = [row.get(id_field, "") for row in attempts]
    if not all(ids) or len(ids) != len(set(ids)):
        raise WebQueryError("EVIDENCE_MISMATCH", "运行身份重复或缺失")
    if len(attempts) > MAX_STAGE_ATTEMPTS:
        raise WebQueryError("CONFLICT", "单步骤运行尝试超过固定上限")
    return actual, attempts


def _stage_summary(
    name: str,
    attempts: list[dict[str, str]],
    *,
    id_field: str,
    not_due_status: str = "NOT_READY",
) -> dict[str, object]:
    if len(attempts) > MAX_STAGE_ATTEMPTS:
        raise WebQueryError("CONFLICT", "单步骤运行尝试超过固定上限")
    identities = [row.get(id_field, "") for row in attempts]
    if attempts and (not all(identities) or len(identities) != len(set(identities))):
        raise WebQueryError("EVIDENCE_MISMATCH", f"{name}运行身份重复或缺失")
    if not attempts:
        return {
            "stage": name,
            "status": not_due_status,
            "attempt_count": 0,
            "failed_attempt_count": 0,
            "recovered": False,
            "first_error_type": None,
            "terminal_finished_at": None,
            "terminal_run_id": None,
        }
    ordered = sorted(
        attempts,
        key=lambda row: _parse_timestamp(row.get("finished_at"), name),
    )
    statuses = [str(row.get("status", "")) for row in ordered]
    if any(status not in {"PASS", "FAIL"} for status in statuses):
        raise WebQueryError("EVIDENCE_MISMATCH", f"{name}运行状态无效")
    failed = [row for row in ordered if row["status"] == "FAIL"]
    terminal = ordered[-1]
    return {
        "stage": name,
        "status": terminal["status"],
        "attempt_count": len(ordered),
        "failed_attempt_count": len(failed),
        "recovered": terminal["status"] == "PASS" and bool(failed),
        "first_error_type": failed[0].get("error_type") or None if failed else None,
        "terminal_finished_at": terminal.get("finished_at") or None,
        "terminal_run_id": terminal.get(id_field) or None,
        "operator": terminal.get("operator") or None,
    }


def _reject_sensitive_params(value: object, path: str = "params") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(marker in normalized for marker in ("token", "secret", "password", "api_key")):
                raise WebQueryError("EVIDENCE_MISMATCH", f"{path}包含禁止的敏感字段")
            _reject_sensitive_params(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_sensitive_params(child, f"{path}[{index}]")


def _safe_metric(value: object, path: str = "metrics") -> object:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise WebQueryError("EVIDENCE_MISMATCH", "哨兵指标包含非有限数值")
        return value
    if isinstance(value, str):
        if (
            value.startswith("/")
            or "://" in value
            or value.endswith(".BJ")
            or "\n" in value
            or "\r" in value
        ):
            raise WebQueryError("EVIDENCE_MISMATCH", "哨兵指标包含禁止展示的值")
        return value
    if isinstance(value, list):
        return [_safe_metric(child, f"{path}[]") for child in value]
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for key, child in value.items():
            text = str(key)
            normalized = text.lower().replace("-", "_")
            if any(
                marker in normalized
                for marker in (
                    "token",
                    "secret",
                    "password",
                    "api_key",
                    "webhook",
                    "signature",
                    "path",
                    "url",
                )
            ):
                raise WebQueryError("EVIDENCE_MISMATCH", "哨兵指标包含禁止展示的字段")
            result[text] = _safe_metric(child, f"{path}.{text}")
        return result
    raise WebQueryError("EVIDENCE_MISMATCH", "哨兵指标包含不支持的类型")


def _ingest_profile(
    payload: bytes,
    *,
    started_at: datetime,
    finished_at: datetime,
    expected_batch_count: int,
) -> dict[str, object]:
    try:
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
    except UnicodeDecodeError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "采集账本编码无效") from error
    required = {
        "batch_id",
        "ingest_time",
        "source_api",
        "params_json",
        "row_count",
        "content_sha256",
    }
    if not reader.fieldnames or not required <= set(reader.fieldnames):
        raise WebQueryError("EVIDENCE_MISMATCH", "采集账本字段不完整")
    digest = hashlib.sha256()
    digest.update(b"[")
    first = True
    batch_ids: set[str] = set()
    source_counts: Counter[str] = Counter()
    registered_rows = 0
    included_batches = 0
    incremental: list[dict[str, object]] = []
    for row in reader:
        ingest_time = _parse_timestamp(row.get("ingest_time"), "采集")
        if ingest_time > finished_at:
            continue
        batch_id = str(row.get("batch_id", ""))
        source_api = str(row.get("source_api", ""))
        if not batch_id or not source_api or batch_id in batch_ids:
            raise WebQueryError("EVIDENCE_MISMATCH", "采集批次身份重复或缺失")
        batch_ids.add(batch_id)
        try:
            params = json.loads(row["params_json"])
            row_count = int(row["row_count"])
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise WebQueryError("EVIDENCE_MISMATCH", "采集批次字段无效") from error
        if not isinstance(params, dict) or row_count < 0:
            raise WebQueryError("EVIDENCE_MISMATCH", "采集批次参数或行数无效")
        _reject_sensitive_params(params)
        content_hash = _require_sha256(row.get("content_sha256"), "采集内容")
        canonical = {
            "batch_id": batch_id,
            "source_api": source_api,
            "params_json": params,
            "row_count": row_count,
            "content_sha256": content_hash,
        }
        if not first:
            digest.update(b",")
        digest.update(_canonical(canonical))
        first = False
        included_batches += 1
        registered_rows += row_count
        source_counts[source_api] += 1
        if started_at <= ingest_time <= finished_at:
            incremental.append(
                {
                    "batch_id": batch_id,
                    "ingest_time": row["ingest_time"],
                    "source_api": source_api,
                    "row_count": row_count,
                    "content_sha256": content_hash,
                }
            )
    digest.update(b"]")
    if len(incremental) > MAX_INCREMENTAL_BATCHES:
        raise WebQueryError("CONFLICT", "当日新增批次超过固定响应上限")
    if len(incremental) != expected_batch_count:
        raise WebQueryError("EVIDENCE_MISMATCH", "日运行批次数与采集账本时间切片不一致")
    return {
        "registered_batch_count": included_batches,
        "registered_row_count": registered_rows,
        "source_api_count": len(source_counts),
        "source_api_batch_counts": dict(sorted(source_counts.items())),
        "reconstructed_data_snapshot_sha256": digest.hexdigest(),
        "incremental_batch_count": len(incremental),
        "incremental_batches": incremental,
        "raw_parquet_rehash_status": "NOT_EVALUATED",
        "raw_parquet_rehash_reason": "P3-2A 不挂载 data/raw",
    }


def _sentinel_profile(
    cut: _OperationsCut,
    *,
    actual_as_of: str,
    daily_terminal: dict[str, str],
    shadow_rows: list[dict[str, str]],
) -> tuple[dict[str, object], dict[str, object] | None, dict[str, str] | None]:
    attempts = [row for row in shadow_rows if row.get("signal_trade_date") == actual_as_of]
    ordered_attempts = sorted(
        attempts,
        key=lambda row: _parse_timestamp(row.get("finished_at"), "影子运行"),
    )
    if not ordered_attempts or ordered_attempts[-1].get("status") != "PASS":
        return (
            {
                "status": "NOT_READY",
                "evidence_status": "NOT_READY",
                "binding_status": "NOT_AVAILABLE",
                "reason": "当日没有终态 PASS 影子运行",
                "sentinels": [],
            },
            None,
            None,
        )
    terminal = ordered_attempts[-1]
    if terminal.get("daily_run_id") != daily_terminal.get("run_id"):
        raise WebQueryError("EVIDENCE_MISMATCH", "影子运行未绑定当日日增量")
    if terminal.get("data_snapshot_sha256") != daily_terminal.get("data_snapshot_sha256"):
        raise WebQueryError("EVIDENCE_MISMATCH", "影子与日增量数据快照不一致")
    signal_relative = terminal.get("signal_manifest_path", "")
    signal_payload = cut.artifact(signal_relative, prefix="data/shadow/signals/")
    signal = _json_document(signal_payload, "信号证据")
    signal_hash = _require_sha256(signal.get("signal_sha256"), "信号")
    unsigned_signal = {key: value for key, value in signal.items() if key != "signal_sha256"}
    if _sha256(unsigned_signal) != signal_hash or signal_hash != terminal.get("signal_sha256"):
        raise WebQueryError("EVIDENCE_MISMATCH", "信号内容哈希不一致")
    if str(signal.get("signal_date", "")).replace("-", "") != actual_as_of:
        raise WebQueryError("EVIDENCE_MISMATCH", "信号日期与运维切片不一致")
    for field in ("code_snapshot_sha256", "data_snapshot_sha256"):
        if signal.get(field) != terminal.get(field):
            raise WebQueryError("EVIDENCE_MISMATCH", "信号与影子运行身份不一致")

    sentinel_relative = terminal.get("sentinel_report_path", "")
    sentinel_payload = cut.artifact(sentinel_relative, prefix="logs/sentinels/")
    report = _json_document(sentinel_payload, "哨兵报告")
    for field in ("code_snapshot_sha256", "data_snapshot_sha256"):
        if report.get(field) != terminal.get(field):
            raise WebQueryError("EVIDENCE_MISMATCH", "哨兵与影子运行身份不一致")
    daily_finished = _parse_timestamp(daily_terminal.get("finished_at"), "日增量")
    signal_complete = _parse_timestamp(signal.get("data_complete_at"), "数据完成")
    shadow_started = _parse_timestamp(terminal.get("started_at"), "影子运行")
    sentinel_generated = _parse_timestamp(report.get("generated_at"), "哨兵")
    signal_generated = _parse_timestamp(signal.get("generated_at"), "信号")
    shadow_finished = _parse_timestamp(terminal.get("finished_at"), "影子运行")
    if daily_finished != signal_complete or not (
        shadow_started <= sentinel_generated <= signal_generated <= shadow_finished
    ):
        raise WebQueryError("EVIDENCE_MISMATCH", "哨兵、信号与运行时钟关系无效")

    raw_results = report.get("results")
    if not isinstance(raw_results, list) or len(raw_results) != 10:
        raise WebQueryError("EVIDENCE_MISMATCH", "哨兵报告必须恰含 S1-S10")
    by_name: dict[str, dict[str, object]] = {}
    for value in raw_results:
        if not isinstance(value, dict):
            raise WebQueryError("EVIDENCE_MISMATCH", "哨兵明细格式无效")
        name = str(value.get("sentinel", ""))
        if name in by_name:
            raise WebQueryError("EVIDENCE_MISMATCH", "哨兵明细重复")
        by_name[name] = value
    expected_names = {f"S{index}" for index in range(1, 11)}
    if set(by_name) != expected_names:
        raise WebQueryError("EVIDENCE_MISMATCH", "哨兵明细缺项或含未知项")
    accepted = {f"S{index}": {"PASS"} for index in range(1, 10)}
    accepted["S10"] = {"PASS", "NOT_APPLICABLE"}
    computed_failures: list[str] = []
    projections: list[dict[str, object]] = []
    for name in sorted(by_name, key=lambda value: int(value[1:])):
        value = by_name[name]
        status = str(value.get("status", ""))
        if status not in {"PASS", "FAIL", "NOT_APPLICABLE"}:
            raise WebQueryError("EVIDENCE_MISMATCH", "哨兵状态无效")
        if status == "FAIL":
            computed_failures.append(name)
        metrics = value.get("metrics", {})
        anomalies = value.get("anomalies", [])
        if not isinstance(metrics, dict) or not isinstance(anomalies, list):
            raise WebQueryError("EVIDENCE_MISMATCH", "哨兵指标或异常格式无效")
        if len(_canonical(metrics)) > MAX_SENTINEL_METRIC_BYTES:
            raise WebQueryError("CONFLICT", "单项哨兵指标超过固定上限")
        safe_metrics = _safe_metric(metrics)
        projections.append(
            {
                "sentinel": name,
                "status": status,
                "accepted_for_signal": status in accepted[name],
                "metrics": safe_metrics,
                "anomaly_count": len(anomalies),
            }
        )
    if report.get("required_failures") != computed_failures:
        raise WebQueryError("EVIDENCE_MISMATCH", "哨兵失败汇总与明细不一致")
    status = "PASS" if all(value["accepted_for_signal"] for value in projections) else "FAIL"
    return (
        {
            "status": status,
            "evidence_status": "WARN",
            "binding_status": "IDENTITY_MATCH_UNHASHED",
            "evidence_warning": "SENTINEL_REPORT_NOT_HASH_BOUND",
            "report_generated_at": report["generated_at"],
            "report_sha256": hashlib.sha256(sentinel_payload).hexdigest(),
            "required_failures": computed_failures,
            "sentinels": projections,
        },
        signal,
        terminal,
    )


def _notification_records(
    cut: _OperationsCut,
    *,
    actual_as_of: str,
) -> tuple[dict[str, dict[str, object]], list[dict[str, object]], set[str], int]:
    payloads = {
        relative_path: cut.sources[relative_path].payload
        for relative_path in cut.notification_inventory
    }
    return notification_records(payloads, actual_as_of=actual_as_of)


def _release_profile(
    cut: _OperationsCut,
    *,
    run_finished_at: datetime,
    expected_code_snapshot: str | None,
) -> tuple[dict[str, object], str | None]:
    relative = "logs/releases/scheduler_releases.jsonl"
    source = cut.sources.get(relative)
    if source is None:
        return {
            "status": "NOT_EVALUATED",
            "reason": "没有已挂载的 release 审计链",
            "live_container_identity_status": "NOT_EVALUATED",
        }, None
    previous = ""
    starts: list[dict[str, object]] = []
    try:
        lines = source.payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "release 审计链编码无效") from error
    for line_number, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise WebQueryError("EVIDENCE_MISMATCH", "release 审计链格式无效") from error
        if not isinstance(record, dict) or record.get("schema_version") != RELEASE_SCHEMA:
            raise WebQueryError("EVIDENCE_MISMATCH", "release 审计链 schema 无效")
        if record.get("previous_record_sha256") != previous:
            raise WebQueryError("EVIDENCE_MISMATCH", f"release 审计链在第 {line_number} 行断裂")
        expected = _require_sha256(record.get("record_sha256"), "release 记录")
        unsigned = {key: value for key, value in record.items() if key != "record_sha256"}
        actual = _sha256(unsigned)
        if expected != actual:
            raise WebQueryError("EVIDENCE_MISMATCH", "release 审计记录哈希不一致")
        previous = actual
        recorded_at = _parse_timestamp(record.get("recorded_at"), "release")
        if record.get("event") == "START_PASS" and recorded_at <= run_finished_at:
            starts.append(record)
    if not starts:
        return {
            "status": "NOT_EVALUATED",
            "reason": "运行完成前没有已登记 START_PASS",
            "audit_chain_status": "PASS",
            "live_container_identity_status": "NOT_EVALUATED",
        }, relative
    record = starts[-1]
    details = record.get("details")
    if not isinstance(details, dict):
        raise WebQueryError("EVIDENCE_MISMATCH", "release START_PASS 明细无效")
    code_snapshot = _require_sha256(details.get("code_snapshot_sha256"), "release 代码")
    image_id = str(details.get("image_id", ""))
    git_head = str(details.get("git_head", record.get("git_head", "")))
    mounts = details.get("mount_destinations")
    if (
        not IMAGE_SHA256_PATTERN.fullmatch(image_id)
        or len(git_head) not in {40, 64}
        or not isinstance(mounts, list)
        or not all(isinstance(value, str) for value in mounts)
        or details.get("read_only_rootfs") is not True
    ):
        raise WebQueryError("EVIDENCE_MISMATCH", "release START_PASS 身份或隔离字段无效")
    identity_status = "PASS"
    if expected_code_snapshot is not None and code_snapshot != expected_code_snapshot:
        raise WebQueryError("EVIDENCE_MISMATCH", "已登记 release 与影子代码快照不一致")
    return {
        "status": identity_status,
        "audit_chain_status": "PASS",
        "recorded_at": record["recorded_at"],
        "image_id": image_id,
        "code_snapshot_sha256": code_snapshot,
        "git_head": git_head,
        "read_only_rootfs": True,
        "mount_destinations": sorted(mounts),
        "live_container_identity_status": "NOT_EVALUATED",
        "live_container_identity_reason": "Web 查询不挂 Docker socket",
        "record_sha256": record["record_sha256"],
    }, relative


def _health_profile(cut: _OperationsCut) -> tuple[dict[str, object], str | None]:
    relative = "logs/scheduler/health.json"
    source = cut.sources.get(relative)
    if source is None:
        return {
            "status": "NOT_EVALUATED",
            "scope": "RECORDED_HEARTBEAT_ONLY",
            "reason": "没有已挂载的 scheduler 心跳",
        }, None
    document = _json_document(source.payload, "scheduler 心跳")
    recorded_status = str(document.get("status", ""))
    if recorded_status not in HEALTH_STATUSES:
        raise WebQueryError("EVIDENCE_MISMATCH", "scheduler 心跳状态无效")
    updated_at = _parse_timestamp(document.get("updated_at"), "scheduler 心跳")
    detail = document.get("detail", "")
    if not isinstance(detail, str) or not SAFE_TOKEN_PATTERN.fullmatch(detail):
        raise WebQueryError("EVIDENCE_MISMATCH", "scheduler 心跳 detail 无效")
    return {
        "status": "RECORDED",
        "scope": "RECORDED_HEARTBEAT_ONLY",
        "recorded_status": recorded_status,
        "detail": detail,
        "updated_at": updated_at.isoformat(),
        "freshness_status": "NOT_EVALUATED",
    }, relative


def _build_from_cut(cut: _OperationsCut, requested_as_of: str | None) -> OperationsBundle:
    daily_rows = cut.rows("ledger/daily_runs.csv")
    actual_as_of, daily_attempts = _attempts_for_latest_date(
        daily_rows,
        date_field="target_trade_date",
        requested_as_of=requested_as_of,
        id_field="run_id",
    )
    daily_terminal = daily_attempts[-1]
    daily_stage = _stage_summary("daily_increment", daily_attempts, id_field="run_id")
    started_at = _parse_timestamp(daily_terminal.get("started_at"), "日增量")
    finished_at = _parse_timestamp(daily_terminal.get("finished_at"), "日增量")
    if finished_at < started_at:
        raise WebQueryError("EVIDENCE_MISMATCH", "日增量完成时间早于开始时间")
    try:
        expected_batch_count = int(daily_terminal.get("batch_count", ""))
        market_row_count = int(daily_terminal.get("row_count", ""))
    except ValueError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "日增量批次或行数字段无效") from error
    if expected_batch_count < 0 or market_row_count < 0:
        raise WebQueryError("EVIDENCE_MISMATCH", "日增量批次或行数为负")
    ingest = _ingest_profile(
        cut.sources["ledger/ingest_batches.csv"].payload,
        started_at=started_at,
        finished_at=finished_at,
        expected_batch_count=expected_batch_count,
    )
    expected_data_snapshot = str(daily_terminal.get("data_snapshot_sha256", ""))
    if daily_terminal.get("status") == "PASS":
        _require_sha256(expected_data_snapshot, "日增量数据快照")
        if ingest["reconstructed_data_snapshot_sha256"] != expected_data_snapshot:
            raise WebQueryError("EVIDENCE_MISMATCH", "采集账本身份链与日增量快照不一致")

    shadow_rows = cut.rows("ledger/shadow_runs.csv")
    sentinel, signal, shadow_terminal = _sentinel_profile(
        cut,
        actual_as_of=actual_as_of,
        daily_terminal=daily_terminal,
        shadow_rows=shadow_rows,
    )
    if daily_terminal.get("status") != "PASS":
        data_status = "FAIL"
    elif sentinel["status"] == "NOT_READY":
        data_status = "NOT_READY"
    else:
        data_status = str(sentinel["status"])
    data_quality = {
        "status": data_status,
        "evidence_status": sentinel.get("evidence_status", "NOT_READY"),
        "status_reasons": (
            ["SENTINEL_REPORT_NOT_HASH_BOUND"]
            if sentinel.get("evidence_status") == "WARN"
            else []
        ),
        "as_of": _display_date(actual_as_of),
        "data_snapshot_sha256": expected_data_snapshot or None,
        "code_snapshot_sha256": (
            shadow_terminal.get("code_snapshot_sha256") if shadow_terminal else None
        ),
        "daily_increment": {
            **daily_stage,
            "batch_count": expected_batch_count,
            "market_row_count": market_row_count,
            "data_snapshot_sha256": expected_data_snapshot or None,
        },
        "batch_chain": ingest,
        "sentinel_gate": sentinel,
        "bse_gate": {
            "status": "PASS" if daily_terminal.get("status") == "PASS" else "NOT_READY",
            "validated_market_batch_bse_count": 0 if daily_terminal.get("status") == "PASS" else None,
            "returned_security_bse_count": 0,
            "excluded_bse_reference_count": next(
                (
                    dict(value["metrics"]).get("excluded_bse_count")
                    for value in sentinel.get("sentinels", [])
                    if value["sentinel"] == "S1"
                ),
                None,
            ),
        },
    }

    shadow_attempts = [row for row in shadow_rows if row.get("signal_trade_date") == actual_as_of]
    shadow_stage = _stage_summary("shadow_signal", shadow_attempts, id_field="run_id")
    sentinel_stage = {
        "stage": "sentinels",
        "status": sentinel["status"],
        "attempt_count": 1 if sentinel.get("report_generated_at") else 0,
        "failed_attempt_count": 1 if sentinel["status"] == "FAIL" else 0,
        "recovered": False,
        "first_error_type": None,
        "terminal_finished_at": sentinel.get("report_generated_at"),
        "terminal_run_id": None,
        "evidence_status": sentinel.get("evidence_status"),
    }
    reconciliation_rows = [
        row
        for row in cut.rows("ledger/shadow_reconciliations.csv")
        if row.get("execution_trade_date") == actual_as_of
    ]
    reconciliation_stage = _stage_summary(
        "next_open_reconciliation",
        reconciliation_rows,
        id_field="reconciliation_id",
        not_due_status="NOT_DUE",
    )
    paper_rows = [
        row
        for row in cut.rows("ledger/paper_runs.csv")
        if row.get("execution_trade_date") == actual_as_of
    ]
    paper_stage = _stage_summary("paper_cycle", paper_rows, id_field="run_id")
    try:
        replay = build_snapshot(_display_date(actual_as_of), project_root=cut.root).paper_replay
        replay_stage = {
            "stage": "paper_replay",
            "status": str(replay["status"]),
            "attempt_count": 1,
            "failed_attempt_count": 0,
            "recovered": False,
            "first_error_type": None,
            "terminal_finished_at": None,
            "terminal_run_id": None,
            "run_count": replay["run_count"],
            "event_count": replay["event_count"],
        }
    except WebQueryError as error:
        if error.code != "NO_DATA":
            raise
        replay_stage = {
            "stage": "paper_replay",
            "status": "NOT_READY",
            "attempt_count": 0,
            "failed_attempt_count": 0,
            "recovered": False,
            "first_error_type": None,
            "terminal_finished_at": None,
            "terminal_run_id": None,
        }

    (
        notifications,
        notification_attempts,
        notification_sources,
        legacy_unaddressable_count,
    ) = _notification_records(
        cut,
        actual_as_of=actual_as_of,
    )
    same_day_notification_attempts = [
        row
        for row in notification_attempts
        if str(row["source_ref"]).endswith(f"feishu_{actual_as_of}.jsonl")
    ]
    core_failure_messages = {
        str(row["message_id"])
        for row in same_day_notification_attempts
        if row["event"] == "daily_scheduler_cycle_failed"
    }
    notification_failed = sum(row["status"] == "FAIL" for row in same_day_notification_attempts)
    notification_recovered = sum(
        summary["recovered"]
        for summary in notifications.values()
        if any(
            str(attempt["source_ref"]).endswith(f"feishu_{actual_as_of}.jsonl")
            for attempt in summary["attempts"]
        )
    )
    if notification_failed:
        notification_status = "WARN"
    elif same_day_notification_attempts:
        notification_status = "PASS"
    else:
        notification_status = "NOT_READY"

    expected_code_snapshot = (
        shadow_terminal.get("code_snapshot_sha256") if shadow_terminal is not None else None
    )
    run_finished = (
        _parse_timestamp(shadow_terminal["finished_at"], "影子运行")
        if shadow_terminal is not None
        else finished_at
    )
    release, release_source = _release_profile(
        cut,
        run_finished_at=run_finished,
        expected_code_snapshot=expected_code_snapshot,
    )
    health, health_source = _health_profile(cut)
    stages = [
        daily_stage,
        sentinel_stage,
        reconciliation_stage,
        shadow_stage,
        paper_stage,
        replay_stage,
    ]
    failed_terminal = any(stage["status"] == "FAIL" for stage in stages)
    missing_required = any(
        stage["status"] == "NOT_READY"
        for stage in stages
        if stage["stage"] != "next_open_reconciliation"
    )
    recovered_failures = any(stage["failed_attempt_count"] for stage in stages)
    if failed_terminal:
        system_status = "FAIL"
    elif missing_required:
        system_status = "NOT_READY"
    elif recovered_failures or core_failure_messages:
        system_status = "WARN"
    else:
        system_status = "PASS"
    system_run = {
        "status": system_status,
        "as_of": _display_date(actual_as_of),
        "core_status": system_status,
        "notification_status": notification_status,
        "core_failure_message_count": len(core_failure_messages),
        "core_failure_message_ids": sorted(core_failure_messages),
        "stages": stages,
        "notifications": {
            "status": notification_status,
            "message_count": len(
                {
                    str(row["message_id"]) for row in same_day_notification_attempts
                }
            ),
            "attempt_count": len(same_day_notification_attempts),
            "failed_attempt_count": notification_failed,
            "recovered_message_count": notification_recovered,
            "legacy_unaddressable_attempt_count": legacy_unaddressable_count,
        },
        "release_identity": release,
        "scheduler_heartbeat": health,
    }

    used_sources = {
        *FIXED_LEDGER_PATHS,
        *notification_sources,
    }
    if shadow_terminal is not None:
        used_sources.add(shadow_terminal["signal_manifest_path"])
        used_sources.add(shadow_terminal["sentinel_report_path"])
    if release_source is not None:
        used_sources.add(release_source)
    if health_source is not None:
        used_sources.add(health_source)
    source_refs = tuple(sorted(used_sources))
    evidence_hashes = {
        f"{relative_path.replace('/', '_')}_sha256": cut.sources[relative_path].sha256
        for relative_path in source_refs
    }
    generated_candidates = [finished_at]
    for stage in stages:
        if stage.get("terminal_finished_at"):
            generated_candidates.append(
                _parse_timestamp(stage["terminal_finished_at"], str(stage["stage"]))
            )
    for row in same_day_notification_attempts:
        generated_candidates.append(_parse_timestamp(row["delivered_at"], "通知"))
    if release.get("recorded_at"):
        generated_candidates.append(_parse_timestamp(release["recorded_at"], "release"))
    if health.get("updated_at"):
        generated_candidates.append(_parse_timestamp(health["updated_at"], "scheduler 心跳"))
    generated_at = max(generated_candidates).isoformat()
    snapshot_id = _sha256(
        {
            "protocol_id": "p3-web-operations-v1",
            "schema_version": SCHEMA_VERSION,
            "as_of": actual_as_of,
            "evidence_hashes": evidence_hashes,
        }
    )
    return OperationsBundle(
        snapshot_id=snapshot_id,
        as_of=_display_date(actual_as_of),
        generated_at=generated_at,
        source_refs=source_refs,
        evidence_hashes=evidence_hashes,
        data_quality=data_quality,
        system_run=system_run,
        notifications=notifications,
    )


def build_operations_snapshot(
    as_of: str | None = None,
    *,
    project_root: Path | None = None,
) -> OperationsBundle:
    """Build one stable operations snapshot without secrets, raw data, or Docker access."""
    normalized = _normalize_as_of(as_of)
    root = (project_root or _default_root()).resolve()
    for _attempt in range(2):
        cut = _OperationsCut(root)
        try:
            cut.open()
            bundle = _build_from_cut(cut, normalized)
        except _EvidenceChanged:
            continue
        if cut.stable():
            return bundle
    raise WebQueryError(
        "CONFLICT",
        "查询期间运维证据发生变化，请重试",
        retryable=True,
    )


def notification_for(
    bundle: OperationsBundle,
    message_id: str,
) -> dict[str, object]:
    if not MESSAGE_ID_PATTERN.fullmatch(message_id):
        raise WebQueryError(
            "INVALID_ARGUMENT",
            "message_id 必须是 16 位小写十六进制",
            status_code=422,
        )
    try:
        return bundle.notifications[message_id]
    except KeyError as error:
        raise WebQueryError("NO_DATA", "没有找到该通知消息", status_code=404) from error
