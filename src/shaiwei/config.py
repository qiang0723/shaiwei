"""配置加载与 schema 校验：所有代码只准从这里取配置，禁止散落的魔法数字。"""
import hashlib
import os
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Runtime(BaseModel):
    data_root: Path
    environment: Literal["dev", "prod"]
    tushare_token: SecretStr | None = None


class Notifications(BaseModel):
    feishu_enabled: bool = False
    feishu_webhook_url: SecretStr | None = None
    feishu_signing_secret: SecretStr | None = None
    timeout_seconds: float = Field(gt=0, le=60)
    max_attempts: int = Field(ge=1, le=5)
    retry_base_seconds: float = Field(ge=0, le=10)
    heartbeat_seconds: int = Field(ge=60, le=86400)

    @model_validator(mode="after")
    def validate_feishu_credentials(self) -> "Notifications":
        if self.feishu_enabled and not (self.feishu_webhook_url and self.feishu_signing_secret):
            raise ValueError("enabled Feishu alerts require webhook URL and signing secret")
        return self


class Universe(BaseModel):
    index_code: str
    include_bse: bool

class Backtest(BaseModel):
    start: date
    benchmark: str
    rebalance_days: int = Field(ge=1)
    topk: int = Field(gt=0)
    n_drop: int = Field(gt=0)
    deal_price: Literal["open"]
    open_cost: float = Field(ge=0)
    close_cost: float = Field(ge=0)
    min_cost: float = Field(ge=0)
    cost_scenarios: list[float]

    @model_validator(mode="after")
    def validate_cross_fields(self) -> "Backtest":
        if self.n_drop > self.topk:
            raise ValueError("n_drop must be <= topk")
        if not self.cost_scenarios or any(x <= 0 for x in self.cost_scenarios):
            raise ValueError("cost_scenarios must contain positive multipliers")
        if 1.0 not in self.cost_scenarios:
            raise ValueError("cost_scenarios must include the baseline 1.0 scenario")
        return self

class LimitRules(BaseModel):
    main: float
    chinext_before_20200824: float
    chinext_after_20200824: float
    star: float
    st: float
    price_tick_tolerance: float

class Compute(BaseModel):
    joblib_max_procs: int = Field(ge=1, le=8, description="M5 24G 上限，改动须先改 STATE.md 口径")


class Ingest(BaseModel):
    max_attempts: int = Field(ge=1, le=10)
    retry_base_seconds: float = Field(ge=0, le=60)
    min_request_interval_seconds: float = Field(ge=0, le=10)
    max_concurrent_requests: int = Field(ge=1, le=8)
    source_row_limit: int = Field(gt=0)
    history_window_years: int = Field(ge=1, le=20)


class DailyPipeline(BaseModel):
    poll_seconds: int = Field(ge=60, le=3600)
    ready_hour: int = Field(ge=0, le=23)
    ready_minute: int = Field(ge=0, le=59)
    max_catchup_trade_days: int = Field(ge=1, le=120)
    min_market_rows: int = Field(ge=1000, le=6000)
    health_stale_seconds: int = Field(ge=300, le=86400)


class ShadowPipeline(BaseModel):
    enabled: bool = True
    signal_deadline_hour: int = Field(ge=0, le=23)
    signal_deadline_minute: int = Field(ge=0, le=59)
    qlib_versions_to_keep: int = Field(ge=2, le=10)
    trial_trade_days: int = Field(ge=1, le=20)


class PaperPortfolio(BaseModel):
    enabled: bool = True
    account_id: Literal["model_baseline"]
    initial_cash: float = Field(gt=0)
    currency: Literal["RMB"]
    benchmark: str
    execution_policy_version: Literal["paper-v1"]
    forward_start_date: date
    commission_rate: float = Field(ge=0, le=0.003)
    minimum_commission: float = Field(ge=0)
    stamp_tax_rate: float = Field(ge=0, le=0.001)
    transfer_fee_rate: float = Field(ge=0, le=0.001)
    main_board_lot_size: int = Field(ge=1)
    star_minimum_lot: int = Field(ge=1)
    st_main_ten_percent_effective: date
    stale_price_trade_days: int = Field(ge=1, le=120)
    accounting_tolerance: float = Field(gt=0, le=1)


