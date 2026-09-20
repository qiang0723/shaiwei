"""Synthetic-only R3L contract tests, with no live metadata or execution adapter."""

import ast
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from shaiwei.r2d_post_close_contract import (
    ContractViolation, PostCloseEvidence, PostCloseProtocol, assess_post_close,
)


def dt(value):
    return datetime.fromisoformat(value)


def bundle(now=None):
    now = now or dt("2026-09-18T22:00:00+08:00")
    binding = dict(
        candidate_image_id="sha256:" + "a" * 64, candidate_code_sha256="b" * 64,
        legacy_code_sha256="c" * 64, legacy_container_id="d" * 64,
        state_sha256="e" * 64, audit_sha256="f" * 64, calendar_sha256="1" * 64,
        controller_sha256="2" * 64, git_head="3" * 40, origin_main="3" * 40,
    )
    protocol = PostCloseProtocol(
        schema_version="r2d-post-close-contract-v1", mode="POST_CLOSE_PARKED",
        closed_trade_date="20260918", first_candidate_trade_date="20260921",
        not_before=dt("2026-09-18T20:00:00+08:00"),
        expires_at=dt("2026-09-19T20:00:00+08:00"),
        next_dispatch_not_before=dt("2026-09-21T16:00:00+08:00"),
        binding=binding, baseline_artifact_sha256="4" * 64,
        top20_artifact_sha256="5" * 64, candidate_floor_fixture_sha256="6" * 64,
    )
    rows = tuple(
        dict(account_id=account, execution_trade_date="20260918",
             code_snapshot_sha256="c" * 64, artifact_sha256=digest * 64,
             finished_at=now - timedelta(minutes=40 - index), status="PASS",
             freshness_status="PASS", mode="FORWARD", operator="docker-scheduler",
             hash_and_identity_verified=True)
        for index, (account, digest) in enumerate(
            (("model_baseline", "4"), ("model_top20", "5"))
        )
    )
    evidence = PostCloseEvidence(
        binding=binding, daily_trade_date="20260918", shadow_trade_date="20260918",
        daily_status="PASS", shadow_status="PASS", shadow_code_sha256="c" * 64,
        calendar_next_trade_date="20260921",
        observed_at=now - timedelta(minutes=4), cycle_finished_at=now - timedelta(minutes=30),
        health_updated_at=now - timedelta(minutes=5), health_status="noop", health_detail="20260918",
        completed_attempts=dict(daily=1, shadow=1, paper=2),
        first_day_attempts=dict(daily=0, shadow=0, paper=0), pending_trade_dates=(),
        latest_forwards=rows, independent_replay_pass=True, notifications_pass=True,
        legacy_quiescence_method="ALL_WRITERS_FENCED_AND_DRAINED",
        legacy_quiescence_report_sha256="7" * 64, fence_held=True, legacy_writers_inflight=0,
        candidate_mode="PARKED_UNTIL_FIRST_ELIGIBLE_DATE", candidate_floor_fixture_sha256="6" * 64,
    )
    return protocol, evidence, now


def change(model, **updates):
    return type(model).model_validate({**model.model_dump(), **updates})


def test_valid_contract_never_authorizes_or_dispatches():
    protocol, evidence, now = bundle()
    decision = assess_post_close(protocol, evidence, now=now)
    assert decision.status == "CONTRACT_VALID_NOT_FOR_EXECUTION"
    assert decision.production_authorized is False
    assert decision.closed_trade_date == "20260918"
    assert decision.first_candidate_trade_date == "20260921"
    assert decision == assess_post_close(protocol, evidence, now=now)


@pytest.mark.parametrize("timestamp,valid", [
    ("2026-09-18T19:59:59+08:00", False),
    ("2026-09-18T20:00:00+08:00", True),
    ("2026-09-18T23:59:59+08:00", True),
    ("2026-09-19T00:00:00+08:00", True),
    ("2026-09-19T19:59:59+08:00", True),
    ("2026-09-19T20:00:00+08:00", False),
])
def test_wide_window_endpoints_and_midnight(timestamp, valid):
    protocol, evidence, now = bundle(dt(timestamp))
    if valid:
        assert not assess_post_close(protocol, evidence, now=now).production_authorized
    else:
        with pytest.raises(ContractViolation, match="OUTSIDE_WINDOW"):
            assess_post_close(protocol, evidence, now=now)


@pytest.mark.parametrize("hours", [-1, 0, 25])
def test_window_cannot_roll_or_expand_without_bound(hours):
    protocol, _, _ = bundle()
    with pytest.raises(ValidationError, match="AT_MOST_24H"):
        change(protocol, expires_at=protocol.not_before + timedelta(hours=hours))


def test_window_must_end_before_next_dispatch():
    protocol, _, _ = bundle()
    with pytest.raises(ValidationError, match="OVERLAPS_FIRST_DISPATCH"):
        change(protocol, first_candidate_trade_date="20260919",
               next_dispatch_not_before=dt("2026-09-19T19:00:00+08:00"))


