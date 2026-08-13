from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCOPE_V1 = ROOT / "config/ts_v5_llm_research_scope_v1.yaml"
SCOPE_V2 = ROOT / "config/ts_v5_llm_research_scope_v2.yaml"


def load_scope() -> dict[str, object]:
    return yaml.safe_load(SCOPE_V2.read_text(encoding="utf-8"))


def test_v2_preserves_v1_and_supersedes_it_before_execution() -> None:
    scope = load_scope()
    prior = scope["supersedes_before_execution"]

    assert sha256(SCOPE_V1.read_bytes()).hexdigest() == prior["scope_sha256"]
    assert prior["provider_calls_under_prior_scope"] == 0
    assert prior["secret_reads_under_prior_scope"] == 0
    assert scope["program_budget_authorized_by_user"] is True
    assert scope["execution_authorized"] is False
    assert scope["first_batch_user_approval_received"] is False
    assert scope["deepseek_api_called"] is False


def test_program_ceiling_does_not_expand_first_batch() -> None:
    scope = load_scope()
    cost = scope["cost_contract"]
    planned = Decimal(cost["planned_worst_case_all_cache_miss_usd"])
    batch = Decimal(cost["first_batch_hard_ceiling_usd"])
    program = Decimal(cost["ts_v5_program_hard_ceiling_usd"])

    assert planned < batch < program
    assert batch == Decimal("0.50")
    assert program == Decimal("5.00")
    assert cost["unused_program_budget_is_not_execution_authority"] is True
    assert cost["unused_batch_budget_carryover"] is False
    assert cost["every_future_batch_requires_new_scoped_release_and_user_approval"] is True


def test_v2_keeps_the_first_batch_and_send_boundary_unchanged() -> None:
    v1 = yaml.safe_load(SCOPE_V1.read_text(encoding="utf-8"))
    v2 = load_scope()

    assert v2["provider_contract"] == v1["provider_contract"]
    assert v2["attempt_contract"] == v1["attempt_contract"]
    assert v2["send_allowlist"] == v1["send_allowlist"]
    assert v2["send_forbidden"] == v1["send_forbidden"]
    assert v2["production_authorization"] == "none"
