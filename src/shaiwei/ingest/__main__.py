"""`python -m shaiwei.ingest` command line entry point."""

import argparse
import json
from datetime import date

from shaiwei.config import load
from shaiwei.ingest.catalog import canonical_params_key, committed_params_keys, load_latest_api
from shaiwei.ingest.core import RawBatchWriter
from shaiwei.ingest.tushare import (
    TushareIngestor,
    build_bootstrap_plan,
    build_financial_plan,
    build_market_plan,
    build_namechange_plan,
    create_client,
    public_request_params,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="筛微阶段 0 不可变数据采集")
    parser.add_argument(
        "--stage", choices=("bootstrap", "namechange", "market", "financial"), default="bootstrap"
    )
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--dry-run", action="store_true", help="只打印请求计划，不读取 token、不访问网络")
    parser.add_argument("--resume", action="store_true", help="跳过账本中同参数且文件哈希完整的已提交请求")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load()
    if args.stage == "bootstrap":
        plan = build_bootstrap_plan(settings, args.as_of)
    else:
        stock_basic = load_latest_api("tushare.stock_basic")
        builders = {
            "namechange": build_namechange_plan,
            "market": build_market_plan,
            "financial": build_financial_plan,
        }
        builder = builders[args.stage]
        plan = builder(settings, args.as_of, stock_basic)
    planned_count = len(plan)
    if args.resume:
        keys_by_api = {
            api: committed_params_keys(f"tushare.{api}")
            for api in {request.api_name for request in plan}
        }
        plan = [
            request
            for request in plan
            if canonical_params_key(public_request_params(request)) not in keys_by_api[request.api_name]
        ]
    if args.dry_run:
        summary = {
            "stage": args.stage,
            "as_of": args.as_of.isoformat(),
            "planned_request_count": planned_count,
            "request_count": len(plan),
            "skipped_committed_count": planned_count - len(plan),
            "requests_by_api": {
                api: sum(request.api_name == api for request in plan)
                for api in sorted({request.api_name for request in plan})
            },
        }
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0

    if not plan:
        print(json.dumps({"batch_count": 0, "row_count": 0, "skipped_committed_count": planned_count}))
        return 0

    secret = settings.runtime.tushare_token
    if secret is None or not secret.get_secret_value().strip():
        raise SystemExit("TUSHARE_TOKEN is missing; create local .env from .env.example (do not commit it)")
    ingestor = TushareIngestor(
        client=create_client(secret.get_secret_value()),
        writer=RawBatchWriter(settings.runtime.data_root),
        settings=settings,
    )
    batches = ingestor.run(plan)
    print(json.dumps({"batch_count": len(batches), "row_count": sum(batch.row_count for batch in batches)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
