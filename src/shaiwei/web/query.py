"""Deterministic, fail-closed projections over registered Web 1.0 evidence."""

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
)
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


def _paper_projection(
    row: dict[str, str],
    document: dict[str, object],
) -> dict[str, object]:
    result = dict(document.get("result", {}))
    nav = dict(result.get("nav", {}))
    cash = _money(nav.get("cash"))
    market_value = _money(nav.get("market_value"))
    net_asset = _money(nav.get("net_asset"))
    if net_asset <= 0 or cash + market_value != net_asset:
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟组合会计恒等失败")
    positions: list[dict[str, object]] = []
    position_market_value = Decimal("0")
    for value in list(nav.get("positions", [])):
        position = dict(value)
        code = str(position.get("ts_code", ""))
        if code.endswith(".BJ"):
            raise WebQueryError("FORBIDDEN_UNIVERSE", "模拟组合包含禁止的北交所证券")
        market = _money(position.get("market_value"))
        cost = _money(position.get("cost_basis"))
        position_market_value += market
        positions.append(
            {
                "ts_code": code,
                "quantity": int(position.get("quantity", 0)),
                "close": str(position.get("close", "")),
                "price_date": str(position.get("price_date", "")),
                "market_value": str(position.get("market_value", "")),
                "cost_basis": str(position.get("cost_basis", "")),
                "actual_weight": _decimal_text(market / net_asset),
                "unrealized_pnl": _decimal_text(market - cost),
                "realized_pnl": str(position.get("realized_pnl", "")),
                "stale_trade_days": int(position.get("stale_trade_days", 0)),
            }
        )
    if position_market_value != market_value:
        raise WebQueryError("EVIDENCE_MISMATCH", "逐仓市值与账户市值不一致")
    freshness = str(nav.get("freshness_status", ""))
    if freshness not in {"PASS", "STALE"}:
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟组合新鲜度状态无效")
    return {
        "as_of": _display_date(str(document["execution_trade_date"])),
        "generated_at": str(document["generated_at"]),
        "account_id": str(document["account_id"]),
        "mode": str(document["mode"]),
        "execution_policy_version": str(document.get("execution_policy_version", "")),
        "freshness_status": freshness,
        "cash": str(nav["cash"]),
        "market_value": str(nav["market_value"]),
        "net_asset": str(nav["net_asset"]),
        "normalized_nav": str(nav["normalized_nav"]),
        "benchmark_nav": str(nav["benchmark_nav"]),
        "net_excess": str(nav["net_excess"]),
        "drawdown": str(nav["drawdown"]),
        "cash_ratio": str(nav["cash_ratio"]),
        "turnover": str(nav["turnover"]),
        "cumulative_fees": str(nav["cumulative_fees"]),
        "cumulative_dividends": str(nav["cumulative_dividends"]),
        "position_count": len(positions),
        "positions": positions,
        "bse_count": 0,
        "source_ref": row["artifact_path"],
        "evidence_hashes": {
            "artifact_sha256": row["artifact_sha256"],
            "content_sha256": document["content_sha256"],
            "signal_sha256": document["signal_sha256"],
            "reconciliation_sha256": document["reconciliation_sha256"],
            "policy_sha256": document["policy_sha256"],
            "code_snapshot_sha256": document["code_snapshot_sha256"],
            "data_snapshot_sha256": document["data_snapshot_sha256"],
        },
    }


def _paper_nav(
    rows: list[dict[str, str]],
    documents: list[dict[str, object]],
    *,
    account_id: str,
) -> dict[str, object]:
    series: list[dict[str, object]] = []
    versions: set[str] = set()
    freshness = "PASS"
    for row, document in zip(rows, documents, strict=True):
        nav = dict(dict(document["result"])["nav"])
        versions.add(str(document.get("execution_policy_version", "")))
        if nav.get("freshness_status") == "STALE":
            freshness = "STALE"
        series.append(
            {
                "trade_date": _display_date(str(document["execution_trade_date"])),
                "mode": str(document["mode"]),
                "normalized_nav": str(nav["normalized_nav"]),
                "benchmark_nav": str(nav["benchmark_nav"]),
                "net_excess": str(nav["net_excess"]),
                "drawdown": str(nav["drawdown"]),
                "turnover": str(nav["turnover"]),
                "cash_ratio": str(nav["cash_ratio"]),
                "daily_fees": str(nav["daily_fees"]),
                "freshness_status": str(nav["freshness_status"]),
                "artifact_sha256": row["artifact_sha256"],
            }
        )
    if len(versions) != 1 or "" in versions:
        raise WebQueryError("CONFLICT", "模拟组合序列跨越不同执行策略版本")
    forward_count = sum(value["mode"] == "FORWARD" for value in series)
    return {
        "as_of": series[-1]["trade_date"],
        "account_id": account_id,
        "execution_policy_version": next(iter(versions)),
        "freshness_status": freshness,
        "forward_status": "PASS" if forward_count else "NOT_READY",
        "forward_observation_count": forward_count,
        "observation_count": len(series),
        "series": series,
    }


