"""Independent read-only verification of frozen M3-0 artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from tools.m3_star_custom_pit.contract import GateFailure, PROJECT_ROOT, canonical_sha256, sha256_file


MANIFEST_PATH = PROJECT_ROOT / "config/m3_star_custom_pit_manifest_v1.json"


def _artifact(manifest: dict[str, Any], name: str) -> Path:
    evidence = manifest["artifacts"][name]
    path = PROJECT_ROOT / evidence["path"]
    if not path.is_file() or sha256_file(path) != evidence["sha256"]:
        raise GateFailure(f"M3 verification hash mismatch: {name}")
    return path


def verify() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    formation_path = _artifact(manifest, "formation_members")
    daily_path = _artifact(manifest, "daily_members")
    report_path = _artifact(manifest, "quality_report")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if manifest["verdict"] != "GO_CUSTOM_PIT_DATA_RULE_GATE_ONLY":
        raise GateFailure("M3 verification requires the frozen data/rule GO verdict")
    if report["strategy_effective"] != "NOT_EVALUATED" or report["production_authorization"] != "none":
        raise GateFailure("M3 verification found a strategy or production overclaim")

    connection = duckdb.connect(":memory:")
    try:
        connection.read_parquet(str(formation_path)).create_view("formation")
        connection.read_parquet(str(daily_path)).create_view("daily")
        metrics = {
            "formation_rows": int(connection.execute("SELECT count(*) FROM formation").fetchone()[0]),
            "daily_rows": int(connection.execute("SELECT count(*) FROM daily").fetchone()[0]),
            "formation_duplicate_keys": int(
                connection.execute(
                    """SELECT count(*) FROM (
                    SELECT formation_date, universe_id, ts_code
                    FROM formation GROUP BY ALL HAVING count(*) > 1)"""
                ).fetchone()[0]
            ),
            "daily_duplicate_keys": int(
                connection.execute(
                    """SELECT count(*) FROM (
                    SELECT trade_date, universe_id, ts_code
                    FROM daily GROUP BY ALL HAVING count(*) > 1)"""
                ).fetchone()[0]
            ),
            "bse_rows": int(
                connection.execute(
                    "SELECT (SELECT count(*) FROM formation WHERE ends_with(ts_code, '.BJ')) + "
                    "(SELECT count(*) FROM daily WHERE ends_with(ts_code, '.BJ'))"
                ).fetchone()[0]
            ),
            "invalid_effective_clock_rows": int(
                connection.execute(
                    "SELECT count(*) FROM formation WHERE effective_date <= formation_date"
                ).fetchone()[0]
            ),
            "daily_before_effective_rows": int(
                connection.execute(
                    """SELECT count(*) FROM daily d JOIN (
                    SELECT DISTINCT formation_date, effective_date FROM formation
                    ) f USING (formation_date) WHERE d.trade_date < f.effective_date"""
                ).fetchone()[0]
            ),
            "mid_small_overlap_rows": int(
                connection.execute(
                    """SELECT count(*) FROM daily m JOIN daily s
                    USING (trade_date, ts_code)
                    WHERE m.universe_id='star-board-midcap-pit-v1'
                    AND s.universe_id='star-board-smallcap-pit-v1'"""
                ).fetchone()[0]
            ),
            "mid_small_missing_from_all_rows": int(
                connection.execute(
                    """SELECT count(*) FROM daily child
                    LEFT JOIN daily parent ON child.trade_date=parent.trade_date
                    AND child.ts_code=parent.ts_code
                    AND parent.universe_id='star-board-all-pit-v1'
                    WHERE child.universe_id IN (
                      'star-board-midcap-pit-v1','star-board-smallcap-pit-v1'
                    ) AND parent.ts_code IS NULL"""
                ).fetchone()[0]
            ),
        }
    finally:
        connection.close()

    expected = report["metrics"]["output"]
    if metrics["formation_rows"] != int(expected["formation_row_count"]):
        raise GateFailure("M3 independent formation row count differs")
    if metrics["daily_rows"] != int(expected["daily_row_count"]):
        raise GateFailure("M3 independent daily row count differs")
    zero_expected = (
        "formation_duplicate_keys",
        "daily_duplicate_keys",
        "bse_rows",
        "invalid_effective_clock_rows",
        "daily_before_effective_rows",
        "mid_small_overlap_rows",
        "mid_small_missing_from_all_rows",
    )
    zero_fields = [field for field in zero_expected if metrics[field] != 0]
    if zero_fields:
        raise GateFailure(f"M3 independent structural verification failed: {sorted(zero_fields)}")
    result = {
        "schema_version": "m3-star-custom-pit-independent-verification-v1",
        "manifest_sha256": sha256_file(MANIFEST_PATH),
        "quality_report_sha256": sha256_file(report_path),
        "metrics": metrics,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verification_pass": True,
    }
    return {**result, "verification_sha256": canonical_sha256(result)}


def main() -> int:
    print(json.dumps(verify(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
