from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from shaiwei import daily_early_release_guard as base
from shaiwei import r2d_release_guard as guard
from shaiwei.r2d_legacy_boundary import (
    LegacyNoopBoundary,
    target_write_counts,
    validate_noop_boundary,
)


def _boundary() -> LegacyNoopBoundary:
    return LegacyNoopBoundary.model_validate(
        {
            "mode": "PRIOR_DAY_NOOP",
            "status": "noop",
            "detail_trade_date": "20260826",
            "updated_on_target_date_not_before": "16:00:00",
            "require_target_daily_rows": 0,
            "require_target_shadow_rows": 0,
            "require_target_paper_rows": 0,
        }
    )


def _write(path: Path, header: str, rows: tuple[str, ...]) -> None:
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def test_target_write_counts_include_failed_attempts(tmp_path: Path) -> None:
    daily = tmp_path / "daily.csv"
    shadow = tmp_path / "shadow.csv"
    paper = tmp_path / "paper.csv"
    _write(
        daily,
        "run_id,target_trade_date,status",
        ("d1,20260827,FAILED", "d2,20260826,PASS"),
    )
    _write(
        shadow,
        "run_id,signal_trade_date,status",
        ("s1,20260827,FAILED",),
    )
    _write(
        paper,
        "run_id,execution_trade_date,status",
        ("p1,20260827,FAILED", "p2,20260827,PASS"),
    )

    assert target_write_counts(
        "20260827",
        daily_path=daily,
        shadow_path=shadow,
        paper_path=paper,
    ) == {"daily": 1, "shadow": 1, "paper": 2}


def test_validate_noop_boundary_accepts_only_fresh_zero_write_boundary() -> None:
    evidence = validate_noop_boundary(
        _boundary(),
        target_trade_date="20260827",
        timezone="Asia/Shanghai",
        health={
            "status": "noop",
            "detail": "20260826",
            "updated_at": "2026-08-27T08:01:00+00:00",
        },
        counts={"daily": 0, "shadow": 0, "paper": 0},
    )
    assert evidence["detail"] == "20260826"
    assert evidence["target_write_counts"] == {"daily": 0, "shadow": 0, "paper": 0}


@pytest.mark.parametrize(
    ("health", "counts", "message"),
    [
        (
            {
                "status": "waiting_source",
                "detail": "20260827",
                "updated_at": "2026-08-27T08:01:00+00:00",
            },
            {"daily": 0, "shadow": 0, "paper": 0},
            "not the frozen noop",
        ),
        (
            {
                "status": "noop",
                "detail": "20260826",
                "updated_at": "2026-08-27T07:59:59+00:00",
            },
            {"daily": 0, "shadow": 0, "paper": 0},
            "outside the target boundary",
        ),
        (
            {
                "status": "noop",
                "detail": "20260826",
                "updated_at": "2026-08-27T08:01:00+00:00",
            },
            {"daily": 0, "shadow": 1, "paper": 0},
            "already written the target date",
        ),
    ],
)
def test_validate_noop_boundary_rejects_ambiguous_evidence(health, counts, message):
    with pytest.raises(base.GuardError, match=message):
        validate_noop_boundary(
            _boundary(),
            target_trade_date="20260827",
            timezone="Asia/Shanghai",
            health=health,
            counts=counts,
        )


def test_tracked_recovery_guard_and_scope_are_exactly_bound() -> None:
    protocol = guard.load_protocol(guard.RECOVERY_PROTOCOL_PATH)
    release_path = (
        guard.PROJECT_ROOT / "config" / "r2d_scheduler_release_scope_r1_v1.json"
    )
    release = json.loads(release_path.read_text(encoding="utf-8"))
    scope = release["scope"]
    canonical = json.dumps(scope, sort_keys=True, separators=(",", ":")).encode()

    assert release["schema_version"] == "r2d-scheduler-release-r1-scope-v1"
    assert release["release_scope_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert release["release_scope_sha256"] == (
        "bb74c299a4ce5d76dc0cafd337b4d6529d6b433de72c012bcc6c54531297119a"
    )
    assert scope["action"] == (
        "R2D_R1_START_CURRENT_20260827_ONCE_AFTER_LEGACY_NOOP_BOUNDARY"
    )
    assert scope["candidate"] == protocol.candidate.model_dump()
    assert scope["expected_running_release"] == (
        protocol.expected_running_release.model_dump()
    )
    assert scope["expected_latest_forward"] == [
        item.model_dump() for item in protocol.expected_latest_forward
    ]
    assert scope["phase_a_repeat_authorized"] is False
    assert scope["start_window"]["date"] == protocol.target_trade_date
    assert scope["guard_protocol"]["sha256"] == hashlib.sha256(
        guard.RECOVERY_PROTOCOL_PATH.read_bytes()
    ).hexdigest()