def _forward_projection(
    rows: list[dict[str, str]],
    documents: list[dict[str, object]],
) -> dict[str, object]:
    forward_indexes = [
        index for index, document in enumerate(documents) if document.get("mode") == "FORWARD"
    ]
    if not forward_indexes:
        versions = {
            str(document.get("execution_policy_version", "")) for document in documents
        }
        if len(versions) != 1 or "" in versions:
            raise WebQueryError("CONFLICT", "模拟组合序列跨越不同执行策略版本")
        return {
            "status": "NOT_READY",
            "performance_maturity": "NOT_READY",
            "forward_anchor_trade_date": None,
            "forward_anchor_portfolio_nav": None,
            "forward_anchor_benchmark_nav": None,
            "forward_anchor_artifact_sha256": None,
            "execution_policy_version": next(iter(versions)),
            "forward_observation_count": 0,
            "forward_rebalance_count": 0,
            "coverage_status": "NOT_EVALUATED",
            "coverage_ratio": None,
            "coverage_reason": "尚无自然 FORWARD 账户日，只保留工程回放证据",
            "forward_cumulative_fees": None,
            "forward_cumulative_dividends": None,
            "forward_turnover": None,
            "forward_cash_ratio": None,
            "latest": None,
            "series": [],
            "suppressed_metrics": [
                "forward_annualized_return",
                "forward_annualized_volatility",
                "forward_sharpe",
                "forward_information_ratio",
            ],
        }
    first = forward_indexes[0]
    if first == 0 or documents[first - 1].get("mode") != "BACKFILL":
        raise WebQueryError("EVIDENCE_MISMATCH", "FORWARD 序列缺少合法 BACKFILL 锚点")
    if any(document.get("mode") != "FORWARD" for document in documents[first:]):
        raise WebQueryError("EVIDENCE_MISMATCH", "FORWARD 开始后出现非法模式回退")
    anchor = documents[first - 1]
    anchor_row = rows[first - 1]
    anchor_nav = dict(dict(anchor["result"])["nav"])
    anchor_portfolio = _money(anchor_nav["normalized_nav"])
    anchor_benchmark = _money(anchor_nav["benchmark_nav"])
    if anchor_portfolio <= 0 or anchor_benchmark <= 0:
        raise WebQueryError("EVIDENCE_MISMATCH", "FORWARD 锚点净值无效")
    version = str(anchor.get("execution_policy_version", ""))
    peak = Decimal("1")
    series: list[dict[str, object]] = []
    turnover = Decimal("0")
    rebalances = 0
    for row, document in zip(rows[first:], documents[first:], strict=True):
        if str(document.get("execution_policy_version", "")) != version:
            raise WebQueryError("CONFLICT", "FORWARD 序列跨越不同执行策略版本")
        nav = dict(dict(document["result"])["nav"])
        portfolio = _money(nav["normalized_nav"]) / anchor_portfolio
        benchmark = _money(nav["benchmark_nav"]) / anchor_benchmark
        peak = max(peak, portfolio)
        drawdown = portfolio / peak - Decimal("1")
        turnover += _money(nav["turnover"])
        if int(row["order_count"]) > 0:
            rebalances += 1
        series.append(
            {
                "trade_date": _display_date(str(document["execution_trade_date"])),
                "forward_portfolio_nav": _decimal_text(portfolio),
                "forward_benchmark_nav": _decimal_text(benchmark),
                "forward_net_excess": _decimal_text(portfolio - benchmark),
                "forward_drawdown": _decimal_text(drawdown),
                "cash_ratio": str(nav["cash_ratio"]),
                "turnover": str(nav["turnover"]),
                "daily_fees": str(nav["daily_fees"]),
                "artifact_sha256": row["artifact_sha256"],
            }
        )
    latest_nav = dict(dict(documents[-1]["result"])["nav"])
    forward_fees = _money(latest_nav["cumulative_fees"]) - _money(
        anchor_nav["cumulative_fees"]
    )
    forward_dividends = _money(latest_nav["cumulative_dividends"]) - _money(
        anchor_nav["cumulative_dividends"]
    )
    return {
        "status": "PASS",
        "performance_maturity": "OBSERVING",
        "forward_anchor_trade_date": _display_date(str(anchor["execution_trade_date"])),
        "forward_anchor_portfolio_nav": str(anchor_nav["normalized_nav"]),
        "forward_anchor_benchmark_nav": str(anchor_nav["benchmark_nav"]),
        "forward_anchor_artifact_sha256": anchor_row["artifact_sha256"],
        "execution_policy_version": version,
        "forward_observation_count": len(series),
        "forward_rebalance_count": rebalances,
        "coverage_status": "NOT_EVALUATED",
        "coverage_ratio": None,
        "coverage_reason": "P3-0 未挂载官方交易日历，成熟度保持 OBSERVING",
        "forward_cumulative_fees": _decimal_text(forward_fees),
        "forward_cumulative_dividends": _decimal_text(forward_dividends),
        "forward_turnover": _decimal_text(turnover),
        "forward_cash_ratio": str(latest_nav["cash_ratio"]),
        "latest": series[-1],
        "series": series,
        "suppressed_metrics": [
            "forward_annualized_return",
            "forward_annualized_volatility",
            "forward_sharpe",
            "forward_information_ratio",
        ],
    }


