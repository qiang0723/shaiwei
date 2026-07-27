"""Signal, reconciliation, and notification projections for Web queries."""

from __future__ import annotations

from decimal import Decimal

from shaiwei.web.query_evidence import (
    SecurityNameCatalog,
    _EvidenceCut,
    _decimal_text,
    _display_date,
    _instrument_to_tushare,
    _money,
    _parse_timestamp,
    _read_reconciliation,
)
from shaiwei.web.query_paper import _paper_projection


def _signal_projection(
    signal_row: dict[str, str],
    signal: dict[str, object],
    previous: dict[str, object] | None,
    paper_rows: list[dict[str, str]],
    paper_documents: list[dict[str, object]],
    security_names: SecurityNameCatalog,
    *,
    security_name_bundle_sha256: str,
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
            security_names,
            security_name_bundle_sha256=security_name_bundle_sha256,
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
