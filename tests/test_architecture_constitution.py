import ast
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
POLICY_PATH = ROOT / "config/architecture_constitution_v1.yaml"


def _load_policy() -> dict:
    return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))


def _matched_files(includes: list[str], excludes: list[str]) -> set[Path]:
    included = {path for pattern in includes for path in ROOT.glob(pattern) if path.is_file()}
    excluded = {path for pattern in excludes for path in ROOT.glob(pattern) if path.is_file()}
    return included - excluded


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _python_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package_parts = path.relative_to(ROOT / "src").parent.parts
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if not node.level:
                if node.module:
                    imports.add(node.module)
                continue
            parent_count = node.level - 1
            base = package_parts[: len(package_parts) - parent_count] if parent_count else package_parts
            if node.module:
                imports.add(".".join((*base, *node.module.split("."))))
            else:
                imports.update(".".join((*base, alias.name)) for alias in node.names)
    return imports


def _matches_prefix(import_name: str, prefix: str) -> bool:
    return import_name == prefix or import_name.startswith(f"{prefix}.")


def test_architecture_policy_identity_and_entrypoints_are_bound():
    policy = _load_policy()
    document_path = ROOT / policy["document"]
    document = document_path.read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert policy["policy_id"] == "architecture-constitution-v1"
    assert policy["version"] == 1
    assert policy["status"] == "ACTIVE"
    assert policy["policy_id"] in document
    assert policy["document"] in agents
    assert "architecture-check:" in makefile


def test_production_module_hard_limit_is_a_non_growing_ratchet():
    policy = _load_policy()["module_size"]
    soft_limit = policy["soft_limit_lines"]
    hard_limit = policy["hard_limit_lines"]
    assert 0 < soft_limit < hard_limit

    files = _matched_files(policy["include"], policy["exclude"])
    registered_items = policy["grandfathered_hotspots"]
    registered = {item["path"]: item for item in registered_items}
    assert len(registered) == len(registered_items)

    oversized = {_relative(path): _line_count(path) for path in files if _line_count(path) > hard_limit}
    assert set(oversized) == set(registered)

    for relative, item in registered.items():
        assert relative in oversized
        assert oversized[relative] <= item["max_lines"]
        assert item["boundary"].strip()
        assert item["exit_trigger"].strip()


def test_declared_dependency_directions_hold():
    violations: list[str] = []
    for rule in _load_policy()["dependency_rules"]:
        files = _matched_files(rule["include"], rule["exclude"])
        for path in sorted(files):
            if path.suffix != ".py":
                continue
            for import_name in sorted(_python_imports(path)):
                for prefix in rule["forbidden_import_prefixes"]:
                    if _matches_prefix(import_name, prefix):
                        violations.append(f"{rule['id']}: {_relative(path)} imports {import_name}")
    assert violations == []
