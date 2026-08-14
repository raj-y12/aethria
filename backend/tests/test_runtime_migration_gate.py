from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_runtime_migration_gate_rejects_an_older_database(monkeypatch, tmp_path):
    import api

    monkeypatch.setattr(api, "_PORTABLE_MIGRATIONS_DIR", tmp_path)
    monkeypatch.setattr(
        api,
        "inspect_migration_head",
        lambda *_args: _missing_migrations(),
    )

    with pytest.raises(RuntimeError, match="migration_head_behind:20260813000001"):
        await api._ensure_portable_migrations(object())


async def _missing_migrations():
    return SimpleNamespace(ready=False, missing_versions=("20260813000001",))


@pytest.mark.asyncio
async def test_runtime_migration_gate_accepts_a_current_database(monkeypatch, tmp_path):
    import api

    monkeypatch.setattr(api, "_PORTABLE_MIGRATIONS_DIR", tmp_path)
    monkeypatch.setattr(
        api,
        "inspect_migration_head",
        lambda *_args: _current_migrations(),
    )

    status = await api._ensure_portable_migrations(object())

    assert status.ready is True


async def _current_migrations():
    return SimpleNamespace(ready=True, missing_versions=())
