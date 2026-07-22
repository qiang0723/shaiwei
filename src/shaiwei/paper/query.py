"""Read-only query contracts over verified paper-account artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ledger import PAPER_RUNS, resolve_artifact_path, sha256_file
from shaiwei.pipeline.paper_cycle import _verify_paper_document


class PaperQueryError(RuntimeError):
    pass


def _passed_runs(account_id: str, *, path: Path = PAPER_RUNS) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if row["account_id"] == account_id and row["status"] == "PASS"
        ]
    latest: dict[tuple[str, str], dict[str, str]] = {}
    for row in sorted(rows, key=lambda value: value["finished_at"]):
        latest[(row["signal_sha256"], row["execution_trade_date"])] = row
    return sorted(latest.values(), key=lambda row: row["execution_trade_date"])


def _document(row: dict[str, str]) -> tuple[Path, dict[str, object]]:
    path = resolve_artifact_path(row["artifact_path"])
    if not path.is_file() or sha256_file(path) != row["artifact_sha256"]:
        raise PaperQueryError("paper run artifact hash mismatch")
    return path, _verify_paper_document(path)


def _common(document: dict[str, object], artifact: Path) -> dict[str, object]:
    return {
        "as_of": document["execution_trade_date"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "account_id": document["account_id"],
        "execution_policy_version": load().paper_portfolio.execution_policy_version,
        "source_refs": document["source_refs"],
        "evidence_hashes": {
            "artifact_sha256": sha256_file(artifact),
            "content_sha256": document["content_sha256"],
            "signal_sha256": document["signal_sha256"],
            "reconciliation_sha256": document["reconciliation_sha256"],
            "policy_sha256": document["policy_sha256"],
            "code_snapshot_sha256": document["code_snapshot_sha256"],
            "data_snapshot_sha256": document["data_snapshot_sha256"],
        },
    }


def paper_portfolio_snapshot(
    account_id: str = "model_baseline",
    as_of: str | None = None,
    *,
    runs_path: Path = PAPER_RUNS,
) -> dict[str, object]:
    candidates = _passed_runs(account_id, path=runs_path)
    if as_of is not None:
        candidates = [row for row in candidates if row["execution_trade_date"] <= as_of]
    if not candidates:
        raise PaperQueryError("paper portfolio has no completed snapshot")
    artifact, document = _document(candidates[-1])
    nav = dict(dict(document["result"])["nav"])
    return {
        **_common(document, artifact),
        "freshness_status": nav["freshness_status"],
        "mode": document["mode"],
        "cash": nav["cash"],
        "market_value": nav["market_value"],
        "net_asset": nav["net_asset"],
        "normalized_nav": nav["normalized_nav"],
        "benchmark_nav": nav["benchmark_nav"],
        "net_excess": nav["net_excess"],
        "drawdown": nav["drawdown"],
        "cumulative_fees": nav["cumulative_fees"],
        "cumulative_dividends": nav["cumulative_dividends"],
        "positions": nav["positions"],
    }


def paper_orders_fills(
    signal_sha256: str,
    account_id: str = "model_baseline",
    *,
    runs_path: Path = PAPER_RUNS,
) -> dict[str, object]:
    matches = [row for row in _passed_runs(account_id, path=runs_path) if row["signal_sha256"] == signal_sha256]
    if len(matches) != 1:
        raise PaperQueryError("signal must resolve to exactly one completed paper run")
    artifact, document = _document(matches[0])
    result = dict(document["result"])
    nav = dict(result["nav"])
    return {
        **_common(document, artifact),
        "freshness_status": nav["freshness_status"],
        "mode": document["mode"],
        "orders": result["orders"],
        "fills": result["fills"],
        "corporate_actions": result["corporate_actions"],
    }


def paper_nav_series(
    account_id: str = "model_baseline",
    start: str | None = None,
    end: str | None = None,
    *,
    runs_path: Path = PAPER_RUNS,
) -> dict[str, object]:
    rows = _passed_runs(account_id, path=runs_path)
    if start is not None:
        rows = [row for row in rows if row["execution_trade_date"] >= start]
    if end is not None:
        rows = [row for row in rows if row["execution_trade_date"] <= end]
    if not rows:
        raise PaperQueryError("paper portfolio has no NAV observations in range")
    series: list[dict[str, object]] = []
    artifacts: list[str] = []
    for row in rows:
        artifact, document = _document(row)
        nav = dict(dict(document["result"])["nav"])
        series.append(
            {
                "trade_date": document["execution_trade_date"],
                "mode": document["mode"],
                "normalized_nav": nav["normalized_nav"],
                "benchmark_nav": nav["benchmark_nav"],
                "net_excess": nav["net_excess"],
                "drawdown": nav["drawdown"],
                "turnover": nav["turnover"],
                "cash_ratio": nav["cash_ratio"],
                "daily_fees": nav["daily_fees"],
                "freshness_status": nav["freshness_status"],
            }
        )
        artifacts.append(portable_path(artifact))
    forward_count = sum(row["mode"] == "FORWARD" for row in series)
    return {
        "as_of": series[-1]["trade_date"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "account_id": account_id,
        "execution_policy_version": load().paper_portfolio.execution_policy_version,
        "freshness_status": (
            "STALE" if any(row["freshness_status"] == "STALE" for row in series) else "PASS"
        ),
        "forward_status": "PASS" if forward_count else "NOT_READY",
        "forward_observation_count": forward_count,
        "source_refs": artifacts,
        "evidence_hashes": {row["execution_trade_date"]: row["artifact_sha256"] for row in rows},
        "series": series,
    }


def portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", choices=("snapshot", "nav", "orders"))
    parser.add_argument("--account-id", default="model_baseline")
    parser.add_argument("--as-of")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--signal-sha256")
    args = parser.parse_args(argv)
    if args.view == "snapshot":
        document = paper_portfolio_snapshot(args.account_id, args.as_of)
    elif args.view == "nav":
        document = paper_nav_series(args.account_id, args.start, args.end)
    else:
        if not args.signal_sha256:
            parser.error("--signal-sha256 is required for orders")
        document = paper_orders_fills(args.signal_sha256, args.account_id)
    print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
