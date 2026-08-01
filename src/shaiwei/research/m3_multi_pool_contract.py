"""Frozen M3-1 protocol and read-only three-pool input identity checks."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.research.alphagen_expression import ALLOWED_FEATURES, ALLOWED_OPERATOR_NAMES
from shaiwei.research.llm_factor import D1ControlError
from shaiwei.research.m3_multi_pool_prompt import M3PromptBundle, TOPICS


PROTOCOL_SCHEMA = "m3-multi-pool-factor-research-protocol-v1"
PROTOCOL_ID = "m3-star-three-pool-price-volume-v1"
POOL_IDS = {
    "all": "star-board-all-pit-v1",
    "midcap": "star-board-midcap-pit-v1",
    "smallcap": "star-board-smallcap-pit-v1",
}


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _project_path(root: Path, value: object, *, kind: str = "file") -> Path:
    relative = Path(str(value))
    if relative.is_absolute() or ".." in relative.parts:
        raise D1ControlError("M3-1 evidence path must be project-relative")
    resolved_root = root.resolve()
    path = (resolved_root / relative).resolve()
    try:
        path.relative_to(resolved_root)
    except ValueError as error:
        raise D1ControlError("M3-1 evidence path escapes the project") from error
    exists = path.is_file() if kind == "file" else path.is_dir()
    if not exists:
        raise D1ControlError(f"M3-1 evidence {kind} is missing")
    return path


@dataclass(frozen=True)
class M3Protocol:
    path: Path
    document: dict[str, Any]
    sha256: str
    prompt_bundle: M3PromptBundle

    @classmethod
    def load(cls, path: Path, *, project_root: Path = PROJECT_ROOT) -> "M3Protocol":
        if not path.is_file():
            raise D1ControlError("M3-1 protocol is missing")
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise D1ControlError("M3-1 protocol must be a YAML object")
        cls._validate_authority(document)
        cls._validate_identity_and_budget(document)
        cls._validate_data_and_evaluation(document)
        prompt_contract = document["prompt_contract"]
        prompt = M3PromptBundle.load(
            _project_path(project_root, prompt_contract["path"]),
            expected_sha256=str(prompt_contract["sha256"]),
        )
        knowledge = _project_path(project_root, prompt_contract["knowledge_manifest_path"])
        if sha256_file(knowledge) != prompt_contract["knowledge_manifest_sha256"]:
            raise D1ControlError("M3-1 knowledge manifest differs from its freeze")
        return cls(path=path, document=document, sha256=sha256_file(path), prompt_bundle=prompt)

    @staticmethod
    def _validate_authority(document: dict[str, Any]) -> None:
        expected = {
            "schema_version": PROTOCOL_SCHEMA,
            "protocol_id": PROTOCOL_ID,
            "status": "M3_1_RESULT_BEFORE_PROTOCOL_FROZEN_FIXTURE_ONLY",
            "execution_authorized": False,
            "llm_api_called": False,
            "factor_results_inspected": False,
            "sealed_results_inspected": False,
            "model_training_authorized": False,
            "backtest_authorized": False,
            "signal_authorized": False,
            "production_authorization": "none",
            "scheduler_changes_authorized": False,
        }
        if any(document.get(key) != value for key, value in expected.items()):
            raise D1ControlError("M3-1 authority boundary differs from the freeze")
        scope = document.get("scope", {})
        if "deepseek_api_call" not in scope.get("forbidden_now", ()):
            raise D1ControlError("M3-1 must forbid provider calls during pre-execution")
        if "real_factor_evaluation" not in scope.get("forbidden_now", ()):
            raise D1ControlError("M3-1 must forbid real factor evaluation")

    @staticmethod
    def _validate_identity_and_budget(document: dict[str, Any]) -> None:
        identity = document["identity"]
        if (
            identity.get("research_family") != PROTOCOL_ID
            or identity.get("factor_identity_scope") != "GLOBAL_EXACT_DEFINITION"
            or identity.get("same_formula_in_all_pools_required") is not True
        ):
            raise D1ControlError("M3-1 factor identity differs")
        universes = document["universes"]
        actual_ids = {name: universes[name]["universe_id"] for name in POOL_IDS}
        if actual_ids != POOL_IDS or universes.get("official_index_alias_forbidden") is not True:
            raise D1ControlError("M3-1 universe identities differ")
        budget = document["attempt_budget"]
        if (
            tuple(budget.get("topic_order", ())) != TOPICS
            or int(budget.get("attempts_per_topic", 0)) * len(TOPICS) != 24
            or int(budget.get("completed_llm_responses_exact", 0)) != 24
            or int(budget.get("cross_pool_evaluation_cells_exact", 0)) != 72
            or int(budget.get("one_response_evaluated_in_three_pools_counts_as_attempts", 0)) != 1
        ):
            raise D1ControlError("M3-1 attempt or evaluation-cell budget differs")
        schedule = budget["topic_schedule"]
        if int(schedule["independent_proposals"]) + int(schedule["bounded_mutations"]) != 6:
            raise D1ControlError("M3-1 topic schedule does not exhaust the budget")
        multiple = document["multiple_testing_contract"]
        prior = multiple["prior_completed_or_registered_attempts"]
        if (
            sum(int(value) for value in prior.values()) != 246
            or int(multiple["prior_related_trial_count"]) != 246
            or int(multiple["new_batch_trial_count"]) != 24
            or int(multiple["effective_trial_count_after_complete_batch"]) != 270
            or multiple.get("reset_or_effective_N_discount_forbidden") is not True
        ):
            raise D1ControlError("M3-1 multiple-testing trial count differs")
        provider = document["provider"]
        cost = document["cost_budget"]
        if (
            provider.get("name") != "deepseek"
            or provider.get("base_url") != "https://api.deepseek.com"
            or provider.get("model") != "deepseek-v4-pro"
            or provider.get("thinking") != "enabled"
            or provider.get("reasoning_effort") != "high"
            or provider.get("tool_calls") is not False
            or int(provider.get("concurrency", 0)) != 1
        ):
            raise D1ControlError("M3-1 provider contract differs")
        per_attempt = (
            int(provider["maximum_prompt_tokens_per_attempt"])
            * float(cost["pro_input_cache_miss_per_million"])
            + int(provider["maximum_output_tokens_per_attempt"])
            * float(cost["pro_output_per_million"])
        ) / 1_000_000
        planned = per_attempt * 24
        if (
            not math.isclose(
                planned,
                float(cost["planned_worst_case_all_cache_miss_usd"]),
                rel_tol=0,
                abs_tol=1e-12,
            )
            or planned > float(cost["hard_ceiling_usd"])
        ):
            raise D1ControlError("M3-1 cost budget differs")

    @staticmethod
    def _validate_data_and_evaluation(document: dict[str, Any]) -> None:
        data = document["data_contract"]
        candidate = document["candidate_contract"]
        if set(data.get("feature_fields", ())) != ALLOWED_FEATURES:
            raise D1ControlError("M3-1 feature allowlist differs from the parser")
        if set(candidate.get("allowed_operators", ())) != ALLOWED_OPERATOR_NAMES:
            raise D1ControlError("M3-1 operator allowlist differs from the parser")
        if (
            data.get("discovery_signal_period") != ["2021-01-04", "2022-12-15"]
            or data.get("final_discovery_label_maturity_date") != "2022-12-30"
            or data.get("sealed_validation_period") != ["2023-01-03", "2025-12-31"]
            or int(data.get("horizon_trade_days", 0)) != 10
        ):
            raise D1ControlError("M3-1 research clock or label differs")
        discovery = document["discovery_evaluation"]
        if (
            discovery.get("direction_anchor_universe") != POOL_IDS["all"]
            or discovery.get("per_pool_direction_flip_forbidden") is not True
            or discovery.get("eligible_requires_positive_directed_rank_ic_in_all_three_pools")
            is not True
            or int(discovery.get("promoted_count", 0)) != 2
        ):
            raise D1ControlError("M3-1 discovery direction or selection differs")
        sealed = document["sealed_evaluation_contract"]
        windows = sealed.get("validation_windows", ())
        if sealed.get("access_authorized_now") is not False or len(windows) != 6:
            raise D1ControlError("M3-1 sealed evaluation boundary differs")
        previous_end = ""
        for window in windows:
            start, end = str(window["start"]), str(window["end"])
            if start > end or (previous_end and start <= previous_end):
                raise D1ControlError("M3-1 sealed windows overlap or are unordered")
            previous_end = end


@dataclass(frozen=True)
class M3InputIdentity:
    snapshot_sha256: str
    membership_sha256: str
    full_rows: int
    discovery_trade_days: int
    discovery_rows: dict[str, int]
    sealed_trade_days: int


def verify_m3_inputs(protocol: M3Protocol, *, project_root: Path = PROJECT_ROOT) -> M3InputIdentity:
    """Verify the M3-0 truth without reading or computing any factor result."""
    document = protocol.document
    upstream = document["upstream_contract"]
    for path_key, hash_key in (
        ("m3_data_protocol_path", "m3_data_protocol_sha256"),
        ("m3_data_manifest_path", "m3_data_manifest_sha256"),
        ("quality_report_path", "quality_report_sha256"),
        ("membership_path", "membership_sha256"),
    ):
        evidence = _project_path(project_root, upstream[path_key])
        if sha256_file(evidence) != upstream[hash_key]:
            raise D1ControlError(f"M3-1 upstream evidence differs: {path_key}")
    manifest_path = _project_path(project_root, upstream["m3_data_manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("verdict") != upstream["m3_data_verdict_required"]
        or manifest.get("strategy_effective") != upstream["m3_strategy_effective_required"]
        or manifest.get("production_authorization") != "none"
        or manifest.get("selected_input_sha256") != upstream["selected_input_sha256"]
    ):
        raise D1ControlError("M3-1 upstream manifest authority differs")
    artifact = manifest["artifacts"]["daily_members"]
    if (
        artifact.get("path") != upstream["membership_path"]
        or artifact.get("sha256") != upstream["membership_sha256"]
        or int(artifact.get("rows", 0)) != int(upstream["membership_rows"])
    ):
        raise D1ControlError("M3-1 membership manifest binding differs")
    membership_path = _project_path(project_root, upstream["membership_path"])
    data = document["data_contract"]
    start, end = (value.replace("-", "") for value in data["discovery_signal_period"])
    sealed_start, sealed_end = (
        value.replace("-", "") for value in data["sealed_validation_period"]
    )
    connection = duckdb.connect(":memory:")
    try:
        connection.read_parquet(str(membership_path)).create_view("members")
        full_rows = int(connection.execute("SELECT count(*) FROM members").fetchone()[0])
        violations = connection.execute(
            """SELECT
            (SELECT count(*) FROM members WHERE ends_with(upper(ts_code), '.BJ')) AS bse,
            (SELECT count(*) FROM (
              SELECT trade_date, universe_id, ts_code FROM members GROUP BY ALL HAVING count(*) > 1
            )) AS duplicate_keys,
            (SELECT count(*) FROM members m JOIN members s USING (trade_date, ts_code)
              WHERE m.universe_id=? AND s.universe_id=?) AS child_overlap,
            (SELECT count(*) FROM members c LEFT JOIN members a
              ON c.trade_date=a.trade_date AND c.ts_code=a.ts_code AND a.universe_id=?
              WHERE c.universe_id IN (?, ?) AND a.ts_code IS NULL) AS child_outside""",
            [POOL_IDS["midcap"], POOL_IDS["smallcap"], *POOL_IDS.values()],
        ).fetchone()
        if full_rows != int(upstream["membership_rows"]) or any(int(value) for value in violations):
            raise D1ControlError("M3-1 membership structure or .BJ gate failed")
        rows = connection.execute(
            """SELECT universe_id, count(*) AS row_count,
            count(DISTINCT trade_date) AS trade_days, count(DISTINCT ts_code) AS names,
            min(daily_count) AS min_daily, max(daily_count) AS max_daily
            FROM (
              SELECT universe_id, trade_date, ts_code,
              count(*) OVER (PARTITION BY universe_id, trade_date) AS daily_count
              FROM members WHERE trade_date BETWEEN ? AND ?
            ) GROUP BY universe_id ORDER BY universe_id""",
            [start, end],
        ).fetchall()
        sealed = connection.execute(
            """SELECT universe_id, count(DISTINCT trade_date)
            FROM members WHERE trade_date BETWEEN ? AND ? GROUP BY universe_id""",
            [sealed_start, sealed_end],
        ).fetchall()
    finally:
        connection.close()
    by_pool = {str(row[0]): row for row in rows}
    expected_rows = data["discovery_member_days_expected"]
    expected_names = data["discovery_distinct_names_expected"]
    expected_range = data["discovery_daily_member_range"]
    for pool_id in POOL_IDS.values():
        row = by_pool.get(pool_id)
        if row is None or (
            int(row[1]) != int(expected_rows[pool_id])
            or int(row[2]) != int(data["discovery_trade_days_expected"])
            or int(row[3]) != int(expected_names[pool_id])
            or [int(row[4]), int(row[5])] != list(expected_range[pool_id])
        ):
            raise D1ControlError(f"M3-1 discovery membership differs: {pool_id}")
    sealed_days = {str(pool): int(days) for pool, days in sealed}
    if set(sealed_days) != set(POOL_IDS.values()) or any(
        days != int(data["sealed_validation_trade_days_expected"])
        for days in sealed_days.values()
    ):
        raise D1ControlError("M3-1 sealed membership clock differs")
    discovery_rows = {pool: int(by_pool[pool][1]) for pool in sorted(by_pool)}
    payload = {
        "protocol_sha256": protocol.sha256,
        "upstream_manifest_sha256": upstream["m3_data_manifest_sha256"],
        "selected_input_sha256": upstream["selected_input_sha256"],
        "membership_sha256": upstream["membership_sha256"],
        "discovery_period": data["discovery_signal_period"],
        "sealed_period": data["sealed_validation_period"],
        "discovery_rows": discovery_rows,
    }
    return M3InputIdentity(
        snapshot_sha256=_canonical_sha256(payload),
        membership_sha256=sha256_file(membership_path),
        full_rows=full_rows,
        discovery_trade_days=int(data["discovery_trade_days_expected"]),
        discovery_rows=discovery_rows,
        sealed_trade_days=int(data["sealed_validation_trade_days_expected"]),
    )
