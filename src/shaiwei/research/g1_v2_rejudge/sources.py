"""各家族原始因子重建与复现门（协议 §3.1）：先按 v1 口径重算并复现 v1 落盘物，通过后才把原始因子交给 g1-v2。

复现只证明“原始因子重建忠实”，不计算任何 g1-v2 统计量。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from shaiwei.config import PROJECT_ROOT, Settings
from shaiwei.research.factor_portfolio import daily_rank_ic
from shaiwei.research.g1_calibration import controls
from shaiwei.research.g1_pipeline import ResearchData
from shaiwei.research.g1_v2_rejudge.protocol import Candidate

# v1 时期缓存的 Alpha158 OOS 预测（F 家族冻结配置绑定其哈希；P1 当年写出同一文件）：复现时用它做基线正交化。
PREDICTION_CACHE = PROJECT_ROOT / "data" / "research" / "moneyflow" / "residuals" / "p1-moneyflow-alpha158-predictions-v1-46a24aad0c21e2df.parquet"
PREDICTION_CACHE_SHA256 = "46a24aad0c21e2df054b2f4ba9d58ffebbadaf8bf9a811318fedd836663cc38a"
OOS_START, OOS_END = "20190101", "20241231"
F_PROTOCOLS = {
    "f1-csi800-fundamental-v1": PROJECT_ROOT / "config" / "f1_csi800_fundamental_effect_v1.yaml",
    "f2-csi800-fundamental-dynamics-v1": PROJECT_ROOT / "config" / "f2_csi800_fundamental_effect_v1.yaml",
}


@dataclass(frozen=True)
class Reconstruction:
    family: str
    candidate: Candidate
    raw: pd.Series | None
    reproduction: dict[str, object]
    v1: dict[str, object] = field(default_factory=dict)  # v1 证据中的经济含义、复杂度、PIT/shift、多重检验家族

    @property
    def reproduced(self) -> bool:
        return self.reproduction.get("status") == "PASS"


def v1_metadata(candidate: Candidate) -> dict[str, object]:
    evidence = json.loads((PROJECT_ROOT / candidate.v1_evidence_path).read_text(encoding="utf-8"))
    tests = json.loads((PROJECT_ROOT / evidence["integrity"]["test_report_path"]).read_text(encoding="utf-8"))
    return {
        "economic_rationale": evidence["economic_rationale"],
        "complexity": evidence["complexity"],
        "pit_sentinel_pass": bool(tests["pit_sentinel_pass"]),
        "shift_sentinel_pass": bool(tests["shift_sentinel_pass"]),
        "multiple_testing_families": list(evidence.get("multiple_testing_families") or ()),
        "v1_in_sample_rank_ic": float(evidence["rank_ic"]["in_sample"]),
    }


def compare_series(rebuilt: pd.Series, stored: pd.Series, *, tolerance: float) -> dict[str, object]:
    """复现门：键集合必须一致，逐键最大绝对差 ≤ 容差。"""
    rebuilt, stored = rebuilt.dropna().sort_index(), stored.dropna().sort_index()
    missing = stored.index.difference(rebuilt.index)
    extra = rebuilt.index.difference(stored.index)
    common = stored.index.intersection(rebuilt.index)
    difference = float(np.max(np.abs(rebuilt.loc[common].to_numpy() - stored.loc[common].to_numpy()))) if len(common) else float("inf")
    passed = len(missing) == 0 and len(extra) == 0 and difference <= tolerance
    return {
        "status": "PASS" if passed else "FAIL", "max_abs_difference": difference, "compared": int(len(common)),
        "missing_keys": int(len(missing)), "extra_keys": int(len(extra)), "tolerance": tolerance,
    }


def rebuild_gp(
    candidate: Candidate,
    research: ResearchData,
    *,
    min_cross_section: int,
    tolerance: float,
    expression_values: Callable[[str, object], pd.Series] = controls.raw_expression_values,
) -> Reconstruction:
    """GP：冻结表达式 → 原始值；v1 中性化后须复现 v1 因子面板（中性化残差）。"""
    raw = expression_values(candidate.formula, research.stock_data)
    residual, _ = controls.neutralize(raw, research, min_cross_section=min_cross_section)
    panel = pd.read_parquet(PROJECT_ROOT / candidate.reproduction_target.path)
    stored = panel.set_index(["datetime", "instrument"])["factor"]
    stored.index = stored.index.set_names(["datetime", "instrument"])
    return Reconstruction("stage1-gp-preflight-v1", candidate, raw, compare_series(residual, stored, tolerance=tolerance), v1_metadata(candidate))


def stored_factor_ic(candidate: Candidate, name: str) -> pd.Series:
    frame = pd.read_parquet(PROJECT_ROOT / candidate.reproduction_target.path)
    frame = frame.loc[frame["candidate"].eq(name) & frame["series_type"].eq("factor") & frame["window"].eq("ALL")]
    return pd.Series(frame["rank_ic"].to_numpy(dtype=float), index=pd.to_datetime(frame["trade_date"], format="%Y%m%d")).sort_index()


def load_prediction_cache() -> pd.DataFrame:
    from shaiwei.ledger import sha256_file

    if sha256_file(PREDICTION_CACHE) != PREDICTION_CACHE_SHA256:
        raise ValueError("v1 Alpha158 prediction cache changed")
    predictions = pd.read_parquet(PREDICTION_CACHE)
    predictions["trade_date"] = predictions["trade_date"].astype(str)
    return predictions


@dataclass
class FundamentalInputs:
    """F1/F2 冻结输入：按家族协议读一次，供该家族全部候选复用。"""

    protocol: object
    exposed: pd.DataFrame
    formal: pd.DataFrame
    labels: pd.Series


def load_fundamental_inputs(family: str, settings: Settings) -> FundamentalInputs:
    from shaiwei.ingest.catalog import load_latest_api
    from shaiwei.research.fundamental_effect.metrics import load_labels
    from shaiwei.research.fundamental_effect.panel import (
        _open_days,
        attach_pit_exposures,
        expand_monthly_features,
        formalize_panel,
        residualize_candidates,
    )

    if family == "f1-csi800-fundamental-v1":
        from shaiwei.research.fundamental_effect.contract import FundamentalEffectProtocol as Protocol
    else:
        from shaiwei.research.fundamental_dynamics_effect_contract import FundamentalDynamicsEffectProtocol as Protocol
    protocol = Protocol.load(F_PROTOCOLS[family])
    names = tuple(spec.name for spec in protocol.candidates)
    bindings = protocol.document["input_bindings"]
    features = pd.read_parquet(protocol.project_path(str(bindings["fundamental_feature_panel"]["path"])))
    frames = {source: load_latest_api(source) for source in protocol.required_apis}
    open_days = _open_days(frames["tushare.trade_cal"], "19000101", "20260731")
    expanded = expand_monthly_features(features, open_days, start_date="20160701", end_date="20260630", candidate_names=names)
    exposed = attach_pit_exposures(expanded, frames["tushare.daily_basic"], frames["tushare.index_member_all"])
    core = residualize_candidates(exposed, candidate_names=names, include_baseline_score=False)
    predictions = load_prediction_cache().loc[:, ["trade_date", "ts_code", "baseline_score"]]
    incremental_input = exposed.merge(predictions, on=["trade_date", "ts_code"], how="inner", validate="one_to_one")
    incremental = residualize_candidates(incremental_input, candidate_names=names, include_baseline_score=True)
    formal = formalize_panel(core, incremental, oos_start=OOS_START, oos_end=OOS_END)
    return FundamentalInputs(protocol=protocol, exposed=exposed, formal=formal, labels=load_labels(settings))


def rebuild_fundamental(family: str, candidate: Candidate, inputs: FundamentalInputs, *, tolerance: float) -> Reconstruction:
    """F1/F2：月度特征按冻结口径展开到日 → v1 正式残差（OOS 内对基线正交）→ v1 标签上的日频 RankIC 须复现落盘 factor/ALL。"""
    from shaiwei.research.fundamental_effect.metrics import factor_series
    from shaiwei.research.fundamental_effect.panel import ts_code_to_qlib

    # 实验总账存的是冻结公式文本；按家族协议把公式映射回候选名，唯一匹配才继续。
    matches = [spec.name for spec in inputs.protocol.candidates if spec.formula == candidate.formula]  # type: ignore[attr-defined]
    if len(matches) != 1:
        raise ValueError(f"{family} formula does not map to exactly one frozen candidate: {candidate.formula}")
    name = matches[0]
    rebuilt_ic = daily_rank_ic(factor_series(inputs.formal, name), inputs.labels)
    reproduction = compare_series(rebuilt_ic, stored_factor_ic(candidate, name), tolerance=tolerance)
    raw_frame = inputs.exposed.loc[:, ["trade_date", "ts_code", name]].dropna()
    index = pd.MultiIndex.from_arrays(
        [pd.to_datetime(raw_frame["trade_date"], format="%Y%m%d"), raw_frame["ts_code"].map(ts_code_to_qlib)],
        names=["datetime", "instrument"],
    )
    raw = pd.Series(pd.to_numeric(raw_frame[name]).to_numpy(dtype=float), index=index, name="factor").sort_index()
    return Reconstruction(family, candidate, raw, reproduction, v1_metadata(candidate))


@dataclass
class MoneyflowInputs:
    """P1：原代码（tools/p1_moneyflow）在 v1 原始候选面板上重建正式残差；raw 为原始候选值。"""

    features: pd.DataFrame
    formal: pd.DataFrame


def load_moneyflow_inputs(settings: Settings, research: ResearchData, raw_path: Path, *, min_cross_section: int) -> MoneyflowInputs:
    from shaiwei.ledger import INGEST
    from tools.p1_moneyflow.features import residualize_moneyflow_candidates
    from tools.p1_moneyflow.residual_builder import _liquidity_exposures, _universe_features, formalize_core_with_oos

    # 原 main() 会拒绝新增数据批次的总账快照；这里只调用其纯计算函数，新增批次全部晚于 v1 面板日期，不进入连接结果。
    ledger = pd.read_csv(INGEST, dtype=str, keep_default_na=False)
    exposures = _liquidity_exposures(research.exposures, ledger)
    features = _universe_features(raw_path, exposures)
    core = residualize_moneyflow_candidates(features, exposures, min_cross_section=min_cross_section, include_baseline_score=False)
    predictions = load_prediction_cache()
    incremental = []
    for window in settings.evaluation.g0_windows:  # 与原 residual_builder 相同：按冻结窗口起止筛选
        prediction = predictions.loc[predictions["window"].eq(window.name), ["ts_code", "trade_date", "baseline_score"]]
        start, end = window.test_start.strftime("%Y%m%d"), window.test_end.strftime("%Y%m%d")
        window_features = features.loc[features["trade_date"].astype(str).between(start, end)].copy()
        window_exposures = exposures.loc[exposures["trade_date"].astype(str).between(start, end)].merge(
            prediction, on=["ts_code", "trade_date"], how="inner", validate="one_to_one"
        )
        incremental.append(
            residualize_moneyflow_candidates(window_features, window_exposures, min_cross_section=min_cross_section, include_baseline_score=True)
        )
    formal = formalize_core_with_oos(core, pd.concat(incremental, ignore_index=True), oos_start=OOS_START, oos_end=OOS_END)
    return MoneyflowInputs(features=features, formal=formal)


def rebuild_moneyflow(candidate: Candidate, inputs: MoneyflowInputs, research: ResearchData, *, tolerance: float) -> Reconstruction:
    from tools.p1_moneyflow.experiment import CANDIDATE_SPECS, _factor_series

    matches = [spec.name for spec in CANDIDATE_SPECS if spec.formula == candidate.formula]
    if len(matches) != 1:
        raise ValueError(f"P1 formula does not map to exactly one frozen candidate: {candidate.formula}")
    name = matches[0]
    rebuilt_ic = daily_rank_ic(_factor_series(inputs.formal, name), research.labels)
    reproduction = compare_series(rebuilt_ic, stored_factor_ic(candidate, name), tolerance=tolerance)
    raw = _factor_series(inputs.features, name).rename("factor")
    return Reconstruction("p1-moneyflow-v1", candidate, raw, reproduction, v1_metadata(candidate))


def not_reevaluated(family: str, candidate: Candidate, reason: str) -> Reconstruction:
    return Reconstruction(family, candidate, None, {"status": "FAIL", "reason": reason}, v1_metadata(candidate))


def write_reproduction_report(path: Path, items: list[Reconstruction]) -> dict[str, object]:
    document = {
        "schema_version": 1, "scope": "reproduction only; no g1-v2 statistic computed",
        "candidates": [
            {"family": item.family, "candidate_experiment_id": item.candidate.candidate_experiment_id,
             "formula": item.candidate.formula, **item.reproduction}
            for item in items
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document