class PaperTop20Portfolio(PaperPortfolio):
    """Independent comparison account over a deterministic baseline-signal projection."""

    account_id: Literal["model_top20"]
    execution_policy_version: Literal["paper-top20-v1"]
    source_account_id: Literal["model_baseline"]
    source_signal_topk: Literal[30]
    target_topk: Literal[20]
    target_projection: Literal["rank_head_equal_weight"]
    target_weight: float = Field(gt=0, lt=1)
    rebalance_days: Literal[10]

    @model_validator(mode="after")
    def validate_projection_weights(self) -> "PaperTop20Portfolio":
        if abs(self.target_topk * self.target_weight - 1.0) > 1e-12:
            raise ValueError("Top20 target weights must sum exactly to one")
        return self


class PaperTop20ResultFirewall(BaseModel):
    strategy_results_inspected_before_freeze: Literal[False]
    baseline_account_must_remain_byte_immutable: Literal[True]
    production_scheduler_must_remain_on_last_good_release_until_acceptance: Literal[True]
    strategy_effective: Literal["NOT_EVALUATED"]


class PaperTop20Protocol(BaseModel):
    schema_version: Literal["paper-comparison-account-protocol-v1"]
    protocol_id: Literal["paper-top20-v1.2"]
    protocol_status: Literal["FROZEN_BEFORE_RESULTS"]
    frozen_on: date
    production_authorization: Literal["PENDING_ENGINEERING_ACCEPTANCE"]
    paper_portfolio: PaperTop20Portfolio
    result_firewall: PaperTop20ResultFirewall


class PaperTop20Release(BaseModel):
    schema_version: Literal["paper-comparison-account-release-v1"]
    release_id: Literal["paper-top20-scheduler-v1"]
    status: Literal["PAPER_ONLY_AUTHORIZED"]
    account_id: Literal["model_top20"]
    protocol_path: Literal["config/paper_top20_v1.yaml"]
    protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorized_on: date
    broker_connection: Literal[False]
    strategy_effective: Literal["NOT_EVALUATED"]


class G1Admission(BaseModel):
    """Pre-registered Stage-1 factor admission thresholds."""

    spec_version: Literal["g1-v1"]
    dsr_probability_threshold: float = Field(gt=0.5, lt=1)
    hac_t_threshold: float = Field(gt=0)
    hac_lags: int = Field(ge=1, le=60)
    min_observations: int = Field(ge=60)
    min_valid_trial_sharpes: int = Field(ge=2)
    max_expression_tokens: int = Field(ge=1)
    max_ast_nodes: int = Field(ge=1)
    min_economic_rationale_chars: int = Field(ge=10)
    max_library_abs_correlation: float = Field(gt=0, lt=1)
    min_positive_windows: int = Field(ge=1)
    min_rank_ic_retention: float = Field(gt=0, le=1)
    max_stress_drawdown: float = Field(gt=0, lt=1)
    max_turnover_ratio: float = Field(ge=1)
    discovery_start: date
    discovery_end: date
    factor_blend_weight: float = Field(gt=0, lt=0.5)
    slippage_stress_extra_each_side: float = Field(ge=0)
    promoted_candidates: int = Field(ge=2, le=10)

    @model_validator(mode="after")
    def validate_discovery_period(self) -> "G1Admission":
        if self.discovery_start >= self.discovery_end:
            raise ValueError("G1 discovery_start must be before discovery_end")
        return self