@pytest.mark.parametrize("field", ["not_before", "expires_at", "next_dispatch_not_before"])
def test_naive_protocol_times_rejected(field):
    protocol, _, _ = bundle()
    with pytest.raises(ValidationError):
        change(protocol, **{field: getattr(protocol, field).replace(tzinfo=None)})


def test_naive_clock_rejected():
    protocol, evidence, now = bundle()
    with pytest.raises(ContractViolation, match="NAIVE_CLOCK"):
        assess_post_close(protocol, evidence, now=now.replace(tzinfo=None))


@pytest.mark.parametrize("field,value", [
    ("first_candidate_trade_date", "20260918"),
    ("closed_trade_date", "20260230"),
    ("health_max_age_seconds", 7200),
    ("rollback_policy", "ALLOW"),
    ("extra_permission", True),
])
def test_invalid_or_expanded_protocol_rejected(field, value):
    protocol, _, _ = bundle()
    with pytest.raises(ValidationError):
        change(protocol, **{field: value})


@pytest.mark.parametrize("field,value,reason", [
    ("daily_trade_date", "20260917", "CLOSED_DATE_DIFFERS"),
    ("shadow_trade_date", "20260917", "CLOSED_DATE_DIFFERS"),
    ("shadow_code_sha256", "b" * 64, "SHADOW_CODE_DIFFERS"),
    ("calendar_next_trade_date", "20260919", "NOT_FIRST_CALENDAR_TRADE_DATE"),
    ("health_detail", "20260917", "HEALTH_DETAIL_DIFFERS"),
    ("pending_trade_dates", ("20260918",), "PENDING_WORK"),
    ("independent_replay_pass", False, "REPLAY_NOT_VERIFIED"),
    ("notifications_pass", False, "NOTIFICATIONS_NOT_VERIFIED"),
    ("fence_held", False, "NOT_QUIESCENT"),
    ("legacy_writers_inflight", 1, "NOT_QUIESCENT"),
    ("candidate_floor_fixture_sha256", "8" * 64, "CANDIDATE_FLOOR_FIXTURE_DIFFERS"),
])
def test_noop_or_pass_counts_do_not_substitute_for_proofs(field, value, reason):
    protocol, evidence, now = bundle()
    with pytest.raises(ContractViolation, match=reason):
        assess_post_close(protocol, change(evidence, **{field: value}), now=now)


@pytest.mark.parametrize("field", ["daily", "shadow", "paper"])
def test_any_first_day_attempt_blocks(field):
    protocol, evidence, now = bundle()
    counts = evidence.first_day_attempts.model_dump()
    counts[field] = 1
    with pytest.raises(ContractViolation, match="FIRST_DAY_ALREADY_ATTEMPTED"):
        assess_post_close(protocol, change(evidence, first_day_attempts=counts), now=now)


@pytest.mark.parametrize("field", ["daily", "shadow", "paper"])
def test_ambiguous_closed_attempts_block(field):
    protocol, evidence, now = bundle()
    counts = evidence.completed_attempts.model_dump()
    counts[field] += 1
    with pytest.raises(ContractViolation, match="CLOSED_ATTEMPTS_NOT_UNAMBIGUOUS"):
        assess_post_close(protocol, change(evidence, completed_attempts=counts), now=now)


@pytest.mark.parametrize("field", ["observed_at", "health_updated_at"])
@pytest.mark.parametrize("offset", [-3601, 1])
def test_stale_or_future_evidence(field, offset):
    protocol, evidence, now = bundle()
    with pytest.raises(ContractViolation, match="STALE_OR_FUTURE_EVIDENCE"):
        assess_post_close(protocol, change(evidence, **{field: now + timedelta(seconds=offset)}), now=now)


def test_exact_3600_second_age_remains_allowed():
    protocol, evidence, now = bundle()
    health = now - timedelta(seconds=3600)
    rows = tuple(change(row, finished_at=health - timedelta(minutes=2)) for row in evidence.latest_forwards)
    evidence = change(evidence, health_updated_at=health, cycle_finished_at=health - timedelta(minutes=1),
                      latest_forwards=rows)
    assert assess_post_close(protocol, evidence, now=now).production_authorized is False


@pytest.mark.parametrize("field", ["state_sha256", "audit_sha256", "calendar_sha256",
                                  "controller_sha256", "legacy_container_id", "candidate_code_sha256"])
def test_identity_drift_blocks(field):
    protocol, evidence, now = bundle()
    binding = change(evidence.binding, **{field: "9" * 64})
    with pytest.raises(ContractViolation, match="RELEASE_BINDING_DRIFT"):
        assess_post_close(protocol, change(evidence, binding=binding), now=now)


