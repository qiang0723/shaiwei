"""No-input runtime preflight for the Top30 recovery Compose services."""

from __future__ import annotations

import json
import os
from pathlib import Path

from shaiwei.research.top30_diagnostic.fixture import run_fixture


def run_runtime_fixture() -> dict[str, object]:
    uid = os.geteuid()
    if uid == 0:
        raise RuntimeError("Top30 recovery fixture must run as non-root")
    interfaces = sorted(path.name for path in Path("/sys/class/net").iterdir())
    route_lines = [line for line in Path("/proc/net/route").read_text().splitlines()[1:] if line]
    if route_lines:
        raise RuntimeError("Top30 recovery fixture has an IPv4 route")
    probe = Path("/tmp/top30-recovery-runtime-probe")
    probe.write_text("ok", encoding="utf-8")
    if probe.read_text(encoding="utf-8") != "ok":
        raise RuntimeError("Top30 recovery tmpfs is not writable")
    probe.unlink()
    classifier = run_fixture()
    return {
        "runtime_preflight": "PASS",
        "effective_uid": uid,
        "network_interfaces": interfaces,
        "ipv4_route_entry_count": len(route_lines),
        "tmpfs_writable": True,
        "classification_case_count": classifier["classification_case_count"],
        "real_input_mount_count": 0,
        "real_qlib_read": False,
        "sealed_report_read": False,
        "real_top30_backtest_count": 0,
        "top20_backtest_count": 0,
        "external_call_count": 0,
        "production_authorization": "none",
    }


def main() -> int:
    print(json.dumps(run_runtime_fixture(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
