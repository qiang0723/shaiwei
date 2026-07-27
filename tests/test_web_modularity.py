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
    )
    oversized = {path: _lines(path) for path in bounded_modules if _lines(path) > 600}
    assert oversized == {}


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
