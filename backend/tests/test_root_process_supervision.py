from importlib.util import module_from_spec, spec_from_file_location
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
