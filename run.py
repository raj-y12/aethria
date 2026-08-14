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
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

REPO_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = REPO_ROOT / "backend"
APP_FRONTEND_DIR = REPO_ROOT / "app-front-end"
WEB_FRONTEND_DIR = REPO_ROOT / "web-front-end"
ENV_FILE = REPO_ROOT / ".env"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
SNAPSHOT_COMPOSE_FILE = REPO_ROOT / "docker-compose.snapshot.yml"
SNAPSHOT_DATABASE_NAME = "aethria_prod_snapshot"
SNAPSHOT_VERIFIER = BACKEND_DIR / "scripts" / "verify_local_snapshot.py"

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


class _TerminalRenderer:
    """Keep the launcher banner fixed while log lines scroll below it."""

    def __init__(
        self,
        banner: str,
        *,
        stream=None,
        enabled: bool | None = None,
        terminal_lines: int | None = None,
        terminal_columns: int | None = None,
        use_color: bool = False,
    ) -> None:
        self._stream = stream or sys.stdout
        self._banner = banner.rstrip("\n")
        self._banner_lines = self._banner.splitlines()
        self._terminal_lines = terminal_lines or shutil.get_terminal_size(
            fallback=(120, 24)
        ).lines
        self._terminal_columns = terminal_columns or shutil.get_terminal_size(
            fallback=(120, 24)
        ).columns
        self._use_color = use_color
        title_lines = self._banner_lines[1:7]
        title_width = max(
            (len(ANSI_RE.sub("", line)) for line in title_lines),
            default=0,
        )
        self._title_box_width = min(
            max(title_width + 4, BANNER_WIDTH),
            self._terminal_columns,
        )
        interactive = self._stream.isatty() if enabled is None else enabled
        self._fixed = bool(
            interactive and self._terminal_lines > len(self._banner_lines) + 2
        )
        self._lock = threading.RLock()

    def _banner_line(self, index: int, line: str) -> str:
        clean_line = ANSI_RE.sub("", line)
        if 1 <= index <= 6:
            # Keep the artwork at its original left-aligned banner position.
            clean_line = clean_line.rstrip().ljust(self._title_box_width)
            left_padding = 0
            right_padding = self._terminal_columns - self._title_box_width
            if not self._use_color:
                return f"{' ' * left_padding}{clean_line}{' ' * right_padding}"
            return (
                f"{' ' * left_padding}\x1b[47m{OXFORD_BLUE}{clean_line}"
                f"{RESET}{' ' * right_padding}"
            )
        else:
            clean_line = clean_line.ljust(self._terminal_columns)
        if not self._use_color:
            return clean_line
        return clean_line

    def start(self) -> None:
        with self._lock:
            if not self._fixed:
                self._stream.write(f"{self._banner}\n")
                self._stream.flush()
                return
            self._stream.write("\x1b[2J\x1b[H")
            for index, line in enumerate(self._banner_lines):
                self._stream.write(f"{self._banner_line(index, line)}\x1b[K\n")
            first_log_line = len(self._banner_lines) + 1
            self._stream.write(
                f"\x1b[{first_log_line};{self._terminal_lines}r"
                f"\x1b[{first_log_line};1H"
            )
            self._stream.flush()

    def emit(self, line: str) -> None:
        with self._lock:
            if not self._fixed:
                self._stream.write(f"{line}\n")
                self._stream.flush()
                return
            self._stream.write(f"\r{line}\x1b[K\n")
            self._stream.flush()

    def close(self) -> None:
        if not self._fixed:
            return
        with self._lock:
            self._stream.write("\x1b[r\x1b[?25h")
            self._stream.flush()


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


def _should_start_agents(*, use_supabase: bool, agent_user_id: str) -> bool:
    """Only start the tenant-scoped agent CLI when an explicit tenant exists."""
    return bool(agent_user_id.strip())


def _local_postgres_dsn() -> str:
    """Return the configured local DSN, or an empty string for remote storage."""
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        return ""
    parsed = urlsplit(dsn)
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        return ""
    if parsed.port != 15432:
        return ""
    return dsn


def _is_snapshot_database(database_url: str) -> bool:
    """Return whether a DSN targets the preserved local production snapshot."""
    return urlsplit(database_url).path.lstrip("/") == SNAPSHOT_DATABASE_NAME


def _compose_file_for_database(database_url: str) -> Path:
    """Keep the preserved snapshot on a volume separate from disposable tests."""
    return SNAPSHOT_COMPOSE_FILE if _is_snapshot_database(database_url) else COMPOSE_FILE


def _should_apply_local_migrations(database_url: str) -> bool:
    """Normal startup may migrate disposable test databases, never the snapshot."""
    return not _is_snapshot_database(database_url)


