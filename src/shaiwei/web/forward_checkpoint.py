"""Authoritative R2-1 Web projection for paired natural paper-account evidence."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
from zoneinfo import ZoneInfo

import yaml

from shaiwei.web.query_evidence import (
    SHA256_PATTERN,
    _EvidenceCut,
    _decimal_text,
    _display_date,
    _money,
    _parse_timestamp,
    WebQueryError,
)


CONTRACT_PATH = "config/web_forward_checkpoint_v1.yaml"
TIMEZONE = ZoneInfo("Asia/Shanghai")
PAIR_FIELDS = (
    "signal_trade_date",
    "execution_trade_date",
    "signal_sha256",
    "reconciliation_sha256",
    "data_snapshot_sha256",
    "code_snapshot_sha256",
)


@dataclass(frozen=True)
class AccountIdentity:
    account_id: str
    policy_version: str
    policy_sha256: str


@dataclass(frozen=True)
class ForwardCheckpointContract:
    control: AccountIdentity
    comparison: AccountIdentity
    protocol_start: str
    live_start: str
    anchor_date: str
    anchor_runs: dict[str, str]
    anchor_artifacts: dict[str, str]
    minimum_days: int
    minimum_rebalances: int
    first_rebalance_date: str
    first_due_date: str
    open_dates: tuple[str, ...]
    calendar_end: str
    source_refs: tuple[str, ...]
    source_hashes: dict[str, str]


def _read_hashed_source(cut: _EvidenceCut, path: str, expected: str) -> bytes:
    if not SHA256_PATTERN.fullmatch(expected):
        raise WebQueryError("EVIDENCE_MISMATCH", "前瞻检查点来源哈希无效")
    prefix = "config/" if path.startswith("config/") else "docs/"
    payload = cut._read(path, prefixes=(prefix,))
    if hashlib.sha256(payload).hexdigest() != expected:
        raise WebQueryError("EVIDENCE_MISMATCH", "前瞻检查点权威来源哈希漂移")
    return payload


def _identity(value: object, label: str) -> AccountIdentity:
    if not isinstance(value, dict):
        raise WebQueryError("EVIDENCE_MISMATCH", f"{label}账户合同无效")
    identity = AccountIdentity(
        account_id=str(value.get("account_id", "")),
        policy_version=str(value.get("execution_policy_version", "")),
        policy_sha256=str(value.get("policy_sha256", "")),
    )
    if (
        not identity.account_id
        or not identity.policy_version
        or not SHA256_PATTERN.fullmatch(identity.policy_sha256)
    ):
        raise WebQueryError("EVIDENCE_MISMATCH", f"{label}账户身份无效")
    return identity


def load_forward_checkpoint_contract(cut: _EvidenceCut) -> ForwardCheckpointContract:
    payload = cut._read(CONTRACT_PATH, prefixes=("config/",))
    try:
        document = yaml.safe_load(payload)
    except yaml.YAMLError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "前瞻检查点合同格式无效") from error
    if not isinstance(document, dict) or document.get("schema_version") != "web-forward-checkpoint-contract-v1":
        raise WebQueryError("EVIDENCE_MISMATCH", "前瞻检查点合同版本无效")
    sources = [dict(document.get("base_protocol", {})), *list(document.get("evidence", []))]
    source_hashes: dict[str, str] = {
        CONTRACT_PATH: hashlib.sha256(payload).hexdigest(),
    }
    source_refs = [CONTRACT_PATH]
    for source in sources:
        path = str(source.get("path", ""))
        digest = str(source.get("sha256", ""))
        if not path.startswith(("config/", "docs/")) or path in source_refs:
            raise WebQueryError("EVIDENCE_MISMATCH", "前瞻检查点来源路径无效")
        _read_hashed_source(cut, path, digest)
        source_refs.append(path)
        source_hashes[path] = digest
    accounts = dict(document.get("accounts", {}))
    control = _identity(accounts.get("control"), "主")
    comparison = _identity(accounts.get("comparison"), "比较")
    if (control.account_id, comparison.account_id) != ("model_baseline", "model_top20"):
        raise WebQueryError("EVIDENCE_MISMATCH", "前瞻检查点账户集合漂移")
    anchor = dict(document.get("anchor", {}))
    minimums = dict(document.get("minimums", {}))
    planning = dict(document.get("planning_dates", {}))
    calendar = dict(document.get("calendar", {}))
    open_dates = tuple(str(value) for value in list(calendar.get("open_dates", [])))
    if (
        not open_dates
        or list(open_dates) != sorted(set(open_dates))
        or open_dates[0] != str(calendar.get("coverage_start", ""))
        or open_dates[-1] != str(calendar.get("coverage_end", ""))
        or calendar.get("exchange") != "SSE"
        or not SHA256_PATTERN.fullmatch(str(calendar.get("source_batch_sha256", "")))
        or planning.get("dates_are_planning_only") is not True
    ):
        raise WebQueryError("EVIDENCE_MISMATCH", "前瞻检查点日历或计划合同无效")
    contract = ForwardCheckpointContract(
        control=control,
        comparison=comparison,
        protocol_start=str(document.get("protocol_forward_start_execution_date", "")),
        live_start=str(document.get("live_dual_start_execution_date", "")),
        anchor_date=str(anchor.get("execution_trade_date", "")),
        anchor_runs={
            control.account_id: str(anchor.get("control_run_id", "")),
            comparison.account_id: str(anchor.get("comparison_run_id", "")),
        },
        anchor_artifacts={
            control.account_id: str(anchor.get("control_artifact_sha256", "")),
            comparison.account_id: str(anchor.get("comparison_artifact_sha256", "")),
        },
        minimum_days=int(minimums.get("live_dual_days", 0)),
        minimum_rebalances=int(minimums.get("live_dual_rebalance_cycles", 0)),
        first_rebalance_date=str(planning.get("expected_first_live_rebalance_execution_date", "")),
        first_due_date=str(planning.get("expected_first_due_execution_date", "")),
        open_dates=open_dates,
        calendar_end=str(calendar.get("coverage_end", "")),
        source_refs=tuple(source_refs),
        source_hashes=source_hashes,
    )
    dates = (
        contract.protocol_start,
        contract.live_start,
        contract.anchor_date,
        contract.first_rebalance_date,
        contract.first_due_date,
    )
    if any(len(value) != 8 or not value.isdigit() for value in dates):
        raise WebQueryError("EVIDENCE_MISMATCH", "前瞻检查点日期合同无效")
    if contract.minimum_days != 20 or contract.minimum_rebalances != 2:
        raise WebQueryError("EVIDENCE_MISMATCH", "前瞻检查点门槛漂移")
    if any(not SHA256_PATTERN.fullmatch(value) for value in contract.anchor_artifacts.values()):
        raise WebQueryError("EVIDENCE_MISMATCH", "前瞻检查点锚点身份无效")
    return contract


def account_evidence_stratum(row: dict[str, str], document: dict[str, object]) -> str:
    mode = str(document.get("mode", ""))
    if mode == "BACKFILL":
        return "BACKFILL"
    if mode != "FORWARD":
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟账户观察类型无效")
    execution_date = str(row.get("execution_trade_date", ""))
    started = _parse_timestamp(row.get("started_at", "")).astimezone(TIMEZONE)
    started_date = started.strftime("%Y%m%d")
    if started_date == execution_date:
        return "SAME_DAY_FORWARD"
    if started_date > execution_date:
        return "CONTROLLED_CATCHUP_FORWARD"
    raise WebQueryError("EVIDENCE_MISMATCH", "模拟账户在执行日前启动，时间身份无效")


def _rows_by_date(rows: list[dict[str, str]], documents: list[dict[str, object]]) -> dict[str, tuple[dict[str, str], dict[str, object]]]:
    result = {
        row["execution_trade_date"]: (row, document)
        for row, document in zip(rows, documents, strict=True)
    }
    if len(result) != len(rows):
        raise WebQueryError("EVIDENCE_MISMATCH", "双账户检查点存在重复账户日")
    return result


def _daily_gate(document: dict[str, object]) -> bool:
    nav = dict(dict(document.get("result", {})).get("nav", {}))
    positions = [dict(value) for value in list(nav.get("positions", []))]
    cash = _money(nav.get("cash"))
    market = _money(nav.get("market_value"))
    net = _money(nav.get("net_asset"))
    position_market = sum((_money(value.get("market_value")) for value in positions), Decimal("0"))
    return (
        net > 0
        and cash + market == net
        and position_market == market
        and nav.get("freshness_status") == "PASS"
        and not any(str(value.get("ts_code", "")).endswith(".BJ") for value in positions)
    )


def _pair_identity_matches(left: dict[str, str], right: dict[str, str]) -> bool:
    return all(left.get(field) == right.get(field) and left.get(field) for field in PAIR_FIELDS)


def _is_rebalance(signal_hash: str, signals: dict[str, dict[str, object]]) -> bool:
    signal = signals.get(signal_hash)
    if signal is None or not isinstance(signal.get("rebalance_due"), bool):
        raise WebQueryError("EVIDENCE_MISMATCH", "前瞻检查点缺少可验证的调仓信号")
    return bool(signal["rebalance_due"])


def _anchored_point(
    date: str,
    pair: dict[str, tuple[dict[str, str], dict[str, object]]],
    anchor_navs: dict[str, dict[str, object]],
    contract: ForwardCheckpointContract,
) -> dict[str, object]:
    values: dict[str, dict[str, object]] = {}
    for role, identity in (("top30", contract.control), ("top20", contract.comparison)):
        row, document = pair[identity.account_id]
        nav = dict(dict(document["result"])["nav"])
        anchor = anchor_navs[identity.account_id]
        portfolio = _money(nav["normalized_nav"]) / _money(anchor["normalized_nav"])
        benchmark = _money(nav["benchmark_nav"]) / _money(anchor["benchmark_nav"])
        values[role] = {
            "portfolio_nav": _decimal_text(portfolio),
            "benchmark_nav": _decimal_text(benchmark),
            "net_excess": _decimal_text(portfolio - benchmark),
            "daily_fees": str(nav["daily_fees"]),
            "cash_ratio": str(nav["cash_ratio"]),
            "turnover": str(nav["turnover"]),
            "position_count": len(list(nav.get("positions", []))),
            "order_count": int(row["order_count"]),
            "fill_count": int(row["fill_count"]),
        }
    return {
        "trade_date": _display_date(date),
        "rebalance_due": False,
        "top30": values["top30"],
        "top20": values["top20"],
        "top20_minus_top30_portfolio_nav": _decimal_text(
            _money(values["top20"]["portfolio_nav"]) - _money(values["top30"]["portfolio_nav"])
        ),
        "top20_minus_top30_net_excess": _decimal_text(
            _money(values["top20"]["net_excess"]) - _money(values["top30"]["net_excess"])
        ),
    }


def build_forward_checkpoint(
    contract: ForwardCheckpointContract,
    *,
    rows: dict[str, list[dict[str, str]]],
    documents: dict[str, list[dict[str, object]]],
    signals: dict[str, dict[str, object]],
    replay_statuses: dict[str, str],
    as_of: str,
) -> dict[str, object]:
    identities = (contract.control, contract.comparison)
    indexed = {
        identity.account_id: _rows_by_date(rows[identity.account_id], documents[identity.account_id])
        for identity in identities
    }
    blocked: list[str] = []
    anchor_navs: dict[str, dict[str, object]] = {}
    if as_of >= contract.anchor_date:
        for identity in identities:
            item = indexed[identity.account_id].get(contract.anchor_date)
            if item is None:
                blocked.append(f"MISSING_ANCHOR_{identity.account_id}")
                continue
            row, document = item
            if (
                row.get("run_id") != contract.anchor_runs[identity.account_id]
                or row.get("artifact_sha256") != contract.anchor_artifacts[identity.account_id]
                or row.get("policy_sha256") != identity.policy_sha256
                or document.get("execution_policy_version") != identity.policy_version
            ):
                blocked.append(f"ANCHOR_IDENTITY_MISMATCH_{identity.account_id}")
                continue
            anchor_navs[identity.account_id] = dict(dict(document["result"])["nav"])
    date_sets = []
    for identity in identities:
        date_sets.append(
            {
                date
                for date, (_row, document) in indexed[identity.account_id].items()
                if contract.protocol_start <= date <= as_of and document.get("mode") == "FORWARD"
            }
        )
    protocol_dates = sorted(date_sets[0] & date_sets[1])
    controlled_dates: list[str] = []
    live_dates: list[str] = []
    pairs: dict[str, dict[str, tuple[dict[str, str], dict[str, object]]]] = {}
    for date in protocol_dates:
        pair = {identity.account_id: indexed[identity.account_id][date] for identity in identities}
        pairs[date] = pair
        strata = [account_evidence_stratum(*pair[identity.account_id]) for identity in identities]
        if "CONTROLLED_CATCHUP_FORWARD" in strata:
            controlled_dates.append(date)
            continue
        left = pair[contract.control.account_id][0]
        right = pair[contract.comparison.account_id][0]
        if (
            strata == ["SAME_DAY_FORWARD", "SAME_DAY_FORWARD"]
            and left.get("operator") == right.get("operator") == "docker-scheduler"
            and left.get("policy_sha256") == contract.control.policy_sha256
            and right.get("policy_sha256") == contract.comparison.policy_sha256
            and _pair_identity_matches(left, right)
            and _daily_gate(pair[contract.control.account_id][1])
            and _daily_gate(pair[contract.comparison.account_id][1])
        ):
            live_dates.append(date)
        elif date >= contract.live_start:
            blocked.append(f"LIVE_DUAL_IDENTITY_OR_ACCOUNTING_MISMATCH_{date}")
    expected_dates = [date for date in contract.open_dates if contract.live_start <= date <= as_of]
    if as_of > contract.calendar_end:
        blocked.append("OFFICIAL_CALENDAR_COVERAGE_EXPIRED")
    missing = sorted(set(expected_dates) - set(live_dates))
    extra = sorted(set(live_dates) - set(expected_dates))
    if missing:
        blocked.append("MISSING_LIVE_DUAL_OPEN_DAYS")
    if extra:
        blocked.append("NON_CALENDAR_LIVE_DUAL_DAYS")
    if any(replay_statuses.get(identity.account_id) != "PASS" for identity in identities):
        blocked.append("ACCOUNT_REPLAY_NOT_PASS")
    protocol_rebalances = sum(
        _is_rebalance(pairs[date][contract.control.account_id][0]["signal_sha256"], signals)
        for date in protocol_dates
    )
    controlled_rebalances = sum(
        _is_rebalance(pairs[date][contract.control.account_id][0]["signal_sha256"], signals)
        for date in controlled_dates
    )
    live_rebalance_dates = [
        date
        for date in live_dates
        if _is_rebalance(pairs[date][contract.control.account_id][0]["signal_sha256"], signals)
    ]
    series: list[dict[str, object]] = []
    if len(anchor_navs) == 2:
        for date in live_dates:
            point = _anchored_point(date, pairs[date], anchor_navs, contract)
            point["rebalance_due"] = date in live_rebalance_dates
            series.append(point)
    blocked = sorted(set(blocked))
    if blocked:
        terminal = "BLOCKED_EVIDENCE"
    elif len(live_dates) >= contract.minimum_days and len(live_rebalance_dates) >= contract.minimum_rebalances:
        terminal = "CHECKPOINT_OBSERVED"
    else:
        terminal = "NOT_DUE"
    next_open = next((date for date in contract.open_dates if date > as_of), None)
    expected_count = len(expected_dates)
    return {
        "schema_version": "web-forward-checkpoint-v1",
        "status": terminal,
        "as_of": _display_date(as_of),
        "protocol_forward_count": len(protocol_dates),
        "protocol_forward_rebalance_count": protocol_rebalances,
        "controlled_catchup_count": len(controlled_dates),
        "controlled_catchup_rebalance_count": controlled_rebalances,
        "live_dual_count": len(live_dates),
        "live_dual_rebalance_count": len(live_rebalance_dates),
        "minimum_live_dual_days": contract.minimum_days,
        "minimum_live_dual_rebalances": contract.minimum_rebalances,
        "coverage_status": "BLOCKED_EVIDENCE" if blocked else "PASS",
        "coverage_ratio": _decimal_text(Decimal(len(live_dates)) / Decimal(expected_count)) if expected_count else None,
        "expected_open_day_count": expected_count,
        "missing_open_dates": [_display_date(value) for value in missing],
        "unexpected_live_dates": [_display_date(value) for value in extra],
        "blocked_reasons": blocked,
        "anchor_trade_date": _display_date(contract.anchor_date),
        "live_dual_start_trade_date": _display_date(contract.live_start),
        "comparison_anchor_source": "CONTROLLED_CATCHUP_FORWARD",
        "next_official_open_date": _display_date(next_open) if next_open else None,
        "expected_first_live_rebalance_execution_date": _display_date(contract.first_rebalance_date),
        "expected_first_due_execution_date": _display_date(contract.first_due_date),
        "dates_are_planning_only": True,
        "series": series,
        "source_refs": list(contract.source_refs),
        "evidence_hashes": dict(contract.source_hashes),
        "prohibited_outputs": [
            "winner_or_loser_label",
            "strategy_effectiveness",
            "production_switch_recommendation",
            "annualized_metrics",
            "significance_claim",
        ],
    }
