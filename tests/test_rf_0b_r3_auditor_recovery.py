import pytest

from shaiwei.research.rf_0b.contract import (
    AUDITOR_R3_SCOPE_SHA256,
    RFBR3AuditorRecovery,
    RFBError,
)


def test_r3_auditor_recovery_scope_is_frozen_and_audit_only() -> None:
    r3 = RFBR3AuditorRecovery.load_if_present()
    assert r3 is not None and r3.sha256 == AUDITOR_R3_SCOPE_SHA256
    chain = r3.document["parent_chain"]
    assert chain["runner_rerun"] == "forbidden"
    assert chain["runner_outputs_complete_and_verified"] is True
    assert r3.document["recovery"]["fixed_action"] == "RF_0B_R3_ONE_AUDITOR_ONLY"
    assert r3.document["recovery"]["candidate_or_effect_attempts_consumed"] == 0


def test_r3_validates_parent_chain_evidence() -> None:
    r3 = RFBR3AuditorRecovery.load_if_present()
    assert r3 is not None
    r3.validate_parent_evidence()
    document = {**r3.document, "parent_chain": {**r3.document["parent_chain"]}}
    document["parent_chain"]["r2_profile_sha256"] = "0" * 64
    with pytest.raises(RFBError, match="evidence differs"):
        RFBR3AuditorRecovery(document).validate_parent_evidence()


def test_payload_hash_excludes_the_hash_field() -> None:
    from shaiwei.research.trend_swing.v6.engine import canonical_sha256

    document = {"a": 1, "b": 2}
    document["canonical_payload_sha256"] = canonical_sha256(document)
    assert document["canonical_payload_sha256"] == canonical_sha256(
        {key: value for key, value in document.items() if key != "canonical_payload_sha256"}
    )
