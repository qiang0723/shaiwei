import ast
import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
POLICY_PATH = ROOT / "config/codebase_consolidation_v1.yaml"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tool_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names if alias.name.startswith("tools"))
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("tools"):
            result.add(node.module)
    return result


def _load() -> dict:
    return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))


def test_consolidation_policy_binds_frozen_parent_without_rewriting_it():
    policy = _load()
    assert policy["policy_id"] == "codebase-consolidation-v1"
    assert policy["version"] == 1
    assert policy["status"] == "SCHEDULED_NOT_EXECUTION_AUTHORIZED"
    for authority in policy["parent_authority"].values():
        assert _sha256(ROOT / authority["path"]) == authority["sha256"]
    assert (ROOT / policy["plan_document"]).is_file()


def test_checkpoint_requires_inventory_and_user_review_before_deletion():
    policy = _load()
    checkpoint = policy["first_checkpoint"]
    assert checkpoint == {
        "inventory_phase": "A1-0",
        "deletion_phase": "A1-1",
        "trigger": "after_m6_series_closes_before_next_major_strategy_pool_or_web_capability",
        "if_m6_followup_is_skipped": "before_next_major_capability",
        "automatic_deletion_authorized": False,
        "candidate_list_user_review_required": True,
    }
    assert policy["mandatory_line_reduction_target"] is None
    assert "immutable_data_artifacts_and_ledgers" in policy["protected_classes"]
    assert "characterization_tests_frozen_before_deletion" in policy["deletion_gates"]


def test_baseline_and_architecture_hotspot_identity_are_bound():
    policy = _load()
    architecture = yaml.safe_load(
        (ROOT / "config/architecture_constitution_v1.yaml").read_text(encoding="utf-8")
    )
    baseline = policy["baseline"]
    assert baseline["tracked_code_physical_lines"] == 113500
    assert baseline["core_python_physical_lines"] == 56703
    assert baseline["grandfathered_hotspot_count"] == len(
        architecture["module_size"]["grandfathered_hotspots"]
    )


def test_no_new_production_to_tools_dependency_is_hidden():
    policy = _load()["dependency_debt"]
    observed = {
        (path.relative_to(ROOT).as_posix(), imported)
        for path in (ROOT / "src/shaiwei").rglob("*.py")
        for imported in _tool_imports(path)
    }
    registered = {(item["path"], item["import"]) for item in policy["grandfathered"]}
    assert observed == registered
    for item in policy["grandfathered"]:
        assert item["boundary"].strip()
        assert item["decision"] == "A1_1A_DEFERRED_FROZEN_IDENTITY_CONFLICT"
        assert item["exit_trigger"].startswith("only after a versioned")
        assert (ROOT / item["decision_document"]).is_file()


def test_grandfathered_star50_executor_keeps_the_frozen_m4_identity():
    protocol = yaml.safe_load(
        (ROOT / "config/m4_star50_residual_effect_v1.yaml").read_text(encoding="utf-8")
    )
    upstream = protocol["upstream_contract"]
    path = ROOT / upstream["corrected_executor_path"]
    assert path.relative_to(ROOT).as_posix() == "tools/p2_star50_effect_correction/executor.py"
    assert _sha256(path) == upstream["corrected_executor_sha256"]
    assert upstream["corrected_executor_sha256"] == (
        "d8dbdb8bf0706af86757a853602c70dc4e7b5f73a901de1ea8f4045165bc9679"
    )
