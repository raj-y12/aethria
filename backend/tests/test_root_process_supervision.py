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


def test_run_never_applies_migrations_to_snapshot_database():
    root_run = _root_run_module()

    snapshot_dsn = "postgresql://aethria:local-test-password@127.0.0.1:15432/aethria_prod_snapshot"
    test_dsn = "postgresql://aethria:local-test-password@127.0.0.1:15432/aethria_test"

    assert root_run._should_apply_local_migrations(snapshot_dsn) is False
    assert root_run._should_apply_local_migrations(test_dsn) is True


def test_terminal_renderer_pins_banner_and_scrolls_log_region():
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
    assert "\x1b[3;8r" in output
    assert "\x1b[r" in output


def test_terminal_renderer_left_aligns_aethria_in_white_header():
    root_run = _root_run_module()
    stream = StringIO()
    renderer = root_run._TerminalRenderer(
        "---\n       AETHRIA\n\n\n\n\n\n---\nBackend (API)",
        stream=stream,
        enabled=True,
        terminal_lines=20,
        terminal_columns=100,
        use_color=True,
    )

    renderer.start()

    output = stream.getvalue()
    lines = output.splitlines()
    assert lines[1].startswith("\x1b[47m")
    assert "\x1b[47m" not in lines[8]
    assert "\x1b[30m" not in output
    assert "\x1b[38;2;0;33;71m" in output or "AETHRIA" in output
    assert "AETHRIA" in lines[1]


def test_white_logo_box_covers_ascii_art_side_padding():
    root_run = _root_run_module()
    banner = root_run._build_banner(False)
    renderer = root_run._TerminalRenderer(
        banner,
        stream=StringIO(),
        enabled=True,
        terminal_lines=30,
        terminal_columns=100,
        use_color=True,
    )

    raw_logo_width = max(len(line) for line in banner.splitlines()[1:7])

    assert renderer._title_box_width >= max(raw_logo_width, root_run.BANNER_WIDTH)
