import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
import yaml

from shaiwei.web.api import create_app
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
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    position_state = {
        "quantity": 100,
        "cost_basis": "1000.00",
        "realized_pnl": "0.00",
        "last_close": close,
        "last_price_date": execution_date,
    }
    state = {
        "account_id": "model_baseline",
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
        "account_id": "model_baseline",
        "signal_trade_date": signal_date,
        "execution_trade_date": execution_date,
        "mode": mode,
        "signal_sha256": signal_hash,
        "reconciliation_sha256": "3" * 64,
        "data_snapshot_sha256": "4" * 64,
        "code_snapshot_sha256": "5" * 64,
        "policy_sha256": "a" * 64,
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
        payload["execution_policy_version"] = "paper-v1"
    document = {**payload, "content_sha256": _hash(payload)}
    relative = f"data/paper/model_baseline/runs/{execution_date}-{signal_hash[:12]}.json"
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
        "account_id": "model_baseline",
        "signal_trade_date": signal_date,
        "execution_trade_date": execution_date,
        "status": "PASS",
        "signal_sha256": signal_hash,
        "reconciliation_sha256": "3" * 64,
        "data_snapshot_sha256": "4" * 64,
        "code_snapshot_sha256": "5" * 64,
        "policy_sha256": "a" * 64,
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
        "operator": "docker-scheduler",
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
                "account_id": "model_baseline",
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
                "operator": "docker-scheduler",
            }
        )
    return run, state, events


def _fixture(root: Path) -> str:
    for relative in (
        "data/shadow/signals",
        "data/shadow/reconciliations",
        "data/paper",
        "logs/notifications",
        "ledger",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)
    signal_payload = {
        "schema_version": 2,
        "signal_date": "2026-07-24",
        "data_complete_at": "2026-07-24T11:30:00+00:00",
        "generated_at": "2026-07-24T12:00:00+00:00",
        "data_snapshot_sha256": "6" * 64,
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
                "data_snapshot_sha256": "6" * 64,
                "code_snapshot_sha256": "7" * 64,
                "qlib_artifact_sha256": "8" * 64,
                "model_spec_sha256": "9" * 64,
                "model_artifact_sha256": "b" * 64,
                "sentinel_report_path": "redacted",
                "signal_manifest_path": signal_relative,
                "signal_sha256": signal_hash,
                "rebalance_due": "false",
                "on_time": "true",
                "operator": "docker-scheduler",
            }
        ],
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
            }
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
    _write_csv(
        root / "ledger/paper_runs.csv",
        PAPER_RUN_FIELDS,
        [backfill, forward],
    )
    _write_csv(
        root / "ledger/paper_events.csv",
        EVENT_FIELDS,
        [*backfill_events, *forward_events],
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
    assert client.get("/api/v1/not-allowed").status_code == 404


def test_web_compose_is_default_off_and_has_no_production_write_surface():
    root = Path(__file__).parents[1]
    compose = yaml.safe_load((root / "compose.web.yaml").read_text(encoding="utf-8"))
    assert set(compose["services"]) == {"web-query", "web-ui"}
    query = compose["services"]["web-query"]
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
        "/workspace/logs/notifications",
    }
    assert all(value["read_only"] is True for value in query["volumes"])
    assert all(value["target"] != "/workspace" for value in query["volumes"])
    dockerfile = (root / "Dockerfile.web").read_text(encoding="utf-8")
    assert "USER 10001:10001" in dockerfile
    query_source = (root / "src/shaiwei/web/query.py").read_text(encoding="utf-8")
    assert "load_dotenv" not in query_source
    assert ' / ".env"' not in query_source
