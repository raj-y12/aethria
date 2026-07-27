#!/usr/bin/env python3
"""
Single canonical entrypoint for running Aethria locally.

Starts:
  - FastAPI backend (port 8000) — serves both app and web APIs
  - App frontend (port 3000)
  - Web frontend (port 3001) — public marketing site
  - DealFlow agents (Scout, Reviewer, Partner, Portfolio)

Loads .env from repo root. Banner stays at top; rolling logs stream below
with [Backend] / [App] / [Web] / [Agents] so you can see API and frontend activity.
"""
import os
import re
import socket
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
APP_FRONTEND_DIR = REPO_ROOT / "app-front-end"
WEB_FRONTEND_DIR = REPO_ROOT / "web-front-end"
ENV_FILE = REPO_ROOT / ".env"

BACKEND_PORT = 8000
APP_FRONTEND_PORT = 3000
WEB_FRONTEND_PORT = 3001

# Keep banner at top; logs roll below
BANNER_WIDTH = 76

# ANSI colours for prefixes (only when stdout is a TTY)
RESET = "\033[0m"
BACKEND_COLOR = "\033[36m"   # cyan
APP_COLOR = "\033[32m"       # green
WEB_COLOR = "\033[35m"       # magenta
AGENTS_COLOR = "\033[33m"    # yellow
TIME_COLOR = "\033[90m"      # bright black / gray
ERROR_COLOR = "\033[91m"     # bright red
WARN_COLOR = "\033[93m"      # bright yellow
INFO_COLOR = "\033[96m"      # bright cyan
DEBUG_COLOR = "\033[94m"     # bright blue
DEFAULT_TEXT_COLOR = "\033[37m"  # white
TAG_DEFAULT_COLOR = "\033[95m"   # bright magenta
METHOD_COLOR = "\033[94m"        # bright blue
PATH_COLOR = "\033[97m"          # bright white
IP_COLOR = "\033[90m"            # gray
OXFORD_BLUE = "\033[38;2;0;33;71m"

ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
TAG_RE = re.compile(r"\[([A-Z0-9_\- ]{2,})\]")
LEADING_LEVEL_RE = re.compile(r"^\s*(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL)\s*:\s*", re.IGNORECASE)
HTTP_ACCESS_RE = re.compile(
    r'(?P<ip>\d{1,3}(?:\.\d{1,3}){3}):(?P<port>\d+)\s*-\s*"(?P<method>[A-Z]+)\s+(?P<path>[^"]+?)\s+HTTP/[0-9.]+"\s+(?P<status>\d{3})\s*(?P<rest>.*)$'
)
TAG_COLORS = {
    "SCOUT": "\033[92m",       # bright green
    "REVIEWER": "\033[94m",    # bright blue
    "PARTNER": "\033[95m",     # bright magenta
    "PORTFOLIO": "\033[96m",   # bright cyan
    "META": "\033[93m",        # bright yellow
    "MEMORY": "\033[90m",      # gray
    "AGENT": "\033[33m",       # yellow
    "SYSTEM": "\033[36m",      # cyan
    "PIPELINE": "\033[35m",    # magenta
    "AUTH": "\033[91m",        # red
    "BACKEND": "\033[36m",     # cyan
    "WEB": "\033[35m",         # magenta
    "APP": "\033[32m",         # green
}

SOURCE_COL_WIDTH = 8
LEVEL_COL_WIDTH = 5
HTTP_PATH_COL_WIDTH = 42


def _build_banner(use_color: bool) -> str:
    title = (
        "      █████╗ ███████╗████████╗██╗  ██╗██████╗ ██╗ █████╗      ",
        "     ██╔══██╗██╔════╝╚══██╔══╝██║  ██║██╔══██╗██║██╔══██╗     ",
        "     ███████║█████╗     ██║   ███████║██████╔╝██║███████║     ",
        "     ██╔══██║██╔══╝     ██║   ██╔══██║██╔══██╗██║██╔══██║     ",
        "     ██║  ██║███████╗   ██║   ██║  ██║██║  ██║██║██║  ██║     ",
        "     ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═╝     ",
    )
    line = "=" * BANNER_WIDTH
    if use_color:
        title_block = "\n".join(f"{OXFORD_BLUE}{row}{RESET}" for row in title)
    else:
        title_block = "\n".join(title)
    return (
        f"{line}\n"
        f"{title_block}\n"
        f"{line}\n"
        f"  Backend (API):      http://localhost:{BACKEND_PORT}  (app + web)\n"
        f"  App frontend:       http://localhost:{APP_FRONTEND_PORT}\n"
        f"  Web frontend:       http://localhost:{WEB_FRONTEND_PORT}\n"
        f"  Agents:             Scout, Reviewer, Partner, Portfolio\n"
        f"  Mode:               local development\n"
        f"{line}\n"
        f"  Press Ctrl+C to stop all processes.\n"
        f"  Rolling logs below.\n"
        f"{line}\n"
    )