def test_unpushed_controller_binding_rejected():
    protocol, _, _ = bundle()
    with pytest.raises(ValidationError, match="UNPUSHED_CONTROLLER"):
        change(protocol.binding, origin_main="9" * 40)


@pytest.mark.parametrize("rows", ["missing", "duplicate"])
def test_account_set_must_be_exact(rows):
    protocol, evidence, now = bundle()
    account = evidence.latest_forwards[0]
    changed = (account,) if rows == "missing" else (account, account)
    with pytest.raises(ContractViolation, match="FORWARD_ACCOUNT"):
        assess_post_close(protocol, change(evidence, latest_forwards=changed), now=now)


@pytest.mark.parametrize("field,value,reason", [
    ("execution_trade_date", "20260917", "FORWARD_DATE_DIFFERS"),
    ("code_snapshot_sha256", "b" * 64, "FORWARD_CODE_DIFFERS"),
    ("artifact_sha256", "9" * 64, "FORWARD_HASH_DIFFERS"),
    ("hash_and_identity_verified", False, "FORWARD_UNVERIFIED"),
])
def test_forward_anchors_are_bound(field, value, reason):
    protocol, evidence, now = bundle()
    row = change(evidence.latest_forwards[0], **{field: value})
    evidence = change(evidence, latest_forwards=(row, evidence.latest_forwards[1]))
    with pytest.raises(ContractViolation, match=reason):
        assess_post_close(protocol, evidence, now=now)


@pytest.mark.parametrize("field,value", [
    ("mode", "BACKFILL"), ("status", "FAIL"), ("freshness_status", "FAIL"),
    ("operator", "manual"), ("hash_and_identity_verified", "true"),
])
def test_invalid_forward_evidence_is_not_coerced(field, value):
    _, evidence, _ = bundle()
    with pytest.raises(ValidationError):
        change(evidence.latest_forwards[0], **{field: value})


@pytest.mark.parametrize("field", ["legacy_quiescence_report_sha256", "candidate_floor_fixture_sha256"])
def test_missing_capability_proof_is_not_optional(field):
    _, evidence, _ = bundle()
    data = evidence.model_dump()
    del data[field]
    with pytest.raises(ValidationError):
        PostCloseEvidence.model_validate(data)


def test_counts_reject_boolean_and_negative_values():
    _, evidence, _ = bundle()
    for bad in (True, -1, "0"):
        with pytest.raises(ValidationError):
            change(evidence.first_day_attempts, daily=bad)


@pytest.mark.parametrize("field,value", [
    ("health_status", "healthy"),
    ("daily_status", "FAIL"),
    ("shadow_status", "FAIL"),
    ("legacy_quiescence_method", "TWO_UNCHANGED_SNAPSHOTS"),
    ("candidate_mode", "START_CURRENT_DIRECTLY"),
    ("fence_held", "true"),
    ("legacy_quiescence_report_sha256", ""),
    ("production_authorized", True),
])
def test_observation_cannot_claim_weaker_or_extra_authority(field, value):
    _, evidence, _ = bundle()
    with pytest.raises(ValidationError):
        change(evidence, **{field: value})


def test_cycle_must_finish_before_idle_heartbeat():
    protocol, evidence, now = bundle()
    evidence = change(evidence, cycle_finished_at=now - timedelta(minutes=1))
    with pytest.raises(ContractViolation, match="INCONSISTENT_EVIDENCE_ORDER"):
        assess_post_close(protocol, evidence, now=now)


def test_forward_must_finish_before_cycle_closes():
    protocol, evidence, now = bundle()
    row = change(evidence.latest_forwards[0], finished_at=now - timedelta(minutes=1))
    evidence = change(evidence, latest_forwards=(row, evidence.latest_forwards[1]))
    with pytest.raises(ContractViolation, match="FORWARD_FINISH_AFTER_CYCLE"):
        assess_post_close(protocol, evidence, now=now)


def test_dispatch_time_must_belong_to_first_candidate_date():
    protocol, _, _ = bundle()
    with pytest.raises(ValidationError, match="DISPATCH_DATE_DIFFERS"):
        change(protocol, next_dispatch_not_before=dt("2026-09-22T16:00:00+08:00"))


def test_utc_and_shanghai_clock_represent_the_same_decision():
    protocol, evidence, now = bundle()
    utc_now = now.astimezone(dt("2026-09-18T00:00:00+00:00").tzinfo)
    assert assess_post_close(protocol, evidence, now=now) == assess_post_close(
        protocol, evidence, now=utc_now,
    )


def test_pure_module_has_no_production_adapter_or_io_imports():
    source = Path("src/shaiwei/r2d_post_close_contract.py").read_text()
    tree = ast.parse(source)
    imports = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    assert imports <= {"__future__", "datetime", "typing", "zoneinfo", "pydantic"}
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id in {"open", "exec", "eval", "__import__"} for node in ast.walk(tree))
    assert "def run(" not in source and "def main(" not in source
