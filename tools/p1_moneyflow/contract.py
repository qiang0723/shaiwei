"""Frozen P1 money-flow collection contract and data-quality profiler."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from shaiwei.config import PROJECT_ROOT, Settings
from shaiwei.ingest.catalog import CatalogError, canonical_params_key
from shaiwei.ingest.core import RawBatch, RawBatchWriter
from shaiwei.ledger import INGEST, resolve_artifact_path, sha256_file

MONEYFLOW_FIELDS: dict[str, tuple[str, ...]] = {
    "moneyflow": (
        "ts_code", "trade_date", "buy_sm_vol", "buy_sm_amount", "sell_sm_vol",
        "sell_sm_amount", "buy_md_vol", "buy_md_amount", "sell_md_vol",
        "sell_md_amount", "buy_lg_vol", "buy_lg_amount", "sell_lg_vol",
        "sell_lg_amount", "buy_elg_vol", "buy_elg_amount", "sell_elg_vol",
        "sell_elg_amount", "net_mf_vol", "net_mf_amount",
    ),
    "moneyflow_ths": (
        "trade_date", "ts_code", "name", "pct_change", "latest", "net_amount",
        "net_d5_amount", "buy_lg_amount", "buy_lg_amount_rate", "buy_md_amount",
        "buy_md_amount_rate", "buy_sm_amount", "buy_sm_amount_rate",
    ),
    "moneyflow_dc": (
        "trade_date", "ts_code", "name", "pct_change", "close", "net_amount",
        "net_amount_rate", "buy_elg_amount", "buy_elg_amount_rate", "buy_lg_amount",
        "buy_lg_amount_rate", "buy_md_amount", "buy_md_amount_rate", "buy_sm_amount",
        "buy_sm_amount_rate",
    ),
}
MONEYFLOW_APIS = tuple(MONEYFLOW_FIELDS)
PRIMARY_MONEYFLOW_API = "moneyflow"
PRIMARY_MIN_DAILY_COVERAGE = 0.995
PRIMARY_MAX_SOURCE_ONLY_RATE = 0.005
PIT_POLICY = {
    "version": "moneyflow-pit-v1",
    "same_day_1930_status": "UNPROVEN",
    "feature_available_lag_trade_days": 1,
    "earliest_feature_use": "next_official_trade_day",
}

_KEY_COLUMNS = ("ts_code", "trade_date")
_TEXT_COLUMNS = {"ts_code", "trade_date", "name"}


class QueryClient(Protocol):
    def query(self, api_name: str, **kwargs: object) -> pd.DataFrame: ...


class MoneyflowIngestError(RuntimeError):
    pass


@dataclass(frozen=True)
class Request:
    api_name: str
    trade_date: str

    @property
    def params(self) -> dict[str, object]:
        return {"trade_date": self.trade_date}

    @property
    def partitions(self) -> dict[str, str]:
        return {"trade_date": self.trade_date}


def public_request_params(request: Request) -> dict[str, object]:
    return {**request.params, "fields": ",".join(MONEYFLOW_FIELDS[request.api_name])}


def build_moneyflow_plan(
    trade_dates: Iterable[str],
    *,
    apis: Iterable[str] = (PRIMARY_MONEYFLOW_API,),
) -> list[Request]:
    selected_apis = tuple(dict.fromkeys(apis))
    unknown = set(selected_apis) - set(MONEYFLOW_APIS)
    if not selected_apis or unknown:
        raise ValueError(f"invalid moneyflow APIs: {sorted(unknown) if selected_apis else []}")
    selected_dates = sorted(set(trade_dates))
    if not selected_dates:
        raise ValueError("at least one trade date is required")
    for trade_date in selected_dates:
        try:
            parsed = date.fromisoformat(
                f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
            )
        except (TypeError, ValueError):
            raise ValueError(f"invalid YYYYMMDD trade date: {trade_date!r}") from None
        if parsed.strftime("%Y%m%d") != trade_date:
            raise ValueError(f"invalid YYYYMMDD trade date: {trade_date!r}")
    return [
        Request(api_name, trade_date)
        for trade_date in selected_dates
        for api_name in selected_apis
    ]


class MoneyflowIngestor:
    """Sequential, fail-closed collector isolated from the production scheduler."""

    def __init__(
        self,
        *,
        client: QueryClient,
        writer: RawBatchWriter,
        settings: Settings,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client
        self.writer = writer
        self.settings = settings
        self.sleep = sleep
        self.monotonic = monotonic
        self._last_request_at: float | None = None

    def _throttle(self) -> None:
        if self._last_request_at is not None:
            elapsed = self.monotonic() - self._last_request_at
            remaining = self.settings.ingest.min_request_interval_seconds - elapsed
            if remaining > 0:
                self.sleep(remaining)
        self._last_request_at = self.monotonic()

    def _query(self, request: Request) -> pd.DataFrame:
        fields = MONEYFLOW_FIELDS[request.api_name]
        error: Exception | None = None
        frame: pd.DataFrame | None = None
        for attempt in range(self.settings.ingest.max_attempts):
            self._throttle()
            try:
                frame = self.client.query(
                    request.api_name,
                    trade_date=request.trade_date,
                    fields=",".join(fields),
                )
            except Exception as exc:
                error = exc
                if attempt + 1 < self.settings.ingest.max_attempts:
                    self.sleep(self.settings.ingest.retry_base_seconds * (2**attempt))
                continue
            if not isinstance(frame, pd.DataFrame):
                raise MoneyflowIngestError(
                    f"Tushare {request.api_name} returned {type(frame).__name__}, expected DataFrame"
                )
            if (
                frame.empty
                and request.api_name == PRIMARY_MONEYFLOW_API
                and attempt + 1 < self.settings.ingest.max_attempts
            ):
                self.sleep(self.settings.ingest.retry_base_seconds * (2**attempt))
                continue
            break
        else:
            raise MoneyflowIngestError(
                f"Tushare {request.api_name} failed after {self.settings.ingest.max_attempts} attempts"
            ) from error

        assert frame is not None
        if frame.empty and len(frame.columns) == 0:
            frame = pd.DataFrame(columns=fields)
        missing = set(fields) - set(frame.columns)
        extra = set(frame.columns) - set(fields)
        if missing or extra:
            raise MoneyflowIngestError(
                f"Tushare {request.api_name} schema drift: missing={sorted(missing)}, extra={sorted(extra)}"
            )
        # Check the provider payload before BSE exclusion.  A saturated raw
        # response must not look safe merely because filtering makes it smaller.
        if len(frame) >= self.settings.ingest.source_row_limit:
            raise MoneyflowIngestError(
                f"Tushare {request.api_name} returned {len(frame)} rows at/above configured limit; "
                "refuse possible truncation"
            )
        observed_dates = set(frame["trade_date"].dropna().astype(str))
        if observed_dates and observed_dates != {request.trade_date}:
            raise MoneyflowIngestError(
                f"Tushare {request.api_name} trade_date mismatch: {sorted(observed_dates)}"
            )
        if not self.settings.universe.include_bse:
            frame = frame.loc[
                ~frame["ts_code"].astype("string").str.endswith(".BJ", na=False)
            ].copy()
        return frame.loc[:, fields]

    def run(self, requests: Iterable[Request]) -> list[RawBatch]:
        batches = []
        for request in requests:
            batches.append(
                self.writer.write(
                    source_api=f"tushare.{request.api_name}",
                    params=public_request_params(request),
                    frame=self._query(request),
                    partitions=request.partitions,
                )
            )
        return batches


def request_evidence_history(
    source_api: str,
    params: dict[str, object],
    *,
    ledger_path: Path = INGEST,
) -> list[dict[str, str | int]]:
    entries = pd.read_csv(ledger_path, dtype=str, keep_default_na=False)
    entries = entries.loc[entries["source_api"].eq(source_api)].copy()
    wanted = canonical_params_key(params)
    entries = entries.loc[
        entries["params_json"].map(
            lambda value: canonical_params_key(json.loads(value))
        ).eq(wanted)
    ]
    if entries.empty:
        return []
    entries["_time"] = pd.to_datetime(entries["ingest_time"], utc=True, errors="raise")
    history = []
    for entry in entries.sort_values("_time").itertuples(index=False):
        path = resolve_artifact_path(entry.parquet_path)
        if not path.is_file():
            raise CatalogError(f"committed batch file is missing: {path}")
        if pq.read_metadata(path).num_rows != int(entry.row_count):
            raise CatalogError(f"row count mismatch: {path}")
        if sha256_file(path) != entry.content_sha256:
            raise CatalogError(f"content hash mismatch: {path}")
        history.append(
            {
                "batch_id": str(entry.batch_id),
                "ingest_time": str(entry.ingest_time),
                "row_count": int(entry.row_count),
                "content_sha256": str(entry.content_sha256),
                "path": str(entry.parquet_path),
            }
        )
    return history


def canonical_frame_sha256(api_name: str, frame: pd.DataFrame) -> str:
    if api_name not in MONEYFLOW_APIS:
        raise ValueError(f"unsupported moneyflow API: {api_name}")
    columns = list(MONEYFLOW_FIELDS[api_name])
    if missing := set(columns) - set(frame.columns):
        raise ValueError(f"{api_name} missing fields: {sorted(missing)}")
    canonical = frame.loc[:, columns].sort_values(list(_KEY_COLUMNS), kind="stable").reset_index(drop=True)
    payload = canonical.to_csv(
        index=False,
        float_format="%.12g",
        lineterminator="\n",
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _numeric_summary(series: pd.Series) -> dict[str, float | int] | None:
    numeric = pd.to_numeric(series, errors="coerce")
    numeric = numeric[np.isfinite(numeric)]
    if numeric.empty:
        return None
    quantiles = numeric.quantile([0.001, 0.5, 0.999])
    return {
        "count": int(numeric.size),
        "min": float(numeric.min()),
        "p001": float(quantiles.loc[0.001]),
        "median": float(quantiles.loc[0.5]),
        "p999": float(quantiles.loc[0.999]),
        "max": float(numeric.max()),
    }


def _ratio_summary(numerator: pd.Series, denominator: pd.Series) -> dict[str, float | int] | None:
    left = pd.to_numeric(numerator, errors="coerce")
    right = pd.to_numeric(denominator, errors="coerce")
    valid = left.notna() & right.gt(0)
    if not valid.any():
        return None
    ratio = left.loc[valid] / right.loc[valid]
    quantiles = ratio.quantile([0.01, 0.5, 0.99])
    return {
        "count": int(ratio.size),
        "p01": float(quantiles.loc[0.01]),
        "median": float(quantiles.loc[0.5]),
        "p99": float(quantiles.loc[0.99]),
    }


def profile_moneyflow_batch(
    api_name: str,
    trade_date: str,
    frame: pd.DataFrame,
    *,
    daily: pd.DataFrame,
    suspensions: pd.DataFrame | None = None,
) -> dict[str, object]:
    if api_name not in MONEYFLOW_APIS:
        raise ValueError(f"unsupported moneyflow API: {api_name}")
    expected = list(MONEYFLOW_FIELDS[api_name])
    missing_columns = sorted(set(expected) - set(frame.columns))
    extra_columns = sorted(set(frame.columns) - set(expected))
    issues: list[str] = []
    warnings: list[str] = []
    if missing_columns:
        issues.append("SCHEMA_MISSING_COLUMNS")
    if extra_columns:
        issues.append("SCHEMA_EXTRA_COLUMNS")
    working = frame.copy()
    for column in missing_columns:
        working[column] = pd.NA
    working = working.loc[:, expected]

    key_null_count = int(working.loc[:, list(_KEY_COLUMNS)].isna().any(axis=1).sum())
    duplicate_key_count = int(working.duplicated(list(_KEY_COLUMNS)).sum())
    wrong_trade_date_count = int(
        working["trade_date"].dropna().astype(str).ne(trade_date).sum()
    )
    bse_row_count = int(
        working["ts_code"].astype("string").str.endswith(".BJ", na=False).sum()
    )
    for condition, issue in (
        (key_null_count, "NULL_KEY"),
        (duplicate_key_count, "DUPLICATE_KEY"),
        (wrong_trade_date_count, "WRONG_TRADE_DATE"),
        (bse_row_count, "BSE_ROW_PRESENT"),
    ):
        if condition:
            issues.append(issue)

    numeric_columns = [column for column in expected if column not in _TEXT_COLUMNS]
    numeric: dict[str, pd.Series] = {}
    invalid_numeric_counts: dict[str, int] = {}
    infinite_numeric_counts: dict[str, int] = {}
    numeric_summary: dict[str, dict[str, float | int]] = {}
    for column in numeric_columns:
        converted = pd.to_numeric(working[column], errors="coerce")
        numeric[column] = converted
        invalid = int((working[column].notna() & converted.isna()).sum())
        infinite = int((converted.notna() & ~np.isfinite(converted)).sum())
        if invalid:
            invalid_numeric_counts[column] = invalid
        if infinite:
            infinite_numeric_counts[column] = infinite
        summary = _numeric_summary(converted)
        if summary is not None:
            numeric_summary[column] = summary
    if invalid_numeric_counts:
        issues.append("INVALID_NUMERIC")
    if infinite_numeric_counts:
        issues.append("INFINITE_NUMERIC")

    nonnegative_columns = (
        [column for column in numeric_columns if column.startswith(("buy_", "sell_"))]
        if api_name == PRIMARY_MONEYFLOW_API
        else []
    )
    negative_counts = {
        column: int(numeric[column].lt(0).sum())
        for column in nonnegative_columns
        if int(numeric[column].lt(0).sum())
    }
    if negative_counts:
        issues.append("NEGATIVE_GROSS_FLOW")
    invalid_rate_counts = {
        column: int(numeric[column].abs().gt(100).sum())
        for column in numeric_columns
        if column.endswith("_rate") and int(numeric[column].abs().gt(100).sum())
    }
    if invalid_rate_counts:
        issues.append("RATE_OUT_OF_RANGE")

    daily_slice = daily.loc[daily["trade_date"].astype(str).eq(trade_date)].copy()
    daily_codes = set(daily_slice["ts_code"].dropna().astype(str))
    source_codes = set(working["ts_code"].dropna().astype(str))
    intersection = source_codes & daily_codes
    source_only = source_codes - daily_codes
    daily_only = daily_codes - source_codes
    coverage = len(intersection) / len(daily_codes) if daily_codes else None
    source_only_rate = len(source_only) / len(daily_codes) if daily_codes else None

    suspension_start_codes: set[str] = set()
    resumption_codes: set[str] = set()
    if suspensions is not None and not suspensions.empty:
        suspension_slice = suspensions.loc[
            suspensions["trade_date"].astype(str).eq(trade_date)
        ]
        if "suspend_type" in suspension_slice.columns:
            suspension_start_codes = set(
                suspension_slice.loc[
                    suspension_slice["suspend_type"].astype(str).eq("S"), "ts_code"
                ].dropna().astype(str)
            )
            resumption_codes = set(
                suspension_slice.loc[
                    suspension_slice["suspend_type"].astype(str).eq("R"), "ts_code"
                ].dropna().astype(str)
            )
        else:
            suspension_start_codes = set(suspension_slice["ts_code"].dropna().astype(str))

    if working.empty and daily_codes:
        issues.append("NO_DATA_ON_OPEN_DAY")
    if not daily_codes:
        issues.append("DAILY_REFERENCE_MISSING")
    if api_name == PRIMARY_MONEYFLOW_API and coverage is not None:
        if coverage < PRIMARY_MIN_DAILY_COVERAGE:
            issues.append("PRIMARY_COVERAGE_BELOW_GATE")
        if source_only_rate is not None and source_only_rate > PRIMARY_MAX_SOURCE_ONLY_RATE:
            issues.append("PRIMARY_SOURCE_ONLY_ABOVE_GATE")

    consistency: dict[str, object] = {}
    if intersection:
        reference = daily_slice.loc[
            daily_slice["ts_code"].astype(str).isin(intersection),
            ["ts_code", "close", "pct_chg", "vol", "amount"],
        ].rename(columns={"close": "daily_close", "pct_chg": "daily_pct_chg"})
        aligned = working.loc[working["ts_code"].astype(str).isin(intersection)].merge(
            reference,
            on="ts_code",
            how="inner",
        )
        if api_name in {"moneyflow_ths", "moneyflow_dc"}:
            price_column = "latest" if api_name == "moneyflow_ths" else "close"
            close_diff = (
                pd.to_numeric(aligned[price_column], errors="coerce")
                - pd.to_numeric(aligned["daily_close"], errors="coerce")
            ).abs()
            pct_diff = (
                pd.to_numeric(aligned["pct_change"], errors="coerce")
                - pd.to_numeric(aligned["daily_pct_chg"], errors="coerce")
            ).abs()
            consistency.update(
                close_mismatch_count=int(close_diff.gt(1e-6).sum()),
                close_abs_diff_max=float(close_diff.max()),
                pct_abs_diff_max=float(pct_diff.max()),
            )
        if api_name == PRIMARY_MONEYFLOW_API:
            amount_columns = [
                f"{side}_{size}_amount"
                for size in ("sm", "md", "lg", "elg")
                for side in ("buy", "sell")
            ]
            volume_columns = [
                f"{side}_{size}_vol"
                for size in ("sm", "md", "lg", "elg")
                for side in ("buy", "sell")
            ]
            amount_ratio = _ratio_summary(
                aligned.loc[:, amount_columns].apply(pd.to_numeric, errors="coerce").sum(axis=1),
                pd.to_numeric(aligned["amount"], errors="coerce") / 10,
            )
            volume_ratio = _ratio_summary(
                aligned.loc[:, volume_columns].apply(pd.to_numeric, errors="coerce").sum(axis=1),
                pd.to_numeric(aligned["vol"], errors="coerce"),
            )
            consistency["classified_amount_to_daily_ratio"] = amount_ratio
            consistency["classified_volume_to_daily_ratio"] = volume_ratio
            if amount_ratio is None or not 1.9 <= float(amount_ratio["median"]) <= 2.1:
                issues.append("PRIMARY_AMOUNT_SCALE_MISMATCH")
            if volume_ratio is None or not 1.9 <= float(volume_ratio["median"]) <= 2.1:
                issues.append("PRIMARY_VOLUME_SCALE_MISMATCH")

            for name, values, denominator in (
                (
                    "net_amount_abs_to_daily_ratio",
                    pd.to_numeric(aligned["net_mf_amount"], errors="coerce").abs(),
                    pd.to_numeric(aligned["amount"], errors="coerce") / 10,
                ),
                (
                    "net_volume_abs_to_daily_ratio",
                    pd.to_numeric(aligned["net_mf_vol"], errors="coerce").abs(),
                    pd.to_numeric(aligned["vol"], errors="coerce"),
                ),
            ):
                summary = _ratio_summary(values, denominator)
                if summary is not None:
                    valid = denominator.gt(0) & values.notna()
                    ratios = values.loc[valid] / denominator.loc[valid]
                    summary.update(
                        max=float(ratios.max()),
                        over_1_01_count=int(ratios.gt(1.01).sum()),
                    )
                    if int(summary["over_1_01_count"]):
                        warnings.append("NET_FLOW_EXCEEDS_DAILY_SCALE_TAIL")
                consistency[name] = summary
    warnings = sorted(set(warnings))

    null_counts = {
        column: int(count)
        for column, count in working.isna().sum().items()
        if int(count)
    }
    if api_name == PRIMARY_MONEYFLOW_API:
        gate_status = "FAIL" if issues else "PASS"
    else:
        gate_status = "DIAGNOSTIC_WARN" if issues else "DIAGNOSTIC_PASS"
    return {
        "api": api_name,
        "trade_date": trade_date,
        "grain": ["ts_code", "trade_date"],
        "row_count": int(len(working)),
        "canonical_frame_sha256": canonical_frame_sha256(api_name, working),
        "gate_status": gate_status,
        "issues": issues,
        "warnings": warnings,
        "schema": {"missing_columns": missing_columns, "extra_columns": extra_columns},
        "keys": {
            "null_key_count": key_null_count,
            "duplicate_key_count": duplicate_key_count,
            "wrong_trade_date_count": wrong_trade_date_count,
        },
        "validity": {
            "bse_row_count": bse_row_count,
            "invalid_numeric_counts": invalid_numeric_counts,
            "infinite_numeric_counts": infinite_numeric_counts,
            "negative_gross_flow_counts": negative_counts,
            "invalid_rate_counts": invalid_rate_counts,
            "null_counts": null_counts,
        },
        "coverage": {
            "daily_reference_rows": int(len(daily_slice)),
            "intersection_codes": int(len(intersection)),
            "daily_coverage_rate": coverage,
            "source_only_codes": int(len(source_only)),
            "source_only_rate": source_only_rate,
            "daily_only_codes": int(len(daily_only)),
            "source_only_sample": sorted(source_only)[:10],
            "daily_only_sample": sorted(daily_only)[:10],
            "suspension_start_reference_codes": int(len(suspension_start_codes)),
            "resumption_reference_codes": int(len(resumption_codes)),
            "source_suspension_start_codes": int(len(source_codes & suspension_start_codes)),
            "source_resumption_codes": int(len(source_codes & resumption_codes)),
            "source_only_suspended_codes": int(len(source_only & suspension_start_codes)),
        },
        "consistency": consistency,
        "numeric_summary": numeric_summary,
        "pit_policy": PIT_POLICY,
    }


def tool_snapshot_sha256(root: Path | None = None) -> str:
    package_root = (root or Path(__file__).resolve().parent).resolve()
    payload = hashlib.sha256()
    for path in sorted(package_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        payload.update(path.relative_to(package_root).as_posix().encode("utf-8"))
        payload.update(b"\0")
        payload.update(hashlib.sha256(path.read_bytes()).digest())
    return payload.hexdigest()


def write_project_json(path: Path, payload: dict[str, object]) -> None:
    target = Path(path)
    project = PROJECT_ROOT.resolve()
    if not target.resolve().is_relative_to(project):
        raise ValueError(f"evidence path must stay inside project: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.link(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