def _strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def _extract_level(text: str) -> tuple[str, str]:
    """Map log level from a leading stdlib/uvicorn prefix only (e.g. INFO: ...).

    Do not scan the full line: multiline log continuations and JSON payloads often
    contain words like 'critical' or 'error' and would falsely show as ERROR.
    """
    clean_text = _strip_ansi(text).strip()
    m = LEADING_LEVEL_RE.match(clean_text)
    if not m:
        return "LOG", DEFAULT_TEXT_COLOR
    lev = m.group(1).upper()
    if lev == "DEBUG":
        return "DEBUG", DEBUG_COLOR
    if lev == "INFO":
        return "INFO", INFO_COLOR
    if lev in ("WARNING", "WARN"):
        return "WARN", WARN_COLOR
    return "ERROR", ERROR_COLOR


def _colorize_tags(text: str, use_color: bool) -> str:
    if not use_color:
        return text

    def _replace(match: re.Match) -> str:
        raw = match.group(1).strip()
        key = raw.upper()
        color = TAG_COLORS.get(key, TAG_DEFAULT_COLOR)
        return f"{color}[{raw}]{RESET}"

    return TAG_RE.sub(_replace, text)


def _status_color(status_code: int) -> str:
    if status_code >= 500:
        return ERROR_COLOR
    if status_code >= 400:
        return WARN_COLOR
    if status_code >= 300:
        return DEBUG_COLOR
    return "\033[92m"  # bright green for 2xx


def _fit(text: str, width: int) -> str:
    if len(text) <= width:
        return f"{text:<{width}}"
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


def _source_name(prefix: str) -> str:
    stripped = prefix.strip()
    if stripped.startswith("[") and stripped.endswith("]") and len(stripped) > 2:
        return stripped[1:-1]
    return stripped


def _normalize_message(text: str) -> str:
    clean = _strip_ansi(text).strip()
    # Avoid duplicated level text like "INFO: ...", because level has its own column.
    return LEADING_LEVEL_RE.sub("", clean)


def _format_http_access(text: str, use_color: bool) -> str | None:
    match = HTTP_ACCESS_RE.search(text)
    if not match:
        return None

    ip = match.group("ip")
    port = match.group("port")
    method = match.group("method")
    path = match.group("path")
    status = int(match.group("status"))
    rest = match.group("rest").strip()
    status_text = str(status)
    path_fitted = _fit(path, HTTP_PATH_COL_WIDTH)

    if not use_color:
        suffix = f" {rest}" if rest else ""
        return f"{method:<6} {path_fitted} [{status_text:>3}] ({ip}:{port}){suffix}"

    status_part = f"{_status_color(status)}[{status_text}]{RESET}"
    method_part = f"{METHOD_COLOR}{method:<6}{RESET}"
    path_part = f"{PATH_COLOR}{path_fitted}{RESET}"
    ip_part = f"{IP_COLOR}({ip}:{port}){RESET}"
    rest_part = f" {DEFAULT_TEXT_COLOR}{rest}{RESET}" if rest else ""
    return f"{method_part} {path_part}  {status_part}  {ip_part}{rest_part}"


def _format_log_line(prefix: str, source_color: str, text: str, use_color: bool) -> str:
    timestamp = time.strftime("%H:%M:%S")
    level, level_color = _extract_level(text)
    clean_text = _normalize_message(text)
    http_message = _format_http_access(clean_text, use_color)
    final_message = http_message if http_message is not None else _colorize_tags(clean_text, use_color)
    source_label = _fit(_source_name(prefix), SOURCE_COL_WIDTH)
    if not use_color:
        return f"{timestamp} | {source_label} | {level:<{LEVEL_COL_WIDTH}} | {final_message}"
    ts_part = f"{TIME_COLOR}{timestamp}{RESET}"
    source_part = f"{source_color}{source_label}{RESET}" if source_color else source_label
    level_part = f"{level_color}{level:<{LEVEL_COL_WIDTH}}{RESET}"
    message_part = f"{DEFAULT_TEXT_COLOR}{final_message}{RESET}"
    return f"{ts_part} | {source_part} | {level_part} | {message_part}"


def _stream_output(pipe, prefix: str, color: str = "", use_color: bool = False) -> None:
    """Read lines from pipe and print with enhanced formatting. Runs in thread."""
    try:
        for line in iter(pipe.readline, b""):
            if line:
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    print(f"  {_format_log_line(prefix, color, text, use_color)}", flush=True)
    except (ValueError, OSError):
        pass
    finally:
        try:
            pipe.close()
        except OSError:
            pass


def _stop_process(proc: subprocess.Popen | None) -> None:
    """Send SIGTERM, wait up to 15s. On timeout or Ctrl+C during wait, SIGKILL."""
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    except KeyboardInterrupt:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except (KeyboardInterrupt, subprocess.TimeoutExpired):
            pass


