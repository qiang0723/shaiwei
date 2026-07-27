"""Public facade and atomic orchestration for registered Web query evidence."""

from __future__ import annotations

from pathlib import Path

from shaiwei.web.query_evidence import (
    DEFAULT_ACCOUNT_ID,
    FIXED_LEDGER_PATHS,
    SCHEMA_VERSION,
    SHA256_PATTERN,
    STATUS_PRECEDENCE,
    TIMEZONE,
    SnapshotBundle,
    WebQueryError,
    _EvidenceChanged,
    _EvidenceCut,
    _default_root,
    _display_date,
    _latest_by,
    _latest_timestamp,
    _normalize_as_of,
    _normalize_paper_account_id,
    _passed_paper_runs,
    _read_paper_document,
    _read_security_name_catalog,
    _read_signal,
    _resolve_legacy_policy_versions,
    _sha256,
)
from shaiwei.web.query_paper import (
    _forward_projection,
    _paper_nav,
    _paper_projection,
    _paper_replay,
)
from shaiwei.web.query_signal import (
    _notification_projection,
    _reconciliation_projection,
    _signal_projection,
)


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
    security_names, name_pointer_ref, name_bundle_ref, name_bundle_sha256 = (
        _read_security_name_catalog(cut)
    )
    paper_portfolio = _paper_projection(
        paper_rows[-1],
        paper_documents[-1],
        security_names,
        security_name_bundle_sha256=name_bundle_sha256,
    )
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
        security_names,
        security_name_bundle_sha256=name_bundle_sha256,
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
        "security_name_pointer_sha256": cut.sources[name_pointer_ref].sha256,
        "security_name_bundle_sha256": name_bundle_sha256,
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
        security_names.source_cutoff,
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
                name_pointer_ref,
                name_bundle_ref,
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
