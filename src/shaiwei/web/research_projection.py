"""Immutable, typed research evidence projections for the P3-3B read-only API."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import yaml

from shaiwei.web.query import SCHEMA_VERSION, TIMEZONE, WebQueryError


PROTOCOL_PATH = "config/p3_factor_experiment_queries_v1.yaml"
CATALOG_PROTOCOL_PATH = "config/p3_experiment_catalog_v1.yaml"
CATALOG_PROTOCOL_ID = "p3-experiment-catalog-v1"
DEFAULT_OUTPUT = "data/web/research_snapshots"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
BSE_RE = re.compile(r"(?<!\d)\d{6}\.BJ(?![A-Z])")
DATE_RE = re.compile(r"^\d{4}-?\d{2}-?\d{2}$")
ALLOWED_EXPERIMENT_KINDS = {
    "research_experiment",
    "p2_engineering_run",
    "p2_effect_original",
    "p2_effect_correction",
}
CATALOG_OUTCOMES = {
    "RECORDED",
    "FAILED",
    "DISCOVERY_ONLY",
    "DISCOVERY_REJECTED",
    "G1_REJECTED",
    "G1_ADMITTED",
    "REVIEW_STOPPED",
    "ENGINEERING_GO_ONLY",
    "HISTORICAL_EFFECT_REJECTED",
    "INVALIDATED_METHOD",
}
UNAVAILABLE_SECTIONS = (
    "coverage_ratio",
    "quantile_returns_and_monotonicity",
    "factor_autocorrelation",
    "candidate_pool_correlation",
)
ADAPTERS = {
    "Alpha158": "BASELINE_BACKTEST",
    "Alpha158-shadow": "SHADOW_SIGNAL",
    "Alpha158-forward-shadow": "FORWARD_SHADOW_SIGNAL",
    "AlphaGen-GP": "GP_DISCOVERY_ATTEMPT",
    "AlphaGen-GP-stage1": "GP_STAGE1_ATTEMPT",
    "AlphaGen-GP-G1": "G1_FACTOR_DECISION",
    "Tushare-moneyflow-P1": "G1_FACTOR_DECISION",
    "LLM_DSL": "D1_DISCOVERY_ATTEMPT_WITH_REVIEW_OVERLAY",
}


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256(value: object) -> str:
    return _sha256_bytes(_canonical(value))


def factor_id(research_family: str, feature_or_formula: str) -> str:
    payload = f"factor-exact-v1\0{research_family}\0{feature_or_formula}".encode()
    return _sha256_bytes(payload)


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text not in {"true", "false"}:
        raise WebQueryError("EVIDENCE_MISMATCH", "研究证据布尔字段无效")
    return text == "true"


def _json_object(value: str, *, field: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", f"{field} 不是合法 JSON") from error
    if not isinstance(parsed, dict):
        raise WebQueryError("EVIDENCE_MISMATCH", f"{field} 必须是对象")
    return parsed


def _require_sha(value: object) -> str:
    text = str(value)
    if not SHA256_RE.fullmatch(text):
        raise WebQueryError("EVIDENCE_MISMATCH", "研究证据哈希格式无效")
    return text


def _parse_timestamp(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "研究证据时间格式无效") from error
    if parsed.tzinfo is None:
        raise WebQueryError("EVIDENCE_MISMATCH", "研究证据时间缺少时区")
    return parsed.astimezone(timezone.utc)


def _normalize_as_of(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not DATE_RE.fullmatch(text):
        raise WebQueryError("INVALID_ARGUMENT", "as_of 必须使用 YYYY-MM-DD 或 YYYYMMDD", status_code=422)
    compact = text.replace("-", "")
    try:
        datetime.strptime(compact, "%Y%m%d")
    except ValueError as error:
        raise WebQueryError("INVALID_ARGUMENT", "as_of 不是有效日期", status_code=422) from error
    return compact


def _as_of_keeps(timestamp: str, compact: str | None) -> bool:
    if compact is None:
        return True
    return _parse_timestamp(timestamp).astimezone(ZoneInfo(TIMEZONE)).strftime("%Y%m%d") <= compact


def _check_no_bse(value: object) -> None:
    if BSE_RE.search(json.dumps(value, ensure_ascii=False, sort_keys=True)):
        raise WebQueryError("FORBIDDEN_UNIVERSE", "研究证据出现北交所证券代码")


class _Reader:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.sources: dict[str, bytes] = {}

    def _safe_path(self, relative_path: str, prefixes: tuple[str, ...]) -> Path:
        relative = Path(relative_path)
        if (
            not relative_path
            or "\\" in relative_path
            or relative.is_absolute()
            or ".." in relative.parts
            or not relative_path.startswith(prefixes)
        ):
            raise WebQueryError("EVIDENCE_MISMATCH", "研究证据路径不在白名单")
        candidate = self.root / relative
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(self.root)
        except (FileNotFoundError, ValueError) as error:
            raise WebQueryError("EVIDENCE_MISMATCH", "研究证据不存在或路径越界") from error
        current = candidate
        while current != self.root:
            if current.is_symlink():
                raise WebQueryError("EVIDENCE_MISMATCH", "研究证据路径不得经过符号链接")
            current = current.parent
        if not resolved.is_file():
            raise WebQueryError("EVIDENCE_MISMATCH", "研究证据不是文件")
        return resolved

    def read(self, relative_path: str, prefixes: tuple[str, ...]) -> bytes:
        if relative_path in self.sources:
            return self.sources[relative_path]
        path = self._safe_path(relative_path, prefixes)
        before = path.stat()
        payload = path.read_bytes()
        after = path.stat()
        if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
            raise WebQueryError("EVIDENCE_MISMATCH", "投影期间研究证据发生变化")
        self.sources[relative_path] = payload
        return payload

    def csv_rows(self, relative_path: str) -> list[dict[str, str]]:
        try:
            text = self.read(relative_path, ("ledger/",)).decode("utf-8")
            rows = list(csv.DictReader(io.StringIO(text)))
        except (UnicodeDecodeError, csv.Error) as error:
            raise WebQueryError("EVIDENCE_MISMATCH", "研究账本格式无效") from error
        _check_no_bse(rows)
        return rows

    def json(self, relative_path: str, prefixes: tuple[str, ...]) -> dict[str, Any]:
        try:
            value = json.loads(self.read(relative_path, prefixes))
        except json.JSONDecodeError as error:
            raise WebQueryError("EVIDENCE_MISMATCH", "研究 JSON 格式无效") from error
        if not isinstance(value, dict):
            raise WebQueryError("EVIDENCE_MISMATCH", "研究 JSON 顶层必须是对象")
        _check_no_bse(value)
        return value

    def verified_json(
        self, relative_path: str, expected_sha: str, prefixes: tuple[str, ...]
    ) -> dict[str, Any]:
        payload = self.read(relative_path, prefixes)
        if _sha256_bytes(payload) != _require_sha(expected_sha):
            raise WebQueryError("EVIDENCE_MISMATCH", "研究证据 SHA-256 不匹配")
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as error:
            raise WebQueryError("EVIDENCE_MISMATCH", "研究 JSON 格式无效") from error
        if not isinstance(value, dict):
            raise WebQueryError("EVIDENCE_MISMATCH", "研究 JSON 顶层必须是对象")
        _check_no_bse(value)
        return value


def _unique(rows: Iterable[dict[str, str]], key: str, label: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key, "")
        if not value or value in result:
            raise WebQueryError("EVIDENCE_MISMATCH", f"{label} 主键缺失或重复")
        result[value] = row
    return result


def _safe_refs(*refs: str) -> list[str]:
    return sorted(set(ref for ref in refs if ref))


def _profile(config: dict[str, Any], family: str) -> dict[str, Any]:
    profiles = config.get("factor_family_profiles", {})
    profile = profiles.get(family)
    if not isinstance(profile, dict):
        raise WebQueryError("EVIDENCE_MISMATCH", "G1 家族缺少冻结 profile")
    return dict(profile)


def _authority(config: dict[str, Any], family: str, admission: dict[str, str], evidence: dict[str, Any]) -> str:
    for rule in config["factor_authority"]["rules"]:
        if rule["research_family"] != family:
            continue
        selector = rule["current_selector"]
        current = (
            int(admission["trial_count"]) == int(selector["trial_count"])
            and evidence.get("code_snapshot_sha256") == selector["candidate_code_sha256"]
        )
        return "AUTHORITATIVE_CURRENT" if current else str(rule["nonmatching_state"])
    return "HISTORICAL_ONLY"


def _g1_version(
    config: dict[str, Any],
    reader: _Reader,
    admission: dict[str, str],
    experiment: dict[str, str],
) -> dict[str, Any]:
    report_prefixes = tuple(config["source_allowlist"]["g1_report_prefixes"])
    evidence_prefixes = tuple(config["source_allowlist"]["g1_evidence_prefixes"])
    report = reader.verified_json(admission["report_path"], admission["report_sha256"], report_prefixes)
    bindings = report.get("bindings")
    candidate = report.get("candidate")
    if not isinstance(bindings, dict) or not isinstance(candidate, dict):
        raise WebQueryError("EVIDENCE_MISMATCH", "G1 判决缺少绑定或候选")
    evidence_path = str(bindings.get("evidence_path", ""))
    evidence_sha = _require_sha(bindings.get("evidence_sha256", ""))
    evidence = reader.verified_json(evidence_path, evidence_sha, evidence_prefixes)
    if evidence.get("candidate_experiment_id") != admission["candidate_experiment_id"]:
        raise WebQueryError("EVIDENCE_MISMATCH", "G1 证据外键不匹配")
    integrity = evidence.get("integrity")
    if not isinstance(integrity, dict):
        raise WebQueryError("EVIDENCE_MISMATCH", "G1 完整性证据缺失")
    test_path = str(integrity.get("test_report_path", ""))
    test_sha = _require_sha(integrity.get("test_report_sha256", ""))
    test = reader.verified_json(test_path, test_sha, evidence_prefixes)
    if test.get("candidate_experiment_id") != admission["candidate_experiment_id"]:
        raise WebQueryError("EVIDENCE_MISMATCH", "因子测试外键不匹配")
    if experiment["feature_or_formula"] != str(candidate.get("feature_or_formula", "")):
        raise WebQueryError("EVIDENCE_MISMATCH", "因子公式与实验账本不一致")
    if str(report.get("decision_id", "")) != admission["decision_id"]:
        raise WebQueryError("EVIDENCE_MISMATCH", "G1 判决主键不一致")
    params = _json_object(experiment["params_json"], field="params_json")
    family = admission["research_family"]
    authority = _authority(config, family, admission, evidence)
    admitted = _bool(admission["admitted"])
    profile = _profile(config, family)
    comparison = (
        params.get("benchmark_report_sha256")
        if family == "stage1-gp-preflight-v1"
        else params.get("comparison_policy_sha256")
    )
    fingerprint = {
        **{k: profile[k] for k in (
            "universe_id", "benchmark_id", "label_id", "horizon_id",
            "neutralization_id", "window_set_id", "stress_set_id",
            "portfolio_policy_id", "cost_policy_id", "decision_rule_version",
        )},
        "candidate_code_sha256": _require_sha(evidence.get("code_snapshot_sha256", "")),
        "data_snapshot_sha256": _require_sha(evidence.get("data_snapshot_sha256", "")),
        "comparison_policy_id": _require_sha(comparison),
    }
    stats = report.get("statistics", {})
    gates = report.get("gates", {})
    if not isinstance(stats, dict) or not isinstance(gates, dict) or len(gates) != 15:
        raise WebQueryError("EVIDENCE_MISMATCH", "G1 统计或 15 门证据不完整")
    rank_ic = evidence.get("rank_ic", {})
    portfolio = evidence.get("portfolio", {})
    complexity = evidence.get("complexity", {})
    stress = evidence.get("stress_max_drawdown", {})
    if not all(isinstance(x, dict) for x in (rank_ic, portfolio, complexity, stress)):
        raise WebQueryError("EVIDENCE_MISMATCH", "G1 详情结构无效")
    definition = {
        "feature_or_formula": experiment["feature_or_formula"],
        "direction": stats.get("direction"),
        "economic_rationale": evidence.get("economic_rationale"),
    }
    if "expression" in test:
        definition["normalized_expression"] = test.get("normalized_expression")
    detail = {
        "identity": {
            "candidate_experiment_id": admission["candidate_experiment_id"],
            "research_family": family,
            "data_category": profile["data_category"],
        },
        "frozen_definition_and_direction": definition,
        "pit_shift_and_complexity": {
            "pit_sentinel_pass": integrity.get("pit_sentinel_pass"),
            "shift_sentinel_pass": integrity.get("shift_sentinel_pass"),
            "ast_nodes": complexity.get("ast_nodes"),
            "expression_tokens": complexity.get("expression_tokens"),
            "max_lookback_days": test.get("max_lookback_days"),
            "required_backtrack_days": test.get("required_backtrack_days"),
            "shift_compared_values": test.get("shift_compared_values"),
        },
        "g1_statistics_and_all_gates": {"statistics": stats, "gates": gates},
        "six_oos_window_rank_ic": rank_ic.get("oos_windows"),
        "stress_max_drawdown": stress,
        "turnover_and_incremental_portfolio": {
            key: portfolio.get(key) for key in (
                "baseline_net_excess", "baseline_net_icir", "baseline_turnover",
                "candidate_net_excess", "candidate_net_icir", "candidate_turnover",
            )
        },
        "cost_and_slippage_stress": {
            "cost_2x_net_excess": portfolio.get("cost_2x_net_excess"),
            "slippage_2x_net_excess": portfolio.get("slippage_2x_net_excess"),
        },
        "library_max_abs_correlation": integrity.get("max_library_abs_spearman"),
    }
    detail.update({name: {"status": "NOT_EVALUATED", "recomputed": False} for name in UNAVAILABLE_SECTIONS})
    return {
        "factor_version": admission["candidate_experiment_id"],
        "recorded_at": admission["evaluated_at"],
        "recorded_decision": "ADMITTED" if admitted else "REJECTED",
        "lifecycle_status": "ADMITTED" if admitted else "REJECTED",
        "authority_status": authority,
        "trial_count": int(admission["trial_count"]),
        "failed_gates": sorted(filter(None, admission["failed_gates"].split("|"))),
        "decision_id": admission["decision_id"],
        "decision_rule_version": profile["decision_rule_version"],
        "evidence_sha256": evidence_sha,
        "report_sha256": _require_sha(admission["report_sha256"]),
        "evidence_status": "VERIFIED",
        "fingerprint": fingerprint,
        "detail": detail,
        "source_refs": _safe_refs(
            f"experiment:{experiment['experiment_id']}",
            f"factor_admission:{admission['decision_id']}",
            f"g1_report:{admission['report_sha256'][:16]}",
            f"g1_evidence:{evidence_sha[:16]}",
        ),
        "evidence_hashes": sorted({_require_sha(admission["report_sha256"]), evidence_sha, test_sha}),
    }


def _build_factors(
    config: dict[str, Any], reader: _Reader, experiments: dict[str, dict[str, str]]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    admissions = reader.csv_rows("ledger/factor_admissions.csv")
    _unique(admissions, "decision_id", "因子准入账本")
    grouped: dict[str, dict[str, Any]] = {}
    by_version: dict[str, dict[str, Any]] = {}
    for admission in admissions:
        experiment = experiments.get(admission["candidate_experiment_id"])
        if experiment is None:
            raise WebQueryError("EVIDENCE_MISMATCH", "因子判决引用未知实验")
        version = _g1_version(config, reader, admission, experiment)
        family = admission["research_family"]
        identity = factor_id(family, experiment["feature_or_formula"])
        if version["factor_version"] in by_version:
            raise WebQueryError("EVIDENCE_MISMATCH", "因子版本重复")
        version["factor_id"] = identity
        by_version[version["factor_version"]] = version
        factor = grouped.setdefault(identity, {
            "factor_id": identity,
            "identity_kind": "FAMILY_SCOPED_EXACT_FORMULA_SHA256",
            "research_family": family,
            "data_category": _profile(config, family)["data_category"],
            "feature_or_formula": experiment["feature_or_formula"],
            "versions": [],
        })
        if factor["research_family"] != family or factor["feature_or_formula"] != experiment["feature_or_formula"]:
            raise WebQueryError("EVIDENCE_MISMATCH", "因子哈希身份冲突")
        factor["versions"].append(version)
    for factor in grouped.values():
        factor["versions"].sort(key=lambda x: (x["recorded_at"], x["factor_version"]))
        currents = [v for v in factor["versions"] if v["authority_status"] == "AUTHORITATIVE_CURRENT"]
        if len(currents) > 1:
            raise WebQueryError("EVIDENCE_MISMATCH", "同一因子存在多个当前权威版本")
    return sorted(grouped.values(), key=lambda x: (x["research_family"], x["factor_id"])), by_version


def _research_summary(
    row: dict[str, str],
    admission_by_experiment: dict[str, dict[str, Any]],
    d1_attempt_by_experiment: dict[str, dict[str, str]],
    d1_reviews_by_candidate: dict[str, list[dict[str, str]]],
    d1_overlay: dict[str, Any],
) -> dict[str, Any]:
    source = row["candidate_source"]
    adapter = ADAPTERS.get(source)
    if adapter is None:
        raise WebQueryError("NOT_EVALUATED", "研究实验适配器未知")
    params = _json_object(row["params_json"], field="params_json")
    result = _json_object(row["result_json"], field="result_json")
    family = str(params.get("g1_research_family") or params.get("protocol_id") or source)
    admission = admission_by_experiment.get(row["experiment_id"])
    lifecycle = "COMPLETED"
    authority = "HISTORICAL_ONLY"
    decision: dict[str, Any] = {"status": result.get("status", "RECORDED")}
    failed: list[str] = []
    evidence_hashes = [_require_sha(row["code_sha256"]), _require_sha(row["data_snapshot_sha256"])]
    refs = [f"experiment:{row['experiment_id']}"]
    if admission:
        family = admission["detail"]["identity"]["research_family"]
        lifecycle = admission["lifecycle_status"]
        authority = admission["authority_status"]
        decision = {
            "recorded_decision": admission["recorded_decision"],
            "trial_count": admission["trial_count"],
            "all_gates": admission["detail"]["g1_statistics_and_all_gates"]["gates"],
        }
        failed = admission["failed_gates"]
        evidence_hashes.extend(admission["evidence_hashes"])
        refs.extend(admission["source_refs"])
    elif source == "LLM_DSL":
        attempt = d1_attempt_by_experiment.get(row["experiment_id"])
        if attempt is None:
            raise WebQueryError("EVIDENCE_MISMATCH", "D1 实验缺少尝试账本外键")
        candidate_id = attempt["attempt_id"]
        family = attempt["research_family"]
        lifecycle = attempt["candidate_status"] or "DISCOVERY_ATTEMPT"
        authority = "DISCOVERY_ONLY"
        decision = {
            "discovery_status": attempt["discovery_status"],
            "g1_run": False,
            "strategy_effective": "NOT_EVALUATED",
            "review_overlay": "NOT_APPLICABLE",
        }
        reviewed = d1_reviews_by_candidate.get(candidate_id, [])
        if candidate_id in set(d1_overlay["authority_overrides"]["d1_review"]["applies_to_candidate_ids"]):
            if len(reviewed) != 4:
                raise WebQueryError("EVIDENCE_MISMATCH", "D1 受复核候选必须恰有四角色复核")
            authority = "AUTHORITATIVE_STOP"
            lifecycle = "REVIEW_STOPPED"
            decision.update({
                "review_overlay": "STOP_SEMANTIC_CONTRACT_VIOLATION",
                "human_gate_ready": False,
                "production_authorization": "none",
                "review_roles": sorted(r["role"] for r in reviewed),
            })
            failed = ["SEMANTIC_CONTRACT_VIOLATION"]
        refs.append(f"d1_attempt:{candidate_id}")
        evidence_hashes.extend([
            _require_sha(attempt["response_sha256"]),
            _require_sha(attempt["artifact_manifest_sha256"]),
        ])
    else:
        if result.get("status") == "failed" or result.get("error"):
            lifecycle = "FAILED"
            failed = ["RECORDED_EXECUTION_FAILURE"]
        if source in {"AlphaGen-GP", "AlphaGen-GP-stage1"}:
            lifecycle = "DISCOVERY_ATTEMPT" if not failed else "FAILED"
        authority = "RECORDED_EXPERIMENT"
        decision = {
            key: result.get(key) for key in (
                "status", "decision", "rank_ic", "prediction_rows", "score_rows",
                "rebalance_due", "signal_sha256",
            ) if key in result
        }
    return {
        "experiment_kind": "research_experiment",
        "experiment_id": row["experiment_id"],
        "recorded_at": row["ts"],
        "research_family": family,
        "evidence_tier": adapter,
        "authority_status": authority,
        "lifecycle_status": lifecycle,
        "model_or_engine": row["model_or_engine"],
        "engine_version": row["engine_version"],
        "seed": row["seed"],
        "train_period": row["train_period"],
        "valid_period": row["valid_period"],
        "code_snapshot_sha256": _require_sha(row["code_sha256"]),
        "data_snapshot_sha256": _require_sha(row["data_snapshot_sha256"]),
        "decision": decision,
        "failed_reasons": sorted(set(failed)),
        "evidence_status": "VERIFIED",
        "source_refs": _safe_refs(*refs),
        "evidence_hashes": sorted(set(evidence_hashes)),
    }


def _p2_metrics(report: dict[str, Any]) -> dict[str, Any]:
    allowed_windows = (
        "window", "trade_days", "rebalance_count", "base_net_excess",
        "base_maximum_drawdown", "cost_1_5x_net_excess",
        "double_cost_net_excess", "extra_slippage_net_excess",
    )
    return {
        "window_metrics": [
            {key: row.get(key) for key in allowed_windows if key in row}
            for row in report.get("window_metrics", [])
            if isinstance(row, dict)
        ],
        "pooled": {
            key: report.get("pooled", {}).get(key)
            for key in (
                "trade_days", "base_net_excess", "cost_1_5x_net_excess",
                "double_cost_net_excess", "extra_slippage_net_excess",
            )
        },
    }


def _p2_summaries(config: dict[str, Any], reader: _Reader) -> dict[str, dict[str, dict[str, Any]]]:
    allow = config["source_allowlist"]
    report_entries = allow["p2_report_files"]
    reports = {
        Path(entry["path"]).name: reader.verified_json(entry["path"], entry["sha256"], ("data/research/star50/",))
        for entry in report_entries
    }
    output: dict[str, dict[str, dict[str, Any]]] = {kind: {} for kind in ALLOWED_EXPERIMENT_KINDS if kind != "research_experiment"}
    engineering_report = reports["engineering_report.json"]
    eng_rows = reader.csv_rows("ledger/p2_star50_engineering_runs.csv")
    eng_adm = {r["engineering_report_sha256"]: r for r in reader.csv_rows("ledger/p2_star50_engineering_admissions.csv")}
    _unique(eng_rows, "run_id", "P2 工程运行账本")
    current_eng = config["authority_overrides"]["p2_engineering"]["authoritative_run_id"]
    for row in eng_rows:
        current = row["run_id"] == current_eng
        report_sha = _require_sha(row["engineering_report_sha256"])
        admission = eng_adm.get(report_sha)
        if admission is None:
            raise WebQueryError("EVIDENCE_MISMATCH", "P2 工程运行缺少判决外键")
        if current and report_sha != _sha256_bytes(reader.sources["data/research/star50/p2-star50-engineering-v1/engineering_report.json"]):
            raise WebQueryError("EVIDENCE_MISMATCH", "P2 工程当前报告不匹配")
        output["p2_engineering_run"][row["run_id"]] = {
            "experiment_kind": "p2_engineering_run", "experiment_id": row["run_id"],
            "recorded_at": row["finished_at"], "research_family": row["research_family"],
            "evidence_tier": "P2_ENGINEERING", "authority_status": "AUTHORITATIVE_CURRENT" if current else "PROVISIONAL_HISTORICAL",
            "lifecycle_status": "ENGINEERING_GO_ONLY", "model_or_engine": "Alpha158-LightGBM-TopK",
            "engine_version": "p2-star50-engineering-v1", "seed": "", "train_period": "", "valid_period": "",
            "code_snapshot_sha256": "", "data_snapshot_sha256": "",
            "decision": {
                "verdict": row["verdict"], "engineering_complete": _bool(row["engineering_complete"]),
                "strategy_results_inspected": _bool(row["strategy_results_inspected"]),
                "strategy_effective": row["strategy_effective"], "production_authorization": row["production_authorization"],
                "pipeline_fixture_pass": _bool(row["pipeline_fixture_pass"]), "idempotency_pass": _bool(row["idempotency_pass"]),
                "artifact_file_count": engineering_report.get("qlib", {}).get("artifact_file_count") if current else None,
            },
            "failed_reasons": [],
            "evidence_status": "VERIFIED" if current else "LEDGER_RECORDED_PROVISIONAL",
            "source_refs": _safe_refs(f"p2_engineering_run:{row['run_id']}", f"p2_engineering_admission:{admission['decision_id']}"),
            "evidence_hashes": sorted(set(filter(None, [report_sha, _require_sha(row["protocol_sha256"]), _require_sha(row["qlib_artifact_sha256"])]))),
        }
    for kind, run_ledger, admission_ledger, report_name in (
        ("p2_effect_original", "ledger/p2_star50_effect_runs.csv", "ledger/p2_star50_effect_admissions.csv", "effect_report.json"),
        ("p2_effect_correction", "ledger/p2_star50_effect_correction_runs.csv", "ledger/p2_star50_effect_correction_admissions.csv", "effect_correction_report.json"),
    ):
        rows = reader.csv_rows(run_ledger)
        admissions = {r["effect_report_sha256"]: r for r in reader.csv_rows(admission_ledger)}
        _unique(rows, "run_id", kind)
        report = reports[report_name]
        for row in rows:
            report_sha = _require_sha(row["effect_report_sha256"])
            admission = admissions.get(report_sha)
            if admission is None:
                raise WebQueryError("EVIDENCE_MISMATCH", "P2 效果运行缺少判决外键")
            if report.get("run_id") != row["run_id"] or report_sha != _sha256_bytes(reader.sources[next(e["path"] for e in report_entries if Path(e["path"]).name == report_name)]):
                raise WebQueryError("EVIDENCE_MISMATCH", "P2 效果报告身份不匹配")
            corrected = kind == "p2_effect_correction"
            authority = "AUTHORITATIVE_CURRENT" if corrected else "INVALIDATED_METHOD"
            decision = {
                "historical_effect_gate": row.get("authoritative_historical_effect_gate") or row.get("historical_effect_gate"),
                "strategy_effective": row["strategy_effective"],
                "production_authorization": row["production_authorization"],
                "window_gate_pass": _bool(row["window_gate_pass"]),
                "cost_gate_pass": _bool(row["cost_gate_pass"]),
                "drawdown_gate_pass": _bool(row["drawdown_gate_pass"]),
                "diversification_gate_status": row["diversification_gate_status"],
                "determinism_pass": _bool(row["determinism_pass"]),
                **_p2_metrics(report),
            }
            if corrected:
                decision.update({
                    "original_p2_2_model_valid": False,
                    "original_p2_2_execution_valid": False,
                    "results_known_before_correction": _bool(row["results_known_before_correction"]),
                })
            else:
                decision.update({
                    "numeric_results_status": "REPRODUCIBLE_NOT_AUTHORITATIVE",
                    "authoritative_successor_kind": "p2_effect_correction",
                    "authoritative_successor_id": config["authority_overrides"]["p2_effect_original"]["authoritative_successor_id"],
                })
            output[kind][row["run_id"]] = {
                "experiment_kind": kind, "experiment_id": row["run_id"], "recorded_at": row["run_finished_at"],
                "research_family": row["research_family"], "evidence_tier": "P2_EFFECT_AUTHORITATIVE" if corrected else "P2_EFFECT_INVALIDATED",
                "authority_status": authority, "lifecycle_status": "REJECTED", "model_or_engine": "Alpha158-LightGBM-TopK",
                "engine_version": row.get("correction_code_sha256") or row.get("training_code_sha256", ""), "seed": "42",
                "train_period": "THREE_FROZEN_WINDOWS", "valid_period": "THREE_FROZEN_WINDOWS",
                "code_snapshot_sha256": _require_sha(row.get("correction_code_sha256") or row.get("training_code_sha256", "")),
                "data_snapshot_sha256": _require_sha(row["input_manifest_sha256"]), "decision": decision,
                "failed_reasons": ["WINDOW_GATE", "COST_GATE", "DRAWDOWN_GATE", "DIVERSIFICATION_NOT_EVALUABLE"],
                "evidence_status": "VERIFIED", "source_refs": _safe_refs(f"{kind}:{row['run_id']}", f"{kind}_admission:{admission['decision_id']}"),
                "evidence_hashes": sorted({_require_sha(row["protocol_sha256"]), _require_sha(row["input_manifest_sha256"]), report_sha}),
            }
    return output


def _build_bundle(root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    reader = _Reader(root)
    config_payload = reader.read(PROTOCOL_PATH, ("config/",))
    catalog_config_payload = reader.read(CATALOG_PROTOCOL_PATH, ("config/",))
    try:
        config = yaml.safe_load(config_payload)
        catalog_config = yaml.safe_load(catalog_config_payload)
    except yaml.YAMLError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "研究查询配置无法解析") from error
    if not isinstance(config, dict) or config.get("status") != "FROZEN_BEFORE_BACKEND_IMPLEMENTATION":
        raise WebQueryError("EVIDENCE_MISMATCH", "P3-3A 配置未冻结")
    if (
        not isinstance(catalog_config, dict)
        or catalog_config.get("status") != "FROZEN_BEFORE_IMPLEMENTATION"
        or catalog_config.get("protocol_id") != CATALOG_PROTOCOL_ID
        or catalog_config.get("depends_on", {}).get("projection_protocol")
        != config.get("protocol_id")
    ):
        raise WebQueryError("EVIDENCE_MISMATCH", "P3-4A 配置未冻结或依赖无效")
    for path in config["source_allowlist"]["ledgers"]:
        reader.csv_rows(path)
    d1_correction: dict[str, Any] | None = None
    for entry in config["source_allowlist"]["authority_overlays"]:
        payload = reader.read(entry["path"], ("docs/",))
        if _sha256_bytes(payload) != _require_sha(entry["sha256"]):
            raise WebQueryError("EVIDENCE_MISMATCH", "权威覆盖 SHA-256 不匹配")
        if entry["path"].endswith(".json"):
            try:
                value = json.loads(payload)
            except json.JSONDecodeError as error:
                raise WebQueryError("EVIDENCE_MISMATCH", "D1 权威覆盖 JSON 无效") from error
            if not isinstance(value, dict):
                raise WebQueryError("EVIDENCE_MISMATCH", "D1 权威覆盖必须是对象")
            d1_correction = value
    if (
        d1_correction is None
        or d1_correction.get("status")
        != "AUTHORITATIVE_STOP_SEMANTIC_CONTRACT_VIOLATION"
        or d1_correction.get("authoritative_overlay", {}).get("review_execution_gate")
        != "STOP_SEMANTIC_CONTRACT_VIOLATION"
    ):
        raise WebQueryError("EVIDENCE_MISMATCH", "D1 权威语义纠错缺失")
    overlay = {"authority_overrides": config["authority_overrides"]}
    experiments = _unique(reader.csv_rows("ledger/experiments.csv"), "experiment_id", "实验账本")
    factors, versions = _build_factors(config, reader, experiments)
    admission_by_experiment = {version_id: version for version_id, version in versions.items()}
    attempts = reader.csv_rows("ledger/llm_factor_attempts_v2.csv")
    _unique(attempts, "attempt_id", "D1 尝试账本")
    attempt_by_experiment = {row["experiment_id"]: row for row in attempts if row["experiment_id"]}
    if len(attempt_by_experiment) != len(attempts):
        raise WebQueryError("EVIDENCE_MISMATCH", "D1 尝试到实验外键不唯一")
    reviews = reader.csv_rows("ledger/llm_factor_reviews.csv")
    _unique(reviews, "review_id", "D1 复核账本")
    reviews_by_candidate: dict[str, list[dict[str, str]]] = {}
    for row in reviews:
        reviews_by_candidate.setdefault(row["candidate_id"], []).append(row)
    reviewed_candidates = set(reviews_by_candidate)
    frozen_reviewed = set(
        config["authority_overrides"]["d1_review"]["applies_to_candidate_ids"]
    )
    if reviewed_candidates != frozen_reviewed:
        raise WebQueryError("EVIDENCE_MISMATCH", "D1 复核候选集合与冻结覆盖不一致")
    research = {
        experiment_id: _research_summary(
            row, admission_by_experiment, attempt_by_experiment,
            reviews_by_candidate, overlay,
        )
        for experiment_id, row in experiments.items()
    }
    p2 = _p2_summaries(config, reader)
    timestamps = [v["recorded_at"] for v in research.values()]
    timestamps.extend(v["recorded_at"] for kind in p2.values() for v in kind.values())
    timestamps.extend(row["completed_at"] for row in reviews)
    timestamps.append(str(d1_correction["prepared_at"]))
    generated_at = max(_parse_timestamp(value) for value in timestamps).isoformat()
    source_hashes = {path: _sha256_bytes(payload) for path, payload in sorted(reader.sources.items())}
    source_hashes["builder:shaiwei.web.research_projection"] = _sha256_bytes(
        Path(__file__).read_bytes()
    )
    protocol_ids = [config["protocol_id"], catalog_config["protocol_id"]]
    snapshot_id = _sha256(
        {"protocol_ids": protocol_ids, "source_hashes": source_hashes}
    )
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "protocol_id": config["protocol_id"],
        "protocol_ids": protocol_ids,
        "catalog_protocol_id": catalog_config["protocol_id"],
        "snapshot_id": snapshot_id,
        "generated_at": generated_at,
        "timezone": TIMEZONE,
        "factors": factors,
        "experiments": {"research_experiment": research, **p2},
        "invariants": {
            "raw_json_returned": False,
            "daily_series_returned": False,
            "performance_recalculated": False,
            "formal_library_count": sum(
                1 for v in versions.values() if v["lifecycle_status"] == "ADMITTED" and v["authority_status"] == "AUTHORITATIVE_CURRENT"
            ),
        },
    }
    _check_no_bse(bundle)
    return bundle, source_hashes


def build_research_projection(
    project_root: Path | None = None, output_root: Path | None = None
) -> "ResearchProjectionBundle":
    root = (project_root or Path(__file__).resolve().parents[3]).resolve()
    bundle, source_hashes = _build_bundle(root)
    snapshot_id = bundle["snapshot_id"]
    output = (output_root or (root / DEFAULT_OUTPUT)).resolve()
    try:
        output.relative_to(root)
    except ValueError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "研究投影输出必须位于项目目录") from error
    output.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise WebQueryError("EVIDENCE_MISMATCH", "研究投影目录不得是符号链接")
    bundle_bytes = _canonical(bundle)
    bundle_sha = _sha256_bytes(bundle_bytes)
    manifest = {
        "schema_version": "research-projection-manifest-v1",
        "protocol_id": bundle["protocol_id"],
        "protocol_ids": bundle["protocol_ids"],
        "snapshot_id": snapshot_id,
        "generated_at": bundle["generated_at"],
        "bundle_file": "bundle.json",
        "bundle_bytes": len(bundle_bytes),
        "bundle_sha256": bundle_sha,
        "source_hashes": source_hashes,
    }
    manifest_bytes = _canonical(manifest)
    target = output / snapshot_id
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise WebQueryError("EVIDENCE_MISMATCH", "同名研究投影不是安全目录")
        if (target / "bundle.json").read_bytes() != bundle_bytes or (target / "manifest.json").read_bytes() != manifest_bytes:
            raise WebQueryError("EVIDENCE_MISMATCH", "write-once 研究投影发生内容冲突")
        return load_research_projection(project_root=root, snapshot_id=snapshot_id, output_root=output)
    temp = Path(tempfile.mkdtemp(prefix=f".{snapshot_id[:12]}-", dir=output))
    try:
        (temp / "bundle.json").write_bytes(bundle_bytes)
        (temp / "manifest.json").write_bytes(manifest_bytes)
        os.rename(temp, target)
    except Exception:
        for child in temp.iterdir() if temp.exists() else ():
            child.unlink()
        if temp.exists():
            temp.rmdir()
        raise
    return load_research_projection(project_root=root, snapshot_id=snapshot_id, output_root=output)


@dataclass(frozen=True)
class ResearchProjectionBundle:
    snapshot_id: str
    generated_at: str
    protocol_id: str
    data: dict[str, Any]
    source_hashes: dict[str, str]

    def meta_for(self, as_of: str | None = None) -> dict[str, object]:
        compact = _normalize_as_of(as_of)
        if compact is None:
            compact = _parse_timestamp(self.generated_at).astimezone(
                ZoneInfo(TIMEZONE)
            ).strftime("%Y%m%d")
        normalized_as_of = f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"
        return {
            "as_of": normalized_as_of,
            "generated_at": self.generated_at,
            "timezone": TIMEZONE,
            "freshness_status": "PASS",
            "snapshot_id": self.snapshot_id,
            "source_refs": [f"research_projection:{self.snapshot_id}"],
            "evidence_hashes": {"bundle": _sha256(self.data)},
            "protocol_id": self.protocol_id,
        }

    @property
    def meta(self) -> dict[str, object]:
        return self.meta_for()


def _projection_root(project_root: Path | None, output_root: Path | None) -> Path:
    root = (project_root or Path(__file__).resolve().parents[3]).resolve()
    output = (output_root or root / DEFAULT_OUTPUT).resolve()
    try:
        output.relative_to(root)
    except ValueError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "研究投影读取目录越界") from error
    if output.is_symlink() or not output.is_dir():
        raise WebQueryError("NOT_READY", "研究投影尚未构建", status_code=503)
    return output


def load_research_projection(
    project_root: Path | None = None,
    *,
    snapshot_id: str | None = None,
    output_root: Path | None = None,
) -> ResearchProjectionBundle:
    output = _projection_root(project_root, output_root)
    if snapshot_id is None:
        candidates: list[tuple[datetime, int, str]] = []
        for path in output.iterdir():
            if path.is_symlink() or not path.is_dir() or not SHA256_RE.fullmatch(path.name):
                continue
            manifest_path = path / "manifest.json"
            if manifest_path.is_file() and not manifest_path.is_symlink():
                try:
                    manifest = json.loads(manifest_path.read_bytes())
                    protocol_ids = manifest.get(
                        "protocol_ids", [manifest.get("protocol_id")]
                    )
                    if not isinstance(protocol_ids, list) or any(
                        not isinstance(value, str) for value in protocol_ids
                    ):
                        raise WebQueryError(
                            "EVIDENCE_MISMATCH", "研究投影协议身份无效"
                        )
                    catalog_rank = int(CATALOG_PROTOCOL_ID in protocol_ids)
                    candidates.append(
                        (
                            _parse_timestamp(manifest["generated_at"]),
                            catalog_rank,
                            path.name,
                        )
                    )
                except (json.JSONDecodeError, KeyError, WebQueryError):
                    raise WebQueryError("EVIDENCE_MISMATCH", "研究投影 manifest 无效") from None
        if not candidates:
            raise WebQueryError("NOT_READY", "研究投影尚未构建", status_code=503)
        snapshot_id = max(candidates)[2]
    if not SHA256_RE.fullmatch(snapshot_id):
        raise WebQueryError("INVALID_ARGUMENT", "研究投影 snapshot_id 无效", status_code=422)
    directory = output / snapshot_id
    if directory.is_symlink() or not directory.is_dir():
        raise WebQueryError("NO_DATA", "研究投影不存在", status_code=404)
    for name in ("bundle.json", "manifest.json"):
        if (directory / name).is_symlink() or not (directory / name).is_file():
            raise WebQueryError("EVIDENCE_MISMATCH", "研究投影文件缺失或为符号链接")
    try:
        bundle_payload = (directory / "bundle.json").read_bytes()
        manifest = json.loads((directory / "manifest.json").read_bytes())
        bundle = json.loads(bundle_payload)
    except json.JSONDecodeError as error:
        raise WebQueryError("EVIDENCE_MISMATCH", "研究投影 JSON 无效") from error
    manifest_protocol_ids = manifest.get(
        "protocol_ids", [manifest.get("protocol_id")]
    )
    bundle_protocol_ids = bundle.get("protocol_ids", [bundle.get("protocol_id")])
    if (
        not isinstance(manifest_protocol_ids, list)
        or not isinstance(bundle_protocol_ids, list)
        or any(not isinstance(value, str) for value in manifest_protocol_ids)
        or any(not isinstance(value, str) for value in bundle_protocol_ids)
        or manifest.get("snapshot_id") != snapshot_id
        or bundle.get("snapshot_id") != snapshot_id
        or manifest.get("bundle_sha256") != _sha256_bytes(bundle_payload)
        or manifest.get("bundle_bytes") != len(bundle_payload)
        or manifest.get("protocol_id") != bundle.get("protocol_id")
        or manifest_protocol_ids != bundle_protocol_ids
    ):
        raise WebQueryError("EVIDENCE_MISMATCH", "研究投影哈希绑定无效")
    _check_no_bse(bundle)
    return ResearchProjectionBundle(
        snapshot_id=snapshot_id,
        generated_at=str(bundle["generated_at"]),
        protocol_id=str(bundle["protocol_id"]),
        data=bundle,
        source_hashes=dict(manifest.get("source_hashes", {})),
    )


def _factor_cut(bundle: ResearchProjectionBundle, as_of: str | None) -> list[dict[str, Any]]:
    compact = _normalize_as_of(as_of)
    cut = []
    for factor in bundle.data["factors"]:
        versions = [v for v in factor["versions"] if _as_of_keeps(v["recorded_at"], compact)]
        if versions:
            cut.append({**factor, "versions": versions})
    return cut


def _factor_summary(factor: dict[str, Any]) -> dict[str, Any]:
    versions = factor["versions"]
    current = next((v for v in versions if v["authority_status"] == "AUTHORITATIVE_CURRENT"), None)
    selected = current or versions[-1]
    return {
        "factor_id": factor["factor_id"], "identity_kind": factor["identity_kind"],
        "research_family": factor["research_family"], "data_category": factor["data_category"],
        "lifecycle_status": selected["lifecycle_status"], "authority_status": selected["authority_status"],
        "version_count": len(versions), "current_factor_version": current["factor_version"] if current else None,
        "experiment_attempt_n": selected["trial_count"], "latest_recorded_decision": versions[-1]["recorded_decision"],
        "evidence_status": selected["evidence_status"],
    }


def factor_catalog(
    bundle: ResearchProjectionBundle, *, status: str | None = None,
    family: str | None = None, data_category: str | None = None, as_of: str | None = None,
) -> dict[str, Any]:
    requested = (status or "ALL").upper()
    if requested not in {"ALL", "ADMITTED", "REJECTED", "HISTORICAL_ONLY"}:
        raise WebQueryError("INVALID_ARGUMENT", "factor status 过滤值无效", status_code=422)
    factors = _factor_cut(bundle, as_of)
    rows = [_factor_summary(factor) for factor in factors]
    if family:
        rows = [row for row in rows if row["research_family"] == family]
    if data_category:
        rows = [row for row in rows if row["data_category"] == data_category]
    if requested == "HISTORICAL_ONLY":
        rows = [row for row in rows if row["authority_status"] != "AUTHORITATIVE_CURRENT"]
    elif requested != "ALL":
        rows = [row for row in rows if row["lifecycle_status"] == requested]
    all_summaries = [_factor_summary(factor) for factor in factors]
    return {
        "items": sorted(rows, key=lambda x: (x["research_family"], x["factor_id"])),
        "counters": {
            "formal_library_count": sum(1 for row in all_summaries if row["lifecycle_status"] == "ADMITTED" and row["authority_status"] == "AUTHORITATIVE_CURRENT"),
            "researched_factor_count": len(all_summaries),
            "authoritative_rejected_count": sum(1 for row in all_summaries if row["lifecycle_status"] == "REJECTED" and row["authority_status"] == "AUTHORITATIVE_CURRENT"),
            "historical_only_count": sum(1 for row in all_summaries if row["authority_status"] != "AUTHORITATIVE_CURRENT"),
        },
        "sort": ["research_family", "factor_id"],
        "historical_response_banner": "CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS" if as_of else None,
    }


def _find_factor(bundle: ResearchProjectionBundle, factor_id_value: str, as_of: str | None = None) -> dict[str, Any]:
    if not SHA256_RE.fullmatch(factor_id_value):
        raise WebQueryError("INVALID_ARGUMENT", "factor_id 无效", status_code=422)
    return next((f for f in _factor_cut(bundle, as_of) if f["factor_id"] == factor_id_value), None) or (_raise_no_factor())


def _raise_no_factor() -> Any:
    raise WebQueryError("NO_DATA", "因子不存在", status_code=404)


def factor_detail(
    bundle: ResearchProjectionBundle, factor_id_value: str, *, version: str | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    factor = _find_factor(bundle, factor_id_value, as_of)
    versions = factor["versions"]
    if version:
        selected = next((v for v in versions if v["factor_version"] == version), None)
        if selected is None:
            raise WebQueryError("NO_DATA", "因子版本不存在", status_code=404)
    else:
        selected = next((v for v in versions if v["authority_status"] == "AUTHORITATIVE_CURRENT"), versions[-1])
    return {
        "factor_id": factor["factor_id"], "identity_kind": factor["identity_kind"],
        "factor_version": selected["factor_version"], "authority_status": selected["authority_status"],
        "lifecycle_status": selected["lifecycle_status"], "recorded_decision": selected["recorded_decision"],
        "fallback_to_latest_historical": selected["authority_status"] != "AUTHORITATIVE_CURRENT" and version is None,
        "sections": selected["detail"], "source_refs": selected["source_refs"],
        "evidence_hashes": selected["evidence_hashes"],
        "historical_response_banner": "CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS" if as_of else None,
    }


def factor_admission_history(
    bundle: ResearchProjectionBundle, factor_id_value: str, *, as_of: str | None = None
) -> dict[str, Any]:
    factor = _find_factor(bundle, factor_id_value, as_of)
    return {
        "factor_id": factor_id_value,
        "items": [{key: version[key] for key in (
            "decision_id", "recorded_at", "factor_version", "recorded_decision",
            "authority_status", "trial_count", "failed_gates", "decision_rule_version",
            "evidence_sha256", "report_sha256",
        )} for version in factor["versions"]],
        "append_only": True,
        "historical_response_banner": "CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS" if as_of else None,
    }


def factor_compare(bundle: ResearchProjectionBundle, factor_versions: list[str]) -> dict[str, Any]:
    if not 2 <= len(factor_versions) <= 3 or len(set(factor_versions)) != len(factor_versions):
        raise WebQueryError("INVALID_ARGUMENT", "比较必须提供 2—3 个不同因子版本", status_code=422)
    index = {v["factor_version"]: v for f in bundle.data["factors"] for v in f["versions"]}
    selected = []
    for version in factor_versions:
        item = index.get(version)
        if item is None:
            raise WebQueryError("NO_DATA", "比较因子版本不存在", status_code=404)
        if item["authority_status"] != "AUTHORITATIVE_CURRENT":
            raise WebQueryError("CONFLICT", "只允许比较当前权威因子版本")
        selected.append(item)
    fingerprints = [item.get("fingerprint") for item in selected]
    if any(not isinstance(value, dict) or any(v in {None, ""} for v in value.values()) for value in fingerprints):
        raise WebQueryError("NOT_EVALUATED", "比较 fingerprint 不完整")
    if any(value != fingerprints[0] for value in fingerprints[1:]):
        raise WebQueryError("CONFLICT", "因子版本不具备严格可比性")
    return {
        "factor_versions": factor_versions, "fingerprint": fingerprints[0],
        "items": [{
            "factor_id": item["factor_id"], "factor_version": item["factor_version"],
            "recorded_decision": item["recorded_decision"],
            "statistics": item["detail"]["g1_statistics_and_all_gates"]["statistics"],
            "six_oos_window_rank_ic": item["detail"]["six_oos_window_rank_ic"],
            "stress_max_drawdown": item["detail"]["stress_max_drawdown"],
            "portfolio": item["detail"]["turnover_and_incremental_portfolio"],
            "cost_and_slippage": item["detail"]["cost_and_slippage_stress"],
        } for item in selected],
        "sorted_by_performance": False,
    }


def _experiment_outcome(row: dict[str, Any]) -> str:
    kind = str(row.get("experiment_kind", ""))
    tier = str(row.get("evidence_tier", ""))
    authority = str(row.get("authority_status", ""))
    lifecycle = str(row.get("lifecycle_status", ""))

    if authority == "INVALIDATED_METHOD":
        outcome = "INVALIDATED_METHOD"
    elif authority == "AUTHORITATIVE_STOP" and lifecycle == "REVIEW_STOPPED":
        outcome = "REVIEW_STOPPED"
    elif kind == "p2_engineering_run" and lifecycle == "ENGINEERING_GO_ONLY":
        outcome = "ENGINEERING_GO_ONLY"
    elif (
        kind == "p2_effect_correction"
        and authority == "AUTHORITATIVE_CURRENT"
        and lifecycle == "REJECTED"
    ):
        outcome = "HISTORICAL_EFFECT_REJECTED"
    elif tier == "G1_FACTOR_DECISION" and authority in {
        "AUTHORITATIVE_CURRENT",
        "HISTORICAL_NON_AUTHORITATIVE",
        "SUPERSEDED_ENGINEERING_GENERATION",
    }:
        if lifecycle in {"REJECT", "REJECTED"}:
            outcome = "G1_REJECTED"
        elif lifecycle == "ADMITTED":
            outcome = "G1_ADMITTED"
        else:
            raise WebQueryError("NOT_EVALUATED", "G1 实验目录状态组合未冻结")
    elif tier == "D1_DISCOVERY_ATTEMPT_WITH_REVIEW_OVERLAY":
        if lifecycle == "REJECT":
            outcome = "DISCOVERY_REJECTED"
        elif lifecycle in {"DISCOVERY_ATTEMPT", "DISCOVERY_EVALUATED"}:
            outcome = "DISCOVERY_ONLY"
        elif lifecycle == "FAILED":
            outcome = "FAILED"
        else:
            raise WebQueryError("NOT_EVALUATED", "D1 实验目录状态组合未冻结")
    elif tier in {"GP_DISCOVERY_ATTEMPT", "GP_STAGE1_ATTEMPT"}:
        if lifecycle == "FAILED":
            outcome = "FAILED"
        elif lifecycle == "DISCOVERY_ATTEMPT":
            outcome = "DISCOVERY_ONLY"
        else:
            raise WebQueryError("NOT_EVALUATED", "GP 实验目录状态组合未冻结")
    elif tier in {"BASELINE_BACKTEST", "SHADOW_SIGNAL", "FORWARD_SHADOW_SIGNAL"}:
        if lifecycle == "FAILED":
            outcome = "FAILED"
        elif lifecycle == "COMPLETED":
            outcome = "RECORDED"
        else:
            raise WebQueryError("NOT_EVALUATED", "基线或信号目录状态组合未冻结")
    elif tier == "G1_FACTOR_DECISION" and authority == "RECORDED_EXPERIMENT":
        if lifecycle == "FAILED":
            outcome = "FAILED"
        elif lifecycle == "COMPLETED":
            outcome = "RECORDED"
        else:
            raise WebQueryError("NOT_EVALUATED", "未提交 G1 的实验状态组合未冻结")
    else:
        raise WebQueryError("NOT_EVALUATED", "实验目录 adapter/outcome 组合未冻结")
    if outcome not in CATALOG_OUTCOMES:
        raise WebQueryError("EVIDENCE_MISMATCH", "实验目录 outcome 不在冻结枚举")
    return outcome


def _experiment_catalog_row(row: dict[str, Any]) -> dict[str, Any]:
    item_keys = (
        "experiment_kind",
        "experiment_id",
        "recorded_at",
        "research_family",
        "evidence_tier",
        "authority_status",
        "lifecycle_status",
        "model_or_engine",
        "engine_version",
        "evidence_status",
    )
    if any(key not in row or not isinstance(row[key], str) for key in item_keys):
        raise WebQueryError("EVIDENCE_MISMATCH", "实验目录必需字段缺失或类型无效")
    failed_reasons = row.get("failed_reasons")
    if not isinstance(failed_reasons, list) or any(
        not isinstance(value, str) for value in failed_reasons
    ):
        raise WebQueryError("EVIDENCE_MISMATCH", "实验失败原因格式无效")
    return {
        key: row[key]
        for key in item_keys
    } | {
        "outcome_status": _experiment_outcome(row),
        "failed_reason_count": len(failed_reasons),
    }


def _experiment_catalog_rows(bundle: ResearchProjectionBundle) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    experiments = bundle.data.get("experiments")
    if not isinstance(experiments, dict):
        raise WebQueryError("EVIDENCE_MISMATCH", "实验投影目录缺失")
    for kind, values in experiments.items():
        if kind not in ALLOWED_EXPERIMENT_KINDS or not isinstance(values, dict):
            raise WebQueryError("EVIDENCE_MISMATCH", "实验投影 kind 无效")
        for experiment_id_value, row in values.items():
            if not isinstance(row, dict):
                raise WebQueryError("EVIDENCE_MISMATCH", "实验投影行无效")
            identity = (kind, experiment_id_value)
            if identity in seen:
                raise WebQueryError("EVIDENCE_MISMATCH", "实验目录身份重复")
            if (
                row.get("experiment_kind") != kind
                or row.get("experiment_id") != experiment_id_value
            ):
                raise WebQueryError("EVIDENCE_MISMATCH", "实验目录身份与投影键不一致")
            seen.add(identity)
            rows.append(_experiment_catalog_row(row))
    return rows


def experiment_catalog(
    bundle: ResearchProjectionBundle,
    *,
    experiment_kind: str | None = None,
    research_family: str | None = None,
    evidence_tier: str | None = None,
    authority_status: str | None = None,
    lifecycle_status: str | None = None,
    outcome_status: str | None = None,
    evidence_status: str | None = None,
    as_of: str | None = None,
    offset: int = 0,
    limit: int = 25,
) -> dict[str, Any]:
    if bundle.data.get("catalog_protocol_id") != CATALOG_PROTOCOL_ID:
        raise WebQueryError(
            "NOT_READY", "实验目录投影尚未按 P3-4A 构建", status_code=503
        )
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise WebQueryError("INVALID_ARGUMENT", "offset 必须是非负整数", status_code=422)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise WebQueryError("INVALID_ARGUMENT", "limit 必须在 1—100", status_code=422)

    all_rows = _experiment_catalog_rows(bundle)
    compact_as_of = _normalize_as_of(as_of)
    as_of_rows = [
        row for row in all_rows if _as_of_keeps(row["recorded_at"], compact_as_of)
    ]
    filter_values = {
        "experiment_kind": experiment_kind,
        "research_family": research_family,
        "evidence_tier": evidence_tier,
        "authority_status": authority_status,
        "lifecycle_status": lifecycle_status,
        "outcome_status": outcome_status,
        "evidence_status": evidence_status,
    }
    for key, requested in filter_values.items():
        if requested is None:
            continue
        allowed = {str(row[key]) for row in all_rows}
        if requested not in allowed:
            raise WebQueryError(
                "INVALID_ARGUMENT", f"{key} 过滤值无效", status_code=422
            )

    filtered = [
        row
        for row in as_of_rows
        if all(value is None or row[key] == value for key, value in filter_values.items())
    ]
    filtered.sort(
        key=lambda row: (
            -_parse_timestamp(row["recorded_at"]).timestamp(),
            row["experiment_kind"],
            row["experiment_id"],
        )
    )
    page_items = filtered[offset : offset + limit]
    kind_counts = {
        kind: sum(1 for row in as_of_rows if row["experiment_kind"] == kind)
        for kind in sorted(ALLOWED_EXPERIMENT_KINDS)
    }
    available_filters = {
        key: sorted({str(row[key]) for row in as_of_rows})
        for key in filter_values
    }
    returned_count = len(page_items)
    return {
        "catalog_protocol_id": CATALOG_PROTOCOL_ID,
        "items": page_items,
        "counters": {
            "projected_total_count": len(all_rows),
            "as_of_count": len(as_of_rows),
            "filtered_count": len(filtered),
            "returned_count": returned_count,
            "kind_counts": kind_counts,
        },
        "filters": {
            **filter_values,
            "as_of": (
                f"{compact_as_of[:4]}-{compact_as_of[4:6]}-{compact_as_of[6:8]}"
                if compact_as_of
                else None
            ),
        },
        "available_filters": available_filters,
        "page": {
            "offset": offset,
            "limit": limit,
            "has_previous": offset > 0,
            "has_more": offset + returned_count < len(filtered),
            "previous_offset": max(0, offset - limit) if offset > 0 else None,
            "next_offset": (
                offset + returned_count
                if offset + returned_count < len(filtered)
                else None
            ),
        },
        "sort": [
            "recorded_at:desc",
            "experiment_kind:asc",
            "experiment_id:asc",
        ],
        "sorted_by_performance": False,
        "historical_response_banner": (
            "CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS" if as_of else None
        ),
    }


def experiment_summary(
    bundle: ResearchProjectionBundle, experiment_kind: str, experiment_id_value: str,
    *, as_of: str | None = None,
) -> dict[str, Any]:
    if experiment_kind not in ALLOWED_EXPERIMENT_KINDS:
        raise WebQueryError("INVALID_ARGUMENT", "experiment_kind 无效", status_code=422)
    row = bundle.data["experiments"].get(experiment_kind, {}).get(experiment_id_value)
    if row is None or not _as_of_keeps(row["recorded_at"], _normalize_as_of(as_of)):
        raise WebQueryError("NO_DATA", "实验不存在", status_code=404)
    return {
        **row,
        "outcome_status": _experiment_outcome(row),
        "historical_response_banner": "CURRENT_AUTHORITY_APPLIED_TO_HISTORICAL_RECORDS" if as_of else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build one immutable P3-3B research projection")
    parser.add_argument("command", choices=["build"])
    parser.add_argument("--project-root", type=Path, default=None)
    args = parser.parse_args(argv)
    result = build_research_projection(args.project_root)
    print(json.dumps({
        "status": "PASS", "protocol_id": result.protocol_id,
        "snapshot_id": result.snapshot_id, "generated_at": result.generated_at,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
