"""Paper-account projections over an already stable evidence cut."""

from __future__ import annotations

from decimal import Decimal
import hashlib
import json

from shaiwei.web.query_evidence import (
    SecurityNameCatalog,
    SecurityNameError,
    WebQueryError,
    _decimal_text,
    _display_date,
    _money,
    _sha256,
)
from shaiwei.web.forward_checkpoint import account_evidence_stratum


def _paper_projection(
    row: dict[str, str],
    document: dict[str, object],
    security_names: SecurityNameCatalog,
    *,
    security_name_bundle_sha256: str,
) -> dict[str, object]:
    result = dict(document.get("result", {}))
    nav = dict(result.get("nav", {}))
    cash = _money(nav.get("cash"))
    market_value = _money(nav.get("market_value"))
    net_asset = _money(nav.get("net_asset"))
    if net_asset <= 0 or cash + market_value != net_asset:
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟组合会计恒等失败")
    positions: list[dict[str, object]] = []
    name_statuses: list[str] = []
    position_market_value = Decimal("0")
    for value in list(nav.get("positions", [])):
        position = dict(value)
        code = str(position.get("ts_code", ""))
        if code.endswith(".BJ"):
            raise WebQueryError("FORBIDDEN_UNIVERSE", "模拟组合包含禁止的北交所证券")
        market = _money(position.get("market_value"))
        cost = _money(position.get("cost_basis"))
        try:
            name = security_names.resolve(code, str(document["execution_trade_date"]))
        except SecurityNameError as error:
            raise WebQueryError("EVIDENCE_MISMATCH", str(error)) from error
        name_statuses.append(str(name["security_name_status"]))
        position_market_value += market
        positions.append(
            {
                "ts_code": code,
                **name,
                "quantity": int(position.get("quantity", 0)),
                "close": str(position.get("close", "")),
                "price_date": str(position.get("price_date", "")),
                "market_value": str(position.get("market_value", "")),
                "cost_basis": str(position.get("cost_basis", "")),
                "actual_weight": _decimal_text(market / net_asset),
                "unrealized_pnl": _decimal_text(market - cost),
                "realized_pnl": str(position.get("realized_pnl", "")),
                "stale_trade_days": int(position.get("stale_trade_days", 0)),
            }
        )
    if position_market_value != market_value:
        raise WebQueryError("EVIDENCE_MISMATCH", "逐仓市值与账户市值不一致")
    missing_names = sum(status == "NOT_READY" for status in name_statuses)
    fallback_names = sum(status == "WARN" for status in name_statuses)
    name_coverage_status = (
        "NOT_READY" if missing_names else "WARN" if fallback_names else "PASS"
    )
    freshness = str(nav.get("freshness_status", ""))
    if freshness not in {"PASS", "STALE"}:
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟组合新鲜度状态无效")
    return {
        "as_of": _display_date(str(document["execution_trade_date"])),
        "generated_at": str(document["generated_at"]),
        "account_id": str(document["account_id"]),
        "mode": str(document["mode"]),
        "execution_policy_version": str(document.get("execution_policy_version", "")),
        "freshness_status": freshness,
        "cash": str(nav["cash"]),
        "market_value": str(nav["market_value"]),
        "net_asset": str(nav["net_asset"]),
        "normalized_nav": str(nav["normalized_nav"]),
        "benchmark_nav": str(nav["benchmark_nav"]),
        "net_excess": str(nav["net_excess"]),
        "drawdown": str(nav["drawdown"]),
        "cash_ratio": str(nav["cash_ratio"]),
        "turnover": str(nav["turnover"]),
        "cumulative_fees": str(nav["cumulative_fees"]),
        "cumulative_dividends": str(nav["cumulative_dividends"]),
        "position_count": len(positions),
        "positions": positions,
        "security_name_coverage": {
            "status": name_coverage_status,
            "position_count": len(positions),
            "pit_name_count": sum(status == "PASS" for status in name_statuses),
            "fallback_name_count": fallback_names,
            "missing_name_count": missing_names,
            "catalog_source_cutoff": security_names.source_cutoff,
        },
        "bse_count": 0,
        "source_ref": row["artifact_path"],
        "evidence_hashes": {
            "artifact_sha256": row["artifact_sha256"],
            "content_sha256": document["content_sha256"],
            "signal_sha256": document["signal_sha256"],
            "reconciliation_sha256": document["reconciliation_sha256"],
            "policy_sha256": document["policy_sha256"],
            "code_snapshot_sha256": document["code_snapshot_sha256"],
            "data_snapshot_sha256": document["data_snapshot_sha256"],
            "security_name_bundle_sha256": security_name_bundle_sha256,
        },
    }


