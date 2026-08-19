from pathlib import Path

from shaiwei.provenance import CONTROLLED_FILES
from shaiwei.research.rf_1.contract import PROTOCOL_SHA256, RF1Scope


ROOT = Path(__file__).parents[1]


def test_protocol_freezes_batch_and_candidate_contract() -> None:
    scope = RF1Scope.load()
    assert scope.sha256 == PROTOCOL_SHA256
    batch = scope.document["batch_contract"]
    assert batch["completed_responses_maximum"] == 8
    assert batch["qualified_candidates_maximum"] == 3
    assert batch["single_batch_hard_ceiling_usd"] == 1.00
    assert batch["no_backfill_or_substitution"] is True
    candidate = scope.document["candidate_contract"]
    assert candidate["must_reference_open_and_close"] is True
    assert candidate["maximum_lookback_trade_days"] == 50
    assert scope.document["production_authorization"] == "none"


def test_execution_is_double_gated() -> None:
    chain = RF1Scope.load().document["authority_chain"]
    required = chain["execution_requires_all_of"]
    assert "r2_1_natural_forward_checkpoint_completed" in required
    assert "explicit_user_batch_authorization" in required


def test_rf_1_package_respects_module_size_and_no_generic_dumping_ground() -> None:
    package = ROOT / "src/shaiwei/research/rf_1"
    sizes = {path.name: len(path.read_text(encoding="utf-8").splitlines()) for path in package.glob("*.py")}
    assert sizes and max(sizes.values()) <= 400
    assert not ({"utils.py", "helpers.py", "common.py"} & set(sizes))
    assert "Dockerfile.ts-rf-1" in CONTROLLED_FILES
    assert "compose.ts-rf-1.yaml" in CONTROLLED_FILES
