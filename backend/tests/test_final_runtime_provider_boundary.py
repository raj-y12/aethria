"""Guards for the final runtime boundary before SDK/config removal."""

import ast
from pathlib import Path


BACKEND = Path(__file__).parents[1]
RUNTIME_MODULES = (
    "api.py",
    "pipeline_runner.py",
    "admin_service.py",
    "evaluation_v2/prerequisites.py",
    "meta/analyser.py",
    "routers/deps.py",
    "routers/fund_thesis.py",
    "routers/meta.py",
    "startup_repository.py",
    "services/scoring/policy_store.py",
    "services/scoring/policy_upgrade.py",
)


def _module_level_supabase_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    found: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        found.extend(name for name in names if name.startswith("supabase"))
    return found


def test_normal_runtime_modules_have_no_module_level_supabase_imports():
    offenders = {
        str(path.relative_to(BACKEND)): _module_level_supabase_imports(path)
        for relative in RUNTIME_MODULES
        if (path := BACKEND / relative).exists()
        and _module_level_supabase_imports(path)
    }
    assert offenders == {}


def test_migrated_meta_and_startup_boundaries_do_not_import_legacy_storage():
    for relative in ("meta/analyser.py", "startup_repository.py"):
        source = (BACKEND / relative).read_text()
        assert "supabase_doc_store" not in source
        assert "from supabase_storage" not in source
