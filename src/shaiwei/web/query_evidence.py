"""Shared contracts and stable evidence cut for read-only Web queries."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re

from shaiwei.web.security_names import (
    POINTER_SCHEMA_VERSION as SECURITY_NAME_POINTER_SCHEMA,
    SecurityNameCatalog,
    SecurityNameError,
)


SCHEMA_VERSION = "web-v1"
TIMEZONE = "Asia/Shanghai"
DEFAULT_ACCOUNT_ID = "model_baseline"
PAPER_ACCOUNT_IDS = frozenset({"model_baseline", "model_top20"})
MAX_NAV_OBSERVATIONS = 1000
FIXED_LEDGER_PATHS = (
    "ledger/shadow_runs.csv",
    "ledger/shadow_reconciliations.csv",
    "ledger/paper_accounts.csv",
    "ledger/paper_events.csv",
    "ledger/paper_runs.csv",
)
ARTIFACT_PREFIXES = (
    "data/shadow/signals/",
    "data/shadow/reconciliations/",
    "data/paper/",
    "data/web/security_names/",
)
SECURITY_NAME_POINTER_PATH = "data/web/security_names/current.json"
STATUS_PRECEDENCE = ("FAIL", "STALE", "WARN", "NOT_READY", "PASS")
DATE_PATTERN = re.compile(r"^\d{4}-?\d{2}-?\d{2}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class WebQueryError(RuntimeError):
    """A stable, sanitized error safe to expose through the HTTP adapter."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 409,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


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
class SnapshotBundle:
    snapshot_id: str
    as_of: str
    generated_at: str
    source_refs: tuple[str, ...]
    evidence_hashes: dict[str, str]
    overview: dict[str, object]
    paper_portfolio: dict[str, object]
    paper_nav: dict[str, object]
    paper_forward: dict[str, object]
    paper_replay: dict[str, object]
    latest_signal: dict[str, object]
    reconciliations: dict[str, dict[str, object]]

    @property
    def meta(self) -> dict[str, object]:
        return {
            "as_of": self.as_of,
            "generated_at": self.generated_at,
            "timezone": TIMEZONE,
            "freshness_status": self.paper_portfolio["freshness_status"],
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
        raise WebQueryError(
            "INVALID_ARGUMENT",
            "as_of 不是有效日期",
            status_code=422,
        ) from error
    return compact


def _normalize_paper_account_id(value: str) -> str:
    if value not in PAPER_ACCOUNT_IDS:
        raise WebQueryError(
            "INVALID_ARGUMENT",
            "account_id 不是已登记的模拟账户",
            status_code=422,
        )
    return value


def _display_date(compact: str) -> str:
    return datetime.strptime(compact, "%Y%m%d").strftime("%Y-%m-%d")


def _parse_timestamp(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "证据时间格式无效") from error
    if parsed.tzinfo is None:
        raise WebQueryError("EVIDENCE_MISMATCH", "证据时间缺少时区")
    return parsed.astimezone(timezone.utc)


def _latest_timestamp(values: list[object]) -> str:
    if not values:
        raise WebQueryError("NO_DATA", "没有可用的证据时间", status_code=404)
    return max(_parse_timestamp(value) for value in values).isoformat()


def _money(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "组合金额字段无效") from error


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    text = format(normalized, "f")
    return "0" if text in {"-0", ""} else text


def _require_sha256(value: object) -> str:
    text = str(value)
    if not SHA256_PATTERN.fullmatch(text):
        raise WebQueryError("EVIDENCE_MISMATCH", "证据哈希格式无效")
    return text


class _EvidenceCut:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.sources: dict[str, _Source] = {}
        self.notification_inventory: tuple[str, ...] = ()

    def _path(self, relative_path: str, *, prefixes: tuple[str, ...]) -> Path:
        if (
            not relative_path
            or "\\" in relative_path
            or Path(relative_path).is_absolute()
            or ".." in Path(relative_path).parts
            or not relative_path.startswith(prefixes)
        ):
            raise WebQueryError("EVIDENCE_MISMATCH", "证据路径不在只读白名单")
        candidate = self.root / relative_path
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(self.root)
        except (FileNotFoundError, ValueError) as error:
            raise WebQueryError("EVIDENCE_MISMATCH", "已登记证据不存在或越界") from error
        current = candidate
        while current != self.root:
            if current.is_symlink():
                raise WebQueryError("EVIDENCE_MISMATCH", "证据路径不得经过符号链接")
            current = current.parent
        if not resolved.is_file():
            raise WebQueryError("EVIDENCE_MISMATCH", "已登记证据不是文件")
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
        notifications = self.root / "logs" / "notifications"
        if notifications.is_dir() and not notifications.is_symlink():
            self.notification_inventory = tuple(
                f"logs/notifications/{path.name}"
                for path in sorted(notifications.glob("feishu_*.jsonl"))
                if path.is_file() and not path.is_symlink()
            )
        for relative_path in FIXED_LEDGER_PATHS:
            self._read(relative_path, prefixes=("ledger/",))
        for relative_path in self.notification_inventory:
            self._read(relative_path, prefixes=("logs/notifications/",))

    def artifact(self, relative_path: str, *, prefix: str) -> bytes:
        return self._read(relative_path, prefixes=(prefix,))

    def ledger_rows(self, relative_path: str) -> list[dict[str, str]]:
        payload = self.sources[relative_path].payload
        try:
            text = payload.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            if not reader.fieldnames:
                raise ValueError("missing header")
            return list(reader)
        except (UnicodeDecodeError, csv.Error, ValueError) as error:
            raise WebQueryError("EVIDENCE_MISMATCH", "账本格式无效") from error

    def notification_rows(self, compact_date: str) -> tuple[list[dict[str, object]], str | None]:
        relative = f"logs/notifications/feishu_{compact_date}.jsonl"
        source = self.sources.get(relative)
        if source is None:
            return [], None
        rows: list[dict[str, object]] = []
        try:
            for line in source.payload.decode("utf-8").splitlines():
                if line.strip():
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError("notification row is not an object")
                    rows.append(value)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise WebQueryError("EVIDENCE_MISMATCH", "通知证据格式无效") from error
        return rows, relative

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
        for relative, source in self.sources.items():
            try:
                path = self._path(
                    relative,
                    prefixes=("ledger/", "logs/notifications/", *ARTIFACT_PREFIXES),
                )
                stat = path.stat()
            except WebQueryError:
                return False
            if stat.st_size != source.size or stat.st_mtime_ns != source.mtime_ns:
                return False
        return True


def _json_document(payload: bytes, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WebQueryError("EVIDENCE_MISMATCH", f"{label}格式无效") from error
    if not isinstance(value, dict):
        raise WebQueryError("EVIDENCE_MISMATCH", f"{label}格式无效")
    return value


def _read_security_name_catalog(
    cut: _EvidenceCut,
) -> tuple[SecurityNameCatalog, str, str, str]:
    pointer_payload = cut._read(
        SECURITY_NAME_POINTER_PATH,
        prefixes=("data/web/security_names/",),
    )
    pointer = _json_document(pointer_payload, "证券简称投影指针")
    if pointer.get("schema_version") != SECURITY_NAME_POINTER_SCHEMA:
        raise WebQueryError("EVIDENCE_MISMATCH", "证券简称投影指针版本无效")
    digest = _require_sha256(pointer.get("bundle_sha256"))
    bundle_path = str(pointer.get("bundle_path", ""))
    expected = f"data/web/security_names/{digest}/bundle.json"
    if bundle_path != expected:
        raise WebQueryError("EVIDENCE_MISMATCH", "证券简称投影路径与内容身份不一致")
    bundle_payload = cut.artifact(bundle_path, prefix="data/web/security_names/")
    if hashlib.sha256(bundle_payload).hexdigest() != digest:
        raise WebQueryError("EVIDENCE_MISMATCH", "证券简称投影内容哈希不一致")
    document = _json_document(bundle_payload, "证券简称投影")
    try:
        catalog = SecurityNameCatalog.from_document(document)
    except SecurityNameError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", str(error)) from error
    return catalog, SECURITY_NAME_POINTER_PATH, bundle_path, digest


def _latest_by(
    rows: list[dict[str, str]],
    keys: tuple[str, ...],
    *,
    date_field: str,
    requested_as_of: str | None,
) -> list[dict[str, str]]:
    filtered = [
        row
        for row in rows
        if row.get(date_field)
        and (requested_as_of is None or row[date_field] <= requested_as_of)
    ]
    latest: dict[tuple[str, ...], dict[str, str]] = {}
    for row in sorted(filtered, key=lambda item: item.get("finished_at", "")):
        latest[tuple(row.get(key, "") for key in keys)] = row
    return list(latest.values())


def _passed_paper_runs(
    rows: list[dict[str, str]],
    *,
    account_id: str,
    as_of: str,
) -> list[dict[str, str]]:
    selected = [
        row
        for row in rows
        if row.get("account_id") == account_id
        and row.get("status") == "PASS"
        and row.get("execution_trade_date", "") <= as_of
    ]
    latest: dict[tuple[str, str], dict[str, str]] = {}
    for row in sorted(selected, key=lambda item: item.get("finished_at", "")):
        latest[(row["signal_sha256"], row["execution_trade_date"])] = row
    ordered = sorted(latest.values(), key=lambda item: item["execution_trade_date"])
    dates = [row["execution_trade_date"] for row in ordered]
    if dates != sorted(set(dates)):
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟账户日不唯一或未递增")
    if len(ordered) > MAX_NAV_OBSERVATIONS:
        raise WebQueryError("CONFLICT", "模拟账户日超过 P3-0 响应上限")
    return ordered


def _resolve_legacy_policy_versions(
    accounts: list[dict[str, str]],
    documents: list[dict[str, object]],
    *,
    account_id: str,
) -> None:
    identities = [row for row in accounts if row.get("account_id") == account_id]
    if len(identities) != 1:
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟账户身份不唯一")
    account = identities[0]
    version = account.get("execution_policy_version", "")
    policy_hash = account.get("policy_sha256", "")
    if not version or not SHA256_PATTERN.fullmatch(policy_hash):
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟账户策略身份无效")
    for document in documents:
        current = str(document.get("execution_policy_version", "")).strip()
        if current:
            if current != version:
                raise WebQueryError("CONFLICT", "模拟组合序列跨越不同执行策略版本")
            continue
        if document.get("policy_sha256") != policy_hash:
            raise WebQueryError("EVIDENCE_MISMATCH", "旧模拟产物无法由账户身份解析策略版本")
        # Legacy BACKFILL artifacts predate the explicit version field. Resolve
        # only from the immutable account row; never consult settings or .env.
        document["execution_policy_version"] = version


def _read_signal(cut: _EvidenceCut, row: dict[str, str]) -> dict[str, object]:
    relative = row.get("signal_manifest_path", "")
    document = _json_document(
        cut.artifact(relative, prefix="data/shadow/signals/"),
        "信号证据",
    )
    claimed = _require_sha256(document.get("signal_sha256"))
    payload = {key: value for key, value in document.items() if key != "signal_sha256"}
    if _sha256(payload) != claimed or claimed != row.get("signal_sha256"):
        raise WebQueryError("EVIDENCE_MISMATCH", "信号证据哈希不一致")
    if str(document.get("signal_date", "")).replace("-", "") != row.get("signal_trade_date"):
        raise WebQueryError("EVIDENCE_MISMATCH", "信号日期与账本不一致")
    if document.get("code_snapshot_sha256") != row.get("code_snapshot_sha256"):
        raise WebQueryError("EVIDENCE_MISMATCH", "信号代码快照与账本不一致")
    if document.get("data_snapshot_sha256") != row.get("data_snapshot_sha256"):
        raise WebQueryError("EVIDENCE_MISMATCH", "信号数据快照与账本不一致")
    orders = list(document.get("orders", []))
    instruments = [str(dict(order).get("instrument", "")) for order in orders]
    if len(instruments) != len(set(instruments)) or len(orders) != int(document.get("topk", -1)):
        raise WebQueryError("EVIDENCE_MISMATCH", "信号目标集合不唯一或数量不符")
    if any(_instrument_to_tushare(value).endswith(".BJ") for value in instruments):
        raise WebQueryError("FORBIDDEN_UNIVERSE", "信号证据包含禁止的北交所证券")
    return document


def _read_paper_document(cut: _EvidenceCut, row: dict[str, str]) -> dict[str, object]:
    relative = row.get("artifact_path", "")
    payload = cut.artifact(relative, prefix="data/paper/")
    if hashlib.sha256(payload).hexdigest() != _require_sha256(row.get("artifact_sha256")):
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟组合产物文件哈希不一致")
    document = _json_document(payload, "模拟组合证据")
    claimed = _require_sha256(document.get("content_sha256"))
    content = {key: value for key, value in document.items() if key != "content_sha256"}
    if _sha256(content) != claimed:
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟组合产物内容哈希不一致")
    for field in (
        "account_id",
        "signal_trade_date",
        "execution_trade_date",
        "signal_sha256",
        "reconciliation_sha256",
        "data_snapshot_sha256",
        "code_snapshot_sha256",
        "policy_sha256",
    ):
        if str(document.get(field, "")) != row.get(field, ""):
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟组合产物与账本身份不一致")
    return document


def _read_reconciliation(cut: _EvidenceCut, row: dict[str, str]) -> dict[str, object]:
    relative = row.get("artifact_path", "")
    payload = cut.artifact(relative, prefix="data/shadow/reconciliations/")
    if hashlib.sha256(payload).hexdigest() != _require_sha256(row.get("artifact_sha256")):
        raise WebQueryError("EVIDENCE_MISMATCH", "次日对账产物哈希不一致")
    document = _json_document(payload, "次日对账证据")
    for field in ("signal_sha256", "signal_trade_date", "execution_trade_date"):
        if str(document.get(field, "")) != row.get(field, ""):
            raise WebQueryError("EVIDENCE_MISMATCH", "次日对账产物与账本身份不一致")
    rows = [dict(value) for value in list(document.get("rows", []))]
    if any(str(value.get("ts_code", "")).endswith(".BJ") for value in rows):
        raise WebQueryError("FORBIDDEN_UNIVERSE", "次日对账包含禁止的北交所证券")
    return document


def _instrument_to_tushare(value: str) -> str:
    text = value.strip().upper()
    if "." in text:
        return text
    if len(text) == 8 and text[:2] in {"SH", "SZ", "BJ"} and text[2:].isdigit():
        return f"{text[2:]}.{text[:2]}"
    raise WebQueryError("EVIDENCE_MISMATCH", "信号证券代码格式无效")
