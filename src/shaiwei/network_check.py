"""脱敏网络诊断：验证 Tushare 直连，不写入研究数据或账本。"""

import json
import os
import time
from datetime import date, timedelta

from shaiwei.config import load
from shaiwei.ingest.tushare import FIELDS, TUSHARE_API_HOST, create_client


def _host_in_no_proxy(host: str) -> bool:
    entries = {
        item.strip().lstrip(".").lower()
        for key in ("NO_PROXY", "no_proxy")
        for item in os.environ.get(key, "").split(",")
        if item.strip()
    }
    host = host.lower()
    return any(host == entry or host.endswith(f".{entry}") for entry in entries)


def _proxy_state() -> dict[str, bool]:
    return {
        "http_proxy_set": bool(os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")),
        "https_proxy_set": bool(os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")),
        "all_proxy_set": bool(os.environ.get("ALL_PROXY") or os.environ.get("all_proxy")),
        "tushare_no_proxy": _host_in_no_proxy(TUSHARE_API_HOST),
    }


def _safe_error(error: Exception, token: str) -> str:
    message = str(error).replace(token, "[REDACTED]") if token else str(error)
    return " ".join(message.split())[:300]


def main() -> int:
    settings = load()
    if settings.runtime.tushare_token is None:
        print(json.dumps({"ok": False, "error": "TUSHARE_TOKEN is not configured"}, sort_keys=True))
        return 2

    token = settings.runtime.tushare_token.get_secret_value()
    today = date.today()
    started = time.perf_counter()
    try:
        client = create_client(token)
        frame = client.query(
            "trade_cal",
            exchange="SSE",
            start_date=(today - timedelta(days=7)).strftime("%Y%m%d"),
            end_date=today.strftime("%Y%m%d"),
            fields=",".join(FIELDS["trade_cal"]),
        )
    except Exception as error:  # Tushare exposes provider failures through several exception types.
        print(
            json.dumps(
                {
                    "ok": False,
                    "host": TUSHARE_API_HOST,
                    "error_type": type(error).__name__,
                    "error": _safe_error(error, token),
                    "proxy": _proxy_state(),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1

    # A seven-day SSE calendar window is dense by definition, including closed
    # days. Tushare can return an empty frame instead of an explicit error when
    # the request exits from a rejected region, so an empty result must not be
    # reported as a successful connectivity check.
    if frame.empty:
        print(
            json.dumps(
                {
                    "ok": False,
                    "host": TUSHARE_API_HOST,
                    "api": "trade_cal",
                    "error": "empty_response",
                    "row_count": 0,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000),
                    "proxy": _proxy_state(),
                },
                sort_keys=True,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "host": TUSHARE_API_HOST,
                "api": "trade_cal",
                "row_count": len(frame),
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "proxy": _proxy_state(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