def _compose_command() -> list[str]:
    docker = shutil.which("docker")
    if docker is not None:
        probe = subprocess.run(
            [docker, "compose", "version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode == 0:
            return [docker, "compose"]
    legacy = shutil.which("docker-compose")
    if legacy is not None:
        return [legacy]
    raise RuntimeError(
        "Docker Compose is required to start local PostgreSQL "
        "(install the Docker Compose plugin or docker-compose)"
    )


def _docker_compose(
    *args: str,
    check: bool = True,
    capture_output: bool = False,
    compose_file: Path = COMPOSE_FILE,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*_compose_command(), "-f", str(compose_file), *args],
        cwd=str(REPO_ROOT),
        check=check,
        capture_output=capture_output,
        text=True,
    )


def _local_postgres_running(compose_file: Path = COMPOSE_FILE) -> bool:
    result = _docker_compose(
        "ps",
        "--status",
        "running",
        "-q",
        "postgres",
        check=False,
        capture_output=True,
        compose_file=compose_file,
    )
    return bool(result.stdout and result.stdout.strip())


def _start_local_postgres_and_migrate(database_url: str) -> bool:
    """Start local PostgreSQL and verify the snapshot or migrate test storage."""
    compose_file = _compose_file_for_database(database_url)
    if not compose_file.exists():
        raise RuntimeError(f"Local PostgreSQL compose file is missing: {compose_file}")
    already_running = _local_postgres_running(compose_file)
    started = not already_running
    if not already_running:
        print("  [run.py] Starting local PostgreSQL...", flush=True)
        _docker_compose("up", "-d", "postgres", compose_file=compose_file)
    try:
        parsed = urlsplit(database_url)
        database_name = parsed.path.lstrip("/")
        database_user = parsed.username or "aethria"
        deadline = time.time() + 30.0
        database_ready = False
        while time.time() < deadline:
            if _wait_for_tcp("127.0.0.1", 15432, timeout_seconds=0.5):
                probe = _docker_compose(
                    "exec",
                    "-T",
                    "postgres",
                    "pg_isready",
                    "-U",
                    database_user,
                    "-d",
                    database_name,
                    check=False,
                    capture_output=True,
                    compose_file=compose_file,
                )
                if probe.returncode == 0:
                    database_ready = True
                    break
            time.sleep(0.25)
        if not database_ready:
            raise RuntimeError(
                f"Local PostgreSQL database {database_name!r} did not become ready"
            )

        if _should_apply_local_migrations(database_url):
            print("  [run.py] Applying local PostgreSQL migrations...", flush=True)
            subprocess.run(
                [
                    sys.executable,
                    str(BACKEND_DIR / "scripts" / "migrate_postgres.py"),
                    "--database-url",
                    database_url,
                ],
                cwd=str(BACKEND_DIR),
                check=True,
                env={**os.environ, "DATABASE_URL": database_url},
            )
        else:
            print("  [run.py] Verifying preserved local production snapshot...", flush=True)
            subprocess.run(
                [
                    sys.executable,
                    str(SNAPSHOT_VERIFIER),
                    "--database-url",
                    database_url,
                ],
                cwd=str(REPO_ROOT),
                check=True,
                env={**os.environ, "DATABASE_URL": database_url},
            )
        return started
    except Exception:
        if started:
            _docker_compose("stop", "postgres", check=False, compose_file=compose_file)
        raise


def _stream_output(
    pipe,
    prefix: str,
    color: str = "",
    use_color: bool = False,
    renderer: _TerminalRenderer | None = None,
) -> None:
    """Read lines from pipe and print with enhanced formatting. Runs in thread."""
    try:
        for line in iter(pipe.readline, b""):
            if line:
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    formatted = f"  {_format_log_line(prefix, color, text, use_color)}"
                    if renderer is not None:
                        renderer.emit(formatted)
                    else:
                        print(formatted, flush=True)
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


def _wait_for_tcp(
    host: str,
    port: int,
    timeout_seconds: float = 20.0,
    process: subprocess.Popen | None = None,
) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            return False
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
    started_local_postgres = False
    local_database_url = ""
    renderer = _TerminalRenderer(
        _build_banner(use_color),
        stream=sys.stdout,
        enabled=sys.stdout.isatty(),
        use_color=use_color,
    )
    renderer.start()

    try:
        local_database_url = _local_postgres_dsn()
        if local_database_url:
            started_local_postgres = _start_local_postgres_and_migrate(
                local_database_url
            )
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", str(BACKEND_PORT), "--workers", "1"],
            cwd=str(BACKEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        t_backend = threading.Thread(
            target=_stream_output,
            args=(backend_proc.stdout, "[Backend]", BACKEND_COLOR, use_color, renderer),
            daemon=True,
        )
        t_backend.start()
        if backend_proc.poll() is not None:
            t_backend.join(timeout=1)
            print("  [run.py] Backend process exited before accepting connections.", flush=True)
            return 1
        if not _wait_for_tcp("127.0.0.1", BACKEND_PORT, process=backend_proc):
            t_backend.join(timeout=1)
            if backend_proc.poll() is not None:
                print(
                    f"  [run.py] Backend exited during startup (code {backend_proc.returncode}).",
                    flush=True,
                )
            else:
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
        start_agents = _should_start_agents(
            use_supabase=use_supabase,
            agent_user_id=agent_user_id,
        )
        if not start_agents:
            print("  [run.py] No AETHRIA_AGENT_USER_ID. Skipping the legacy agents subprocess. "
                  "The API will run user-scoped agent loops after login.", flush=True)
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
        t_app = threading.Thread(
            target=_stream_output,
            args=(app_proc.stdout, "[App]", APP_COLOR, use_color, renderer),
            daemon=True,
        )
        t_web = threading.Thread(
            target=_stream_output,
            args=(web_proc.stdout, "[Web]", WEB_COLOR, use_color, renderer),
            daemon=True,
        )
        if agents_proc is not None:
            t_agents = threading.Thread(
                target=_stream_output,
                args=(agents_proc.stdout, "[Agents]", AGENTS_COLOR, use_color, renderer),
                daemon=True,
            )
            t_agents.start()
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
    except Exception as exc:
        print(f"  [run.py] Startup failed: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        _stop_process(backend_proc)
        _stop_process(app_proc)
        _stop_process(web_proc)
        _stop_process(agents_proc)
        if started_local_postgres:
            try:
                _docker_compose(
                    "stop",
                    "postgres",
                    check=False,
                    compose_file=_compose_file_for_database(local_database_url),
                )
            except Exception as exc:
                print(
                    f"  [run.py] Could not stop local PostgreSQL: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
        renderer.close()
        print("\nStopped.", flush=True)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