def _paper_nav(
    rows: list[dict[str, str]],
    documents: list[dict[str, object]],
    *,
    account_id: str,
) -> dict[str, object]:
    series: list[dict[str, object]] = []
    versions: set[str] = set()
    freshness = "PASS"
    for row, document in zip(rows, documents, strict=True):
        nav = dict(dict(document["result"])["nav"])
        versions.add(str(document.get("execution_policy_version", "")))
        if nav.get("freshness_status") == "STALE":
            freshness = "STALE"
        series.append(
            {
                "trade_date": _display_date(str(document["execution_trade_date"])),
                "mode": str(document["mode"]),
                "evidence_stratum": account_evidence_stratum(row, document),
                "normalized_nav": str(nav["normalized_nav"]),
                "benchmark_nav": str(nav["benchmark_nav"]),
                "net_excess": str(nav["net_excess"]),
                "drawdown": str(nav["drawdown"]),
                "turnover": str(nav["turnover"]),
                "cash_ratio": str(nav["cash_ratio"]),
                "daily_fees": str(nav["daily_fees"]),
                "freshness_status": str(nav["freshness_status"]),
                "artifact_sha256": row["artifact_sha256"],
            }
        )
    if len(versions) != 1 or "" in versions:
        raise WebQueryError("CONFLICT", "模拟组合序列跨越不同执行策略版本")
    forward_count = sum(value["mode"] == "FORWARD" for value in series)
    return {
        "as_of": series[-1]["trade_date"],
        "account_id": account_id,
        "execution_policy_version": next(iter(versions)),
        "freshness_status": freshness,
        "forward_status": "PASS" if forward_count else "NOT_READY",
        "forward_observation_count": forward_count,
        "observation_count": len(series),
        "series": series,
    }


