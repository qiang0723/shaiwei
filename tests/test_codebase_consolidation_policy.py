import ast
import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
POLICY_PATH = ROOT / "config/codebase_consolidation_v1.yaml"
A1_1B_ADDENDUM_PATH = ROOT / "config/architecture_constitution_a1_1b_addendum_v1.yaml"
A1_1C_ADDENDUM_PATH = ROOT / "config/architecture_constitution_a1_1c_addendum_v1.yaml"


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


def _project_import_cycles() -> list[tuple[str, ...]]:
    source_root = ROOT / "src/shaiwei"
    modules: dict[str, Path] = {}
    for path in source_root.rglob("*.py"):
        relative = path.relative_to(ROOT / "src").with_suffix("")
        module = (
            ".".join(relative.parts[:-1])
            if relative.parts[-1] == "__init__"
            else ".".join(relative.parts)
        )
        modules[module] = path

    edges = {module: set() for module in modules}
    for module, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    parts = package.split(".")
                    prefix = ".".join(parts[: len(parts) - node.level + 1])
                    base = (
                        f"{prefix}.{node.module}"
                        if prefix and node.module
                        else prefix or node.module or ""
                    )
                else:
                    base = node.module or ""
                if base:
                    targets.append(base)
                targets.extend(
                    f"{base}.{alias.name}" if base else alias.name
                    for alias in node.names
                    if alias.name != "*"
                )
            for target in targets:
                candidate = target
                while candidate:
                    if candidate in modules:
                        if candidate != module:
                            edges[module].add(candidate)
                        break
                    candidate = candidate.rpartition(".")[0]

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    cycles: list[tuple[str, ...]] = []

    def visit(module: str) -> None:
        nonlocal index
        indices[module] = lowlinks[module] = index
        index += 1
        stack.append(module)
        on_stack.add(module)
        for dependency in edges[module]:
            if dependency not in indices:
                visit(dependency)
                lowlinks[module] = min(lowlinks[module], lowlinks[dependency])
            elif dependency in on_stack:
                lowlinks[module] = min(lowlinks[module], indices[dependency])
        if lowlinks[module] != indices[module]:
            return
        component: list[str] = []
        while True:
            dependency = stack.pop()
            on_stack.remove(dependency)
            component.append(dependency)
            if dependency == module:
                break
        if len(component) > 1:
            cycles.append(tuple(sorted(component)))

    for module in sorted(modules):
        if module not in indices:
            visit(module)
    return sorted(cycles)


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


def test_a1_1b_addendum_ratchets_d1_modules_without_rewriting_frozen_parent():
    addendum = yaml.safe_load(A1_1B_ADDENDUM_PATH.read_text(encoding="utf-8"))
    assert addendum["status"] == "ACTIVE"
    parent = addendum["parent_authority"]
    assert _sha256(ROOT / parent["path"]) == parent["sha256"]
    assert addendum["scope"]["frozen_parent_rewritten"] is False

    observed = {
        item["path"]: len((ROOT / item["path"]).read_text(encoding="utf-8").splitlines())
        for item in addendum["module_size_ratchets"]
    }
    limits = {
        item["path"]: item["max_lines"] for item in addendum["module_size_ratchets"]
    }
    assert observed == {
        "src/shaiwei/research/llm_factor.py": 944,
        "src/shaiwei/research/llm_factor_contract.py": 357,
        "src/shaiwei/research/deepseek_client.py": 808,
    }
    assert all(observed[path] <= limits[path] for path in observed)


def test_a1_1c_addendum_ratchets_m3_modules_and_all_import_cycles_to_zero():
    addendum = yaml.safe_load(A1_1C_ADDENDUM_PATH.read_text(encoding="utf-8"))
    assert addendum["status"] == "ACTIVE"
    parent = addendum["parent_authority"]
    assert _sha256(ROOT / parent["path"]) == parent["sha256"]
    assert addendum["scope"]["frozen_parent_rewritten"] is False

    observed = {
        item["path"]: len((ROOT / item["path"]).read_text(encoding="utf-8").splitlines())
        for item in addendum["module_size_ratchets"]
    }
    limits = {
        item["path"]: item["max_lines"] for item in addendum["module_size_ratchets"]
    }
    assert observed == {
        "src/shaiwei/research/m3_multi_pool_contract.py": 376,
        "src/shaiwei/research/m3_multi_pool_data.py": 295,
        "src/shaiwei/research/m3_multi_pool_release.py": 257,
    }
    assert all(observed[path] <= limits[path] for path in observed)
    assert addendum["dependency_ratchets"]["expected_python_import_cycle_count"] == 0
    release_tree = ast.parse(
        (ROOT / "src/shaiwei/research/m3_multi_pool_release.py").read_text(encoding="utf-8")
    )
    release_imports = {
        node.module
        for node in ast.walk(release_tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert set(addendum["dependency_ratchets"]["release_forbidden_imports"]).isdisjoint(
        release_imports
    )
    assert _project_import_cycles() == []