def _paper_replay(
    accounts: list[dict[str, str]],
    events: list[dict[str, str]],
    rows: list[dict[str, str]],
    documents: list[dict[str, object]],
    *,
    as_of: str,
    account_id: str,
) -> dict[str, object]:
    identities = [row for row in accounts if row.get("account_id") == account_id]
    if len(identities) != 1:
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟账户身份不唯一")
    account = identities[0]
    run_ids = {row["run_id"] for row in rows}
    selected_events = [
        row
        for row in events
        if row.get("account_id") == account_id
        and row.get("effective_date", "") <= as_of
    ]
    event_ids = [row.get("event_id", "") for row in selected_events]
    if not all(event_ids) or len(event_ids) != len(set(event_ids)):
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件身份重复或缺失")
    orphaned = {row.get("run_id", "") for row in selected_events} - run_ids
    if orphaned:
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件没有对应的 PASS 运行")
    by_run: dict[str, list[dict[str, str]]] = {}
    for event in selected_events:
        by_run.setdefault(event["run_id"], []).append(event)
    previous_state: dict[str, object] | None = None
    mode_counts: dict[str, int] = {}
    total_orders = 0
    total_fills = 0
    for row, document in zip(rows, documents, strict=True):
        if (
            document["account_id"] != account_id
            or document["policy_sha256"] != account.get("policy_sha256")
            or str(document.get("execution_policy_version", ""))
            != account.get("execution_policy_version")
        ):
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟账户或策略身份不一致")
        if document.get("prior_state_sha256") != _sha256(previous_state):
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟账户状态链断裂")
        run_events = sorted(by_run.get(row["run_id"], []), key=lambda item: int(item["sequence"]))
        sequences = [int(event["sequence"]) for event in run_events]
        if sequences != list(range(1, len(run_events) + 1)):
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件序列不连续")
        if len(run_events) != int(row["event_count"]):
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件数量与运行账本不一致")
        actual: dict[str, list[object]] = {}
        for event in run_events:
            try:
                payload = json.loads(event["payload_json"])
            except json.JSONDecodeError as error:
                raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件载荷格式无效") from error
            if event["evidence_sha256"] != _sha256(payload):
                raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件证据哈希不一致")
            expected_id = hashlib.sha256(
                (
                    f"{row['run_id']}|{event['sequence']}|"
                    f"{event['event_type']}|{event['business_key']}"
                ).encode()
            ).hexdigest()[:20]
            if event["event_id"] != expected_id:
                raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件身份校验失败")
            if (
                event["effective_date"] != row["execution_trade_date"]
                or event["signal_sha256"] != row["signal_sha256"]
            ):
                raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件业务身份不一致")
            if str(event.get("ts_code", "")).endswith(".BJ"):
                raise WebQueryError("FORBIDDEN_UNIVERSE", "模拟事件包含禁止的北交所证券")
            actual.setdefault(event["event_type"], []).append(payload)
        result = dict(document["result"])
        nav = dict(result["nav"])
        expected = {
            "CORPORATE_ACTION": list(result["corporate_actions"]),
            "ORDER": list(result["orders"]),
            "FILL": list(result["fills"]),
            "POSITION": list(nav["positions"]),
            "CASH": [{"cash": nav["cash"]}],
            "NAV": [nav],
        }
        for event_type, payloads in expected.items():
            if actual.get(event_type, []) != payloads:
                raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件与不可变产物不一致")
        expected_types = {event_type for event_type, payloads in expected.items() if payloads}
        if set(actual) != expected_types:
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件包含未支持的类型")
        if (
            len(expected["ORDER"]) != int(row["order_count"])
            or len(expected["FILL"]) != int(row["fill_count"])
        ):
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟订单或成交数量不一致")
        state = dict(document["state"])
        if state["cash"] != nav["cash"]:
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟现金与状态不一致")
        state_positions = dict(state["positions"])
        nav_positions = {str(value["ts_code"]): dict(value) for value in nav["positions"]}
        if set(state_positions) != set(nav_positions):
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟持仓集合与状态不一致")
        for code, state_value in state_positions.items():
            position = dict(state_value)
            snapshot = nav_positions[code]
            for state_field, nav_field in (
                ("quantity", "quantity"),
                ("cost_basis", "cost_basis"),
                ("realized_pnl", "realized_pnl"),
                ("last_price_date", "price_date"),
            ):
                if str(position[state_field]) != str(snapshot[nav_field]):
                    raise WebQueryError("EVIDENCE_MISMATCH", "模拟逐仓状态重放不一致")
        if (
            _money(nav["cash"]) + _money(nav["market_value"]) != _money(nav["net_asset"])
            or _money(nav["equation_difference"]) != 0
            or row["net_asset"] != str(nav["net_asset"])
        ):
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟会计恒等或账本净值不一致")
        mode = str(document["mode"])
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        total_orders += len(expected["ORDER"])
        total_fills += len(expected["FILL"])
        previous_state = state
    return {
        "status": "PASS",
        "account_id": account_id,
        "as_of": _display_date(rows[-1]["execution_trade_date"]),
        "run_count": len(rows),
        "event_count": len(selected_events),
        "order_count": total_orders,
        "fill_count": total_fills,
        "mode_counts": mode_counts,
        "bse_count": 0,
    }


