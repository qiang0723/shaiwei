from pathlib import Path


ROOT = Path(__file__).parents[1]


def _lines(relative: str) -> int:
    return len((ROOT / relative).read_text(encoding="utf-8").splitlines())


def test_web_modularization_ratchet():
    bounded_modules = (
        "src/shaiwei/web/query.py",
        "src/shaiwei/web/query_evidence.py",
        "src/shaiwei/web/query_paper.py",
        "src/shaiwei/web/query_signal.py",
        "web-ui/src/validation.ts",
        "web-ui/src/validation/core.ts",
        "web-ui/src/validation/paper.ts",
        "web-ui/src/validation/operations.ts",
        "web-ui/src/validation/factors.ts",
        "web-ui/src/validation/experiments.ts",
        "web-ui/src/styles.css",
        "web-ui/src/styles/00-foundation-shell.css",
        "web-ui/src/styles/10-components-paper.css",
        "web-ui/src/styles/20-tables-evidence.css",
        "web-ui/src/styles/30-operations.css",
        "web-ui/src/styles/40-factors.css",
        "web-ui/src/styles/50-experiments.css",
        "web-ui/src/styles/60-responsive-legacy.css",
        "web-ui/src/styles/70-redesign-base.css",
        "web-ui/src/styles/80-redesign-components.css",
        "web-ui/src/styles/90-responsive-current.css",
        "web-ui/src/pages/FactorsPage.tsx",
        "web-ui/src/pages/factors/presentation.tsx",
        "web-ui/src/pages/factors/CatalogPage.tsx",
        "web-ui/src/pages/factors/DetailPage.tsx",
        "web-ui/src/pages/factors/AdmissionsPage.tsx",
        "web-ui/src/pages/factors/ComparePage.tsx",
        "web-ui/src/pages/ExperimentsPage.tsx",
        "web-ui/src/pages/experiments/presentation.tsx",
        "web-ui/src/pages/experiments/CatalogPage.tsx",
        "web-ui/src/pages/experiments/DetailPage.tsx",
    )
    oversized = {path: _lines(path) for path in bounded_modules if _lines(path) > 600}
    assert oversized == {}


def test_web_page_entries_are_thin_and_domain_isolated():
    entries = (
        "web-ui/src/pages/FactorsPage.tsx",
        "web-ui/src/pages/ExperimentsPage.tsx",
    )
    for relative in entries:
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert _lines(relative) <= 100
        assert "@tanstack/react-query" not in source
        assert "@ant-design/charts" not in source
        assert "fetchFactor" not in source
        assert "fetchExperiment" not in source

    for relative in (ROOT / "web-ui/src/pages/factors").glob("*.tsx"):
        assert "../experiments/" not in relative.read_text(encoding="utf-8")
    for relative in (ROOT / "web-ui/src/pages/experiments").glob("*.tsx"):
        assert "../factors/" not in relative.read_text(encoding="utf-8")


def test_web_query_layers_do_not_pull_runtime_configuration():
    for relative in (
        "src/shaiwei/web/query.py",
        "src/shaiwei/web/query_evidence.py",
        "src/shaiwei/web/query_paper.py",
        "src/shaiwei/web/query_signal.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "shaiwei.config" not in source
        assert "load_dotenv" not in source
        assert "shaiwei.web.api" not in source
