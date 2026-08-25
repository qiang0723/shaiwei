"""Idempotently materialize the model-baseline paper account after shadow reconciliation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

import pandas as pd

from shaiwei.config import (
    PaperPortfolio,
    PaperTop20Portfolio,
    Settings,
    load,
    load_paper_top20_protocol,
)
from shaiwei.ingest.catalog import latest_request_evidence, load_latest_api, load_latest_request
from shaiwei.ingest.tushare import Request, public_request_params
from shaiwei.ledger import (
    PAPER_ACCOUNTS,
    PAPER_RUNS,
    SHADOW_RECONCILIATIONS,
    SHADOW_RUNS,
    append_paper_account,
    append_paper_event,
    append_paper_run,
    ingest_snapshot_sha256,
    portable_artifact_path,
    resolve_artifact_path,
    sha256_file,
)
from shaiwei.notify.feishu import FeishuNotifier
from shaiwei.paper.engine import PortfolioState, execute_day, policy_sha256
from shaiwei.paper.projection import project_top20_signal
from shaiwei.provenance import code_snapshot_sha256
from shaiwei.shadow.manifest import verify_signal_manifest
from shaiwei.storage.interprocess_lock import logical_lock
from shaiwei.storage.lock_resources import cycle_resource


class PaperCycleError(RuntimeError):
    pass


@dataclass(frozen=True)
class PaperCycleResult:
    status: str
    account_id: str
    completed_trade_dates: tuple[str, ...]
    latest_artifact_path: str


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@contextmanager
def paper_lock(path: Path | None = None) -> Iterator[None]:
    with logical_lock(cycle_resource("paper", path)):
        yield


def _request(api_name: str, params: dict[str, object]) -> tuple[pd.DataFrame, dict[str, str | int]]:
    request = Request(api_name, params, {})
    public = public_request_params(request)
    return (
        load_latest_request(f"tushare.{api_name}", public),
        latest_request_evidence(f"tushare.{api_name}", public),
    )


def _compact_day(value: object) -> str:
    digits = "".join(character for character in str(value).strip() if character.isdigit())
    return digits[:8]


def _validate_temporal_contract(
    *,
    signal: dict[str, object],
    signal_date: str,
    execution_date: str,
    trade_cal: pd.DataFrame,
    today: str | None = None,
) -> None:
    if _compact_day(signal.get("signal_date", "")) != signal_date:
        raise PaperCycleError("signal manifest date does not match reconciliation")
    local_today = today or datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")
    if execution_date > local_today:
        raise PaperCycleError("paper execution date is in the future")
    if not {"cal_date", "is_open"}.issubset(trade_cal.columns):
        raise PaperCycleError("trade calendar is incomplete")
    open_mask = trade_cal["is_open"].astype(str).isin({"1", "1.0"})
    open_days = sorted({_compact_day(value) for value in trade_cal.loc[open_mask, "cal_date"]})
    if signal_date not in open_days:
        raise PaperCycleError("paper signal date is not an open trading day")
    following = [day for day in open_days if day > signal_date]
    if not following or following[0] != execution_date:
        raise PaperCycleError("paper execution is not the next open trading day")


def _validate_market_dates(
    *,
    daily: pd.DataFrame,
    signal_daily: pd.DataFrame,
    suspend: pd.DataFrame,
    index_daily: pd.DataFrame,
    signal_date: str,
    execution_date: str,
) -> None:
    for label, frame, expected, allow_empty in (
        ("execution daily", daily, execution_date, False),
        ("signal daily", signal_daily, signal_date, False),
        ("execution suspension", suspend, execution_date, True),
        ("benchmark daily", index_daily, execution_date, False),
    ):
        if frame.empty and allow_empty:
            continue
        if frame.empty or "trade_date" not in frame.columns:
            raise PaperCycleError(f"{label} evidence is empty or missing trade_date")
        observed = {_compact_day(value) for value in frame["trade_date"].dropna()}
        if observed != {expected}:
            raise PaperCycleError(f"{label} evidence does not match requested date")


def _latest_passes(path: Path, fields: tuple[str, ...]) -> dict[tuple[str, ...], dict[str, str]]:
    latest: dict[tuple[str, ...], dict[str, str]] = {}
    for row in sorted(_read(path), key=lambda value: value["finished_at"]):
        if row["status"] == "PASS":
            latest[tuple(row[field] for field in fields)] = row
    return latest


def _manifest_for(reconciliation: dict[str, str]) -> Path:
    matches = [
        row
        for row in _read(SHADOW_RUNS)
        if row["status"] == "PASS"
        and row["signal_trade_date"] == reconciliation["signal_trade_date"]
        and row["signal_sha256"] == reconciliation["signal_sha256"]
    ]
    if len(matches) != 1:
        raise PaperCycleError("shadow reconciliation does not resolve to exactly one signal")
    path = resolve_artifact_path(matches[0]["signal_manifest_path"])
    if verify_signal_manifest(path) != reconciliation["signal_sha256"]:
        raise PaperCycleError("shadow signal hash does not match reconciliation")
    return path


def _verify_reconciliation(row: dict[str, str]) -> Path:
    path = resolve_artifact_path(row["artifact_path"])
    if not path.is_file() or sha256_file(path) != row["artifact_sha256"]:
        raise PaperCycleError("shadow reconciliation artifact hash mismatch")
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("signal_sha256") != row["signal_sha256"]:
        raise PaperCycleError("shadow reconciliation payload is bound to another signal")
    return path


def _existing_account(policy: PaperPortfolio, policy_hash: str) -> bool:
    rows = [row for row in _read(PAPER_ACCOUNTS) if row["account_id"] == policy.account_id]
    if not rows:
        return False
    if len(rows) != 1 or rows[0]["policy_sha256"] != policy_hash:
        raise PaperCycleError("paper account identity or policy hash is inconsistent")
    return True


def _latest_state(account_id: str) -> tuple[PortfolioState | None, str]:
    passes = [
        row
        for row in _read(PAPER_RUNS)
        if row["account_id"] == account_id and row["status"] == "PASS"
    ]
    if not passes:
        return None, ""
    latest = max(passes, key=lambda row: row["execution_trade_date"])
    artifact = resolve_artifact_path(latest["artifact_path"])
    if sha256_file(artifact) != latest["artifact_sha256"]:
        raise PaperCycleError("latest paper state artifact hash mismatch")
    document = _verify_paper_document(artifact)
    return PortfolioState.from_dict(document["state"]), str(artifact)


def _verify_paper_document(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    claimed = str(document.pop("content_sha256"))
    actual = hashlib.sha256(_canonical(document)).hexdigest()
    if claimed != actual:
        raise PaperCycleError(f"paper artifact content hash mismatch: {path}")
    document["content_sha256"] = claimed
    return document


def _event_rows(
    document: dict[str, object],
    *,
    operator: str = "docker-scheduler",
) -> list[dict[str, object]]:
    run_id = str(document["run_id"])
    account_id = str(document["account_id"])
    effective = str(document["execution_trade_date"])
    signal_hash = str(document["signal_sha256"])
    recorded_at = str(document["generated_at"])
    result = dict(document["result"])
    items: list[tuple[str, str, dict[str, object]]] = []
    for action in list(result["corporate_actions"]):
        payload = dict(action)
        items.append(("CORPORATE_ACTION", str(payload["action_id"]), payload))
    fills = {str(fill["order_id"]): dict(fill) for fill in list(result["fills"])}
    for order_value in list(result["orders"]):
        order = dict(order_value)
        items.append(("ORDER", str(order["order_id"]), order))
        if str(order["order_id"]) in fills:
            fill = fills[str(order["order_id"])]
            items.append(("FILL", str(fill["fill_id"]), fill))
    nav = dict(result["nav"])
    for position_value in list(nav["positions"]):
        position = dict(position_value)
        items.append(("POSITION", f"{effective}:{position['ts_code']}", position))
    items.append(("CASH", effective, {"cash": nav["cash"]}))
    items.append(("NAV", effective, nav))
    rows: list[dict[str, object]] = []
    for sequence, (event_type, business_key, payload) in enumerate(items, start=1):
        evidence = hashlib.sha256(_canonical(payload)).hexdigest()
        event_id = hashlib.sha256(
            f"{run_id}|{sequence}|{event_type}|{business_key}".encode()
        ).hexdigest()[:20]
        rows.append(
            {
                "event_id": event_id,
                "run_id": run_id,
                "recorded_at": recorded_at,
                "account_id": account_id,
                "effective_date": effective,
                "sequence": sequence,
                "event_type": event_type,
                "business_key": business_key,
                "signal_sha256": signal_hash,
                "ts_code": str(payload.get("ts_code", "")),
                "side": str(payload.get("side", "")),
                "quantity": payload.get("quantity", payload.get("filled_quantity", "")),
                "price": payload.get("price", ""),
                "amount": payload.get("notional", payload.get("amount", "")),
                "fee": payload.get("total_fee", ""),
                "cash_after": payload.get("cash_after", payload.get("cash", "")),
                "position_after": payload.get("position_after", payload.get("quantity", "")),
                "payload_json": payload,
                "evidence_sha256": evidence,
                "operator": operator,
            }
        )
    return rows


def _write_artifact(path: Path, payload: dict[str, object]) -> dict[str, object]:
    if path.is_file():
        existing = _verify_paper_document(path)
        for key in (
            "account_id",
            "run_id",
            "signal_sha256",
            "execution_trade_date",
            "policy_sha256",
            "prior_state_sha256",
        ):
            if existing.get(key) != payload.get(key):
                raise PaperCycleError(f"existing paper artifact differs on {key}")
        return existing
    content_hash = hashlib.sha256(_canonical(payload)).hexdigest()
    document = {**payload, "content_sha256": content_hash}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return document


def _journal(
    document: dict[str, object],
    artifact: Path,
    reconciliation_hash: str,
    *,
    operator: str = "docker-scheduler",
) -> None:
    events = _event_rows(document, operator=operator)
    for event in events:
        append_paper_event(**event)
    nav = dict(dict(document["result"])["nav"])
    append_paper_run(
        run_id=document["run_id"],
        started_at=document["started_at"],
        finished_at=document["generated_at"],
        account_id=document["account_id"],
        signal_trade_date=document["signal_trade_date"],
        execution_trade_date=document["execution_trade_date"],
        status="PASS",
        signal_sha256=document["signal_sha256"],
        reconciliation_sha256=reconciliation_hash,
        data_snapshot_sha256=document["data_snapshot_sha256"],
        code_snapshot_sha256=document["code_snapshot_sha256"],
        policy_sha256=document["policy_sha256"],
        artifact_path=portable_artifact_path(artifact),
        artifact_sha256=sha256_file(artifact),
        event_count=len(events),
        order_count=len(list(dict(document["result"])["orders"])),
        fill_count=len(list(dict(document["result"])["fills"])),
        net_asset=nav["net_asset"],
        normalized_nav=nav["normalized_nav"],
        benchmark_nav=nav["benchmark_nav"],
        freshness_status=nav["freshness_status"],
        error_type="",
        operator=operator,
    )


def _append_failure(
    *,
    policy: PaperPortfolio,
    reconciliation: dict[str, str],
    policy_hash: str,
    code_hash: str,
    started_at: str,
    error: Exception,
    operator: str,
) -> None:
    try:
        data_hash = ingest_snapshot_sha256()
    except Exception:
        data_hash = ""
    append_paper_run(
        run_id=f"fail-{uuid.uuid4().hex[:15]}",
        started_at=started_at,
        account_id=policy.account_id,
        signal_trade_date=reconciliation["signal_trade_date"],
        execution_trade_date=reconciliation["execution_trade_date"],
        status="FAIL",
        signal_sha256=reconciliation["signal_sha256"],
        reconciliation_sha256=reconciliation["artifact_sha256"],
        data_snapshot_sha256=data_hash,
        code_snapshot_sha256=code_hash,
        policy_sha256=policy_hash,
        artifact_path="",
        artifact_sha256="",
        event_count=0,
        order_count=0,
        fill_count=0,
        net_asset="",
        normalized_nav="",
        benchmark_nav="",
        freshness_status="FAIL",
        error_type=type(error).__name__,
        operator=operator,
    )


def _notification_contract(policy: PaperPortfolio) -> tuple[str, str, str, str]:
    if isinstance(policy, PaperTop20Portfolio):
        return (
            "paper_top20_cycle_started",
            "Top20模拟组合处理开始",
            "paper_top20_cycle_completed",
            "Top20模拟组合处理完成",
        )
    return (
        "paper_cycle_started",
        "模拟组合处理开始",
        "paper_cycle_completed",
        "模拟组合处理完成",
    )


def run_once(
    settings: Settings | None = None,
    *,
    policy: PaperPortfolio | None = None,
    operator: str = "docker-scheduler",
) -> PaperCycleResult:
    settings = settings or load()
    policy = policy or settings.paper_portfolio
    if not policy.enabled:
        return PaperCycleResult("DISABLED", policy.account_id, (), "")
    if operator not in {"docker-scheduler", "docker-top20-backfill"}:
        raise PaperCycleError("paper cycle operator is not authorized")
    if operator == "docker-top20-backfill" and not isinstance(policy, PaperTop20Portfolio):
        raise PaperCycleError("Top20 backfill operator cannot run the baseline account")
    notifier = FeishuNotifier(settings.notifications)
    started_event, started_title, completed_event, completed_title = _notification_contract(policy)
    with paper_lock():
        reconciliations = sorted(
            _latest_passes(
                SHADOW_RECONCILIATIONS,
                ("signal_trade_date", "execution_trade_date"),
            ).values(),
            key=lambda row: row["execution_trade_date"],
        )
        completed_keys = {
            (row["signal_sha256"], row["execution_trade_date"])
            for row in _read(PAPER_RUNS)
            if row["account_id"] == policy.account_id and row["status"] == "PASS"
        }
        pending = [
            row
            for row in reconciliations
            if (row["signal_sha256"], row["execution_trade_date"]) not in completed_keys
        ]
        state, latest_artifact = _latest_state(policy.account_id)
        if not pending:
            return PaperCycleResult("NOOP", policy.account_id, (), latest_artifact)
        policy_hash = policy_sha256(policy)
        code_hash = code_snapshot_sha256()
        notifier.send(
            started_event,
            started_title,
            {
                "account_id": policy.account_id,
                "pending_trade_days": len(pending),
                "first_execution_date": pending[0]["execution_trade_date"],
                "last_execution_date": pending[-1]["execution_trade_date"],
            },
        )
        completed: list[str] = []
        reconciliation = pending[0]
        started_at = datetime.now(timezone.utc).isoformat()
        try:
            data_hash = ingest_snapshot_sha256()
            stock_basic = load_latest_api("tushare.stock_basic")
            namechange = load_latest_api("tushare.namechange")
            dividends = load_latest_api("tushare.dividend")
            trade_cal = load_latest_api("tushare.trade_cal")
            for reconciliation in pending:
                started_at = datetime.now(timezone.utc).isoformat()
                signal_path = _manifest_for(reconciliation)
                reconciliation_path = _verify_reconciliation(reconciliation)
                signal = json.loads(signal_path.read_text(encoding="utf-8"))
                projection_evidence: dict[str, object] | None = None
                if isinstance(policy, PaperTop20Portfolio):
                    projection = project_top20_signal(
                        signal,
                        source_signal_sha256=reconciliation["signal_sha256"],
                        policy=policy,
                    )
                    signal = projection.signal
                    projection_evidence = projection.evidence
                signal_date = reconciliation["signal_trade_date"]
                execution_date = reconciliation["execution_trade_date"]
                _validate_temporal_contract(
                    signal=signal,
                    signal_date=signal_date,
                    execution_date=execution_date,
                    trade_cal=trade_cal,
                )
                daily, daily_evidence = _request("daily", {"trade_date": execution_date})
                signal_daily, signal_evidence = _request("daily", {"trade_date": signal_date})
                suspend, suspend_evidence = _request("suspend_d", {"trade_date": execution_date})
                index_daily, index_evidence = _request(
                    "index_daily",
                    {"ts_code": policy.benchmark, "trade_date": execution_date},
                )
                _validate_market_dates(
                    daily=daily,
                    signal_daily=signal_daily,
                    suspend=suspend,
                    index_daily=index_daily,
                    signal_date=signal_date,
                    execution_date=execution_date,
                )
                if len(index_daily) != 1:
                    raise PaperCycleError("paper benchmark request must contain exactly one row")
                run_key = (
                    f"{policy.account_id}|{reconciliation['signal_sha256']}|"
                    f"{execution_date}|{policy_hash}"
                )
                run_id = hashlib.sha256(run_key.encode()).hexdigest()[:20]
                prior_state_hash = hashlib.sha256(
                    _canonical(None if state is None else state.to_dict())
                ).hexdigest()
                artifact = (
                    settings.runtime.data_root
                    / "paper"
                    / policy.account_id
                    / "runs"
                    / f"{execution_date}-{reconciliation['signal_sha256'][:12]}.json"
                )
                if artifact.is_file():
                    document = _verify_paper_document(artifact)
                    if document.get("prior_state_sha256") != prior_state_hash:
                        raise PaperCycleError("existing paper artifact is not continuous with prior state")
                    if document.get("signal_projection") != projection_evidence:
                        raise PaperCycleError("existing paper artifact projection evidence differs")
                else:
                    result = execute_day(
                        policy=policy,
                        state=state,
                        signal=signal,
                        signal_sha256=reconciliation["signal_sha256"],
                        execution_date=execution_date,
                        daily=daily,
                        signal_daily=signal_daily,
                        index_row=index_daily.iloc[0],
                        stock_basic=stock_basic,
                        namechange=namechange,
                        suspend=suspend,
                        trade_cal=trade_cal,
                        dividends=dividends,
                        run_id=run_id,
                        market_batch_id=str(daily_evidence["batch_id"]),
                    )
                    generated_at = datetime.now(timezone.utc).isoformat()
                    payload = {
                        "schema_version": 1,
                        "account_id": policy.account_id,
                        "run_id": run_id,
                        "started_at": started_at,
                        "generated_at": generated_at,
                        "mode": (
                            "FORWARD"
                            if execution_date >= policy.forward_start_date.strftime("%Y%m%d")
                            else "BACKFILL"
                        ),
                        "signal_trade_date": signal_date,
                        "execution_trade_date": execution_date,
                        "signal_sha256": reconciliation["signal_sha256"],
                        "reconciliation_sha256": reconciliation["artifact_sha256"],
                        "execution_policy_version": policy.execution_policy_version,
                        "policy_sha256": policy_hash,
                        "code_snapshot_sha256": code_hash,
                        "data_snapshot_sha256": data_hash,
                        "prior_state_sha256": prior_state_hash,
                        "state": result.state.to_dict(),
                        "result": {
                            "orders": list(result.orders),
                            "fills": list(result.fills),
                            "corporate_actions": list(result.corporate_actions),
                            "nav": result.nav,
                        },
                        "source_refs": [
                            daily_evidence,
                            signal_evidence,
                            suspend_evidence,
                            index_evidence,
                            {
                                "source_api": "shadow.reconciliation",
                                "path": portable_artifact_path(reconciliation_path),
                                "content_sha256": reconciliation["artifact_sha256"],
                            },
                        ],
                    }
                    if projection_evidence is not None:
                        payload["signal_projection"] = projection_evidence
                    document = _write_artifact(artifact, payload)
                if not _existing_account(policy, policy_hash):
                    append_paper_account(
                        account_id=policy.account_id,
                        created_at=str(document["generated_at"]),
                        status="ACTIVE",
                        initial_cash=f"{policy.initial_cash:.2f}",
                        currency=policy.currency,
                        benchmark=policy.benchmark,
                        execution_policy_version=policy.execution_policy_version,
                        policy_sha256=policy_hash,
                        code_snapshot_sha256=code_hash,
                        operator=operator,
                    )
                _journal(
                    document,
                    artifact,
                    reconciliation["artifact_sha256"],
                    operator=operator,
                )
                state = PortfolioState.from_dict(dict(document["state"]))
                latest_artifact = str(artifact)
                completed.append(execution_date)
        except Exception as error:
            _append_failure(
                policy=policy,
                reconciliation=reconciliation,
                policy_hash=policy_hash,
                code_hash=code_hash,
                started_at=started_at,
                error=error,
                operator=operator,
            )
            notifier.send(
                f"{started_event.removesuffix('_started')}_failed",
                "Top20模拟组合处理失败"
                if isinstance(policy, PaperTop20Portfolio)
                else "模拟组合处理失败",
                {
                    "account_id": policy.account_id,
                    "execution_date": reconciliation["execution_trade_date"],
                    "error_type": type(error).__name__,
                },
            )
            raise
        notifier.send(
            completed_event,
            completed_title,
            {
                "account_id": policy.account_id,
                "completed_trade_days": len(completed),
                "latest_execution_date": completed[-1],
                "mode": (
                    "FORWARD"
                    if completed[-1] >= policy.forward_start_date.strftime("%Y%m%d")
                    else "BACKFILL"
                ),
            },
        )
        return PaperCycleResult("PASS", policy.account_id, tuple(completed), latest_artifact)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--account-id",
        choices=("model_baseline", "model_top20"),
        default="model_baseline",
    )
    parser.add_argument(
        "--operator",
        choices=("docker-scheduler", "docker-top20-backfill"),
        default="docker-scheduler",
    )
    args = parser.parse_args(argv)
    try:
        policy: PaperPortfolio | None = None
        if args.account_id == "model_top20":
            policy = load_paper_top20_protocol().paper_portfolio
        result = run_once(policy=policy, operator=args.operator)
        print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as error:
        print(
            json.dumps(
                {"status": "FAIL", "error_type": type(error).__name__},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
