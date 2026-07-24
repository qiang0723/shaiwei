"""Frozen P2-0 collection contract for 000688.SH."""

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

from shaiwei.config import PROJECT_ROOT, Settings
from shaiwei.ingest.catalog import canonical_params_key
from shaiwei.ingest.core import RawBatch, RawBatchWriter

INDEX_CODE = "000688.SH"
PROTOCOL_PATH = PROJECT_ROOT / "config" / "p2_star50_v1.yaml"
FIELDS = {
    "index_daily": (
        "ts_code", "trade_date", "open", "high", "low", "close", "pre_close",
        "change", "pct_chg", "vol", "amount",
    ),
    "index_weight": ("index_code", "con_code", "trade_date", "weight"),
}
KEYS = {
    "index_daily": ("ts_code", "trade_date"),
    "index_weight": ("index_code", "con_code", "trade_date"),
}


class QueryClient(Protocol):
    def query(self, api_name: str, **kwargs: object) -> pd.DataFrame: ...


class Star50CollectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class Request:
    api_name: str
    start_date: str
    end_date: str
    partition_name: str

    @property
    def params(self) -> dict[str, object]:
        code_key = "ts_code" if self.api_name == "index_daily" else "index_code"
        return {
            code_key: INDEX_CODE,
            "start_date": self.start_date,
            "end_date": self.end_date,
        }

    @property
    def public_params(self) -> dict[str, object]:
        return {**self.params, "fields": ",".join(FIELDS[self.api_name])}

    @property
    def partitions(self) -> dict[str, str]:
        key = "year" if self.api_name == "index_daily" else "month"
        return {"index": INDEX_CODE, key: self.partition_name}


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


def build_plan(start: date, end: date) -> list[Request]:
    if start > end:
        raise ValueError("start must not exceed end")
    requests: list[Request] = []
    for year in range(start.year, end.year + 1):
        window_start = max(start, date(year, 1, 1))
        window_end = min(end, date(year, 12, 31))
        requests.append(
            Request(
                "index_daily",
                window_start.strftime("%Y%m%d"),
                window_end.strftime("%Y%m%d"),
                str(year),
            )
        )
    for window_start, window_end in _month_windows(start, end):
        requests.append(
            Request(
                "index_weight",
                window_start.strftime("%Y%m%d"),
                window_end.strftime("%Y%m%d"),
                window_start.strftime("%Y-%m"),
            )
        )
    return requests


def canonical_frame_sha256(api_name: str, frame: pd.DataFrame) -> str:
    columns = list(FIELDS[api_name])
    if missing := set(columns) - set(frame.columns):
        raise Star50CollectionError(f"{api_name} missing fields: {sorted(missing)}")
    canonical = frame.loc[:, columns].sort_values(list(KEYS[api_name]), kind="stable")
    payload = canonical.to_csv(
        index=False,
        float_format="%.12g",
        lineterminator="\n",
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_response(request: Request, frame: pd.DataFrame, row_limit: int) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise Star50CollectionError(
            f"Tushare {request.api_name} returned {type(frame).__name__}, expected DataFrame"
        )
    fields = FIELDS[request.api_name]
    if frame.empty and len(frame.columns) == 0:
        frame = pd.DataFrame(columns=fields)
    missing = set(fields) - set(frame.columns)
    extra = set(frame.columns) - set(fields)
    if missing or extra:
        raise Star50CollectionError(
            f"{request.api_name} schema drift: missing={sorted(missing)}, extra={sorted(extra)}"
        )
    if len(frame) >= row_limit:
        raise Star50CollectionError(
            f"{request.api_name} returned {len(frame)} rows at/above frozen limit {row_limit}"
        )
    if not frame.empty:
        code_column = "ts_code" if request.api_name == "index_daily" else "index_code"
        observed_codes = set(frame[code_column].dropna().astype(str))
        if observed_codes != {INDEX_CODE}:
            raise Star50CollectionError(
                f"{request.api_name} code mismatch: {sorted(observed_codes)}"
            )
        dates = frame["trade_date"].dropna().astype(str)
        if not dates.between(request.start_date, request.end_date).all():
            raise Star50CollectionError(f"{request.api_name} returned out-of-window dates")
        constituent_column = "con_code" if request.api_name == "index_weight" else "ts_code"
        if frame[constituent_column].astype("string").str.endswith(".BJ", na=False).any():
            raise Star50CollectionError(f"{request.api_name} returned forbidden .BJ row")
    return frame.loc[:, fields].copy()


class StableCollector:
    """Serial collector that requires two identical provider responses before commit."""

    def __init__(
        self,
        *,
        client: QueryClient,
        writer: RawBatchWriter,
        settings: Settings,
        sleep=time.sleep,
        monotonic=time.monotonic,
    ) -> None:
        self.client = client
        self.writer = writer
        self.settings = settings
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
                return validate_response(
                    request,
                    frame,
                    self.settings.ingest.source_row_limit,
                )
            except Star50CollectionError:
                raise
            except Exception as exc:
                error = exc
                if attempt + 1 < self.settings.ingest.max_attempts:
                    self.sleep(self.settings.ingest.retry_base_seconds * (2**attempt))
        raise Star50CollectionError(
            f"Tushare {request.api_name} request failed after "
            f"{self.settings.ingest.max_attempts} attempts"
        ) from error

    def collect(self, request: Request) -> tuple[RawBatch, dict[str, object]]:
        first = self._query(request)
        second = self._query(request)
        first_hash = canonical_frame_sha256(request.api_name, first)
        second_hash = canonical_frame_sha256(request.api_name, second)
        if first_hash != second_hash:
            raise Star50CollectionError(
                f"{request.api_name} immediate revision mismatch for "
                f"{canonical_params_key(request.public_params)}"
            )
        batch = self.writer.write(
            source_api=f"tushare.{request.api_name}",
            params=request.public_params,
            frame=first,
            partitions=request.partitions,
            operator="docker-p2-star50",
        )
        return batch, {
            "api_name": request.api_name,
            "params_key": canonical_params_key(request.public_params),
            "row_count": len(first),
            "first_canonical_sha256": first_hash,
            "second_canonical_sha256": second_hash,
            "stable": True,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tool_snapshot_sha256() -> str:
    root = Path(__file__).resolve().parent
    rows = []
    for path in sorted(root.glob("*.py")):
        rows.append({"path": path.name, "sha256": sha256_file(path)})
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def write_immutable_json(path: Path, payload: dict[str, object]) -> bool:
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise FileExistsError(f"immutable report exists with different content: {path}")
        return False
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    os.link(temporary, path)
    temporary.unlink()
    return True
