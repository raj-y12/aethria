"""Directly-executed integration scripts (test_scouts.py, test_end_to_end.py,
test_partner_flow.py) must not spend real provider credentials unless
RUN_LIVE_TESTS=1 is explicitly set — even when a credential is already present
in the shell environment, not just in a loaded .env file."""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_require_openai_api_key_exits_without_run_live_tests_opt_in():
    env = {"PATH": "/usr/bin:/bin", "OPENAI_API_KEY": "live-key-must-not-be-used"}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, 'backend/tests'); "
            "from integration_helpers import require_openai_api_key; "
            "require_openai_api_key()",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "RUN_LIVE_TESTS=1" in (result.stdout + result.stderr)


def test_require_openai_api_key_succeeds_with_explicit_opt_in():
    env = {
        "PATH": "/usr/bin:/bin",
        "OPENAI_API_KEY": "live-key",
        "RUN_LIVE_TESTS": "1",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, 'backend/tests'); "
            "from integration_helpers import require_openai_api_key; "
            "print(require_openai_api_key())",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "live-key" in result.stdout
