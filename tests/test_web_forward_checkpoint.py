from __future__ import annotations

from datetime import datetime, timedelta
from shaiwei.web.forward_checkpoint import (
    AccountIdentity,
    ForwardCheckpointContract,
    account_evidence_stratum,
    build_forward_checkpoint,
)


def _timestamp(date: str, *, catchup: bool) -> str:
    value = datetime.strptime(date, "%Y%m%d") + (timedelta(days=1) if catchup else timedelta(hours=16))
    return value.isoformat() + "+08:00"


def _document(account: AccountIdentity, date: str, *, catchup: bool) -> dict[str, object]:
    return {
        "mode": "FORWARD",
        "started_at": _timestamp(date, catchup=catchup),
        "execution_policy_version": account.policy_version,
        "result": {
            "nav": {
                "cash": "100",
                "market_value": "900",
                "net_asset": "1000",
                "normalized_nav": "1",
                "benchmark_nav": "1",
                "daily_fees": "0",
                "cash_ratio": "0.1",
                "turnover": "0",
                "freshness_status": "PASS",
                "positions": [{"ts_code": "600001.SH", "market_value": "900"}],
            }
        },
    }


def _contract() -> ForwardCheckpointContract:
    control = AccountIdentity("model_baseline", "paper-v1", "a" * 64)
    comparison = AccountIdentity("model_top20", "paper-top20-v1", "b" * 64)
    return ForwardCheckpointContract(
        control=control,
        comparison=comparison,
        protocol_start="20260727",
        live_start="20260803",
        anchor_date="20260731",
        anchor_runs={control.account_id: "anchor-30", comparison.account_id: "anchor-20"},
        anchor_artifacts={control.account_id: "c" * 64, comparison.account_id: "d" * 64},
        minimum_days=20,
        minimum_rebalances=2,
        first_rebalance_date="20260814",
        first_due_date="20260828",
        open_dates=("20260803", "20260804", "20260805", "20260806", "20260807"),
        calendar_end="20260807",
        source_refs=("config/contract.yaml",),
        source_hashes={"config/contract.yaml": "e" * 64},
    )


def _evidence():
    contract = _contract()
    dates = ["20260727", "20260728", "20260729", "20260730", "20260731", *contract.open_dates]
    rows: dict[str, list[dict[str, str]]] = {}
    documents: dict[str, list[dict[str, object]]] = {}
    signals: dict[str, dict[str, object]] = {}
    for account in (contract.control, contract.comparison):
        account_rows = []
        account_documents = []
        for index, date in enumerate(dates):
            signal = f"{index + 1:064x}"
            row = {
                "run_id": contract.anchor_runs[account.account_id] if date == contract.anchor_date else f"{account.account_id}-{date}",
                "started_at": _timestamp(date, catchup=account.account_id == "model_top20" and date < contract.live_start),
                "execution_trade_date": date,
                "signal_trade_date": date,
                "signal_sha256": signal,
                "reconciliation_sha256": "f" * 64,
                "data_snapshot_sha256": "1" * 64,
                "code_snapshot_sha256": "2" * 64,
                "policy_sha256": account.policy_sha256,
                "artifact_sha256": contract.anchor_artifacts[account.account_id] if date == contract.anchor_date else "3" * 64,
                "operator": "docker-scheduler",
                "order_count": "0",
                "fill_count": "0",
            }
            account_rows.append(row)
            account_documents.append(_document(account, date, catchup=account.account_id == "model_top20" and date < contract.live_start))
            signals[signal] = {"rebalance_due": date == "20260727"}
        rows[account.account_id] = account_rows
        documents[account.account_id] = account_documents
    return contract, rows, documents, signals


def test_checkpoint_separates_controlled_catchup_from_live_dual() -> None:
    contract, rows, documents, signals = _evidence()
    result = build_forward_checkpoint(
        contract,
        rows=rows,
        documents=documents,
        signals=signals,
        replay_statuses={"model_baseline": "PASS", "model_top20": "PASS"},
        as_of="20260807",
    )
    assert result["status"] == "NOT_DUE"
    assert result["protocol_forward_count"] == 10
    assert result["controlled_catchup_count"] == 5
    assert result["live_dual_count"] == 5
    assert result["protocol_forward_rebalance_count"] == 1
    assert result["controlled_catchup_rebalance_count"] == 1
    assert result["live_dual_rebalance_count"] == 0
    assert result["coverage_status"] == "PASS"
    assert len(result["series"]) == 5


def test_checkpoint_fails_closed_when_an_open_day_is_missing() -> None:
    contract, rows, documents, signals = _evidence()
    rows["model_top20"].pop()
    documents["model_top20"].pop()
    result = build_forward_checkpoint(
        contract,
        rows=rows,
        documents=documents,
        signals=signals,
        replay_statuses={"model_baseline": "PASS", "model_top20": "PASS"},
        as_of="20260807",
    )
    assert result["status"] == "BLOCKED_EVIDENCE"
    assert result["coverage_status"] == "BLOCKED_EVIDENCE"
    assert result["missing_open_dates"] == ["2026-08-07"]


def test_evidence_stratum_uses_execution_date_not_mode_label_alone() -> None:
    document = {"mode": "FORWARD"}
    row = {
        "execution_trade_date": "20260803",
        "started_at": "2026-08-04T10:00:00+08:00",
    }
    assert account_evidence_stratum(row, document) == "CONTROLLED_CATCHUP_FORWARD"
