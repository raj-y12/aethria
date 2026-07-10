import api


def test_lookup_worker_count_uses_configured_lookup_concurrency(monkeypatch):
    monkeypatch.setenv("MAX_CONCURRENT_LOOKUPS", "3")

    assert api._lookup_worker_count() == 3
