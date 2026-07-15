"""Fail-closed Day 0-7 runner.  It never contains a stage-1 command."""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ledger import ingest_snapshot_sha256
from shaiwei.provenance import code_snapshot_sha256


@dataclass(frozen=True)
class Step:
    name: str
    description: str
    argv: tuple[str, ...]


def steps(as_of: date) -> list[Step]:
    python = sys.executable
    day = as_of.isoformat()
    return [
        Step("quality", "离线测试与账本追加约束", (python, "-m", "pytest", "-q")),
        Step(
            "runtime",
            "关键运行时导入",
            (python, "-c", "import qlib,lightgbm,tushare,akshare,torch; print('runtime OK')"),
        ),
        Step("bootstrap", "基础表采集", (python, "-m", "shaiwei.ingest", "--stage", "bootstrap", "--as-of", day, "--resume")),
        Step(
            "suspensions",
            "按交易日采集停复牌记录",
            (python, "-m", "shaiwei.ingest", "--stage", "suspensions", "--as-of", day, "--resume"),
        ),
        Step(
            "namechange",
            "逐票无日期参数采集历史名称",
            (python, "-m", "shaiwei.ingest", "--stage", "namechange", "--as-of", day, "--resume"),
        ),
        Step(
            "corporate_actions",
            "逐票采集分红送股与除权日",
            (python, "-m", "shaiwei.ingest", "--stage", "corporate-actions", "--as-of", day, "--resume"),
        ),
        Step(
            "industry_membership",
            "逐票采集申万行业历史区间",
            (python, "-m", "shaiwei.ingest", "--stage", "industry-membership", "--as-of", day, "--resume"),
        ),
        Step("market", "全市场行情/复权/市值采集", (python, "-m", "shaiwei.ingest", "--stage", "market", "--as-of", day, "--resume")),
        Step(
            "financial",
            "三大财务报表采集",
            (python, "-m", "shaiwei.ingest", "--stage", "financial", "--as-of", day, "--resume"),
        ),
        Step(
            "financial_corrections",
            "按季度补采三大报表更正前值",
            (
                python, "-m", "shaiwei.ingest", "--stage", "financial-corrections",
                "--as-of", day, "--resume",
            ),
        ),
        Step("crosscheck", "AKShare 独立源样本", (python, "-m", "shaiwei.ingest.akshare", "--as-of", day, "--resume")),
        Step("sentinel", "S1-S10 全量门禁", (python, "-m", "shaiwei.sentinel")),
        Step("qlib", "构建带 PIT 涨跌停字段的 qlib bin", (python, "-m", "shaiwei.transform.qlib_bin")),
        Step("baseline", "六窗口 Alpha158+LightGBM G0 基线", (python, "-m", "shaiwei.backtest.baseline")),
        Step("shadow", "生成不可覆盖影子信号", (python, "-m", "shaiwei.shadow", "--as-of", day)),
        Step("alphagen", "AlphaGen 单轮 CPU benchmark", (python, "-m", "shaiwei.benchmark.alphagen_cpu")),
        Step("audit", "汇总 G0 与两项动手证据", (python, "-m", "shaiwei.audit.g0")),
    ]


def _append_event(path: Path, event: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _completed_steps(path: Path, *, code_hash: str, data_hash: str, as_of: date) -> set[str]:
    if not path.is_file():
        return set()
    completed = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if (
            event.get("status") == "PASS"
            and event.get("code_snapshot_sha256") == code_hash
            and event.get("data_snapshot_sha256") == data_hash
            and event.get("as_of") == as_of.isoformat()
        ):
            completed.add(str(event["step"]))
    return completed


def _selected(all_steps: list[Step], start: str | None, through: str | None) -> list[Step]:
    names = [step.name for step in all_steps]
    first = names.index(start) if start else 0
    last = names.index(through) + 1 if through else len(names)
    if first >= last:
        raise ValueError("--from-step must not be after --through-step")
    return all_steps[first:last]


def main() -> int:
    all_steps = steps(date.today())
    names = [step.name for step in all_steps]
    parser = argparse.ArgumentParser(description="筛微阶段 0 可中断续跑施工流")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--plan", action="store_true", help="只显示步骤和就绪状态")
    parser.add_argument("--no-resume", action="store_true", help="忽略流水线成功事件；采集仍按账本去重")
    parser.add_argument("--from-step", choices=names)
    parser.add_argument("--through-step", choices=names)
    args = parser.parse_args()
    settings = load()
    all_steps = steps(args.as_of)
    selected = _selected(all_steps, args.from_step, args.through_step)
    token_ready = bool(settings.runtime.tushare_token and settings.runtime.tushare_token.get_secret_value().strip())
    plan = {
        "as_of": args.as_of.isoformat(),
        "environment": settings.runtime.environment,
        "data_root": str(settings.runtime.data_root),
        "tushare_token_ready": token_ready,
        "steps": [
            {"name": step.name, "description": step.description, "command": list(step.argv)} for step in selected
        ],
        "stop_policy": "first non-zero exit; audit never invokes stage 1",
    }
    if args.plan:
        print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    ingest_steps = {
        "bootstrap", "suspensions", "namechange", "corporate_actions",
        "industry_membership", "market", "financial",
        "financial_corrections",
    }
    if any(step.name in ingest_steps for step in selected) and not token_ready:
        raise SystemExit("TUSHARE_TOKEN is missing from local .env; fill it locally, then rerun the same command")

    code_hash = code_snapshot_sha256()
    log_path = PROJECT_ROOT / "logs/pipeline" / f"stage0_{args.as_of:%Y%m%d}.jsonl"
    current_data_hash = ingest_snapshot_sha256()
    completed = (
        set()
        if args.no_resume
        else _completed_steps(log_path, code_hash=code_hash, data_hash=current_data_hash, as_of=args.as_of)
    )
    for step in selected:
        if step.name in completed:
            print(json.dumps({"step": step.name, "status": "SKIP_RESUMED"}, ensure_ascii=False))
            continue
        started = datetime.now(timezone.utc)
        common = {
            "step": step.name,
            "as_of": args.as_of.isoformat(),
            "code_snapshot_sha256": code_hash,
            "command": list(step.argv),
        }
        _append_event(log_path, {**common, "status": "START", "ts": started.isoformat()})
        result = subprocess.run(step.argv, cwd=PROJECT_ROOT)
        finished = datetime.now(timezone.utc)
        status = "PASS" if result.returncode == 0 else "FAIL"
        _append_event(
            log_path,
            {
                **common,
                "status": status,
                "ts": finished.isoformat(),
                "elapsed_seconds": (finished - started).total_seconds(),
                "returncode": result.returncode,
                "data_snapshot_sha256": ingest_snapshot_sha256(),
            },
        )
        if result.returncode != 0:
            print(json.dumps({"step": step.name, "status": status, "returncode": result.returncode}))
            return result.returncode
    print(json.dumps({"status": "PASS", "completed_steps": [step.name for step in selected]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
