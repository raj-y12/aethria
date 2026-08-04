"""Regression coverage for remote-storage fail-closed behavior."""

import pytest


def _enable_supabase(monkeypatch):
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("FASTAPI_ENV", raising=False)


def _enable_local(monkeypatch):
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "0")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("FASTAPI_ENV", raising=False)


def test_portfolio_store_does_not_read_local_file_after_supabase_read_failure(
    monkeypatch, tmp_path
):
    _enable_supabase(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    from portfolio.store import PortfolioStore

    store = PortfolioStore(data_dir=str(tmp_path / "portfolio"), user_id="user-1")
    monkeypatch.setattr(store, "_supabase_client", lambda: (_ for _ in ()).throw(ConnectionError("db down")))

    with pytest.raises(RuntimeError, match="supabase_read_failed"):
        store.get_all_startups()

    assert not (tmp_path / "portfolio" / "startups.json").exists()


def test_portfolio_store_uses_local_files_only_when_explicitly_local(monkeypatch, tmp_path):
    _enable_local(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", "https://configured.example")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "configured")
    from portfolio.store import PortfolioStore

    store = PortfolioStore(data_dir=str(tmp_path / "portfolio"))

    assert store._using_supabase() is False
    assert (tmp_path / "portfolio" / "startups.json").exists()


def test_cost_controller_does_not_write_local_budget_after_supabase_load_failure(
    monkeypatch, tmp_path
):
    _enable_supabase(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    import portfolio.cost_control as cost_control

    monkeypatch.setattr(cost_control, "load_settings", lambda _user_id: {})
    monkeypatch.setattr(cost_control, "doc_get", lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("db down")))

    with pytest.raises(RuntimeError, match="supabase_budget_load_failed"):
        cost_control.CostController(
            budget_file=str(tmp_path / "budgets.json"),
            user_id="user-1",
        )

    assert not (tmp_path / "budgets.json").exists()


def test_supabase_security_store_does_not_use_memory_on_rpc_failure(monkeypatch):
    _enable_supabase(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    from security.rate_limiter import SupabaseSecurityStore

    class FailingClient:
        def rpc(self, *_args, **_kwargs):
            raise ConnectionError("db down")

    with pytest.raises(RuntimeError, match="security_store_rpc_failed"):
        SupabaseSecurityStore(FailingClient()).increment_fixed_window(
            "rate:key", window_seconds=60
        )


def test_security_store_requires_remote_in_supabase_mode(monkeypatch):
    _enable_supabase(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    from security.rate_limiter import build_security_store

    with pytest.raises(RuntimeError, match="supabase_configuration_missing"):
        build_security_store()


def test_security_store_keeps_explicit_local_dev_behavior(monkeypatch):
    _enable_local(monkeypatch)
    from security.rate_limiter import InMemorySecurityStore, build_security_store

    assert isinstance(build_security_store(), InMemorySecurityStore)


@pytest.mark.asyncio
async def test_event_bus_does_not_start_local_after_production_postgres_failure(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("EVENT_BUS_BACKPLANE", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgres://example")
    monkeypatch.delenv("ALLOW_PROCESS_LOCAL_STATE", raising=False)

    async def failing_connect(_dsn):
        raise ConnectionError("db down")

    import event_bus

    with pytest.raises(RuntimeError, match="event_bus_backplane_unavailable"):
        await event_bus.start_backplane(connect=failing_connect)


def test_file_storage_is_rejected_in_production(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "0")
    from utils.storage import Storage

    with pytest.raises(RuntimeError, match="local_storage_disabled"):
        Storage(str(tmp_path / "startups.json"))


def test_rejection_analyzer_does_not_read_local_file_after_supabase_read_failure(
    monkeypatch, tmp_path
):
    _enable_supabase(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    from portfolio.rejection import RejectionAnalyzer

    analyzer = RejectionAnalyzer(data_dir=str(tmp_path / "portfolio"), user_id="user-1")
    monkeypatch.setattr(
        analyzer, "_supabase_client", lambda: (_ for _ in ()).throw(ConnectionError("db down"))
    )

    with pytest.raises(RuntimeError, match="supabase_read_failed_no_local_fallback"):
        analyzer.get_patterns()


def test_rejection_analyzer_scopes_fallback_file_per_tenant(tmp_path):
    from portfolio.rejection import RejectionAnalyzer

    a = RejectionAnalyzer(data_dir=str(tmp_path), user_id="user-a")
    b = RejectionAnalyzer(data_dir=str(tmp_path), user_id="user-b")

    assert a.patterns_file != b.patterns_file
    assert "user-a" in a.patterns_file.name
    assert "user-b" in b.patterns_file.name


def test_feed_fetcher_does_not_read_local_file_after_supabase_read_failure(
    monkeypatch, tmp_path
):
    _enable_supabase(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    from utils.feed_fetcher import FeedFetcher

    fetcher = FeedFetcher(cache_file=str(tmp_path / "feed_cache.json"), user_id="user-1")
    monkeypatch.setattr(
        fetcher, "_supabase_client", lambda: (_ for _ in ()).throw(ConnectionError("db down"))
    )

    with pytest.raises(RuntimeError, match="supabase_read_failed_no_local_fallback"):
        fetcher._read_cache()


def test_unknown_environment_is_fail_closed_but_local_dev_is_allowed(monkeypatch):
    import env_config

    monkeypatch.setenv("ENVIRONMENT", "production ")
    assert env_config.is_production_env() is True
    monkeypatch.setenv("ENVIRONMENT", "mystery")
    assert env_config.is_production_env() is True
    monkeypatch.setenv("ENVIRONMENT", "local")
    assert env_config.is_production_env() is False
