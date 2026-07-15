"""Send an explicit Feishu connectivity test using local environment secrets."""

import argparse
import json

from shaiwei.config import load
from shaiwei.notify.feishu import FeishuNotifier


def main() -> int:
    parser = argparse.ArgumentParser(description="筛微飞书告警连通性测试")
    parser.add_argument("--test", action="store_true", required=True)
    args = parser.parse_args()
    assert args.test
    notifier = FeishuNotifier(load().notifications)
    result = notifier.send("connectivity_test", "告警通道连通性测试", {"status": "正常"})
    print(json.dumps({"event": result.event, "status": result.status, "error_type": result.error_type}))
    return 0 if result.status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