def _signal_projection(
    signal_row: dict[str, str],
    signal: dict[str, object],
    previous: dict[str, object] | None,
    paper_rows: list[dict[str, str]],
    paper_documents: list[dict[str, object]],
) -> dict[str, object]:
    generated_at = _parse_timestamp(signal["generated_at"])
    reference_indexes = [
        index
        for index, row in enumerate(paper_rows)
        if _parse_timestamp(row["finished_at"]) <= generated_at
    ]
    reference_projection: dict[str, object] | None = None
    actual_weights: dict[str, Decimal] = {}
    if reference_indexes:
        reference_index = reference_indexes[-1]
        reference_projection = _paper_projection(
            paper_rows[reference_index],
            paper_documents[reference_index],
        )
        actual_weights = {
            str(value["ts_code"]): _money(value["actual_weight"])
            for value in list(reference_projection["positions"])
        }
    current_orders = [dict(value) for value in list(signal["orders"])]
    current_targets = {
        _instrument_to_tushare(str(value["instrument"])): _money(value["target_weight"])
        for value in current_orders
    }
    previous_targets: dict[str, Decimal] = {}
    if previous is not None:
        previous_targets = {
            _instrument_to_tushare(str(dict(value)["instrument"])): _money(
                dict(value)["target_weight"]
            )
            for value in list(previous["orders"])
        }
    targets: list[dict[str, object]] = []
    for value in current_orders:
        code = _instrument_to_tushare(str(value["instrument"]))
        target = _money(value["target_weight"])
        actual = actual_weights.get(code, Decimal("0"))
        targets.append(
            {
                "rank": int(value["rank"]),
                "ts_code": code,
                "score": value["score"],
                "target_weight": _decimal_text(target),
                "target_change": "RETAINED" if code in previous_targets else "ADDED",
                "actual_weight": _decimal_text(actual),
                "planned_weight_delta": _decimal_text(target - actual),
            }
        )
    removed = [
        {"ts_code": code, "previous_target_weight": _decimal_text(weight)}
        for code, weight in sorted(previous_targets.items())
        if code not in current_targets
    ]
    rebalance_due = bool(signal["rebalance_due"])
    planned_legs = (
        sum(
            target != actual_weights.get(code, Decimal("0"))
            for code, target in current_targets.items()
        )
        + sum(code not in current_targets for code in actual_weights)
        if rebalance_due
        else 0
    )
    return {
        "signal_date": str(signal["signal_date"]),
        "generated_at": str(signal["generated_at"]),
        "data_complete_at": str(signal["data_complete_at"]),
        "signal_sha256": str(signal["signal_sha256"]),
        "previous_signal_sha256": str(signal.get("previous_signal_sha256", "")),
        "code_snapshot_sha256": str(signal["code_snapshot_sha256"]),
        "data_snapshot_sha256": str(signal["data_snapshot_sha256"]),
        "qlib_artifact_sha256": str(signal["qlib_artifact_sha256"]),
        "model_spec_sha256": str(signal["model_spec_sha256"]),
        "model_artifact_sha256": str(signal["model_artifact_sha256"]),
        "rebalance_due": rebalance_due,
        "rebalance_days": int(signal["rebalance_days"]),
        "target_count": len(targets),
        "planned_trade_leg_count": planned_legs,
        "targets": targets,
        "removed_targets": removed,
        "actual_weight_as_of": (
            None if reference_projection is None else reference_projection["as_of"]
        ),
        "actual_weight_artifact_sha256": (
            None
            if reference_projection is None
            else dict(reference_projection["evidence_hashes"])["artifact_sha256"]
        ),
        "bse_count": 0,
        "source_ref": signal_row["signal_manifest_path"],
        "source_file_sha256": "",
    }


