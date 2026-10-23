"""巡检配置 schema（ADR 0020）；独立成模块，巡检容器的健康检查无需导入 pandas 与日链代码。"""

from __future__ import annotations

from datetime import time
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from shaiwei.config import PROJECT_ROOT

CONFIG_PATH = PROJECT_ROOT / "config" / "ops_patrol_v1.yaml"
Mode = Literal["host", "container"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Containers(FrozenModel):
    scheduler: str
    web: tuple[str, ...]
    patrol: str | None = None  # 巡检容器部署后填写，宿主巡检由此看守巡检


class WebProbe(FrozenModel):
    host_base: str
    container_base: str
    paths: tuple[str, ...] = Field(min_length=1)
    timeout_seconds: float = Field(gt=0, le=30)


class ServiceConfig(FrozenModel):
    interval_minutes: int = Field(ge=1, le=60)
    wake_check_seconds: int = Field(ge=5, le=300)
    resume_gap_intervals: int = Field(ge=2, le=12)
    resume_grace_minutes: int = Field(ge=0, le=120)
    daily_message_cap: int = Field(ge=1, le=50)
    latest_stale_minutes: int = Field(ge=5, le=240)


class PatrolConfig(FrozenModel):
    schema_version: Literal["shaiwei-ops-patrol-v1"]
    patrol_id: Literal["ops-patrol-v1"]
    status: Literal["ACTIVE_READ_ONLY"]
    timezone: Literal["Asia/Shanghai"]
    chain_deadline_local: time
    lookback_open_days: int = Field(ge=1, le=30)
    repeated_shadow_fail_threshold: int = Field(ge=2, le=50)
    ledger_backlog_warn_lines: int = Field(ge=100)
    disk_free_warn_gb: int = Field(ge=1)
    containers: Containers
    scheduler_current_tag: str
    accounts: tuple[str, ...] = Field(min_length=1)
    web_probe: WebProbe
    service: ServiceConfig


def load_config(path: Path = CONFIG_PATH) -> PatrolConfig:
    return PatrolConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