def _wait_for_tcp(host: str, port: int, timeout_seconds: float = 20.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def _critical_services_running(
    backend_proc: subprocess.Popen,
    app_proc: subprocess.Popen,
    web_proc: subprocess.Popen,
) -> bool:
    """Only user-facing services determine the root supervisor lifetime."""

    return all(
        process.poll() is None
        for process in (backend_proc, app_proc, web_proc)
    )


def main() -> int:
    if load_dotenv and ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)

    if not BACKEND_DIR.is_dir():
        print(f"Error: backend directory not found: {BACKEND_DIR}", file=sys.stderr)
        return 1
    if not APP_FRONTEND_DIR.is_dir():
        print(f"Error: app-front-end directory not found: {APP_FRONTEND_DIR}", file=sys.stderr)
        return 1
    if not WEB_FRONTEND_DIR.is_dir():
        print(f"Error: web-front-end directory not found: {WEB_FRONTEND_DIR}", file=sys.stderr)
        return 1

    use_color = sys.stdout.isatty()
    # Banner at top — stays there; logs roll below
    print(_build_banner(use_color), flush=True)
    backend_proc = None
    app_proc = None
    web_proc = None
    agents_proc = None

    try:
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", str(BACKEND_PORT), "--workers", "1"],
            cwd=str(BACKEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        if backend_proc.poll() is not None:
            print("  [run.py] Backend process exited before accepting connections.", flush=True)
            return 1
        if not _wait_for_tcp("127.0.0.1", BACKEND_PORT):
            print(f"  [run.py] Backend did not accept TCP connections on 127.0.0.1:{BACKEND_PORT} within 20s.", flush=True)
            return 1
        if backend_proc.poll() is not None:
            print("  [run.py] Backend process exited during startup.", flush=True)
            return 1
        # `--force` re-optimizes Vite's dep cache on every launch. Without it, a
        # branch switch that adds/removes/renames files can leave node_modules/.vite
        # inconsistent, which renders a blank page with no error in the console.
        # Paying ~200ms of re-optimization here trades that silent failure for a
        # reliably fresh dev server.
        app_proc = subprocess.Popen(
            ["npm", "run", "dev", "--", "--force"],
            cwd=str(APP_FRONTEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=os.environ,
            shell=os.name == "nt",
        )
        web_proc = subprocess.Popen(
            ["npm", "run", "dev", "--", "--force"],
            cwd=str(WEB_FRONTEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={**os.environ, "VITE_API_URL": f"http://127.0.0.1:{BACKEND_PORT}"},
            shell=os.name == "nt",
        )
        # When using Supabase, agents need a user_id (AETHRIA_AGENT_USER_ID or run_system.py --user-id).
        # If unset, skip the agents process; pipeline runs when users log in and trigger via API.
        use_supabase = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
        agent_user_id = os.getenv("AETHRIA_AGENT_USER_ID", "").strip()
        start_agents = True
        if use_supabase and not agent_user_id:
            start_agents = False
            print("  [run.py] Supabase on; no AETHRIA_AGENT_USER_ID. Skipping the legacy agents subprocess. "
                  "The API will resume user-scoped agent loops after login.", flush=True)
        agents_proc = None
        if start_agents:
            agents_cmd = [sys.executable, "run_system.py"]
            if agent_user_id:
                agents_cmd.extend(["--user-id", agent_user_id])
            agents_proc = subprocess.Popen(
                agents_cmd,
                cwd=str(BACKEND_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )

        # Stream logs
        t_backend = threading.Thread(
            target=_stream_output,
            args=(backend_proc.stdout, "[Backend]", BACKEND_COLOR, use_color),
            daemon=True,
        )
        t_app = threading.Thread(
            target=_stream_output,
            args=(app_proc.stdout, "[App]", APP_COLOR, use_color),
            daemon=True,
        )
        t_web = threading.Thread(
            target=_stream_output,
            args=(web_proc.stdout, "[Web]", WEB_COLOR, use_color),
            daemon=True,
        )
        if agents_proc is not None:
            t_agents = threading.Thread(
                target=_stream_output,
                args=(agents_proc.stdout, "[Agents]", AGENTS_COLOR, use_color),
                daemon=True,
            )
            t_agents.start()
        t_backend.start()
        t_app.start()
        t_web.start()

        agent_exit_reported = False
        while _critical_services_running(backend_proc, app_proc, web_proc):
            if (
                agents_proc is not None
                and agents_proc.poll() is not None
                and not agent_exit_reported
            ):
                print(
                    "Agents process exited; Backend and frontends remain available.",
                    file=sys.stderr,
                    flush=True,
                )
                agent_exit_reported = True
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        _stop_process(backend_proc)
        _stop_process(app_proc)
        _stop_process(web_proc)
        _stop_process(agents_proc)
        print("\nStopped.", flush=True)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
