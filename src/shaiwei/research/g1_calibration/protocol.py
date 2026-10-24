"""严格载入冻结配置 `config/g1_positive_control_v1.yaml`，并与 `g1-v1` 规格、协议文档做身份绑定。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from shaiwei.config import PROJECT_ROOT, Settings
from shaiwei.ledger import sha256_file
from shaiwei.research.g1 import _spec_sha256

CONFIG_PATH = PROJECT_ROOT / "config" / "g1_positive_control_v1.yaml"
ADMISSION_SCOPE = "NOT_FOR_ADMISSION"
ROUTES = ("R1", "R2", "R3", "R4", "R5", "N1", "N2")
# g1-v1 裁判产出的全部 15 个门；三层划分必须恰好覆盖它们，否则失败关闭。
G1_V1_GATES = frozenset(
    {
        "pit_and_shift", "complexity", "economic_rationale", "library_correlation",
        "rolling_window_sign", "rank_ic_retention", "stress_drawdown", "turnover",
        "incremental_net_icir", "incremental_net_excess", "cost_2x", "slippage_2x",
        "valid_trial_sharpes", "deflated_sharpe", "hac_t",
    }
)


class ProtocolError(RuntimeError):
    pass


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Judge(_Frozen):
    spec_version: Literal["g1-v1"]
    spec_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ResultBlindBaseline(_Frozen):
    head_before_freeze: str = Field(pattern=r"^[0-9a-f]{40}$")
    experiments_rows: int
    calibration_family_rows: int
    factor_admission_decisions: int
    factor_admission_admitted: int
    g1_reports: int


class Layers(_Frozen):
    A_signal: tuple[str, ...]
    B_transmission: tuple[str, ...]
    report_only: tuple[str, ...]


class Calibration(_Frozen):
    discovery_start: date
    discovery_end: date
    target_mean_rank_ic: tuple[float, ...] = Field(min_length=1)
    tolerance: float = Field(gt=0)
    label: str
    rng: Literal["numpy.random.default_rng"]


class SeedRange(_Frozen):
    start: int
    count: int = Field(ge=1)

    def values(self) -> tuple[int, ...]:
        return tuple(range(self.start, self.start + self.count))


class Route(_Frozen):
    construction: str
    role: Literal["primary", "diagnostic", "report_only", "negative_control"]
    blend: str | None = None
    future_information: bool | None = None
    pit_and_shift_exempt: bool = False
    seeds: tuple[int, ...] | SeedRange | None = None
    seeds_from: str | None = None
    lookback_trade_days: int | None = None
    skip_recent_trade_days: int | None = None
    sign: int | None = None

    def seed_values(self) -> tuple[int, ...]:
        if isinstance(self.seeds, SeedRange):
            return self.seeds.values()
        return tuple(self.seeds or ())


class Dsr(_Frozen):
    main_family_scope: Literal["route_strength_cell"]
    diagnostic_trial_counts: tuple[int, ...]


class Detection(_Frozen):
    route: Literal["R1"]
    min_passing_seeds: int = Field(ge=1)
    seeds_per_strength: int = Field(ge=1)


class Interpretation(_Frozen):
    calibrated_max_strength: float
    terminal_states: tuple[str, ...]
    any_negative_control_pass_is: Literal["G1_PERMISSIVE"]


class FalsePassBound(_Frozen):
    method: Literal["clopper_pearson_one_sided"]
    confidence: float = Field(gt=0, lt=1)


class Budget(_Frozen):
    max_hours: float = Field(gt=0)
    reduction_order: tuple[dict[str, int], ...]
    never_reduce: tuple[str, ...]


class Isolation(_Frozen):
    admission_scope: Literal["NOT_FOR_ADMISSION"]
    ledger: str
    reports_dir: str
    forbidden_writes: tuple[str, ...]
    data_read_only: tuple[str, ...]
    network: Literal[False]
    secrets: Literal[False]


class PositiveControlConfig(_Frozen):
    schema_version: Literal["g1-positive-control-v1"]
    protocol_id: Literal["g1-positive-control-v1"]
    status: Literal["FROZEN_BEFORE_RESULTS"]
    frozen_on: date
    document: str
    family: Literal["g1-calibration-v1"]
    judge: Judge
    result_blind_baseline: ResultBlindBaseline
    layers: Layers
    calibration: Calibration
    routes: dict[str, Route]
    public_priors: dict[str, object]
    dsr: Dsr
    detection: Detection
    interpretation: Interpretation
    false_pass_bound: FalsePassBound
    budget: Budget
    isolation: Isolation


@dataclass(frozen=True)
class ProtocolIdentity:
    config: PositiveControlConfig
    config_path: Path
    config_sha256: str
    document_sha256: str


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ProtocolError(message)


def load_protocol(settings: Settings, path: Path = CONFIG_PATH) -> ProtocolIdentity:
    """任何一处与冻结前提不符都拒绝执行，而不是带着漂移继续跑。"""
    config = PositiveControlConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    document = PROJECT_ROOT / config.document
    _check(document.is_file(), f"protocol document is missing: {config.document}")
    _check(set(config.routes) == set(ROUTES), "routes must be exactly R1-R5, N1, N2")
    layers = config.layers
    named = [*layers.A_signal, *layers.B_transmission, *layers.report_only]
    _check(len(named) == len(set(named)) and set(named) == G1_V1_GATES, "layers must partition the 15 g1-v1 gates")
    threshold = settings.g1_admission
    _check(threshold.spec_version == config.judge.spec_version, "g1 spec version drifted")
    _check(_spec_sha256(settings) == config.judge.spec_sha256, "g1-v1 spec sha256 drifted from the frozen protocol")
    calibration = config.calibration
    _check(
        (calibration.discovery_start, calibration.discovery_end)
        == (threshold.discovery_start, threshold.discovery_end),
        "calibration discovery period must equal g1-v1 discovery period",
    )
    horizon = settings.backtest.rebalance_days + 1
    _check(calibration.label == f"Ref($open,-{horizon})/Ref($open,-1)-1", "calibration label differs from baseline label")
    primary = config.routes["R1"]
    _check(config.routes["R2"].seeds_from == "R1", "R2 must reuse R1 seeds")
    _check(len(primary.seed_values()) == config.detection.seeds_per_strength, "R1 seed count differs from detection rule")
    for route in ("N1", "N2"):
        _check(bool(config.routes[route].seed_values()), f"{route} has no seeds")
    _check(config.interpretation.calibrated_max_strength in calibration.target_mean_rank_ic, "calibrated max strength is not a ladder rung")
    return ProtocolIdentity(
        config=config,
        config_path=path,
        config_sha256=sha256_file(path),
        document_sha256=sha256_file(document),
    )


def cell_family(config: PositiveControlConfig, route: str, strength: float | None) -> str:
    """DSR 主判家族 = 路线×强度格子（协议 §5），与任何真实家族名不相交。"""
    suffix = f"/{strength:.2f}" if strength is not None else ""
    return f"{config.family}/{route}{suffix}"