class G8Evaluation(BaseModel):
    """Pre-registered, no-leverage risk matching for the three-year G8 verdict."""

    spec_version: Literal["g8-v1"]
    comparator_freeze_date: date
    annualization_days: int = Field(ge=200, le=366)
    volatility_lookback_days: int = Field(ge=20, le=252)
    minimum_annualized_volatility: float = Field(gt=0, lt=0.2)
    minimum_risk_coverage: float = Field(gt=0.8, le=1)
    minimum_evaluation_observations: int = Field(ge=600, le=800)
    required_fund_count: int = Field(ge=3, le=20)
    minimum_positive_funds: int = Field(ge=1)
    required_subperiods: int = Field(ge=2, le=6)
    minimum_positive_subperiods: int = Field(ge=1)
    maximum_risk_weight: Literal[1.0]
    residual_cash_daily_return: Literal[0.0]

    @model_validator(mode="after")
    def validate_thresholds(self) -> "G8Evaluation":
        if self.minimum_positive_funds > self.required_fund_count:
            raise ValueError("G8 minimum_positive_funds exceeds required_fund_count")
        if self.minimum_positive_subperiods > self.required_subperiods:
            raise ValueError("G8 minimum_positive_subperiods exceeds required_subperiods")
        return self


class Crosscheck(BaseModel):
    symbols: list[str] = Field(min_length=4)
    lookback_calendar_days: int = Field(ge=30, le=365)

    @model_validator(mode="after")
    def validate_symbols(self) -> "Crosscheck":
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("crosscheck symbols must be unique")
        if any("." not in symbol for symbol in self.symbols):
            raise ValueError("crosscheck symbols must use Tushare codes")
        return self


class ReverseAdjustmentSamples(BaseModel):
    blue_chip: str
    corporate_action: str
    delisted: str
    long_suspension: str


class Sentinels(BaseModel):
    dual_calculation_max_securities: int = Field(ge=4, le=256)
    reverse_adjustment_samples: ReverseAdjustmentSamples


class Baseline(BaseModel):
    instrument: str
    validation_months: int = Field(ge=1, le=12)
    account: float = Field(gt=0)
    seed: int = Field(ge=0)
    learning_rate: float = Field(gt=0, le=1)
    num_leaves: int = Field(ge=2)
    max_depth: int
    colsample_bytree: float = Field(gt=0, le=1)
    subsample: float = Field(gt=0, le=1)
    reg_alpha: float = Field(ge=0)
    reg_lambda: float = Field(ge=0)
    num_boost_round: int = Field(gt=0)
    early_stopping_rounds: int = Field(gt=0)


class AlphaGenBenchmark(BaseModel):
    instrument: str
    index_code: str
    train_start: date
    train_end: date
    population_size: int = Field(gt=1)
    generations: int = Field(gt=0)
    tournament_size: int = Field(gt=1)
    max_expression_tokens: int = Field(gt=0)
    seed: int = Field(ge=0)
    min_cross_section: int = Field(ge=5)
    min_daily_ic_observations: int = Field(ge=60)
    rank_ic_threshold: float
    scale_time_hours: float = Field(gt=0)
    abort_time_hours: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_benchmark(self) -> "AlphaGenBenchmark":
        if self.train_start >= self.train_end:
            raise ValueError("alphagen train_start must be before train_end")
        if self.tournament_size > self.population_size:
            raise ValueError("alphagen tournament_size must not exceed population_size")
        if self.abort_time_hours <= self.scale_time_hours:
            raise ValueError("alphagen abort_time_hours must exceed scale_time_hours")
        return self


class EvaluationWindow(BaseModel):
    name: str
    train_start: date
    train_end: date
    test_start: date
    test_end: date

    @model_validator(mode="after")
    def validate_dates(self) -> "EvaluationWindow":
        if not self.train_start <= self.train_end < self.test_start <= self.test_end:
            raise ValueError(f"invalid chronological window: {self.name}")
        return self


class StressPeriod(BaseModel):
    name: str
    start: date
    end: date


class Evaluation(BaseModel):
    g0_windows: list[EvaluationWindow] = Field(min_length=6, max_length=6)
    stress_periods: list[StressPeriod] = Field(min_length=3, max_length=3)
    forward_oos_start: date

