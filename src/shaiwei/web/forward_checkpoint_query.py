"""Read both paper accounts and project the authoritative paired checkpoint."""

from __future__ import annotations

from typing import Any

from shaiwei.web.forward_checkpoint import (
    build_forward_checkpoint,
    load_forward_checkpoint_contract,
)
from shaiwei.web.query_evidence import (
    _EvidenceCut,
    _passed_paper_runs,
    _read_paper_document,
    _read_signal,
    _resolve_legacy_policy_versions,
    _sha256,
    WebQueryError,
)
from shaiwei.web.query_paper import _paper_replay


def paired_forward_projection(
    cut: _EvidenceCut,
    *,
    actual_as_of: str,
    paper_account_rows: list[dict[str, str]],
    paper_event_rows: list[dict[str, str]],
    paper_ledger_rows: list[dict[str, str]],
    passed_signals: list[dict[str, str]],
) -> tuple[dict[str, object], set[str], dict[str, str]]:
    contract = load_forward_checkpoint_contract(cut)
    account_ids = (contract.control.account_id, contract.comparison.account_id)
    rows: dict[str, list[dict[str, str]]] = {}
    documents: dict[str, list[dict[str, object]]] = {}
    replay_statuses: dict[str, str] = {}
    source_refs = set(contract.source_refs)
    evidence_hashes = {
        f"forward_contract_source_{index:02d}_sha256": digest
        for index, digest in enumerate(contract.source_hashes.values(), start=1)
    }
    for account_id in account_ids:
        account_rows = _passed_paper_runs(
            paper_ledger_rows,
            account_id=account_id,
            as_of=actual_as_of,
        )
        if not account_rows:
            raise WebQueryError("NO_DATA", "双账户前瞻检查点缺少模拟账户日", status_code=404)
        account_documents = [_read_paper_document(cut, row) for row in account_rows]
        _resolve_legacy_policy_versions(
            paper_account_rows,
            account_documents,
            account_id=account_id,
        )
        replay = _paper_replay(
            paper_account_rows,
            paper_event_rows,
            account_rows,
            account_documents,
            as_of=actual_as_of,
            account_id=account_id,
        )
        rows[account_id] = account_rows
        documents[account_id] = account_documents
        replay_statuses[account_id] = str(replay["status"])
        source_refs.update(row["artifact_path"] for row in account_rows)
        evidence_hashes[f"paired_{account_id}_runs_sha256"] = _sha256(account_rows)

    signal_hashes = {
        row["signal_sha256"]
        for account_rows in rows.values()
        for row in account_rows
        if contract.protocol_start <= row["execution_trade_date"] <= actual_as_of
    }
    signal_rows = {
        row["signal_sha256"]: row
        for row in passed_signals
        if row.get("signal_sha256") in signal_hashes
    }
    if set(signal_rows) != signal_hashes:
        raise WebQueryError("EVIDENCE_MISMATCH", "双账户检查点信号身份无法完整解析")
    signals: dict[str, dict[str, Any]] = {}
    for signal_sha256 in sorted(signal_hashes):
        signal_row = signal_rows[signal_sha256]
        signals[signal_sha256] = _read_signal(cut, signal_row)
        source_refs.add(signal_row["signal_manifest_path"])
        evidence_hashes[f"paired_signal_{signal_sha256[:12]}_sha256"] = cut.sources[
            signal_row["signal_manifest_path"]
        ].sha256

    checkpoint = build_forward_checkpoint(
        contract,
        rows=rows,
        documents=documents,
        signals=signals,
        replay_statuses=replay_statuses,
        as_of=actual_as_of,
    )
    return checkpoint, source_refs, evidence_hashes
