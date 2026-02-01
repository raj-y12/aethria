#!/usr/bin/env python3
"""
Single canonical entrypoint for running Aethria locally.

Starts:
  - FastAPI backend (port 8000)
  - Frontend dev server (port 3000)
  - DealFlow agents (Scout, Reviewer, Partner, Portfolio) — agent logic logs stream below

Loads .env from repo root. Banner stays at top; rolling logs stream below
with [Backend] / [Frontend] / [Agents] so you can see API, Vite, and agent activity.
"""
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

REPO_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "app-front-end"
ENV_FILE = REPO_ROOT / ".env"

BACKEND_PORT = 8000
FRONTEND_PORT = 3000

# Keep banner at top; logs roll below
BANNER = (
    "============================================================\n"
    "Aethria — Single run entrypoint\n"
    "============================================================\n"
    "  Backend (FastAPI):  http://localhost:%s\n"
    "  Frontend (Vite):    http://localhost:%s\n"
    "  Agents:             Scout, Reviewer, Partner, Portfolio\n"
    "  Mode:               local development\n"
    "============================================================\n"
    "  Press Ctrl+C to stop all processes.\n"
    "  Rolling logs (API, frontend, agent logic) below.\n"
    "============================================================\n"
) % (BACKEND_PORT, FRONTEND_PORT)

# ANSI colours for prefixes (only when stdout is a TTY)
RESET = "\033[0m"
BACKEND_COLOR = "\033[36m"   # cyan
FRONTEND_COLOR = "\033[32m"  # green
AGENTS_COLOR = "\033[33m"    # yellow


def _stream_output(pipe, prefix: str, color: str = "", use_color: bool = False) -> None:
    """Read lines from pipe and print with coloured prefix. Runs in thread."""
    display_prefix = f"{color}{prefix}{RESET}" if use_color and color else prefix
    try:
        for line in iter(pipe.readline, b""):
            if line:
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    print(f"  {display_prefix} {text}", flush=True)
    except (ValueError, OSError):
        pass
    finally:
        try:
            pipe.close()
        except OSError:
            pass


def main() -> int:
    if load_dotenv and ENV_FILE.exists():
        load_dotenv(ENV_FILE)

    if not BACKEND_DIR.is_dir():
        print(f"Error: backend directory not found: {BACKEND_DIR}", file=sys.stderr)
        return 1
    if not FRONTEND_DIR.is_dir():
        print(f"Error: app-front-end directory not found: {FRONTEND_DIR}", file=sys.stderr)
        return 1

    # Banner at top — stays there; logs roll below
    print(BANNER, flush=True)

    use_color = sys.stdout.isatty()
    backend_proc = None
    frontend_proc = None
    agents_proc = None

    try:
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
            cwd=str(BACKEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        frontend_proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(FRONTEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=os.environ,
            shell=os.name == "nt",
        )
        agents_proc = subprocess.Popen(
            [sys.executable, "run_system.py"],
            cwd=str(BACKEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        # Stream logs so you can see API, frontend, and agent logic (scout/reviewer/partner/storage)
        t_backend = threading.Thread(
            target=_stream_output,
            args=(backend_proc.stdout, "[Backend]", BACKEND_COLOR, use_color),
            daemon=True,
        )
        t_frontend = threading.Thread(
            target=_stream_output,
            args=(frontend_proc.stdout, "[Frontend]", FRONTEND_COLOR, use_color),
            daemon=True,
        )
        t_agents = threading.Thread(
            target=_stream_output,
            args=(agents_proc.stdout, "[Agents]", AGENTS_COLOR, use_color),
            daemon=True,
        )
        t_backend.start()
        t_frontend.start()
        t_agents.start()

        while (
            backend_proc.poll() is None
            and frontend_proc.poll() is None
            and agents_proc.poll() is None
        ):
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        if backend_proc and backend_proc.poll() is None:
            backend_proc.terminate()
            backend_proc.wait()
        if frontend_proc and frontend_proc.poll() is None:
            frontend_proc.terminate()
            frontend_proc.wait()
        if agents_proc and agents_proc.poll() is None:
            agents_proc.terminate()
            agents_proc.wait()
        print("\nStopped.", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
