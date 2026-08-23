from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from shaiwei.research import effect_attempt_claim
from shaiwei.research.effect_attempt_claim import (
    CLAIM_STATUS,
    EffectAttemptClaimError,
    EffectAttemptSpec,
    build_claim_row,
    claim_effect_attempt,
    read_effect_after_claim,
    verify_effect_attempt_claim,
)


HEADER = (
    "experiment_id,parent_experiment_id,ts,candidate_source,model_or_engine,engine_version,seed,"
    "prompt_hash,code_sha256,data_snapshot_sha256,feature_or_formula,params_json,train_period,"
    "valid_period,result_json,admitted,reject_reason\n"
)
CLAIMED_AT = "2026-08-23T09:00:00+08:00"


def _spec(**changes: object) -> EffectAttemptSpec:
    values: dict[str, object] = {
        "attempt_family": "fixture_effect_family",
        "release_scope_sha256": "a" * 64,
        "attempt_ordinal": 1,
        "candidate_source": "fixture-candidate",
        "model_or_engine": "fixture-engine",
        "engine_version": "fixture-v1",
        "code_sha256": "b" * 64,
        "data_snapshot_sha256": "c" * 64,
        "feature_or_formula": "fixture formula ($close / Ref($close, 1))",
        "train_period": "sealed discovery; no fit",
        "valid_period": "sealed historical effect window",
    }
    values.update(changes)
    return EffectAttemptSpec(**values)  # type: ignore[arg-type]


def _ledger(tmp_path: Path) -> Path:
    path = tmp_path / "experiments.csv"
    path.write_text(HEADER, encoding="utf-8")
    return path


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_claim_row_is_deterministic_and_contains_no_effect_result() -> None:
    spec = _spec()
    first = build_claim_row(spec, claimed_at=CLAIMED_AT)
    second = build_claim_row(spec, claimed_at=CLAIMED_AT)

    assert first == second
    assert len(first["experiment_id"]) == 12
    assert json.loads(first["result_json"]) == {
        "attempt_consumed": True,
        "authoritative": False,
        "production_authorization": "none",
        "status": CLAIM_STATUS,
    }
    assert json.loads(first["params_json"])["same_scope_retry_authorized"] is False
    assert first["admitted"] == "false"


def test_reader_is_called_only_after_ledger_and_receipt_are_durable(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    receipt_path = tmp_path / "output" / "attempt_claim_receipt.json"
    observations: list[tuple[int, bool, str]] = []

    def reader(receipt: dict[str, object]) -> str:
        observations.append((len(_rows(ledger)), receipt_path.is_file(), str(receipt["experiment_id"])))
        return "effect-read"

    result = read_effect_after_claim(
        _spec(),
        ledger_path=ledger,
        receipt_path=receipt_path,
        effect_reader=reader,
        claimed_at=CLAIMED_AT,
    )

    assert result == "effect-read"
    assert observations == [(1, True, _spec().experiment_id)]
    assert verify_effect_attempt_claim(ledger_path=ledger, receipt_path=receipt_path)[
        "effect_read_allowed"
    ] is True


def test_same_scope_second_claim_is_rejected_not_idempotently_reopened(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    receipt = tmp_path / "receipt.json"
    claim_effect_attempt(_spec(), ledger_path=ledger, receipt_path=receipt, claimed_at=CLAIMED_AT)

    with pytest.raises(EffectAttemptClaimError, match="already claimed"):
        claim_effect_attempt(_spec(), ledger_path=ledger, receipt_path=receipt, claimed_at=CLAIMED_AT)

    assert len(_rows(ledger)) == 1


def test_reader_failure_keeps_consumed_attempt_and_closes_scope(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    receipt = tmp_path / "receipt.json"

    def fail(_receipt: dict[str, object]) -> None:
        raise RuntimeError("synthetic reader failure")

    with pytest.raises(RuntimeError, match="reader failure"):
        read_effect_after_claim(
            _spec(),
            ledger_path=ledger,
            receipt_path=receipt,
            effect_reader=fail,
            claimed_at=CLAIMED_AT,
        )
    assert len(_rows(ledger)) == 1
    with pytest.raises(EffectAttemptClaimError, match="already claimed"):
        read_effect_after_claim(
            _spec(),
            ledger_path=ledger,
            receipt_path=receipt,
            effect_reader=lambda _: None,
            claimed_at=CLAIMED_AT,
        )


def test_receipt_write_failure_still_consumes_attempt_and_forbids_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger = _ledger(tmp_path)
    receipt = tmp_path / "receipt.json"
    original = effect_attempt_claim._write_receipt
    monkeypatch.setattr(
        effect_attempt_claim,
        "_write_receipt",
        lambda *_: (_ for _ in ()).throw(OSError("synthetic receipt failure")),
    )
    with pytest.raises(OSError, match="receipt failure"):
        claim_effect_attempt(_spec(), ledger_path=ledger, receipt_path=receipt, claimed_at=CLAIMED_AT)
    assert len(_rows(ledger)) == 1
    monkeypatch.setattr(effect_attempt_claim, "_write_receipt", original)
    with pytest.raises(EffectAttemptClaimError, match="already claimed"):
        claim_effect_attempt(_spec(), ledger_path=ledger, receipt_path=receipt, claimed_at=CLAIMED_AT)


def test_verifier_rejects_receipt_and_ledger_tampering(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    receipt = tmp_path / "receipt.json"
    claim_effect_attempt(_spec(), ledger_path=ledger, receipt_path=receipt, claimed_at=CLAIMED_AT)
    original_receipt = receipt.read_text(encoding="utf-8")
    document = json.loads(original_receipt)
    document["effect_read_allowed"] = False
    receipt.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(EffectAttemptClaimError, match="identity differs"):
        verify_effect_attempt_claim(ledger_path=ledger, receipt_path=receipt)

    receipt.write_text(original_receipt, encoding="utf-8")
    rows = _rows(ledger)
    rows[0]["code_sha256"] = "d" * 64
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(EffectAttemptClaimError, match="canonical row differs"):
        verify_effect_attempt_claim(ledger_path=ledger, receipt_path=receipt)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"release_scope_sha256": "bad"}, "release scope"),
        ({"attempt_ordinal": 0}, "ordinal"),
        ({"parent_experiment_id": "bad"}, "parent identity"),
        ({"candidate_source": "/Users/private/result"}, "candidate_source"),
        ({"feature_or_formula": "API_KEY=forbidden-value"}, "feature_or_formula"),
    ],
)
def test_claim_spec_rejects_invalid_identity_paths_and_sensitive_values(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(EffectAttemptClaimError, match=message):
        _spec(**changes).validate()


def test_failure_before_claim_does_not_append_an_attempt(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(EffectAttemptClaimError, match="already claimed"):
        receipt = tmp_path / "receipt.json"
        receipt.write_text("occupied", encoding="utf-8")
        claim_effect_attempt(_spec(), ledger_path=ledger, receipt_path=receipt)
    assert _rows(ledger) == []