def _reconciliation_projection(
    cut: _EvidenceCut,
    row: dict[str, str] | None,
) -> dict[str, object]:
    if row is None:
        return {
            "execution_evidence_status": "NOT_DUE",
            "next_execution_date": None,
            "executed_trade_leg_count": None,
            "tradable_numerator": None,
            "tradable_denominator": None,
            "metric_status": "NOT_DUE",
            "open_gap": None,
            "turnover": None,
            "estimated_cost": None,
            "bse_count": 0,
        }
    if row.get("status") != "PASS":
        return {
            "execution_evidence_status": "FAIL",
            "next_execution_date": _display_date(row["execution_trade_date"]),
            "error_type": str(row.get("error_type", "")),
            "bse_count": 0,
        }
    document = _read_reconciliation(cut, row)
    denominator = int(row["trade_count"])
    numerator = int(row["executable_count"])
    return {
        "execution_evidence_status": "PASS",
        "signal_trade_date": _display_date(row["signal_trade_date"]),
        "next_execution_date": _display_date(row["execution_trade_date"]),
        "signal_sha256": row["signal_sha256"],
        "executed_trade_leg_count": denominator,
        "tradable_numerator": numerator,
        "tradable_denominator": denominator,
        "metric_status": "PASS" if denominator else "NOT_APPLICABLE",
        "open_gap": document["mean_abs_open_deviation"],
        "open_gap_definition": document["open_deviation_definition"],
        "turnover": document["turnover"],
        "estimated_cost": document["estimated_cost"],
        "source_ref": row["artifact_path"],
        "artifact_sha256": row["artifact_sha256"],
        "bse_count": 0,
    }


def _notification_projection(
    cut: _EvidenceCut,
    *,
    as_of: str,
    require_reconciliation: bool,
    require_paper: bool,
    paper_account_id: str,
) -> tuple[dict[str, object], list[object], dict[str, str]]:
    records, relative = cut.notification_rows(as_of)
    required = [
        "daily_catchup_started",
        "daily_catchup_passed",
        "shadow_signal_started",
        "shadow_signal_completed",
    ]
    if require_reconciliation:
        required.append("shadow_next_open_reconciled")
    if require_paper:
        required.extend(
            ["paper_top20_cycle_started", "paper_top20_cycle_completed"]
            if paper_account_id == "model_top20"
            else ["paper_cycle_started", "paper_cycle_completed"]
        )
    selected = [record for record in records if str(record.get("event", "")) in required]
    by_event: dict[str, list[dict[str, object]]] = {}
    for record in selected:
        by_event.setdefault(str(record.get("event", "")), []).append(record)
    missing = [event for event in required if event not in by_event]
    failed_attempts = sum(record.get("status") == "FAIL" for record in selected)
    recovered = 0
    final_statuses: dict[str, str] = {}
    attempts: dict[str, int] = {}
    timestamps: list[object] = []
    for event, event_rows in by_event.items():
        ordered = sorted(
            event_rows,
            key=lambda value: (
                str(value.get("delivered_at", "")),
                int(value.get("attempt", 0)),
            ),
        )
        final = ordered[-1]
        final_statuses[event] = str(final.get("status", ""))
        attempts[event] = max(int(value.get("attempt", 0)) for value in ordered)
        timestamps.extend(
            value["delivered_at"] for value in ordered if value.get("delivered_at")
        )
        if final.get("status") == "PASS" and (
            final.get("recovered") or any(value.get("status") == "FAIL" for value in ordered)
        ):
            recovered += 1
    if missing:
        status = "NOT_READY"
    elif any(value != "PASS" for value in final_statuses.values()):
        status = "WARN"
    elif failed_attempts:
        status = "WARN"
    else:
        status = "PASS"
    projection = {
        "status": status,
        "required_events": required,
        "missing_events": missing,
        "final_delivery_status": final_statuses,
        "max_attempt_by_event": attempts,
        "failed_attempt_count": failed_attempts,
        "recovered_message_count": recovered,
        "duplicate_delivery_risk": any(value > 1 for value in attempts.values()),
        "source_ref": relative,
    }
    evidence = {}
    if relative is not None:
        evidence["notification_evidence_sha256"] = cut.sources[relative].sha256
    return projection, timestamps, evidence


