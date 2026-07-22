"""Read-only query contracts over verified paper-account artifacts."""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ledger import (
    PAPER_ACCOUNTS,
    PAPER_EVENTS,
    PAPER_RUNS,
    resolve_artifact_path,
    sha256_file,
)
from shaiwei.paper.engine import policy_sha256
from shaiwei.pipeline.paper_cycle import _verify_paper_document


class PaperQueryError(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def _execution_policy_version(document: dict[str, object]) -> str:
    if version := str(document.get("execution_policy_version", "")).strip():
        return version
    policy = load().paper_portfolio
    if document.get("policy_sha256") != policy_sha256(policy):
        raise PaperQueryError("legacy paper artifact policy cannot be resolved from current config")
    return policy.execution_policy_version


def _common(document: dict[str, object], artifact: Path) -> dict[str, object]:
    return {
        "as_of": document["execution_trade_date"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "account_id": document["account_id"],
        "execution_policy_version": _execution_policy_version(document),
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
    policy_versions: set[str] = set()
    for row in rows:
        artifact, document = _document(row)
        policy_versions.add(_execution_policy_version(document))
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
    if len(policy_versions) != 1:
        raise PaperQueryError("paper NAV range spans multiple execution policy versions")
    forward_count = sum(row["mode"] == "FORWARD" for row in series)
    return {
        "as_of": series[-1]["trade_date"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "account_id": account_id,
        "execution_policy_version": next(iter(policy_versions)),
        "freshness_status": (
            "STALE" if any(row["freshness_status"] == "STALE" for row in series) else "PASS"
        ),
        "forward_status": "PASS" if forward_count else "NOT_READY",
        "forward_observation_count": forward_count,
        "source_refs": artifacts,
        "evidence_hashes": {row["execution_trade_date"]: row["artifact_sha256"] for row in rows},
        "series": series,
    }


def verify_paper_replay(
    account_id: str = "model_baseline",
    *,
    accounts_path: Path = PAPER_ACCOUNTS,
    events_path: Path = PAPER_EVENTS,
    runs_path: Path = PAPER_RUNS,
) -> dict[str, object]:
    """Independently replay the append-only journal and match every immutable run."""
    accounts = [row for row in _csv_rows(accounts_path) if row["account_id"] == account_id]
    if len(accounts) != 1:
        raise PaperQueryError("paper replay requires exactly one account identity")
    account = accounts[0]
    runs = _passed_runs(account_id, path=runs_path)
    if not runs:
        raise PaperQueryError("paper replay has no completed runs")
    execution_dates = [row["execution_trade_date"] for row in runs]
    if execution_dates != sorted(set(execution_dates)):
        raise PaperQueryError("paper replay execution dates are not unique and increasing")

    events = [row for row in _csv_rows(events_path) if row["account_id"] == account_id]
    event_ids = [row["event_id"] for row in events]
    if len(event_ids) != len(set(event_ids)):
        raise PaperQueryError("paper replay contains duplicate event ids")
    events_by_run: dict[str, list[dict[str, str]]] = {}
    for event in events:
        events_by_run.setdefault(event["run_id"], []).append(event)
    run_ids = {row["run_id"] for row in runs}
    if orphaned := sorted(set(events_by_run) - run_ids):
        raise PaperQueryError(f"paper replay contains events without PASS run: {orphaned}")

    previous_state: dict[str, object] | None = None
    mode_counts: dict[str, int] = {}
    total_orders = 0
    total_fills = 0
    for run in runs:
        artifact, document = _document(run)
        for field in (
            "account_id",
            "signal_trade_date",
            "execution_trade_date",
            "signal_sha256",
            "reconciliation_sha256",
            "data_snapshot_sha256",
            "code_snapshot_sha256",
            "policy_sha256",
        ):
            if str(document[field]) != run[field]:
                raise PaperQueryError(f"paper replay run/document mismatch: {field}")
        if (
            document["account_id"] != account_id
            or document["policy_sha256"] != account["policy_sha256"]
        ):
            raise PaperQueryError("paper replay account or policy identity mismatch")
        document_version = str(
            document.get("execution_policy_version", account["execution_policy_version"])
        )
        if document_version != account["execution_policy_version"]:
            raise PaperQueryError("paper replay execution policy version mismatch")
        expected_prior = hashlib.sha256(_canonical(previous_state)).hexdigest()
        if document["prior_state_sha256"] != expected_prior:
            raise PaperQueryError("paper replay prior-state chain mismatch")

        run_events = sorted(
            events_by_run.get(run["run_id"], []),
            key=lambda row: int(row["sequence"]),
        )
        sequences = [int(row["sequence"]) for row in run_events]
        if sequences != list(range(1, len(run_events) + 1)):
            raise PaperQueryError("paper replay event sequence is not contiguous")
        if len(run_events) != int(run["event_count"]):
            raise PaperQueryError("paper replay event count differs from run ledger")
        actual: dict[str, list[object]] = {}
        for event in run_events:
            try:
                payload = json.loads(event["payload_json"])
            except json.JSONDecodeError as error:
                raise PaperQueryError("paper replay event payload is invalid JSON") from error
            evidence_hash = hashlib.sha256(_canonical(payload)).hexdigest()
            if event["evidence_sha256"] != evidence_hash:
                raise PaperQueryError("paper replay event evidence hash mismatch")
            expected_event_id = hashlib.sha256(
                (
                    f"{run['run_id']}|{event['sequence']}|"
                    f"{event['event_type']}|{event['business_key']}"
                ).encode()
            ).hexdigest()[:20]
            if event["event_id"] != expected_event_id:
                raise PaperQueryError("paper replay event identity mismatch")
            if event["effective_date"] != run["execution_trade_date"]:
                raise PaperQueryError("paper replay event date mismatch")
            if event["signal_sha256"] != run["signal_sha256"]:
                raise PaperQueryError("paper replay event signal mismatch")
            actual.setdefault(event["event_type"], []).append(payload)

        result = dict(document["result"])
        nav = dict(result["nav"])
        expected = {
            "CORPORATE_ACTION": list(result["corporate_actions"]),
            "ORDER": list(result["orders"]),
            "FILL": list(result["fills"]),
            "POSITION": list(nav["positions"]),
            "CASH": [{"cash": nav["cash"]}],
            "NAV": [nav],
        }
        for event_type, payloads in expected.items():
            if actual.get(event_type, []) != payloads:
                raise PaperQueryError(f"paper replay payload mismatch: {event_type}")
        expected_types = {event_type for event_type, payloads in expected.items() if payloads}
        if set(actual) != expected_types:
            raise PaperQueryError("paper replay contains unsupported event type")
        if len(expected["ORDER"]) != int(run["order_count"]):
            raise PaperQueryError("paper replay order count differs from run ledger")
        if len(expected["FILL"]) != int(run["fill_count"]):
            raise PaperQueryError("paper replay fill count differs from run ledger")

        state = dict(document["state"])
        if state["cash"] != nav["cash"]:
            raise PaperQueryError("paper replay cash differs from state")
        state_positions = dict(state["positions"])
        nav_positions = {str(row["ts_code"]): dict(row) for row in nav["positions"]}
        if set(state_positions) != set(nav_positions):
            raise PaperQueryError("paper replay position universe differs from state")
        for code, position_value in state_positions.items():
            position = dict(position_value)
            snapshot = nav_positions[code]
            for state_field, snapshot_field in (
                ("quantity", "quantity"),
                ("cost_basis", "cost_basis"),
                ("realized_pnl", "realized_pnl"),
                ("last_price_date", "price_date"),
            ):
                if str(position[state_field]) != str(snapshot[snapshot_field]):
                    raise PaperQueryError(
                        f"paper replay position mismatch: {code}/{state_field}"
                    )
        cash = Decimal(str(nav["cash"]))
        market_value = Decimal(str(nav["market_value"]))
        net_asset = Decimal(str(nav["net_asset"]))
        if (
            net_asset != cash + market_value
            or Decimal(str(nav["equation_difference"])) != 0
        ):
            raise PaperQueryError("paper replay accounting identity failed")
        if run["net_asset"] != str(nav["net_asset"]):
            raise PaperQueryError("paper replay NAV differs from run ledger")
        if run["artifact_sha256"] != sha256_file(artifact):
            raise PaperQueryError("paper replay artifact hash changed during verification")

        mode = str(document["mode"])
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        total_orders += len(expected["ORDER"])
        total_fills += len(expected["FILL"])
        previous_state = state

    return {
        "status": "PASS",
        "account_id": account_id,
        "as_of": execution_dates[-1],
        "run_count": len(runs),
        "event_count": len(events),
        "order_count": total_orders,
        "fill_count": total_fills,
        "mode_counts": mode_counts,
        "ledger_hashes": {
            "accounts": sha256_file(accounts_path),
            "events": sha256_file(events_path),
            "runs": sha256_file(runs_path),
        },
    }


def portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", choices=("snapshot", "nav", "orders", "verify"))
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
    elif args.view == "orders":
        if not args.signal_sha256:
            parser.error("--signal-sha256 is required for orders")
        document = paper_orders_fills(args.signal_sha256, args.account_id)
    else:
        document = verify_paper_replay(args.account_id)
    print(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