class Settings(BaseModel):
    runtime: Runtime
    notifications: Notifications
    universe: Universe
    backtest: Backtest
    limit_rules: LimitRules
    compute: Compute
    ingest: Ingest
    daily: DailyPipeline
    shadow_pipeline: ShadowPipeline
    paper_portfolio: PaperPortfolio
    g1_admission: G1Admission
    g8_evaluation: G8Evaluation
    crosscheck: Crosscheck
    sentinels: Sentinels
    baseline: Baseline
    alphagen_benchmark: AlphaGenBenchmark
    evaluation: Evaluation

    @model_validator(mode="after")
    def validate_g1_timeline(self) -> "Settings":
        first_test = min(window.test_start for window in self.evaluation.g0_windows)
        if self.g1_admission.discovery_end >= first_test:
            raise ValueError("G1 discovery period must end before the first frozen OOS window")
        return self


def load(path: str | Path | None = None) -> Settings:
    config_path = Path(path) if path is not None else PROJECT_ROOT / "config/settings.yaml"
    config_path = config_path.resolve()
    project_root = config_path.parent.parent
    load_dotenv(project_root / ".env", override=False)

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    runtime = raw.setdefault("runtime", {})
    runtime["data_root"] = os.getenv("SHAIWEI_DATA_ROOT", runtime.get("data_root", "./data"))
    runtime["environment"] = os.getenv("SHAIWEI_ENV", runtime.get("environment", "dev"))
    runtime["tushare_token"] = os.getenv("TUSHARE_TOKEN") or None
    notifications = raw.setdefault("notifications", {})
    enabled = os.getenv("FEISHU_ALERTS_ENABLED")
    if enabled is not None:
        notifications["feishu_enabled"] = enabled.strip().lower() in {"1", "true", "yes", "on"}
    notifications["feishu_webhook_url"] = os.getenv("FEISHU_WEBHOOK_URL") or None
    notifications["feishu_signing_secret"] = os.getenv("FEISHU_SIGNING_SECRET") or None
    if timeout := os.getenv("FEISHU_TIMEOUT_SECONDS"):
        notifications["timeout_seconds"] = float(timeout)
    if max_attempts := os.getenv("FEISHU_MAX_ATTEMPTS"):
        notifications["max_attempts"] = int(max_attempts)
    if retry_base := os.getenv("FEISHU_RETRY_BASE_SECONDS"):
        notifications["retry_base_seconds"] = float(retry_base)
    if heartbeat := os.getenv("FEISHU_HEARTBEAT_SECONDS"):
        notifications["heartbeat_seconds"] = int(heartbeat)
    data_root = Path(runtime["data_root"])
    runtime["data_root"] = data_root if data_root.is_absolute() else (project_root / data_root).resolve()
    return Settings.model_validate(raw)


def load_paper_top20_protocol(path: str | Path | None = None) -> PaperTop20Protocol:
    """Load the result-before Top20 protocol without reading environment secrets."""
    config_path = (
        Path(path)
        if path is not None
        else PROJECT_ROOT / "config" / "paper_top20_v1.yaml"
    )
    raw = yaml.safe_load(config_path.resolve().read_text(encoding="utf-8"))
    return PaperTop20Protocol.model_validate(raw)


def load_paper_top20_release(path: str | Path | None = None) -> PaperTop20Release:
    """Load a distinct post-engineering scheduler authorization and bind its protocol."""
    release_path = (
        Path(path)
        if path is not None
        else PROJECT_ROOT / "config" / "paper_top20_release_v1.yaml"
    ).resolve()
    raw = yaml.safe_load(release_path.read_text(encoding="utf-8"))
    release = PaperTop20Release.model_validate(raw)
    protocol_path = PROJECT_ROOT / release.protocol_path
    digest = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    if digest != release.protocol_sha256:
        raise ValueError("Top20 scheduler release does not bind the frozen protocol")
    return release