def _forward_projection(
    rows: list[dict[str, str]],
    documents: list[dict[str, object]],
) -> dict[str, object]:
    forward_indexes = [
        index for index, document in enumerate(documents) if document.get("mode") == "FORWARD"
    ]
    if not forward_indexes:
        versions = {
            str(document.get("execution_policy_version", "")) for document in documents
        }
        if len(versions) != 1 or "" in versions:
            raise WebQueryError("CONFLICT", "模拟组合序列跨越不同执行策略版本")
        return {
            "status": "NOT_READY",
            "performance_maturity": "NOT_READY",
            "forward_anchor_trade_date": None,
            "forward_anchor_portfolio_nav": None,
            "forward_anchor_benchmark_nav": None,
            "forward_anchor_artifact_sha256": None,
            "execution_policy_version": next(iter(versions)),
            "forward_observation_count": 0,
            "forward_rebalance_count": 0,
            "coverage_status": "NOT_EVALUATED",
            "coverage_ratio": None,
            "coverage_reason": "尚无自然 FORWARD 账户日，只保留工程回放证据",
            "forward_cumulative_fees": None,
            "forward_cumulative_dividends": None,
            "forward_turnover": None,
            "forward_cash_ratio": None,
            "latest": None,
            "series": [],
            "suppressed_metrics": [
                "forward_annualized_return",
                "forward_annualized_volatility",
                "forward_sharpe",
                "forward_information_ratio",
            ],
        }
    first = forward_indexes[0]
    if first == 0 or documents[first - 1].get("mode") != "BACKFILL":
        raise WebQueryError("EVIDENCE_MISMATCH", "FORWARD 序列缺少合法 BACKFILL 锚点")
    if any(document.get("mode") != "FORWARD" for document in documents[first:]):
        raise WebQueryError("EVIDENCE_MISMATCH", "FORWARD 开始后出现非法模式回退")
    anchor = documents[first - 1]
    anchor_row = rows[first - 1]
    anchor_nav = dict(dict(anchor["result"])["nav"])
    anchor_portfolio = _money(anchor_nav["normalized_nav"])
    anchor_benchmark = _money(anchor_nav["benchmark_nav"])
    if anchor_portfolio <= 0 or anchor_benchmark <= 0:
        raise WebQueryError("EVIDENCE_MISMATCH", "FORWARD 锚点净值无效")
    version = str(anchor.get("execution_policy_version", ""))
    peak = Decimal("1")
    series: list[dict[str, object]] = []
    turnover = Decimal("0")
    rebalances = 0
    for row, document in zip(rows[first:], documents[first:], strict=True):
        if str(document.get("execution_policy_version", "")) != version:
            raise WebQueryError("CONFLICT", "FORWARD 序列跨越不同执行策略版本")
        nav = dict(dict(document["result"])["nav"])
        portfolio = _money(nav["normalized_nav"]) / anchor_portfolio
        benchmark = _money(nav["benchmark_nav"]) / anchor_benchmark
        peak = max(peak, portfolio)
        drawdown = portfolio / peak - Decimal("1")
        turnover += _money(nav["turnover"])
        if int(row["order_count"]) > 0:
            rebalances += 1
        series.append(
            {
                "trade_date": _display_date(str(document["execution_trade_date"])),
                "evidence_stratum": account_evidence_stratum(row, document),
                "forward_portfolio_nav": _decimal_text(portfolio),
                "forward_benchmark_nav": _decimal_text(benchmark),
                "forward_net_excess": _decimal_text(portfolio - benchmark),
                "forward_drawdown": _decimal_text(drawdown),
                "cash_ratio": str(nav["cash_ratio"]),
                "turnover": str(nav["turnover"]),
                "daily_fees": str(nav["daily_fees"]),
                "artifact_sha256": row["artifact_sha256"],
            }
        )
    latest_nav = dict(dict(documents[-1]["result"])["nav"])
    forward_fees = _money(latest_nav["cumulative_fees"]) - _money(
        anchor_nav["cumulative_fees"]
    )
    forward_dividends = _money(latest_nav["cumulative_dividends"]) - _money(
        anchor_nav["cumulative_dividends"]
    )
    return {
        "status": "PASS",
        "performance_maturity": "OBSERVING",
        "forward_anchor_trade_date": _display_date(str(anchor["execution_trade_date"])),
        "forward_anchor_portfolio_nav": str(anchor_nav["normalized_nav"]),
        "forward_anchor_benchmark_nav": str(anchor_nav["benchmark_nav"]),
        "forward_anchor_artifact_sha256": anchor_row["artifact_sha256"],
        "execution_policy_version": version,
        "forward_observation_count": len(series),
        "forward_rebalance_count": rebalances,
        "coverage_status": "NOT_EVALUATED",
        "coverage_ratio": None,
        "coverage_reason": "P3-0 未挂载官方交易日历，成熟度保持 OBSERVING",
        "forward_cumulative_fees": _decimal_text(forward_fees),
        "forward_cumulative_dividends": _decimal_text(forward_dividends),
        "forward_turnover": _decimal_text(turnover),
        "forward_cash_ratio": str(latest_nav["cash_ratio"]),
        "latest": series[-1],
        "series": series,
        "suppressed_metrics": [
            "forward_annualized_return",
            "forward_annualized_volatility",
            "forward_sharpe",
            "forward_information_ratio",
        ],
    }


