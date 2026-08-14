"""One-shot official network adapter for the frozen H00906 lineage gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from shaiwei.ledger import INGEST
from shaiwei.research.trend_swing.benchmark_lineage import (
    BenchmarkLineageError,
    FACTSHEET_PATH,
    FIRST_HISTORY_PATH,
    SECOND_HISTORY_PATH,
    canonical_history_data,
    load_protocol,
)
from shaiwei.research.trend_swing.benchmark_lineage_evidence import evaluate_and_persist


def _get(client: httpx.Client, url: str, params: dict[str, str] | None = None) -> bytes:
    response = client.get(url, params=params)
    response.raise_for_status()
    if not response.content:
        raise BenchmarkLineageError("official H00906 response is empty")
    return response.content


def run_once(*, ledger_path: Path = INGEST) -> dict[str, Any]:
    protocol = load_protocol()
    source = protocol["official_sources"]
    history = source["daily_history"]
    if any(path.exists() for path in (FACTSHEET_PATH, FIRST_HISTORY_PATH, SECOND_HISTORY_PATH)):
        raise BenchmarkLineageError("H00906 network scope was already consumed")
    headers = {"User-Agent": "shaiwei-h00906-lineage/1.0", "Accept": "application/json,application/pdf"}
    with httpx.Client(timeout=30.0, follow_redirects=True, trust_env=False, headers=headers) as client:
        factsheet = _get(client, source["identity_factsheet"]["url"])
        first_raw = _get(client, history["url"], history["query"])
        second_raw = _get(client, history["url"], history["query"])
    if canonical_history_data(first_raw) != canonical_history_data(second_raw):
        raise BenchmarkLineageError("two official H00906 responses drifted before persistence")
    return evaluate_and_persist(
        factsheet,
        first_raw,
        second_raw,
        raw_already_persisted=False,
        ledger_path=ledger_path,
    )


def main() -> int:
    report = run_once()
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "row_count": report["row_count"],
                "first_date": report["first_date"],
                "last_date": report["last_date"],
                "strategy_effective": report["strategy_effective"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
