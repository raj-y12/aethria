from pathlib import Path


REPO_ROOT = Path(__file__).parents[2]
RUNTIME_MODULES = (
    REPO_ROOT / "portfolio" / "store.py",
    REPO_ROOT / "pipeline_runner.py",
    REPO_ROOT / "routers" / "deps.py",
    REPO_ROOT / "portfolio" / "engine.py",
)


def test_portfolio_startups_is_not_a_runtime_startup_authority():
    sources = {
        path.relative_to(REPO_ROOT): path.read_text(encoding="utf-8")
        for path in RUNTIME_MODULES
    }
    assert all("portfolio_startups" not in source for source in sources.values()), sources
    assert all('.table("portfolio_startups")' not in source for source in sources.values()), sources
    assert "self._supabase_tables: Dict[str, str] = {}" in sources[Path("portfolio/store.py")]
