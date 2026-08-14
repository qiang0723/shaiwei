"""Pure contract and quality checks for the official H00906 benchmark snapshot."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import resolve_artifact_path
from shaiwei.research.trend_swing.contract import canonical_sha256, sha256_file
from shaiwei.research.trend_swing.sources import latest_source_entries


PROTOCOL_PATH = PROJECT_ROOT / "config/ts_v5_r3g2_benchmark_lineage_v1.yaml"
PROTOCOL_SHA256 = "48ce1e403e13c4921688cda19a7c437490428f53c2e6c457cf5a57e0f4764de7"
RECOVERY_PATH = PROJECT_ROOT / "config/ts_v5_r3g2_benchmark_transport_recovery_r1.yaml"
RECOVERY_SHA256 = "c0945de50895fb013648c05b0d7335c679015c5903b40b81e2b85075696d31bc"
RECOVERY_R2_PATH = PROJECT_ROOT / "config/ts_v5_r3g2_benchmark_transport_recovery_r2.yaml"
RECOVERY_R2_SHA256 = "30eb0458091b39f019c21aa817e731e3826b926cceb5611609000ecbcb2838bb"
OUTPUT_ROOT = PROJECT_ROOT / "data/research/trend_swing/ts-v5-r3g2-benchmark-lineage-v1"
FACTSHEET_PATH = OUTPUT_ROOT / "raw/000906factsheet.pdf"
FIRST_HISTORY_PATH = OUTPUT_ROOT / "raw/H00906-history-first.json"
SECOND_HISTORY_PATH = OUTPUT_ROOT / "raw/H00906-history-second.json"
DAILY_PATH = OUTPUT_ROOT / "H00906-daily.parquet"
REPORT_PATH = OUTPUT_ROOT / "data_gate_report.json"
MANIFEST_DRAFT_PATH = OUTPUT_ROOT / "tracked_manifest.json"
HISTORY_COLUMNS = (
    "trade_date",
    "index_code",
    "index_full_name_cn",
    "index_short_name_cn",
    "index_full_name_en",
    "index_short_name_en",
    "open",
    "high",
    "low",
    "close",
    "change",
    "pct_change",
    "volume",
    "amount",
    "constituent_count",
    "pe_ttm",
)
NUMERIC_COLUMNS = HISTORY_COLUMNS[6:]


class BenchmarkLineageError(RuntimeError):
    """Fail-closed H00906 lineage error."""


@dataclass(frozen=True)
class CalendarEvidence:
    open_days: frozenset[str]
    ledger_sha256: str
    batch_count: int
    batch_bundle_sha256: str


def load_protocol(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    if path.is_symlink() or sha256_file(path) != PROTOCOL_SHA256:
        raise BenchmarkLineageError("H00906 frozen protocol identity differs")
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BenchmarkLineageError("H00906 frozen protocol is not a mapping")
    if (
        value.get("status") != "RESULT_BLIND_BENCHMARK_LINEAGE_PROTOCOL_FROZEN"
        or value.get("benchmark", {}).get("index_code") != "H00906"
        or value.get("verdicts", {}).get("production_authorization") != "none"
    ):
        raise BenchmarkLineageError("H00906 frozen protocol authority differs")
    return value


def load_recovery(
    path: Path = RECOVERY_PATH,
    r2_path: Path = RECOVERY_R2_PATH,
) -> dict[str, Any]:
    if path.is_symlink() or sha256_file(path) != RECOVERY_SHA256:
        raise BenchmarkLineageError("H00906 transport recovery identity differs")
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BenchmarkLineageError("H00906 transport recovery is not a mapping")
    authority = value.get("recovery_authority", {})
    if (
        value.get("status") != "RESULT_UNKNOWN_TRANSPORT_RECOVERY_FROZEN"
        or value.get("parent_protocol", {}).get("sha256") != PROTOCOL_SHA256
        or authority.get("host_transport_only") is not True
        or authority.get("docker_offline_evaluation_once") is not True
        or authority.get("env_or_secret_read") is not False
        or value.get("post_transfer", {}).get("evaluation_network_mode") != "none"
    ):
        raise BenchmarkLineageError("H00906 transport recovery authority differs")
    if r2_path.is_symlink() or sha256_file(r2_path) != RECOVERY_R2_SHA256:
        raise BenchmarkLineageError("H00906 output preflight recovery identity differs")
    r2 = yaml.safe_load(r2_path.read_text(encoding="utf-8"))
    if not isinstance(r2, dict):
        raise BenchmarkLineageError("H00906 output preflight recovery is not a mapping")
    r2_authority = r2.get("r2_authority", {})
    if (
        r2.get("status") != "RESULT_UNKNOWN_HOST_OUTPUT_PREFLIGHT_RECOVERY_FROZEN"
        or r2.get("parent_recovery", {}).get("sha256") != RECOVERY_SHA256
        or not all(r2.get("r2_preflight", {}).values())
        or r2_authority.get("inherits_exact_three_public_requests_from_r1") is not True
        or r2_authority.get("env_or_secret_read") is not False
    ):
        raise BenchmarkLineageError("H00906 output preflight recovery authority differs")
    return r2


def canonical_history_data(raw: bytes) -> bytes:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BenchmarkLineageError("official H00906 response is not valid JSON") from exc
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or not data:
        raise BenchmarkLineageError("official H00906 response has no data rows")
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def parse_history(raw: bytes) -> pd.DataFrame:
    data = json.loads(canonical_history_data(raw))
    frame = pd.DataFrame(data)
    if len(frame.columns) != len(HISTORY_COLUMNS):
        raise BenchmarkLineageError("official H00906 response row shape differs")
    frame.columns = list(HISTORY_COLUMNS)
    parsed_dates = pd.to_datetime(frame["trade_date"], errors="coerce")
    if parsed_dates.isna().any():
        raise BenchmarkLineageError("official H00906 response contains invalid dates")
    frame["trade_date"] = parsed_dates.dt.strftime("%Y%m%d")
    for column in HISTORY_COLUMNS[1:6]:
        frame[column] = frame[column].astype(str).str.strip()
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.loc[:, HISTORY_COLUMNS].sort_values("trade_date").reset_index(drop=True)


def validate_identity_text(text: str) -> None:
    normalized = "".join(text.split()).lower()
    required = ("000906", "n00906", "h00906")
    if any(token not in normalized for token in required):
        raise BenchmarkLineageError("official factsheet lacks the frozen return-code family")
    if "全收益" not in normalized and "totalreturn" not in normalized:
        raise BenchmarkLineageError("official factsheet lacks an explicit total-return label")


def load_calendar_evidence(
    ledger_path: Path,
    *,
    start_date: str,
    end_date: str,
) -> CalendarEvidence:
    before = sha256_file(ledger_path)
    ledger = pd.read_csv(ledger_path, dtype=str, keep_default_na=False)
    entries = latest_source_entries(ledger, "tushare.trade_cal")
    if entries.empty:
        raise BenchmarkLineageError("official SSE calendar evidence is absent")
    frames: list[pd.DataFrame] = []
    batches: list[dict[str, Any]] = []
    for row in entries.itertuples(index=False):
        path = resolve_artifact_path(str(row.parquet_path))
        if not path.is_file() or sha256_file(path) != str(row.content_sha256):
            raise BenchmarkLineageError("official SSE calendar batch identity differs")
        if pq.read_metadata(path).num_rows != int(row.row_count):
            raise BenchmarkLineageError("official SSE calendar batch row count differs")
        frames.append(pd.read_parquet(path, columns=["exchange", "cal_date", "is_open"]))
        batches.append(
            {
                "batch_id": str(row.batch_id),
                "row_count": int(row.row_count),
                "content_sha256": str(row.content_sha256),
            }
        )
    if sha256_file(ledger_path) != before:
        raise BenchmarkLineageError("ingest ledger changed during calendar evidence read")
    calendar = pd.concat(frames, ignore_index=True)
    calendar = calendar.loc[
        calendar["exchange"].astype(str).eq("SSE")
        & calendar["cal_date"].astype(str).between(start_date, end_date)
    ].copy()
    variants = calendar.groupby(calendar["cal_date"].astype(str))["is_open"].nunique()
    if (variants > 1).any():
        raise BenchmarkLineageError("official SSE calendar has conflicting open status")
    open_days = frozenset(
        calendar.loc[calendar["is_open"].astype(str).isin({"1", "1.0"}), "cal_date"].astype(str)
    )
    if not open_days:
        raise BenchmarkLineageError("official SSE calendar has no open days in scope")
    return CalendarEvidence(open_days, before, len(batches), canonical_sha256(batches))


def evaluate_quality(
    first: pd.DataFrame,
    second: pd.DataFrame,
    *,
    identity_text: str,
    calendar: CalendarEvidence,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    validate_identity_text(identity_text)
    if not first.equals(second):
        raise BenchmarkLineageError("two official H00906 responses differ after parsing")
    if first.empty or set(first["index_code"]) != {"H00906"}:
        raise BenchmarkLineageError("official history index identity differs")
    duplicate_count = int(first.duplicated(["index_code", "trade_date"]).sum())
    dates = set(first["trade_date"])
    missing = sorted(calendar.open_days - dates)
    unexpected = sorted(dates - calendar.open_days)
    close = first["close"]
    invalid_close_count = int((close.isna() | ~close.map(math.isfinite) | close.le(0)).sum())
    ohlc = first[["open", "high", "low", "close"]]
    complete_ohlc = ohlc.dropna()
    invalid_ohlc_count = int(
        (
            complete_ohlc["high"].lt(complete_ohlc[["open", "low", "close"]].max(axis=1))
            | complete_ohlc["low"].gt(complete_ohlc[["open", "high", "close"]].min(axis=1))
        ).sum()
    )
    first_date = str(first["trade_date"].min())
    last_date = str(first["trade_date"].max())
    checks = {
        "identity_pass": True,
        "response_determinism_pass": True,
        "unique_key_pass": duplicate_count == 0,
        "official_calendar_coverage_pass": not missing and not unexpected,
        "close_validity_pass": invalid_close_count == 0,
        "optional_ohlc_consistency_pass": invalid_ohlc_count == 0,
        "bounded_date_span_pass": first_date >= start_date and last_date <= end_date,
    }
    if not all(checks.values()):
        raise BenchmarkLineageError("official H00906 quality gate failed")
    return {
        "schema_version": "ts-v5-r3g2-h00906-data-gate-report-v1",
        "protocol_id": "ts-v5-r3g2-h00906-benchmark-lineage-v1",
        "protocol_sha256": PROTOCOL_SHA256,
        "verdict": "GO_H00906_LINEAGE_DATA_GATE_ONLY",
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "index_code": "H00906",
        "row_count": len(first),
        "first_date": first_date,
        "last_date": last_date,
        "official_open_day_count": len(calendar.open_days),
        "duplicate_key_count": duplicate_count,
        "missing_official_open_date_count": len(missing),
        "unexpected_date_count": len(unexpected),
        "invalid_close_count": invalid_close_count,
        "complete_ohlc_row_count": len(complete_ohlc),
        "invalid_ohlc_count": invalid_ohlc_count,
        "calendar_ledger_sha256": calendar.ledger_sha256,
        "calendar_batch_count": calendar.batch_count,
        "calendar_batch_bundle_sha256": calendar.batch_bundle_sha256,
        "checks": checks,
        "official_request_count": 3,
        "tushare_or_secret_read_count": 0,
        "strategy_effect_attempt_count": 0,
    }
