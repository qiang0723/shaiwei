"""R2-1R1 read-only CLI: `progress` prints counts only; `report` writes the single descriptive report after the user's go-ahead."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from shaiwei.research.r2_1r1.contract import REPORT_ROOT, Contract, R21R1Error
from shaiwei.research.r2_1r1.evidence import classify_history, load_account_days, next_official_open_day
from shaiwei.research.r2_1r1.report import build_report, generated_at, write_once
from shaiwei.research.r2_1r1.segment import build_segments, latched_segment, progress


def _latest_execution_date() -> str:
    from shaiwei.paper.query import _passed_runs

    contract = Contract.load()
    dates = [max(row["execution_trade_date"] for row in _passed_runs(account.account_id)) for account in contract.accounts]
    return min(dates)


def run_progress(as_of: str, *, contract: Contract | None = None, history: Callable[..., Any] = classify_history,
                 next_open: Callable[[str], str | None] = next_official_open_day) -> dict[str, Any]:
    contract = contract or Contract.load()
    try:
        days = history(contract, as_of=as_of)
    except R21R1Error as exc:
        return {"schema_version": "r2-1r1-progress-v1", "protocol_sha256": contract.sha256, "as_of": as_of,
                "terminal_state": "BLOCKED_EVIDENCE", "blocked_reason": str(exc), "contains_nav_or_return": False}
    return progress(days, contract, as_of=as_of, next_open=next_open(as_of))


def run_report(as_of: str, *, user_go_ahead: bool, root: Path = REPORT_ROOT) -> dict[str, Any]:
    if not user_go_ahead:
        raise R21R1Error("R2-1R1 descriptive report requires the user's explicit go-ahead")
    from shaiwei.paper.query import _document

    contract = Contract.load()
    segment = latched_segment(build_segments(classify_history(contract, as_of=as_of), contract))
    if segment is None:
        raise R21R1Error("R2-1R1 checkpoint has not latched; no NAV or return may be reported")
    account_days = load_account_days(contract, start=contract.history_start, end=as_of)
    documents = {
        role: {day: _document(rows[0].row)[1] for day, rows in by_date.items() if len(rows) == 1}
        for role, by_date in account_days.items()
    }
    report = build_report(contract, segment, account_days, documents)
    report["as_of"] = as_of
    report["generated_at"] = generated_at()
    digest = write_once(root / contract.document["protocol_id"] / "report.json", report)
    return {"status": "REPORT_WRITTEN", "latch_day": segment.latch_day, "report_sha256": digest}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("progress").add_argument("--as-of", default="")
    report = commands.add_parser("report")
    report.add_argument("--as-of", required=True)
    report.add_argument("--user-go-ahead", action="store_true")
    args = parser.parse_args(argv)
    as_of = args.as_of or _latest_execution_date()
    if args.command == "progress":
        result = run_progress(as_of)
    else:
        result = run_report(as_of, user_go_ahead=args.user_go_ahead)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
