"""Frozen source contract helpers for official-index lineage data gates."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol

import pandas as pd
import yaml

from shaiwei.config import PROJECT_ROOT, Settings
from shaiwei.ingest.catalog import canonical_params_key
from shaiwei.ingest.core import RawBatch, RawBatchWriter

FIELDS = {
    "index_daily": (
        "ts_code",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "pre_close",
        "change",
        "pct_chg",
        "vol",
        "amount",
    ),
    "index_weight": ("index_code", "con_code", "trade_date", "weight"),
}
KEYS = {
    "index_daily": ("ts_code", "trade_date"),
    "index_weight": ("index_code", "con_code", "trade_date"),
}
TOP_LEVEL_KEYS = {
    "schema_version",
    "frozen_at",
    "scope",
    "protocol_document",
    "protocol_sha256",
    "factor_results_inspected",
    "llm_execution_authorized",
    "production_authorization",
    "identity",
    "official_source_policy",
    "methodology_lineage_contract",
    "initial_set_contract",
    "event_contract",
    "tushare_source_contract",
    "quality_gate",
    "verdict_contract",
    "prohibited_actions",
}


class QueryClient(Protocol):
    def query(self, api_name: str, **kwargs: object) -> pd.DataFrame: ...


class DataGateError(RuntimeError):
    """The frozen source or evidence contract has been violated."""


@dataclass(frozen=True)
class Request:
    api_name: str
    index_code: str
    start_date: str
    end_date: str
    partition_name: str

    @property
    def params(self) -> dict[str, object]:
        code_key = "ts_code" if self.api_name == "index_daily" else "index_code"
        return {
            code_key: self.index_code,
            "start_date": self.start_date,
            "end_date": self.end_date,
        }

    @property
    def public_params(self) -> dict[str, object]:
        return {**self.params, "fields": ",".join(FIELDS[self.api_name])}

    @property
    def partitions(self) -> dict[str, str]:
        key = "year" if self.api_name == "index_daily" else "month"
        return {"index": self.index_code, key: self.partition_name}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_path(relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise DataGateError(f"path is not project-relative: {relative}")
    root = PROJECT_ROOT.resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise DataGateError(f"path escapes project root: {relative}") from error
    return candidate


def load_protocol(path: Path) -> dict[str, object]:
    config_path = path if path.is_absolute() else PROJECT_ROOT / path
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != TOP_LEVEL_KEYS:
        observed = set(payload) if isinstance(payload, dict) else set()
        raise DataGateError(
            f"protocol top-level schema drift: missing={sorted(TOP_LEVEL_KEYS - observed)}, "
            f"extra={sorted(observed - TOP_LEVEL_KEYS)}"
        )
    if payload["schema_version"] != "m2-star200-data-protocol-v1":
        raise DataGateError("unexpected protocol schema")
    if payload["factor_results_inspected"] is not False:
        raise DataGateError("data gate cannot inspect factor results")
    if payload["llm_execution_authorized"] is not False:
        raise DataGateError("data gate cannot authorize LLM execution")
    if payload["production_authorization"] != "none":
        raise DataGateError("data gate cannot authorize production")
    protocol_document = project_path(str(payload["protocol_document"]))
    if sha256_file(protocol_document) != payload["protocol_sha256"]:
        raise DataGateError("protocol document hash mismatch")
    identity = payload["identity"]
    source = payload["tushare_source_contract"]
    if identity["index_code"] != "000699.SH" or identity["index_provider_code"] != "000699":
        raise DataGateError("STAR200 identity drift")
    if source["APIs"] != ["index_daily", "index_weight"]:
        raise DataGateError("provider API set drift")
    if source["expected_completed_month_count"] != 24:
        raise DataGateError("completed-month count drift")
    return payload


def _month_windows(start: date, end: date) -> list[tuple[date, date]]:
    windows = []
    cursor = start.replace(day=1)
    while cursor <= end:
        next_month = (
            date(cursor.year + 1, 1, 1)
            if cursor.month == 12
            else date(cursor.year, cursor.month + 1, 1)
        )
        windows.append((max(start, cursor), min(end, next_month - timedelta(days=1))))
        cursor = next_month
    return windows


def build_plan(protocol: dict[str, object]) -> list[Request]:
    identity = protocol["identity"]
    source = protocol["tushare_source_contract"]
    index_code = str(identity["index_code"])
    daily_start = date.fromisoformat(str(source["index_daily_start"]))
    daily_end = date.fromisoformat(str(source["index_daily_end"]))
    month_start = date.fromisoformat(f"{source['index_weight_completed_month_start']}-01")
    month_end_label = str(source["index_weight_completed_month_end"])
    month_end_first = date.fromisoformat(f"{month_end_label}-01")
    next_month = (
        date(month_end_first.year + 1, 1, 1)
        if month_end_first.month == 12
        else date(month_end_first.year, month_end_first.month + 1, 1)
    )
    month_end = next_month - timedelta(days=1)
    requests = []
    for year in range(daily_start.year, daily_end.year + 1):
        window_start = max(daily_start, date(year, 1, 1))
        window_end = min(daily_end, date(year, 12, 31))
        requests.append(
            Request(
                "index_daily",
                index_code,
                window_start.strftime("%Y%m%d"),
                window_end.strftime("%Y%m%d"),
                str(year),
            )
        )
    for window_start, window_end in _month_windows(month_start, month_end):
        requests.append(
            Request(
                "index_weight",
                index_code,
                window_start.strftime("%Y%m%d"),
                window_end.strftime("%Y%m%d"),
                window_start.strftime("%Y-%m"),
            )
        )
    expected = int(source["expected_completed_month_count"])
    observed = sum(item.api_name == "index_weight" for item in requests)
    if observed != expected:
        raise DataGateError(f"request plan has {observed} months, expected {expected}")
    return requests


def canonical_frame_sha256(api_name: str, frame: pd.DataFrame) -> str:
    columns = list(FIELDS[api_name])
    if missing := set(columns) - set(frame.columns):
        raise DataGateError(f"{api_name} missing fields: {sorted(missing)}")
    canonical = frame.loc[:, columns].sort_values(list(KEYS[api_name]), kind="stable")
    payload = canonical.to_csv(
        index=False,
        float_format="%.12g",
        lineterminator="\n",
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_response(request: Request, frame: pd.DataFrame, row_limit: int) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise DataGateError(f"{request.api_name} response is not a DataFrame")
    fields = FIELDS[request.api_name]
    if frame.empty and len(frame.columns) == 0:
        frame = pd.DataFrame(columns=fields)
    missing = set(fields) - set(frame.columns)
    extra = set(frame.columns) - set(fields)
    if missing or extra:
        raise DataGateError(
            f"{request.api_name} schema drift: missing={sorted(missing)}, extra={sorted(extra)}"
        )
    if len(frame) >= row_limit:
        raise DataGateError(f"{request.api_name} reached frozen row limit {row_limit}")
    if not frame.empty:
        code_column = "ts_code" if request.api_name == "index_daily" else "index_code"
        if set(frame[code_column].dropna().astype(str)) != {request.index_code}:
            raise DataGateError(f"{request.api_name} index identity mismatch")
        dates = frame["trade_date"].dropna().astype(str)
        if not dates.between(request.start_date, request.end_date).all():
            raise DataGateError(f"{request.api_name} returned out-of-window dates")
        security = "con_code" if request.api_name == "index_weight" else "ts_code"
        if frame[security].astype("string").str.endswith(".BJ", na=False).any():
            raise DataGateError(f"{request.api_name} returned forbidden .BJ row")
    return frame.loc[:, fields].copy()


class StableCollector:
    """Require two identical serial responses before committing one raw batch."""

    def __init__(
        self,
        *,
        client: QueryClient,
        writer: RawBatchWriter,
        settings: Settings,
        operator: str,
        sleep=time.sleep,
        monotonic=time.monotonic,
    ) -> None:
        self.client = client
        self.writer = writer
        self.settings = settings
        self.operator = operator
        self.sleep = sleep
        self.monotonic = monotonic
        self._last_request_at: float | None = None

    def _throttle(self) -> None:
        if self._last_request_at is not None:
            remaining = (
                self.settings.ingest.min_request_interval_seconds
                - (self.monotonic() - self._last_request_at)
            )
            if remaining > 0:
                self.sleep(remaining)
        self._last_request_at = self.monotonic()

    def _query(self, request: Request) -> pd.DataFrame:
        error: Exception | None = None
        for attempt in range(self.settings.ingest.max_attempts):
            self._throttle()
            try:
                frame = self.client.query(
                    request.api_name,
                    fields=",".join(FIELDS[request.api_name]),
                    **request.params,
                )
                return validate_response(request, frame, self.settings.ingest.source_row_limit)
            except DataGateError:
                raise
            except Exception as exc:
                error = exc
                if attempt + 1 < self.settings.ingest.max_attempts:
                    self.sleep(self.settings.ingest.retry_base_seconds * (2**attempt))
        raise DataGateError(f"{request.api_name} failed after bounded retries") from error

    def collect(self, request: Request) -> tuple[RawBatch, dict[str, object]]:
        first = self._query(request)
        second = self._query(request)
        first_hash = canonical_frame_sha256(request.api_name, first)
        second_hash = canonical_frame_sha256(request.api_name, second)
        if first_hash != second_hash:
            raise DataGateError(f"immediate revision mismatch for {request.api_name}")
        batch = self.writer.write(
            source_api=f"tushare.{request.api_name}",
            params=request.public_params,
            frame=first,
            partitions=request.partitions,
            operator=self.operator,
        )
        return batch, {
            "api_name": request.api_name,
            "params_key": canonical_params_key(request.public_params),
            "row_count": len(first),
            "first_canonical_sha256": first_hash,
            "second_canonical_sha256": second_hash,
            "stable": True,
        }


def tool_snapshot_sha256() -> str:
    root = Path(__file__).resolve().parent
    rows = [
        {"path": path.name, "sha256": sha256_file(path)}
        for path in sorted(root.glob("*.py"))
    ]
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def write_immutable_json(path: Path, payload: dict[str, object]) -> bool:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise FileExistsError(f"immutable report differs: {path}")
        return False
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    os.link(temporary, path)
    temporary.unlink()
    return True
