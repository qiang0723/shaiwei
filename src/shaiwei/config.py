"""配置加载与 schema 校验：所有代码只准从这里取配置，禁止散落的魔法数字。"""
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
    source_row_limit: int = Field(gt=0)
    history_window_years: int = Field(ge=1, le=20)


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
    universe: Universe
    backtest: Backtest
    limit_rules: LimitRules
    compute: Compute
    ingest: Ingest
    evaluation: Evaluation


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
    data_root = Path(runtime["data_root"])
    runtime["data_root"] = data_root if data_root.is_absolute() else (project_root / data_root).resolve()
    return Settings.model_validate(raw)