def _build_from_cut(
    cut: _EvidenceCut,
    requested_as_of: str | None,
    *,
    account_id: str,
) -> SnapshotBundle:
    shadow_rows = cut.ledger_rows("ledger/shadow_runs.csv")
    terminal_shadows = _latest_by(
        shadow_rows,
        ("signal_trade_date",),
        date_field="signal_trade_date",
        requested_as_of=requested_as_of,
    )
    if not terminal_shadows:
        raise WebQueryError("NO_DATA", "没有已登记的影子运行", status_code=404)
    latest_terminal = max(terminal_shadows, key=lambda row: row["signal_trade_date"])
    actual_as_of = latest_terminal["signal_trade_date"]
    passed_signals = [
        row
        for row in terminal_shadows
        if row.get("status") == "PASS" and row.get("signal_manifest_path")
    ]
    if not passed_signals:
        raise WebQueryError("NO_DATA", "没有已完成的影子信号", status_code=404)
    signal_row = max(passed_signals, key=lambda row: row["signal_trade_date"])
    signal = _read_signal(cut, signal_row)
    previous_signal = None
    previous_signal_row: dict[str, str] | None = None
    previous_hash = str(signal.get("previous_signal_sha256", ""))
    if previous_hash:
        previous_rows = [row for row in passed_signals if row["signal_sha256"] == previous_hash]
        if len(previous_rows) != 1:
            raise WebQueryError("EVIDENCE_MISMATCH", "上一信号身份无法唯一解析")
        previous_signal_row = previous_rows[0]
        previous_signal = _read_signal(cut, previous_signal_row)

    paper_account_rows = cut.ledger_rows("ledger/paper_accounts.csv")
    paper_event_rows = cut.ledger_rows("ledger/paper_events.csv")
    paper_ledger_rows = cut.ledger_rows("ledger/paper_runs.csv")
    paper_rows = _passed_paper_runs(
        paper_ledger_rows,
        account_id=account_id,
        as_of=actual_as_of,
    )
    if not paper_rows:
        raise WebQueryError("NO_DATA", "没有已完成的模拟账户日", status_code=404)
    paper_documents = [_read_paper_document(cut, row) for row in paper_rows]
    _resolve_legacy_policy_versions(
        paper_account_rows,
        paper_documents,
        account_id=account_id,
    )
    paper_portfolio = _paper_projection(paper_rows[-1], paper_documents[-1])
    paper_nav = _paper_nav(paper_rows, paper_documents, account_id=account_id)
    paper_forward = _forward_projection(paper_rows, paper_documents)
    paper_replay = _paper_replay(
        paper_account_rows,
        paper_event_rows,
        paper_rows,
        paper_documents,
        as_of=actual_as_of,
        account_id=account_id,
    )

    latest_signal = _signal_projection(
        signal_row,
        signal,
        previous_signal,
        paper_rows,
        paper_documents,
    )
    latest_signal["source_file_sha256"] = cut.sources[
        signal_row["signal_manifest_path"]
    ].sha256

    reconciliation_rows = _latest_by(
        cut.ledger_rows("ledger/shadow_reconciliations.csv"),
        ("signal_sha256", "execution_trade_date"),
        date_field="execution_trade_date",
        requested_as_of=actual_as_of,
    )
    reconciliations: dict[str, dict[str, object]] = {}
    for row in sorted(reconciliation_rows, key=lambda value: value["finished_at"]):
        reconciliations[row["signal_sha256"]] = _reconciliation_projection(cut, row)
    current_reconciliation_row = next(
        (
            row
            for row in reconciliation_rows
            if row["signal_sha256"] == signal_row["signal_sha256"]
        ),
        None,
    )
    current_reconciliation = _reconciliation_projection(cut, current_reconciliation_row)
    latest_signal.update(current_reconciliation)

    same_day_reconciliation = any(
        row.get("execution_trade_date") == actual_as_of and row.get("status") == "PASS"
        for row in reconciliation_rows
    )
    same_day_paper = (
        paper_rows[-1]["execution_trade_date"] == actual_as_of
        and paper_rows[-1].get("operator") == "docker-scheduler"
    )
    notifications, notification_times, notification_hashes = _notification_projection(
        cut,
        as_of=actual_as_of,
        require_reconciliation=same_day_reconciliation,
        require_paper=same_day_paper,
        paper_account_id=account_id,
    )

    current_shadow_attempts = [
        row
        for row in shadow_rows
        if row.get("signal_trade_date") == actual_as_of
    ]
    failed_shadow_attempts = [
        row for row in current_shadow_attempts if row.get("status") == "FAIL"
    ]
    if latest_terminal.get("status") != "PASS":
        operational_status = "FAIL"
    elif latest_terminal.get("on_time") != "true":
        operational_status = "STALE"
    elif failed_shadow_attempts:
        operational_status = "WARN"
    else:
        operational_status = "PASS"
    performance_status = str(paper_forward["performance_maturity"])
    status_reasons: list[str] = []
    if operational_status != "PASS":
        status_reasons.append(f"OPERATIONAL_{operational_status}")
    if paper_portfolio["freshness_status"] == "STALE":
        status_reasons.append("PAPER_STALE")
    if notifications["status"] != "PASS":
        status_reasons.append(f"NOTIFICATION_{notifications['status']}")
    if performance_status == "NOT_READY":
        status_reasons.append("FORWARD_NOT_READY")
    candidates = [
        operational_status,
        "STALE" if paper_portfolio["freshness_status"] == "STALE" else "PASS",
        str(notifications["status"]),
        "NOT_READY" if performance_status == "NOT_READY" else "PASS",
    ]
    overall_status = next(status for status in STATUS_PRECEDENCE if status in candidates)
    required_complete = (
        latest_terminal.get("status") == "PASS"
        and latest_terminal.get("on_time") == "true"
        and paper_portfolio["freshness_status"] == "PASS"
        and paper_replay["status"] == "PASS"
        and latest_signal["bse_count"] == 0
        and paper_portfolio["bse_count"] == 0
    )

    selected_event_rows = [
        row
        for row in paper_event_rows
        if row.get("account_id") == account_id
        and row.get("effective_date", "") <= actual_as_of
    ]
    selected_shadow_attempts = [
        row
        for row in shadow_rows
        if row.get("signal_trade_date", "") <= actual_as_of
    ]
    evidence_hashes: dict[str, str] = {
        "shadow_run_rows_sha256": _sha256(
            sorted(
                selected_shadow_attempts,
                key=lambda row: (row["signal_trade_date"], row["finished_at"]),
            )
        ),
        "shadow_reconciliation_rows_sha256": _sha256(
            sorted(
                reconciliation_rows,
                key=lambda row: (row["execution_trade_date"], row["finished_at"]),
            )
        ),
        "paper_account_rows_sha256": _sha256(
            [row for row in paper_account_rows if row.get("account_id") == account_id]
        ),
        "paper_event_rows_sha256": _sha256(selected_event_rows),
        "paper_run_rows_sha256": _sha256(paper_rows),
        "latest_signal_file_sha256": cut.sources[signal_row["signal_manifest_path"]].sha256,
        "latest_signal_sha256": signal_row["signal_sha256"],
        "latest_paper_artifact_sha256": paper_rows[-1]["artifact_sha256"],
        **notification_hashes,
    }
    if previous_signal_row is not None:
        evidence_hashes["previous_signal_file_sha256"] = cut.sources[
            previous_signal_row["signal_manifest_path"]
        ].sha256
    for index, row in enumerate(paper_rows, start=1):
        evidence_hashes[f"paper_artifact_{index:04d}_sha256"] = row["artifact_sha256"]
    for index, row in enumerate(
        sorted(
            [row for row in reconciliation_rows if row.get("status") == "PASS"],
            key=lambda value: value["execution_trade_date"],
        ),
        start=1,
    ):
        evidence_hashes[f"reconciliation_artifact_{index:04d}_sha256"] = row[
            "artifact_sha256"
        ]
    generated_times: list[object] = [
        latest_terminal["finished_at"],
        signal["generated_at"],
        paper_documents[-1]["generated_at"],
        *notification_times,
    ]
    generated_at = _latest_timestamp(generated_times)
    source_refs = tuple(
        sorted(
            {
                *FIXED_LEDGER_PATHS,
                signal_row["signal_manifest_path"],
                *(
                    [previous_signal_row["signal_manifest_path"]]
                    if previous_signal_row is not None
                    else []
                ),
                *(row["artifact_path"] for row in paper_rows),
                *(
                    row["artifact_path"]
                    for row in reconciliation_rows
                    if row.get("status") == "PASS"
                ),
                *(
                    [str(notifications["source_ref"])]
                    if notifications["source_ref"] is not None
                    else []
                ),
            }
        )
    )
    snapshot_id = _sha256(
        {
            "protocol_id": "p3-web-query-v1",
            "schema_version": SCHEMA_VERSION,
            "paper_account_id": account_id,
            "as_of": actual_as_of,
            "evidence_hashes": evidence_hashes,
        }
    )
    overview = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "as_of": _display_date(actual_as_of),
        "generated_at": generated_at,
        "timezone": TIMEZONE,
        "overall_status": overall_status,
        "status_reason": status_reasons or ["ALL_REQUIRED_EVIDENCE_PASS"],
        "required_evidence_complete": required_complete,
        "operational_status": operational_status,
        "evidence_status": "PASS",
        "performance_observation_status": performance_status,
        "notification_status": notifications["status"],
        "latest_complete_trade_date": _display_date(signal_row["signal_trade_date"]),
        "action": {
            "signal_sha256": latest_signal["signal_sha256"],
            "signal_date": latest_signal["signal_date"],
            "rebalance_due": latest_signal["rebalance_due"],
            "next_execution_date": latest_signal["next_execution_date"],
            "target_count": latest_signal["target_count"],
            "planned_trade_leg_count": latest_signal["planned_trade_leg_count"],
            "execution_evidence_status": latest_signal["execution_evidence_status"],
        },
        "paper": {
            "account_id": account_id,
            "account_day": paper_portfolio["as_of"],
            "net_asset": paper_portfolio["net_asset"],
            "cash": paper_portfolio["cash"],
            "market_value": paper_portfolio["market_value"],
            "position_count": paper_portfolio["position_count"],
            "freshness_status": paper_portfolio["freshness_status"],
            "replay_status": paper_replay["status"],
        },
        "forward": {
            key: paper_forward.get(key)
            for key in (
                "status",
                "performance_maturity",
                "forward_anchor_trade_date",
                "forward_observation_count",
                "forward_rebalance_count",
                "coverage_status",
                "coverage_ratio",
                "forward_cumulative_fees",
                "forward_turnover",
                "forward_cash_ratio",
                "latest",
                "suppressed_metrics",
            )
        },
        "runtime": {
            "task_status": latest_terminal["status"],
            "on_time": latest_terminal.get("on_time") == "true",
            "attempt_count": len(current_shadow_attempts),
            "failed_attempt_count": len(failed_shadow_attempts),
            "recovered": (
                latest_terminal.get("status") == "PASS" and bool(failed_shadow_attempts)
            ),
            "first_failed_step": (
                failed_shadow_attempts[0].get("error_type")
                if failed_shadow_attempts
                else latest_terminal.get("error_type") or None
            ),
            "notification": notifications,
        },
        "evidence": {
            "controlled_code_snapshot": signal_row["code_snapshot_sha256"],
            "data_snapshot_sha256": signal_row["data_snapshot_sha256"],
            "model_artifact_sha256": signal_row["model_artifact_sha256"],
            "signal_sha256": signal_row["signal_sha256"],
            "acceptance_scope": "P3-0_READ_ONLY_QUERY_ONLY",
            "replay_status": paper_replay["status"],
            "bse_count": 0,
            "source_refs": list(source_refs),
            "evidence_hashes": evidence_hashes,
        },
    }
    return SnapshotBundle(
        snapshot_id=snapshot_id,
        as_of=_display_date(actual_as_of),
        generated_at=generated_at,
        source_refs=source_refs,
        evidence_hashes=evidence_hashes,
        overview=overview,
        paper_portfolio=paper_portfolio,
        paper_nav=paper_nav,
        paper_forward=paper_forward,
        paper_replay=paper_replay,
        latest_signal=latest_signal,
        reconciliations=reconciliations,
    )


