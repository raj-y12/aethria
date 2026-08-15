from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path


def _root_run_module():
    path = Path(__file__).resolve().parents[2] / "run.py"
    spec = spec_from_file_location("aethria_root_run", path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Process:
    def __init__(self, exit_code):
        self.exit_code = exit_code

    def poll(self):
        return self.exit_code


def test_agent_child_exit_does_not_mark_critical_services_stopped():
    root_run = _root_run_module()
    running = _Process(None)
    exited_agents = _Process(1)

    assert root_run._critical_services_running(running, running, running) is True
    assert exited_agents.poll() == 1


def test_frontend_or_backend_exit_stops_root_supervisor():
    root_run = _root_run_module()
    running = _Process(None)
    exited = _Process(1)

    assert root_run._critical_services_running(exited, running, running) is False
    assert root_run._critical_services_running(running, exited, running) is False
    assert root_run._critical_services_running(running, running, exited) is False


def test_agents_start_only_with_an_explicit_tenant():
    root_run = _root_run_module()

    assert root_run._should_start_agents(use_supabase=False, agent_user_id="") is False
    assert root_run._should_start_agents(use_supabase=False, agent_user_id="user-a") is True
    assert root_run._should_start_agents(use_supabase=True, agent_user_id="") is False


def test_backend_command_enables_reload_without_worker_mode():
    root_run = _root_run_module()

    command = root_run._backend_command()

    assert command[:4] == [root_run.sys.executable, "-m", "uvicorn", "api:app"]
    assert "--reload" in command
    assert "--workers" not in command


def test_run_pipeline_only_auto_starts_the_explicit_local_postgres_target(monkeypatch):
    root_run = _root_run_module()

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://aethria:local-test-password@127.0.0.1:15432/aethria_test",
    )
    assert root_run._local_postgres_dsn().endswith("@127.0.0.1:15432/aethria_test")

    monkeypatch.setenv("DATABASE_URL", "postgresql://example.supabase.co:5432/postgres")
    assert root_run._local_postgres_dsn() == ""


def test_snapshot_database_selects_isolated_compose_stack():
    root_run = _root_run_module()

    snapshot_dsn = "postgresql://aethria:local-test-password@127.0.0.1:15432/aethria_prod_snapshot"
    test_dsn = "postgresql://aethria:local-test-password@127.0.0.1:15432/aethria_test"

    assert root_run._is_snapshot_database(snapshot_dsn)
    assert not root_run._is_snapshot_database(test_dsn)
    assert root_run._compose_file_for_database(snapshot_dsn) == root_run.SNAPSHOT_COMPOSE_FILE
    assert root_run._compose_file_for_database(test_dsn) == root_run.COMPOSE_FILE


def test_compose_command_starts_colima_when_the_active_daemon_is_unavailable(monkeypatch):
    root_run = _root_run_module()
    calls = []
    docker = "/opt/homebrew/bin/docker"
    colima = "/opt/homebrew/bin/colima"

    def fake_which(command):
        return {"docker": docker, "colima": colima}.get(command)

    def fake_run(command, **kwargs):
        calls.append(command)
        if command == [docker, "info"]:
            return root_run.subprocess.CompletedProcess(command, 1, stderr="daemon unavailable")
        if command == [docker, "context", "show"]:
            return root_run.subprocess.CompletedProcess(command, 0, stdout="colima\n")
        if command == [colima, "start"]:
            return root_run.subprocess.CompletedProcess(command, 0)
        if command == [docker, "compose", "version"]:
            return root_run.subprocess.CompletedProcess(command, 0)
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(root_run.shutil, "which", fake_which)
    monkeypatch.setattr(root_run.subprocess, "run", fake_run)

    assert root_run._compose_command() == [docker, "compose"]
    assert calls[:3] == [
        [docker, "info"],
        [docker, "context", "show"],
        [colima, "start"],
    ]


def test_run_applies_migrations_to_mutable_snapshot_working_copy():
    root_run = _root_run_module()

    snapshot_dsn = "postgresql://aethria:local-test-password@127.0.0.1:15432/aethria_prod_snapshot"
    test_dsn = "postgresql://aethria:local-test-password@127.0.0.1:15432/aethria_test"

    assert root_run._should_apply_local_migrations(snapshot_dsn) is True
    assert root_run._should_apply_local_migrations(test_dsn) is True


def test_terminal_renderer_prints_static_banner_and_normal_logs():
    root_run = _root_run_module()
    stream = StringIO()
    renderer = root_run._TerminalRenderer(
        "BANNER\nSTATUS",
        stream=stream,
        enabled=True,
        terminal_lines=8,
    )

    renderer.start()
    renderer.emit("first log")
    renderer.emit("second log")
    renderer.close()

    output = stream.getvalue()
    assert "BANNER" in output
    assert "STATUS" in output
    assert "first log" in output
    assert "second log" in output
    assert output.count("BANNER") == 1
    assert "\x1b[2J" not in output
    assert "\x1b[?1000h" not in output
    assert "\x1b[r" not in output


def test_terminal_renderer_does_not_capture_terminal_scrolling():
    root_run = _root_run_module()
    renderer = root_run._TerminalRenderer(
        "BANNER\nSTATUS",
        stream=StringIO(),
        enabled=True,
        terminal_lines=8,
    )
    renderer.start()
    renderer.emit("log line")

    output = renderer._stream.getvalue()
    assert "log line" in output
    assert "\x1b[?1000h" not in output
    assert "\x1b[?1006h" not in output


def test_banner_uses_white_aethria_text_without_a_background(monkeypatch):
    root_run = _root_run_module()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://aethria:local-test-password@127.0.0.1:15432/aethria_prod_snapshot",
    )

    banner = root_run._build_banner(True)

    assert "\x1b[37m" in banner
    assert "\x1b[47m" not in banner
    assert "\x1b[38;2;0;33;71m" not in banner
    assert "Current snapshot:   aethria_prod_snapshot (working copy)" in banner


def test_banner_lists_all_local_ports(monkeypatch):
    root_run = _root_run_module()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    banner = root_run._build_banner(False)

    assert "http://localhost:8000" in banner
    assert "http://localhost:3000" in banner
    assert "http://localhost:3001" in banner
