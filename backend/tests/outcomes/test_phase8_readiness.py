import json
import os
import subprocess
import sys
from pathlib import Path


BACKEND = Path(__file__).parents[2]


def test_phase8_readiness_reports_missing_database_without_leaking_configuration():
    env = dict(os.environ)
    env.pop("DATABASE_URL", None)
    env.pop("SUPABASE_DB_URL", None)
    result = subprocess.run(
        [sys.executable, "scripts/check_phase8_readiness.py", "--json"],
        cwd=BACKEND,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ready"] is False
    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["golden_set_v7"]["status"] == "passed"
    assert checks["meta_proposal_only"]["status"] == "passed"
    assert checks["direct_database_dsn"]["status"] == "blocked"
    assert "postgresql://" not in result.stdout.lower()