def build_snapshot(
    as_of: str | None = None,
    *,
    account_id: str = DEFAULT_ACCOUNT_ID,
    project_root: Path | None = None,
) -> SnapshotBundle:
    """Build one stable snapshot without reading configuration, secrets, or raw data."""
    normalized = _normalize_as_of(as_of)
    normalized_account_id = _normalize_paper_account_id(account_id)
    root = (project_root or _default_root()).resolve()
    for _attempt in range(2):
        cut = _EvidenceCut(root)
        try:
            cut.open()
            bundle = _build_from_cut(
                cut,
                normalized,
                account_id=normalized_account_id,
            )
        except _EvidenceChanged:
            continue
        if cut.stable():
            return bundle
    raise WebQueryError(
        "CONFLICT",
        "查询期间权威证据发生变化，请重试",
        retryable=True,
    )


def nav_range(
    bundle: SnapshotBundle,
    *,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, object]:
    start_compact = _normalize_as_of(start)
    end_compact = _normalize_as_of(end)
    if start_compact and end_compact and start_compact > end_compact:
        raise WebQueryError(
            "INVALID_ARGUMENT",
            "start 不得晚于 end",
            status_code=422,
        )
    selected = [
        value
        for value in list(bundle.paper_nav["series"])
        if (start_compact is None or str(value["trade_date"]).replace("-", "") >= start_compact)
        and (end_compact is None or str(value["trade_date"]).replace("-", "") <= end_compact)
    ]
    if not selected:
        raise WebQueryError("NO_DATA", "指定范围没有模拟账户日", status_code=404)
    return {
        **{key: value for key, value in bundle.paper_nav.items() if key != "series"},
        "as_of": selected[-1]["trade_date"],
        "observation_count": len(selected),
        "series": selected,
    }


def reconciliation_for(
    bundle: SnapshotBundle,
    signal_sha256: str,
) -> dict[str, object]:
    if not SHA256_PATTERN.fullmatch(signal_sha256):
        raise WebQueryError(
            "INVALID_ARGUMENT",
            "signal_sha256 必须是 64 位小写 SHA-256",
            status_code=422,
        )
    return bundle.reconciliations.get(
        signal_sha256,
        {
            "signal_sha256": signal_sha256,
            "execution_evidence_status": "NOT_DUE",
            "next_execution_date": None,
            "metric_status": "NOT_DUE",
            "bse_count": 0,
        },
    )
