import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
import yaml

from shaiwei.web.api import create_app
from shaiwei.web.operations import build_operations_snapshot, notification_for
from shaiwei.web.query import WebQueryError, build_snapshot


SHADOW_FIELDS = [
    "run_id",
    "started_at",
    "finished_at",
    "signal_trade_date",
    "status",
    "daily_run_id",
    "data_snapshot_sha256",
    "code_snapshot_sha256",
    "qlib_artifact_sha256",
    "model_spec_sha256",
    "model_artifact_sha256",
    "sentinel_report_path",
    "signal_manifest_path",
    "signal_sha256",
    "rebalance_due",
    "on_time",
    "error_type",
    "operator",
]
RECONCILIATION_FIELDS = [
    "reconciliation_id",
    "started_at",
    "finished_at",
    "signal_trade_date",
    "execution_trade_date",
    "status",
    "signal_sha256",
    "data_snapshot_sha256",
    "artifact_path",
    "artifact_sha256",
    "order_count",
    "trade_count",
    "executable_count",
    "turnover",
    "mean_abs_open_deviation",
    "estimated_cost",
    "error_type",
    "operator",
]
ACCOUNT_FIELDS = [
    "account_id",
    "created_at",
    "status",
    "initial_cash",
    "currency",
    "benchmark",
    "execution_policy_version",
    "policy_sha256",
    "code_snapshot_sha256",
    "operator",
]
EVENT_FIELDS = [
    "event_id",
    "run_id",
    "recorded_at",
    "account_id",
    "effective_date",
    "sequence",
    "event_type",
    "business_key",
    "signal_sha256",
    "ts_code",
    "side",
    "quantity",
    "price",
    "amount",
    "fee",
    "cash_after",
    "position_after",
    "payload_json",
    "evidence_sha256",
    "operator",
]
PAPER_RUN_FIELDS = [
    "run_id",
    "started_at",
    "finished_at",
    "account_id",
    "signal_trade_date",
    "execution_trade_date",
    "status",
    "signal_sha256",
    "reconciliation_sha256",
    "data_snapshot_sha256",
    "code_snapshot_sha256",
    "policy_sha256",
    "artifact_path",
    "artifact_sha256",
    "event_count",
    "order_count",
    "fill_count",
    "net_asset",
    "normalized_nav",
    "benchmark_nav",
    "freshness_status",
    "error_type",
    "operator",
]
DAILY_RUN_FIELDS = [
    "run_id",
    "started_at",
    "finished_at",
    "target_trade_date",
    "status",
    "batch_count",
    "row_count",
    "data_snapshot_sha256",
    "error_type",
    "operator",
]
INGEST_FIELDS = [
    "batch_id",
    "ingest_time",
    "source_api",
    "params_json",
    "row_count",
    "parquet_path",
    "content_sha256",
    "operator",
]


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _paper_day(
    root: Path,
    *,
    run_id: str,
    signal_hash: str,
    signal_date: str,
    execution_date: str,
    mode: str,
    cash: str,
    market_value: str,
    net_asset: str,
    normalized_nav: str,
    benchmark_nav: str,
    close: str,
    previous_state: dict[str, object] | None,
    include_policy_version: bool,
    account_id: str = "model_baseline",
    policy_version: str = "paper-v1",
    policy_hash: str = "a" * 64,
    operator: str = "docker-scheduler",
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    position_state = {
        "quantity": 100,
        "cost_basis": "1000.00",
        "realized_pnl": "0.00",
        "last_close": close,
        "last_price_date": execution_date,
    }
    state = {
        "account_id": account_id,
        "cash": cash,
        "positions": {"600001.SH": position_state},
        "entitlements": {},
        "cumulative_fees": "1.00",
        "cumulative_dividends": "0.00",
        "benchmark_base_open": "100",
        "peak_nav": normalized_nav,
        "last_trade_date": execution_date,
    }
    nav_position = {
        "ts_code": "600001.SH",
        "quantity": 100,
        "close": close,
        "price_date": execution_date,
        "market_value": market_value,
        "cost_basis": "1000.00",
        "realized_pnl": "0.00",
        "stale_trade_days": 0,
    }
    nav = {
        "freshness_status": "PASS",
        "cash": cash,
        "market_value": market_value,
        "net_asset": net_asset,
        "normalized_nav": normalized_nav,
        "benchmark_nav": benchmark_nav,
        "net_excess": str(float(normalized_nav) - float(benchmark_nav)),
        "drawdown": "0",
        "cash_ratio": str(float(cash) / float(net_asset)),
        "turnover": "0",
        "daily_fees": "0.00",
        "cumulative_fees": "1.00",
        "cumulative_dividends": "0.00",
        "equation_difference": "0",
        "positions": [nav_position],
    }
    generated = (
        datetime.strptime(execution_date, "%Y%m%d")
        .replace(hour=11, tzinfo=timezone.utc)
        .isoformat()
    )
    payload: dict[str, object] = {
        "schema_version": 1,
        "run_id": run_id,
        "started_at": generated,
        "generated_at": generated,
        "account_id": account_id,
        "signal_trade_date": signal_date,
        "execution_trade_date": execution_date,
        "mode": mode,
        "signal_sha256": signal_hash,
        "reconciliation_sha256": "3" * 64,
        "data_snapshot_sha256": "4" * 64,
        "code_snapshot_sha256": "5" * 64,
        "policy_sha256": policy_hash,
        "prior_state_sha256": _hash(previous_state),
        "source_refs": [],
        "state": state,
        "result": {
            "corporate_actions": [],
            "orders": [],
            "fills": [],
            "nav": nav,
        },
    }
    if include_policy_version:
        payload["execution_policy_version"] = policy_version
    document = {**payload, "content_sha256": _hash(payload)}
    relative = f"data/paper/{account_id}/runs/{execution_date}-{signal_hash[:12]}.json"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    artifact_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    run = {
        "run_id": run_id,
        "started_at": generated,
        "finished_at": generated,
        "account_id": account_id,
        "signal_trade_date": signal_date,
        "execution_trade_date": execution_date,
        "status": "PASS",
        "signal_sha256": signal_hash,
        "reconciliation_sha256": "3" * 64,
        "data_snapshot_sha256": "4" * 64,
        "code_snapshot_sha256": "5" * 64,
        "policy_sha256": policy_hash,
        "artifact_path": relative,
        "artifact_sha256": artifact_hash,
        "event_count": 3,
        "order_count": 0,
        "fill_count": 0,
        "net_asset": net_asset,
        "normalized_nav": normalized_nav,
        "benchmark_nav": benchmark_nav,
        "freshness_status": "PASS",
        "error_type": "",
        "operator": operator,
    }
    event_payloads = [
        ("POSITION", f"{execution_date}:600001.SH", nav_position),
        ("CASH", execution_date, {"cash": cash}),
        ("NAV", execution_date, nav),
    ]
    events: list[dict[str, object]] = []
    for sequence, (event_type, business_key, event_payload) in enumerate(
        event_payloads,
        start=1,
    ):
        event_id = hashlib.sha256(
            f"{run_id}|{sequence}|{event_type}|{business_key}".encode()
        ).hexdigest()[:20]
        events.append(
            {
                "event_id": event_id,
                "run_id": run_id,
                "recorded_at": generated,
                "account_id": account_id,
                "effective_date": execution_date,
                "sequence": sequence,
                "event_type": event_type,
                "business_key": business_key,
                "signal_sha256": signal_hash,
                "ts_code": (
                    "600001.SH" if event_type == "POSITION" else ""
                ),
                "quantity": 100 if event_type == "POSITION" else "",
                "cash_after": cash if event_type in {"CASH", "NAV"} else "",
                "position_after": 100 if event_type == "POSITION" else "",
                "payload_json": _canonical(event_payload).decode(),
                "evidence_sha256": _hash(event_payload),
                "operator": operator,
            }
        )
    return run, state, events


def _fixture(root: Path) -> str:
    for relative in (
        "data/shadow/signals",
        "data/shadow/reconciliations",
        "data/paper",
        "logs/notifications",
        "logs/releases",
        "logs/scheduler",
        "logs/sentinels",
        "ledger",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)
    ingest_rows = [
        {
            "batch_id": "batch-daily",
            "ingest_time": "2026-07-24T11:25:00+00:00",
            "source_api": "tushare.daily",
            "params_json": json.dumps({"trade_date": "20260724"}, sort_keys=True),
            "row_count": 1,
            "parquet_path": "data/raw/redacted-daily.parquet",
            "content_sha256": "c" * 64,
            "operator": "docker-scheduler",
        },
        {
            "batch_id": "batch-index",
            "ingest_time": "2026-07-24T11:26:00+00:00",
            "source_api": "tushare.index_daily",
            "params_json": json.dumps(
                {"trade_date": "20260724", "ts_code": "000906.SH"},
                sort_keys=True,
            ),
            "row_count": 1,
            "parquet_path": "data/raw/redacted-index.parquet",
            "content_sha256": "d" * 64,
            "operator": "docker-scheduler",
        },
    ]
    ingest_identity = [
        {
            "batch_id": row["batch_id"],
            "source_api": row["source_api"],
            "params_json": json.loads(str(row["params_json"])),
            "row_count": row["row_count"],
            "content_sha256": row["content_sha256"],
        }
        for row in ingest_rows
    ]
    data_hash = _hash(ingest_identity)
    _write_csv(root / "ledger/ingest_batches.csv", INGEST_FIELDS, ingest_rows)
    _write_csv(
        root / "ledger/daily_runs.csv",
        DAILY_RUN_FIELDS,
        [
            {
                "run_id": "daily1",
                "started_at": "2026-07-24T11:20:00+00:00",
                "finished_at": "2026-07-24T11:30:00+00:00",
                "target_trade_date": "20260724",
                "status": "PASS",
                "batch_count": 2,
                "row_count": 2,
                "data_snapshot_sha256": data_hash,
                "error_type": "",
                "operator": "docker-scheduler",
            }
        ],
    )
    signal_payload = {
        "schema_version": 2,
        "signal_date": "2026-07-24",
        "data_complete_at": "2026-07-24T11:30:00+00:00",
        "generated_at": "2026-07-24T12:00:00+00:00",
        "data_snapshot_sha256": data_hash,
        "code_commit": "abc",
        "code_snapshot_sha256": "7" * 64,
        "qlib_artifact_sha256": "8" * 64,
        "model_spec_sha256": "9" * 64,
        "model_artifact_sha256": "b" * 64,
        "model_artifact_path": "redacted",
        "score_rows": 1,
        "rebalance_due": False,
        "previous_signal_sha256": "",
        "rebalance_days": 10,
        "topk": 1,
        "orders": [
            {
                "rank": 1,
                "instrument": "SH600001",
                "score": 1.0,
                "target_weight": 1.0,
            }
        ],
    }
    signal_hash = _hash(signal_payload)
    signal_document = {**signal_payload, "signal_sha256": signal_hash}
    signal_relative = "data/shadow/signals/20260724-fixture.json"
    (root / signal_relative).write_text(
        json.dumps(signal_document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(
        root / "ledger/shadow_runs.csv",
        SHADOW_FIELDS,
        [
            {
                "run_id": "shadow1",
                "started_at": "2026-07-24T11:30:00+00:00",
                "finished_at": "2026-07-24T12:00:00+00:00",
                "signal_trade_date": "20260724",
                "status": "PASS",
                "daily_run_id": "daily1",
                "data_snapshot_sha256": data_hash,
                "code_snapshot_sha256": "7" * 64,
                "qlib_artifact_sha256": "8" * 64,
                "model_spec_sha256": "9" * 64,
                "model_artifact_sha256": "b" * 64,
                "sentinel_report_path": "logs/sentinels/fixture.json",
                "signal_manifest_path": signal_relative,
                "signal_sha256": signal_hash,
                "rebalance_due": "false",
                "on_time": "true",
                "operator": "docker-scheduler",
            }
        ],
    )
    sentinel_results = [
        {
            "sentinel": f"S{index}",
            "status": "NOT_APPLICABLE" if index == 10 else "PASS",
            "metrics": (
                {"security_count": 1, "excluded_bse_count": 3, "anomaly_count": 0}
                if index == 1
                else {"checked_rows": 1}
            ),
            "anomalies": [],
        }
        for index in range(1, 11)
    ]
    (root / "logs/sentinels/fixture.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-07-24T11:45:00+00:00",
                "git_head": "a" * 40,
                "code_snapshot_sha256": "7" * 64,
                "data_snapshot_sha256": data_hash,
                "required_failures": [],
                "results": sentinel_results,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_csv(
        root / "ledger/shadow_reconciliations.csv",
        RECONCILIATION_FIELDS,
        [],
    )
    _write_csv(
        root / "ledger/paper_accounts.csv",
        ACCOUNT_FIELDS,
        [
            {
                "account_id": "model_baseline",
                "created_at": "2026-07-22T11:00:00+00:00",
                "status": "ACTIVE",
                "initial_cash": "10000.00",
                "currency": "RMB",
                "benchmark": "000906.SH",
                "execution_policy_version": "paper-v1",
                "policy_sha256": "a" * 64,
                "code_snapshot_sha256": "5" * 64,
                "operator": "docker-scheduler",
            },
            {
                "account_id": "model_top20",
                "created_at": "2026-07-26T11:00:00+00:00",
                "status": "ACTIVE",
                "initial_cash": "10000.00",
                "currency": "RMB",
                "benchmark": "000906.SH",
                "execution_policy_version": "paper-top20-v1",
                "policy_sha256": "e" * 64,
                "code_snapshot_sha256": "5" * 64,
                "operator": "docker-top20-backfill",
            },
        ],
    )
    backfill, state, backfill_events = _paper_day(
        root,
        run_id="paper-backfill",
        signal_hash="1" * 64,
        signal_date="20260721",
        execution_date="20260722",
        mode="BACKFILL",
        cash="9000.00",
        market_value="1000.00",
        net_asset="10000.00",
        normalized_nav="1",
        benchmark_nav="1",
        close="10.00",
        previous_state=None,
        include_policy_version=False,
    )
    forward, _state, forward_events = _paper_day(
        root,
        run_id="paper-forward",
        signal_hash="2" * 64,
        signal_date="20260722",
        execution_date="20260723",
        mode="FORWARD",
        cash="9000.00",
        market_value="1100.00",
        net_asset="10100.00",
        normalized_nav="1.01",
        benchmark_nav="1.005",
        close="11.00",
        previous_state=state,
        include_policy_version=True,
    )
    top20_backfill, top20_state, top20_backfill_events = _paper_day(
        root,
        run_id="paper-top20-backfill-1",
        signal_hash="6" * 64,
        signal_date="20260721",
        execution_date="20260722",
        mode="BACKFILL",
        cash="8000.00",
        market_value="2000.00",
        net_asset="10000.00",
        normalized_nav="1",
        benchmark_nav="1",
        close="20.00",
        previous_state=None,
        include_policy_version=True,
        account_id="model_top20",
        policy_version="paper-top20-v1",
        policy_hash="e" * 64,
        operator="docker-top20-backfill",
    )
    top20_latest, _top20_state, top20_latest_events = _paper_day(
        root,
        run_id="paper-top20-backfill-2",
        signal_hash="d" * 64,
        signal_date="20260722",
        execution_date="20260723",
        mode="BACKFILL",
        cash="8000.00",
        market_value="1800.00",
        net_asset="9800.00",
        normalized_nav="0.98",
        benchmark_nav="1.005",
        close="18.00",
        previous_state=top20_state,
        include_policy_version=True,
        account_id="model_top20",
        policy_version="paper-top20-v1",
        policy_hash="e" * 64,
        operator="docker-top20-backfill",
    )
    _write_csv(
        root / "ledger/paper_runs.csv",
        PAPER_RUN_FIELDS,
        [backfill, forward, top20_backfill, top20_latest],
    )
    _write_csv(
        root / "ledger/paper_events.csv",
        EVENT_FIELDS,
        [
            *backfill_events,
            *forward_events,
            *top20_backfill_events,
            *top20_latest_events,
        ],
    )
    notification_rows = [
        {
            "attempt": 1,
            "delivered_at": f"2026-07-24T12:0{index}:00+00:00",
            "error_type": "",
            "event": event,
            "max_attempts": 3,
            "message_id": hashlib.sha256(event.encode()).hexdigest()[:16],
            "recovered": False,
            "retryable": False,
            "status": "PASS",
        }
        for index, event in enumerate(
            [
                "daily_catchup_started",
                "daily_catchup_passed",
                "shadow_signal_started",
                "shadow_signal_completed",
            ],
            start=1,
        )
    ]
    (root / "logs/notifications/feishu_20260724.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in notification_rows),
        encoding="utf-8",
    )
    release_unsigned = {
        "schema_version": "shaiwei-scheduler-release-audit-v1",
        "event": "START_PASS",
        "recorded_at": "2026-07-24T11:29:00+00:00",
        "git_head": "a" * 40,
        "previous_record_sha256": "",
        "details": {
            "code_snapshot_sha256": "7" * 64,
            "container_id": "f" * 64,
            "git_head": "a" * 40,
            "image_id": f"sha256:{'e' * 64}",
            "mount_destinations": ["/workspace/data", "/workspace/ledger", "/workspace/logs"],
            "read_only_rootfs": True,
        },
    }
    release = {**release_unsigned, "record_sha256": _hash(release_unsigned)}
    (root / "logs/releases/scheduler_releases.jsonl").write_text(
        json.dumps(release, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (root / "logs/scheduler/health.json").write_text(
        json.dumps(
            {
                "detail": "20260724",
                "pid": 999,
                "status": "noop",
                "updated_at": "2026-07-24T12:05:00+00:00",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return signal_hash


def test_snapshot_replays_evidence_and_keeps_forward_separate(tmp_path: Path):
    _fixture(tmp_path)
    first = build_snapshot(project_root=tmp_path)
    second = build_snapshot(project_root=tmp_path)

    assert first.snapshot_id == second.snapshot_id
    assert first.overview["overall_status"] == "PASS"
    assert first.paper_replay["status"] == "PASS"
    assert first.paper_replay["mode_counts"] == {"BACKFILL": 1, "FORWARD": 1}
    assert first.paper_forward["forward_anchor_trade_date"] == "2026-07-22"
    assert first.paper_forward["forward_observation_count"] == 1
    assert first.paper_forward["latest"]["forward_portfolio_nav"] == "1.01"
    assert first.paper_forward["coverage_status"] == "NOT_EVALUATED"
    assert first.latest_signal["actual_weight_as_of"] == "2026-07-23"
    assert first.latest_signal["planned_trade_leg_count"] == 0
    assert first.latest_signal["execution_evidence_status"] == "NOT_DUE"
    assert first.latest_signal["next_execution_date"] is None
    assert first.overview["evidence"]["bse_count"] == 0
    assert all(not Path(value).is_absolute() for value in first.source_refs)


def test_top20_snapshot_isolated_and_backfill_only(tmp_path: Path):
    _fixture(tmp_path)
    baseline = build_snapshot(project_root=tmp_path)
    top20 = build_snapshot(account_id="model_top20", project_root=tmp_path)

    assert top20.snapshot_id != baseline.snapshot_id
    assert top20.paper_portfolio["account_id"] == "model_top20"
    assert top20.paper_portfolio["execution_policy_version"] == "paper-top20-v1"
    assert top20.paper_nav["account_id"] == "model_top20"
    assert top20.paper_nav["forward_observation_count"] == 0
    assert top20.paper_forward["status"] == "NOT_READY"
    assert top20.paper_forward["forward_anchor_trade_date"] is None
    assert top20.paper_forward["latest"] is None
    assert top20.paper_forward["series"] == []
    assert top20.paper_replay["account_id"] == "model_top20"
    assert top20.paper_replay["mode_counts"] == {"BACKFILL": 2}
    assert top20.paper_replay["bse_count"] == 0

    with pytest.raises(WebQueryError) as invalid:
        build_snapshot(account_id="unregistered", project_root=tmp_path)
    assert invalid.value.code == "INVALID_ARGUMENT"


def test_signal_hash_and_bse_are_fail_closed(tmp_path: Path):
    signal_hash = _fixture(tmp_path)
    signal_path = tmp_path / "data/shadow/signals/20260724-fixture.json"
    signal = json.loads(signal_path.read_text(encoding="utf-8"))
    signal["orders"][0]["score"] = 2.0
    signal_path.write_text(json.dumps(signal), encoding="utf-8")
    with pytest.raises(WebQueryError, match="信号证据哈希不一致") as mismatch:
        build_snapshot(project_root=tmp_path)
    assert mismatch.value.code == "EVIDENCE_MISMATCH"

    _fixture(tmp_path)
    signal = json.loads(signal_path.read_text(encoding="utf-8"))
    signal["orders"][0]["instrument"] = "BJ430001"
    payload = {key: value for key, value in signal.items() if key != "signal_sha256"}
    new_hash = _hash(payload)
    signal["signal_sha256"] = new_hash
    signal_path.write_text(json.dumps(signal), encoding="utf-8")
    rows = list(csv.DictReader((tmp_path / "ledger/shadow_runs.csv").open()))
    rows[0]["signal_sha256"] = new_hash
    _write_csv(tmp_path / "ledger/shadow_runs.csv", SHADOW_FIELDS, rows)
    with pytest.raises(WebQueryError, match="北交所") as forbidden:
        build_snapshot(project_root=tmp_path)
    assert forbidden.value.code == "FORBIDDEN_UNIVERSE"
    assert signal_hash != new_hash


def test_api_is_allowlisted_sanitized_and_idempotent(tmp_path: Path):
    _fixture(tmp_path)
    client = TestClient(create_app(tmp_path))

    first = client.get("/api/v1/overview")
    second = client.get("/api/v1/overview")
    assert first.status_code == 200
    assert first.headers["etag"] == second.headers["etag"]
    assert first.json()["data"] == second.json()["data"]
    assert first.headers["cache-control"] == "no-store"
    assert len(first.content) < 1_048_576
    assert client.head("/api/v1/overview").status_code == 200
    assert client.post("/api/v1/overview").status_code == 405
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    invalid = client.get("/api/v1/overview", params={"as_of": "not-a-date"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_ARGUMENT"
    assert str(tmp_path) not in invalid.text
    assert client.get("/api/v1/signals/reconciliation").status_code == 422
    top20 = client.get(
        "/api/v1/paper/portfolio",
        params={"account_id": "model_top20"},
    )
    assert top20.status_code == 200
    assert top20.json()["data"]["account_id"] == "model_top20"
    assert top20.json()["data"]["mode"] == "BACKFILL"
    unknown_account = client.get(
        "/api/v1/paper/portfolio",
        params={"account_id": "unknown"},
    )
    assert unknown_account.status_code == 422
    assert unknown_account.json()["error"]["code"] == "INVALID_ARGUMENT"
    assert client.get("/api/v1/not-allowed").status_code == 404


def test_operations_snapshot_profiles_quality_without_overclaiming_raw_rehash(tmp_path: Path):
    _fixture(tmp_path)
    first = build_operations_snapshot(project_root=tmp_path)
    second = build_operations_snapshot(project_root=tmp_path)

    assert first.snapshot_id == second.snapshot_id
    quality = first.data_quality
    assert quality["status"] == "PASS"
    assert quality["evidence_status"] == "WARN"
    assert quality["status_reasons"] == ["SENTINEL_REPORT_NOT_HASH_BOUND"]
    assert quality["batch_chain"]["registered_batch_count"] == 2
    assert quality["batch_chain"]["incremental_batch_count"] == 2
    assert quality["batch_chain"]["raw_parquet_rehash_status"] == "NOT_EVALUATED"
    assert quality["batch_chain"]["reconstructed_data_snapshot_sha256"] == quality[
        "data_snapshot_sha256"
    ]
    assert len(quality["sentinel_gate"]["sentinels"]) == 10
    assert quality["sentinel_gate"]["binding_status"] == "IDENTITY_MATCH_UNHASHED"
    assert quality["bse_gate"]["validated_market_batch_bse_count"] == 0
    assert all("params_json" not in row for row in quality["batch_chain"]["incremental_batches"])
    assert all("parquet_path" not in row for row in quality["batch_chain"]["incremental_batches"])

    system = first.system_run
    assert system["status"] == "NOT_READY"
    assert system["release_identity"]["status"] == "PASS"
    assert system["release_identity"]["live_container_identity_status"] == "NOT_EVALUATED"
    assert system["scheduler_heartbeat"]["recorded_status"] == "noop"
    assert "pid" not in system["scheduler_heartbeat"]


def test_operations_fail_closed_on_ingest_or_sentinel_tampering(tmp_path: Path):
    _fixture(tmp_path)
    ingest_path = tmp_path / "ledger/ingest_batches.csv"
    rows = list(csv.DictReader(ingest_path.open()))
    rows[0]["content_sha256"] = "0" * 64
    _write_csv(ingest_path, INGEST_FIELDS, rows)
    with pytest.raises(WebQueryError, match="身份链") as ingest_error:
        build_operations_snapshot(project_root=tmp_path)
    assert ingest_error.value.code == "EVIDENCE_MISMATCH"

    _fixture(tmp_path)
    sentinel_path = tmp_path / "logs/sentinels/fixture.json"
    sentinel = json.loads(sentinel_path.read_text(encoding="utf-8"))
    sentinel["generated_at"] = "2026-07-24T12:01:00+00:00"
    sentinel_path.write_text(json.dumps(sentinel), encoding="utf-8")
    with pytest.raises(WebQueryError, match="时钟") as sentinel_error:
        build_operations_snapshot(project_root=tmp_path)
    assert sentinel_error.value.code == "EVIDENCE_MISMATCH"


def test_notification_contract_preserves_attempts_and_exposes_no_body(tmp_path: Path):
    _fixture(tmp_path)
    (tmp_path / "logs/notifications/feishu_20260722.jsonl").write_text(
        json.dumps(
            {
                "delivered_at": "2026-07-22T12:00:00+00:00",
                "event": "shadow_signal_completed",
                "status": "PASS",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    path = tmp_path / "logs/notifications/feishu_20260724.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    message_id = "0123456789abcdef"
    rows.extend(
        [
            {
                "attempt": 1,
                "delivered_at": "2026-07-24T12:06:00+00:00",
                "error_type": "NETWORK_TimeoutError",
                "event": "paper_cycle_completed",
                "max_attempts": 3,
                "message_id": message_id,
                "recovered": False,
                "retryable": True,
                "status": "FAIL",
            },
            {
                "attempt": 2,
                "delivered_at": "2026-07-24T12:06:01+00:00",
                "error_type": "",
                "event": "paper_cycle_completed",
                "max_attempts": 3,
                "message_id": message_id,
                "recovered": True,
                "retryable": False,
                "status": "PASS",
            },
        ]
    )
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    bundle = build_operations_snapshot(project_root=tmp_path)
    assert bundle.system_run["notifications"]["legacy_unaddressable_attempt_count"] == 1
    summary = notification_for(bundle, message_id)
    assert summary["status"] == "PASS"
    assert summary["failed_attempt_count"] == 1
    assert summary["recovered"] is True
    assert [row["attempt"] for row in summary["attempts"]] == [1, 2]
    serialized = json.dumps(summary)
    assert "webhook" not in serialized.lower()
    assert "signature" not in serialized.lower()

    rows.append(
        {
            "attempt": 1,
            "delivered_at": "2026-07-24T12:07:00+00:00",
            "error_type": "",
            "event": "paper_cycle_started",
            "max_attempts": 3,
            "message_id": "",
            "recovered": False,
            "retryable": False,
            "status": "PASS",
        }
    )
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(WebQueryError, match="缺少消息身份"):
        build_operations_snapshot(project_root=tmp_path)


def test_release_audit_chain_is_fail_closed(tmp_path: Path):
    _fixture(tmp_path)
    path = tmp_path / "logs/releases/scheduler_releases.jsonl"
    release = json.loads(path.read_text(encoding="utf-8"))
    release["details"]["read_only_rootfs"] = False
    path.write_text(json.dumps(release) + "\n", encoding="utf-8")
    with pytest.raises(WebQueryError, match="哈希不一致") as error:
        build_operations_snapshot(project_root=tmp_path)
    assert error.value.code == "EVIDENCE_MISMATCH"


def test_operations_api_and_message_id_validation(tmp_path: Path):
    _fixture(tmp_path)
    client = TestClient(create_app(tmp_path))
    quality = client.get("/api/v1/data-quality")
    system = client.get("/api/v1/system/runs")
    assert quality.status_code == 200
    assert quality.json()["data"]["status"] == "PASS"
    assert system.status_code == 200
    assert client.head("/api/v1/data-quality").status_code == 200
    assert client.post("/api/v1/system/runs").status_code == 405
    invalid = client.get("/api/v1/notifications/not-valid")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_ARGUMENT"
    missing = client.get("/api/v1/notifications/0123456789abcdef")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NO_DATA"


def test_web_compose_is_default_off_and_has_no_production_write_surface():
    root = Path(__file__).parents[1]
    compose = yaml.safe_load((root / "compose.web.yaml").read_text(encoding="utf-8"))
    assert set(compose["services"]) == {"web-query", "research-projector", "web-ui"}
    query = compose["services"]["web-query"]
    projector = compose["services"]["research-projector"]
    ui = compose["services"]["web-ui"]
    for service in (query, ui):
        assert service["profiles"] == ["web"]
        assert service["read_only"] is True
        assert service["user"] == "10001:10001"
        assert service["cap_drop"] == ["ALL"]
        assert "no-new-privileges:true" in service["security_opt"]
        assert "env_file" not in service
        assert "docker.sock" not in json.dumps(service)
    assert "ports" not in query
    assert projector["profiles"] == ["research-projection"]
    assert projector["read_only"] is True
    assert projector["restart"] == "no"
    assert projector["network_mode"] == "none"
    assert "ports" not in projector
    assert "env_file" not in projector
    assert "docker.sock" not in json.dumps(projector)
    assert all(
        value["read_only"] is True
        for value in projector["volumes"]
        if value["target"] != "/workspace/data/web/research_snapshots"
    )
    assert next(
        value for value in projector["volumes"]
        if value["target"] == "/workspace/data/web/research_snapshots"
    )["read_only"] is False
    assert next(
        value for value in projector["volumes"]
        if value["target"] == "/workspace/config/p3_experiment_catalog_v1.yaml"
    )["read_only"] is True
    assert ui["ports"] == ["127.0.0.1:8080:8080"]
    assert "volumes" not in ui
    assert set(query["networks"]) == {"web-internal"}
    assert set(ui["networks"]) == {"web-internal", "web-loopback"}
    assert compose["networks"]["web-internal"]["internal"] is True
    assert (
        compose["networks"]["web-loopback"]["driver_opts"][
            "com.docker.network.bridge.host_binding_ipv4"
        ]
        == "127.0.0.1"
    )
    targets = {value["target"] for value in query["volumes"]}
    assert targets == {
        "/workspace/ledger",
        "/workspace/data/paper",
        "/workspace/data/shadow/signals",
        "/workspace/data/shadow/reconciliations",
        "/workspace/data/web/research_snapshots",
        "/workspace/logs/notifications",
        "/workspace/logs/releases",
        "/workspace/logs/scheduler",
        "/workspace/logs/sentinels",
    }
    assert all(value["read_only"] is True for value in query["volumes"])
    assert all(value["target"] != "/workspace" for value in query["volumes"])
    dockerfile = (root / "Dockerfile.web").read_text(encoding="utf-8")
    assert "USER 10001:10001" in dockerfile
    query_source = (root / "src/shaiwei/web/query.py").read_text(encoding="utf-8")
    assert "load_dotenv" not in query_source
    assert ' / ".env"' not in query_source
    research_source = (root / "src/shaiwei/web/research_projection.py").read_text(
        encoding="utf-8"
    )
    assert "load_dotenv" not in research_source
    assert ' / ".env"' not in research_source
