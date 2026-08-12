"""Claim-first, one-request Tushare recovery for the ChiNext market series."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ingest.core import RawBatchWriter
from shaiwei.ingest.tushare import Request, TushareIngestor, create_client
from shaiwei.ledger import INGEST, resolve_artifact_path
from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.trend_swing.contract import (
    TrendSwingError,
    canonical_sha256,
    sha256_file,
    write_once_json,
)
from shaiwei.research.trend_swing.recovery_contract import (
    CLAIM_PATH,
    EXPECTED_R3_REQUESTS,
    NETWORK_RECEIPT_PATH,
    RecoveryAddendum,
    RecoveryProtocol,
    RecoveryR2,
    RecoveryR2Addendum,
    RecoveryRelease,
)
from shaiwei.research.trend_swing.recovery_r3_contract import RecoveryR3
from shaiwei.research.trend_swing.sources import latest_source_entries


RECOVERY_OPERATOR = "ts-v3-recovery-r3"


@dataclass(frozen=True)
class NetworkSettings:
    ingest: Any
    universe: Any


class CountingClient:
    def __init__(self, client: Any) -> None:
        self.client = client
        self.attempt_count = 0

    def query(self, api_name: str, **kwargs: object) -> pd.DataFrame:
        self.attempt_count += 1
        return self.client.query(api_name, **kwargs)


def _network_settings(root: Path = PROJECT_ROOT) -> NetworkSettings:
    raw = yaml.safe_load((root / "config/settings.yaml").read_text(encoding="utf-8"))
    ingest = raw["ingest"]
    maximum = int(ingest["max_attempts"])
    if not 1 <= maximum <= 6:
        raise TrendSwingError("TS recovery transport-attempt configuration exceeds release")
    if raw["universe"].get("include_bse") is not False:
        raise TrendSwingError("TS recovery requires project-wide BSE exclusion")
    return NetworkSettings(
        ingest=SimpleNamespace(
            max_attempts=maximum,
            min_request_interval_seconds=float(ingest["min_request_interval_seconds"]),
            retry_base_seconds=float(ingest["retry_base_seconds"]),
            source_row_limit=int(ingest["source_row_limit"]),
            max_concurrent_requests=1,
        ),
        universe=SimpleNamespace(include_bse=False),
    )


def _tushare_token(path: Path) -> str:
    """Read only the named project-local secret after a durable request claim."""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "TUSHARE_TOKEN":
            continue
        token = value.strip().strip('"').strip("'")
        if not token:
            break
        return token
    raise TrendSwingError("project-local TUSHARE_TOKEN is absent")


def _claim_document(release: RecoveryRelease) -> dict[str, Any]:
    body = {
        "schema_version": "ts-v3-data-recovery-network-claim-r3-v1",
        "release_scope_sha256": release.scope_sha256,
        "requests_sha256": canonical_sha256(list(EXPECTED_R3_REQUESTS)),
        "logical_request_count": 3,
        "same_scope_retry_authorized": False,
        "secret_output_authorized": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return {**body, "claim_sha256": canonical_sha256(body)}


def claim_network_once(release: RecoveryRelease, path: Path = CLAIM_PATH) -> dict[str, Any]:
    document = _claim_document(release)
    payload = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(payload + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise TrendSwingError("TS recovery network scope was already claimed") from error
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return document


def _official_open_days(ledger_path: Path, root: Path) -> set[str]:
    ledger = pd.read_csv(ledger_path, dtype=str, keep_default_na=False)
    latest = latest_source_entries(ledger, "tushare.trade_cal")
    if latest.empty:
        raise TrendSwingError("TS recovery official calendar source is absent")
    paths = [resolve_artifact_path(value) for value in latest["parquet_path"]]
    frames = [pd.read_parquet(path, columns=["exchange", "cal_date", "is_open"]) for path in paths]
    frame = pd.concat(frames, ignore_index=True)
    return {
        str(day)
        for day in frame.loc[
            frame["exchange"].astype(str).eq("SSE")
            & frame["is_open"].astype(str).isin({"1", "1.0"}),
            "cal_date",
        ]
        if "20160101" <= str(day) <= "20260811"
    }


def validate_response(
    frame: pd.DataFrame,
    request: dict[str, str],
    official_open_days: set[str],
) -> pd.DataFrame:
    expected_columns = request["fields"].split(",")
    if list(frame.columns) != expected_columns:
        raise TrendSwingError("TS recovery response column order differs")
    if frame.empty or len(frame) >= 6000:
        raise TrendSwingError("TS recovery response is empty or possibly truncated")
    codes = set(frame["ts_code"].astype(str))
    if codes != {request["ts_code"]} or any(code.endswith(".BJ") for code in codes):
        raise TrendSwingError("TS recovery response security identity differs")
    dates = frame["trade_date"].astype(str)
    if frame.duplicated(["ts_code", "trade_date"]).any():
        raise TrendSwingError("TS recovery response has duplicate security-date keys")
    if not set(dates) <= official_open_days:
        raise TrendSwingError("TS recovery response contains a non-official trading date")
    expected_dates = sorted(
        day for day in official_open_days if request["start_date"] <= day <= request["end_date"]
    )
    if not expected_dates or list(dates.sort_values()) != expected_dates:
        raise TrendSwingError("TS recovery response date coverage differs")
    numeric = frame[["open", "high", "low", "close", "pre_close"]].apply(
        pd.to_numeric, errors="coerce"
    )
    if numeric.isna().any().any() or (numeric <= 0).any().any():
        raise TrendSwingError("TS recovery response contains invalid index prices")
    if (numeric["high"] < numeric[["open", "close", "low"]].max(axis=1)).any():
        raise TrendSwingError("TS recovery response contains invalid index highs")
    if (numeric["low"] > numeric[["open", "close", "high"]].min(axis=1)).any():
        raise TrendSwingError("TS recovery response contains invalid index lows")
    return frame.loc[:, expected_columns].sort_values("trade_date").reset_index(drop=True)


def _verify_release_identity(release: RecoveryRelease, ledger_path: Path) -> None:
    scope = release.document["scope"]
    if scope["implementation_git_head"] != git_head():
        raise TrendSwingError("TS recovery Git identity differs from release")
    if scope["implementation_snapshot_sha256"] != code_snapshot_sha256():
        raise TrendSwingError("TS recovery code snapshot differs from release")
    if scope["ingest_ledger_before_sha256"] != sha256_file(ledger_path):
        raise TrendSwingError("TS recovery ingest ledger changed after release freeze")


def execute_network_once(
    *,
    root: Path = PROJECT_ROOT,
    ledger_path: Path = INGEST,
) -> dict[str, Any]:
    protocol = RecoveryProtocol.load()
    addendum = RecoveryAddendum.load(protocol)
    recovery_r2 = RecoveryR2.load(protocol, addendum)
    recovery_r2_addendum = RecoveryR2Addendum.load(recovery_r2)
    recovery_r3 = RecoveryR3.load(recovery_r2, recovery_r2_addendum)
    release = RecoveryRelease.load(
        protocol, addendum, recovery_r2, recovery_r2_addendum, recovery_r3
    )
    release.require_user_approval()
    _verify_release_identity(release, ledger_path)
    claim = claim_network_once(release)
    token_path = Path(os.getenv("SHAIWEI_TS_TOKEN_FILE", str(root / ".env")))
    token = _tushare_token(token_path)
    client = CountingClient(create_client(token))
    settings = _network_settings(root)
    requests = [
        Request(
            "index_daily",
            {key: scope[key] for key in ("ts_code", "start_date", "end_date")},
            {"symbol": scope["ts_code"], "period": f"{scope['start_date']}-{scope['end_date']}"},
        )
        for scope in EXPECTED_R3_REQUESTS
    ]
    ingestor = TushareIngestor(
        client=client,
        writer=RawBatchWriter(root / "data"),
        settings=settings,  # type: ignore[arg-type]
    )
    official_days = _official_open_days(ledger_path, root)
    raw_frames = ingestor.query_frames(requests)
    frames = [
        validate_response(frame, scope, official_days)
        for (request, frame), scope in zip(raw_frames, EXPECTED_R3_REQUESTS, strict=True)
    ]
    batches = [
        ingestor.writer.write(
            source_api="tushare.index_daily",
            params=scope,
            frame=frame,
            partitions=request.partitions,
            operator=RECOVERY_OPERATOR,
        )
        for (request, _), scope, frame in zip(raw_frames, EXPECTED_R3_REQUESTS, frames, strict=True)
    ]
    receipt = {
        "schema_version": "ts-v3-data-recovery-network-receipt-r3-v1",
        "release_scope_sha256": release.scope_sha256,
        "release_file_sha256": release.sha256,
        "claim_sha256": claim["claim_sha256"],
        "logical_request_count": 3,
        "transport_attempt_count": client.attempt_count,
        "successful_response_count": 3,
        "batches": [
            {
                "batch_id": batch.batch_id,
                "source_api": batch.source_api,
                "ts_code": scope["ts_code"],
                "row_count": batch.row_count,
                "first_date": str(frame["trade_date"].min()),
                "last_date": str(frame["trade_date"].max()),
                "raw_batch_path": batch.parquet_path.relative_to(root).as_posix(),
                "raw_batch_sha256": batch.content_sha256,
            }
            for batch, scope, frame in zip(batches, EXPECTED_R3_REQUESTS, frames, strict=True)
        ],
        "ingest_ledger_before_sha256": release.document["scope"]["ingest_ledger_before_sha256"],
        "ingest_ledger_after_sha256": sha256_file(ledger_path),
        "secret_output": False,
        "strategy_effect_attempt_count": 0,
    }
    _, reused = write_once_json(NETWORK_RECEIPT_PATH, receipt)
    if reused:
        raise TrendSwingError("TS recovery network receipt unexpectedly pre-existed")
    return receipt
