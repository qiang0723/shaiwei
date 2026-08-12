import json
from pathlib import Path

import duckdb

from shaiwei.research.trend_swing.contract import sha256_file
import shaiwei.research.trend_swing.v4_density_audit as audit_module


class _SyntheticRelease:
    sha256 = "a" * 64
    arms = (
        ("TS4-D015", 0.015),
        ("TS4-D025", 0.025),
        ("TS4-D035", 0.035),
        ("TS4-D040", 0.040),
    )
    adjacent_pairs = (
        ("TS4-D015", "TS4-D025"),
        ("TS4-D025", "TS4-D035"),
        ("TS4-D035", "TS4-D040"),
    )
    document = {
        "density_gate": {
            "per_arm_minimum_legal_events": 30,
            "per_arm_minimum_distinct_signal_days": 20,
            "per_arm_minimum_events_each_calendar_year": 5,
            "required_calendar_years": [2019, 2020, 2021],
            "alpha158_event_key_coverage_required": 1.0,
            "alpha158_duplicate_event_key_count_required": 0,
            "minimum_passing_adjacent_pair_count": 1,
            "pass_verdict": "GO_DENSE_PARAMETER_REGION",
            "failure_verdict": "STOP_NO_DENSE_PARAMETER_REGION",
        }
    }

    def __init__(self, alpha_path: Path) -> None:
        self.inputs = {"alpha158_path": str(alpha_path)}


def _write_fixture(root: Path) -> tuple[Path, Path, Path]:
    event_path = root / "events.parquet"
    daily_path = root / "daily.parquet"
    alpha_path = root / "alpha.parquet"
    connection = duckdb.connect(":memory:")
    try:
        connection.execute(
            "CREATE TABLE events(arm_id VARCHAR,pullback_depth_fraction DOUBLE,"
            "ts_code VARCHAR,trade_date VARCHAR,event_status VARCHAR)"
        )
        event_rows = []
        alpha_rows = []
        dates = [
            *(f"201901{day:02d}" for day in range(1, 11)),
            *(f"202001{day:02d}" for day in range(1, 11)),
            *(f"202101{day:02d}" for day in range(1, 11)),
        ]
        for index, date in enumerate(dates):
            code = f"{index:06d}.SZ"
            alpha_rows.append((code, date))
            for arm_id, depth in _SyntheticRelease.arms:
                event_rows.append((arm_id, depth, code, date, "LEGAL_ENTRY_EVENT"))
        connection.executemany("INSERT INTO events VALUES (?,?,?,?,?)", event_rows)
        connection.execute("CREATE TABLE alpha(ts_code VARCHAR,trade_date VARCHAR)")
        connection.executemany("INSERT INTO alpha VALUES (?,?)", alpha_rows)
        connection.execute(
            "CREATE TABLE daily AS SELECT arm_id,trade_date,count(*) AS legal_event_count "
            "FROM events GROUP BY 1,2"
        )
        connection.execute("COPY events TO ? (FORMAT PARQUET)", [str(event_path)])
        connection.execute("COPY daily TO ? (FORMAT PARQUET)", [str(daily_path)])
        connection.execute("COPY alpha TO ? (FORMAT PARQUET)", [str(alpha_path)])
    finally:
        connection.close()
    return event_path, daily_path, alpha_path


def test_v4_density_independent_audit_recomputes_a_passing_fixture(
    tmp_path: Path, monkeypatch
) -> None:
    event_path, daily_path, alpha_path = _write_fixture(tmp_path)
    report_path = tmp_path / "report.json"
    audit_path = tmp_path / "audit.json"
    release = _SyntheticRelease(alpha_path)
    monkeypatch.setattr(audit_module, "project_path", lambda value: Path(value))
    monkeypatch.setattr(audit_module, "EVENT_PATH", event_path)
    monkeypatch.setattr(audit_module, "DAILY_PATH", daily_path)
    connection = duckdb.connect(":memory:")
    try:
        evidence, passing, pairs = audit_module._recompute(connection, release)
    finally:
        connection.close()
    report = {
        "release_identity": {
            "release_sha256": release.sha256,
            "recovery_sha256": "d" * 64,
            "git_head": "b" * 40,
            "code_snapshot_sha256": "c" * 64,
        },
        "machine_artifacts": {
            "arm_event_intermediate": {
                "sha256": sha256_file(event_path),
                "row_count": 120,
            },
            "anonymous_arm_daily": {
                "sha256": sha256_file(daily_path),
                "row_count": 120,
            },
        },
        "authority": {"result_blind": True, "strategy_effect_attempt_count": 0},
        "arm_evidence": evidence,
        "passing_arms": passing,
        "passing_adjacent_pairs": pairs,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": "GO_DENSE_PARAMETER_REGION",
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")

    class _Loader:
        @staticmethod
        def load():
            return release

    class _RecoveryLoader:
        @staticmethod
        def load(_release):
            class _Recovery:
                sha256 = "d" * 64

            return _Recovery()

    monkeypatch.setattr(audit_module, "REPORT_PATH", report_path)
    monkeypatch.setattr(audit_module, "AUDIT_PATH", audit_path)
    monkeypatch.setattr(audit_module, "V4DensityRelease", _Loader)
    monkeypatch.setattr(audit_module, "V4DensityRecovery", _RecoveryLoader)
    monkeypatch.setattr(audit_module, "validate_bound_inputs", lambda _: None)
    monkeypatch.setattr(
        audit_module,
        "write_once_json",
        lambda path, value: (path.write_text(json.dumps(value), encoding="utf-8"), False),
    )
    monkeypatch.setattr(
        audit_module,
        "runtime_code_identity",
        lambda: {"git_head": "b" * 40, "code_snapshot_sha256": "c" * 64},
    )

    result = audit_module.audit_once()

    assert result["verdict"] == "PASS"
    assert all(result["checks"].values())
    assert result["recomputed_passing_arms"] == [arm for arm, _ in release.arms]
    assert result["recomputed_passing_adjacent_pairs"] == [
        list(pair) for pair in release.adjacent_pairs
    ]


def test_v4_density_audit_rejects_forbidden_effect_column(
    tmp_path: Path, monkeypatch
) -> None:
    event_path, daily_path, alpha_path = _write_fixture(tmp_path)
    connection = duckdb.connect(":memory:")
    contaminated = tmp_path / "contaminated.parquet"
    try:
        connection.execute(
            "CREATE TABLE contaminated AS SELECT *,0.1 AS pnl FROM read_parquet(?)",
            [str(event_path)],
        )
        connection.execute("COPY contaminated TO ? (FORMAT PARQUET)", [str(contaminated)])
    finally:
        connection.close()

    assert "pnl" in audit_module.FORBIDDEN_EVENT_COLUMNS
    assert "pnl" in duckdb.sql(
        "DESCRIBE SELECT * FROM read_parquet(?)", params=[str(contaminated)]
    ).df()["column_name"].tolist()
    assert alpha_path.is_file() and daily_path.is_file()
