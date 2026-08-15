from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _root_run_module():
    path = REPO_ROOT / "run.py"
    spec = spec_from_file_location("aethria_root_run_working_copy", path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _reset_module():
    path = REPO_ROOT / "backend" / "scripts" / "reset_local_snapshot.py"
    spec = spec_from_file_location("aethria_reset_local_snapshot", path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_snapshot_compose_uses_a_separate_mutable_working_volume():
    compose = (REPO_ROOT / "docker-compose.snapshot.yml").read_text(encoding="utf-8")

    assert "aethria-prod-working-data" in compose
    assert "aethria-prod-snapshot-data" not in compose
    assert "POSTGRES_DB: aethria_prod_snapshot" in compose


def test_working_snapshot_startup_does_not_reject_mutable_drift(monkeypatch):
    root_run = _root_run_module()
    database_url = "postgresql://aethria:local-test-password@127.0.0.1:15432/aethria_prod_snapshot"
    verifier_calls = []

    monkeypatch.setattr(root_run, "_local_postgres_running", lambda compose_file: True)
    monkeypatch.setattr(root_run, "_wait_for_tcp", lambda *args, **kwargs: True)

    def fake_run(command, **kwargs):
        verifier_calls.append(command)
        return root_run.subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(root_run.subprocess, "run", fake_run)

    assert root_run._start_local_postgres_and_migrate(database_url) is False
    assert not any("verify_local_snapshot.py" in str(part) for part in verifier_calls)


def test_reset_restore_command_reads_the_golden_dump_into_the_working_database():
    reset = _reset_module()

    command = reset.build_restore_command(
        container_name="aethria-snapshot-working-postgres-1",
        backup_path=Path("/tmp/golden.dump"),
        database_name="aethria_prod_snapshot",
        database_user="aethria",
    )

    assert command == [
        "docker",
        "exec",
        "-i",
        "aethria-snapshot-working-postgres-1",
        "pg_restore",
        "--no-owner",
        "--no-privileges",
        "--exit-on-error",
        "--dbname",
        "aethria_prod_snapshot",
        "--username",
        "aethria",
        "/tmp/golden.dump",
    ]
