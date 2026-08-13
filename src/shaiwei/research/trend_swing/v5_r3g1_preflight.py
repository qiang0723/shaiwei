"""Result-blind feature-only preflight for TS-v5-R3G-1."""

from __future__ import annotations

import json

import duckdb

from shaiwei.research.trend_swing.r4_contract import load_r3_manifest
from shaiwei.research.trend_swing.recovery_market import prepare_market_and_sector
from shaiwei.research.trend_swing.recovery_store import configure_store, prepare_core_tables
from shaiwei.research.trend_swing.v5_r3g1_contract import OUTPUT_ROOT, R3G1Scope, validate_bound_inputs
from shaiwei.research.trend_swing.v5_r3g1_features import prepare_r3g1_features


def preflight() -> dict[str, object]:
    scope = R3G1Scope.load()
    validate_bound_inputs(scope)
    manifest = load_r3_manifest()
    context = scope.document["frozen_inputs"]["source_context"]
    connection = duckdb.connect(":memory:")
    try:
        configure_store(connection, OUTPUT_ROOT / "preflight-tmp")
        prepare_core_tables(
            connection,
            manifest,
            start_date=str(context["start"]),
            end_date=str(context["end"]),
        )
        prepare_market_and_sector(connection)
        prepare_r3g1_features(connection)
        row = connection.execute(
            "SELECT count(*),min(trade_date),max(trade_date),count(DISTINCT ts_code) FROM r3g1_stream"
        ).fetchone()
        result = {
            "feature_row_count": int(row[0]),
            "first_date": str(row[1]),
            "last_date": str(row[2]),
            "security_count": int(row[3]),
            "market_or_security_data_read": True,
            "density_read": False,
            "post_entry_outcome_read": False,
            "external_api_calls": 0,
            "secret_read": False,
        }
        return result
    finally:
        connection.close()


if __name__ == "__main__":
    print(json.dumps(preflight(), sort_keys=True), flush=True)