def _paper_replay(
    accounts: list[dict[str, str]],
    events: list[dict[str, str]],
    rows: list[dict[str, str]],
    documents: list[dict[str, object]],
    *,
    as_of: str,
    account_id: str,
) -> dict[str, object]:
    identities = [row for row in accounts if row.get("account_id") == account_id]
    if len(identities) != 1:
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟账户身份不唯一")
    account = identities[0]
    run_ids = {row["run_id"] for row in rows}
    selected_events = [
        row
        for row in events
        if row.get("account_id") == account_id
        and row.get("effective_date", "") <= as_of
    ]
    event_ids = [row.get("event_id", "") for row in selected_events]
    if not all(event_ids) or len(event_ids) != len(set(event_ids)):
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件身份重复或缺失")
    orphaned = {row.get("run_id", "") for row in selected_events} - run_ids
    if orphaned:
        raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件没有对应的 PASS 运行")
    by_run: dict[str, list[dict[str, str]]] = {}
    for event in selected_events:
        by_run.setdefault(event["run_id"], []).append(event)
    previous_state: dict[str, object] | None = None
    mode_counts: dict[str, int] = {}
    total_orders = 0
    total_fills = 0
    for row, document in zip(rows, documents, strict=True):
        if (
            document["account_id"] != account_id
            or document["policy_sha256"] != account.get("policy_sha256")
            or str(document.get("execution_policy_version", ""))
            != account.get("execution_policy_version")
        ):
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟账户或策略身份不一致")
        if document.get("prior_state_sha256") != _sha256(previous_state):
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟账户状态链断裂")
        run_events = sorted(by_run.get(row["run_id"], []), key=lambda item: int(item["sequence"]))
        sequences = [int(event["sequence"]) for event in run_events]
        if sequences != list(range(1, len(run_events) + 1)):
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件序列不连续")
        if len(run_events) != int(row["event_count"]):
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件数量与运行账本不一致")
        actual: dict[str, list[object]] = {}
        for event in run_events:
            try:
                payload = json.loads(event["payload_json"])
            except json.JSONDecodeError as error:
                raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件载荷格式无效") from error
            if event["evidence_sha256"] != _sha256(payload):
                raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件证据哈希不一致")
            expected_id = hashlib.sha256(
                (
                    f"{row['run_id']}|{event['sequence']}|"
                    f"{event['event_type']}|{event['business_key']}"
                ).encode()
            ).hexdigest()[:20]
            if event["event_id"] != expected_id:
                raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件身份校验失败")
            if (
                event["effective_date"] != row["execution_trade_date"]
                or event["signal_sha256"] != row["signal_sha256"]
            ):
                raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件业务身份不一致")
            if str(event.get("ts_code", "")).endswith(".BJ"):
                raise WebQueryError("FORBIDDEN_UNIVERSE", "模拟事件包含禁止的北交所证券")
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
                raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件与不可变产物不一致")
        expected_types = {event_type for event_type, payloads in expected.items() if payloads}
        if set(actual) != expected_types:
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟事件包含未支持的类型")
        if (
            len(expected["ORDER"]) != int(row["order_count"])
            or len(expected["FILL"]) != int(row["fill_count"])
        ):
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟订单或成交数量不一致")
        state = dict(document["state"])
        if state["cash"] != nav["cash"]:
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟现金与状态不一致")
        state_positions = dict(state["positions"])
        nav_positions = {str(value["ts_code"]): dict(value) for value in nav["positions"]}
        if set(state_positions) != set(nav_positions):
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟持仓集合与状态不一致")
        for code, state_value in state_positions.items():
            position = dict(state_value)
            snapshot = nav_positions[code]
            for state_field, nav_field in (
                ("quantity", "quantity"),
                ("cost_basis", "cost_basis"),
                ("realized_pnl", "realized_pnl"),
                ("last_price_date", "price_date"),
            ):
                if str(position[state_field]) != str(snapshot[nav_field]):
                    raise WebQueryError("EVIDENCE_MISMATCH", "模拟逐仓状态重放不一致")
        if (
            _money(nav["cash"]) + _money(nav["market_value"]) != _money(nav["net_asset"])
            or _money(nav["equation_difference"]) != 0
            or row["net_asset"] != str(nav["net_asset"])
        ):
            raise WebQueryError("EVIDENCE_MISMATCH", "模拟会计恒等或账本净值不一致")
        mode = str(document["mode"])
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        total_orders += len(expected["ORDER"])
        total_fills += len(expected["FILL"])
        previous_state = state
    return {
        "status": "PASS",
        "account_id": account_id,
        "as_of": _display_date(rows[-1]["execution_trade_date"]),
        "run_count": len(rows),
        "event_count": len(selected_events),
        "order_count": total_orders,
        "fill_count": total_fills,
        "mode_counts": mode_counts,
        "bse_count": 0,
    }
