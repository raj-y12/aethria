from datetime import timedelta

from utils.retrieval_cache import (
    build_retrieval_identity,
    freshness_ttl_seconds,
    normalize_retrieval_url,
)
from utils import retrieval_grounding


def test_retrieval_identity_is_stable_across_query_whitespace_and_case():
    first = build_retrieval_identity(
        query="  Acme   funding  ", category="COMPANY", time_range="week", days=7
    )
    second = build_retrieval_identity(
        query="acme funding", category="company", time_range="week", days=7
    )

    assert first == second
    assert len(first) == 64


def test_url_normalization_removes_tracking_parameters_and_trailing_slash():
    assert normalize_retrieval_url(
        "HTTPS://Example.com/path/?utm_source=x&ref=abc&id=42#section"
    ) == "https://example.com/path?id=42"


def test_freshness_policy_differs_by_information_class():
    assert freshness_ttl_seconds("news") < freshness_ttl_seconds("company")
    assert freshness_ttl_seconds("people") == freshness_ttl_seconds("company")


def test_freshness_ttl_can_be_disabled():
    assert freshness_ttl_seconds("general", environ={"RETRIEVAL_CACHE_TTL_GENERAL_SECONDS": "0"}) == 0


def test_repeated_fresh_retrieval_avoids_provider_call(monkeypatch):
    class FakeRepository:
        def __init__(self):
            self.sources = None
            self.successes = 0

        async def get_fresh(self, **kwargs):
            if self.sources is None:
                return None
            return {"sources": self.sources, "provider": "fake", "provider_diagnostics": []}

        async def persist_success(self, **kwargs):
            self.successes += 1
            self.sources = kwargs["sources"]
            return {"duplicate_content_suppressed": 0, "sources_persisted": 1}

        async def persist_failure(self, **kwargs):
            raise AssertionError("successful retrieval must not record failure")

    repository = FakeRepository()
    retrieval_grounding.configure_retrieval_cache(repository)
    calls = {"count": 0}

    def fake_provider(*args, **kwargs):
        calls["count"] += 1
        return [{"title": "Acme", "url": "https://acme.example/", "snippet": "company"}]

    monkeypatch.setattr(retrieval_grounding, "provider_search", fake_provider)
    try:
        first = retrieval_grounding.retrieve_source_pack(query="Acme", user_id="u1", category="company")
        second = retrieval_grounding.retrieve_source_pack(query=" acme ", user_id="u1", category="company")
    finally:
        retrieval_grounding.configure_retrieval_cache(None)

    assert calls["count"] == 1
    assert first["sources"] == second["sources"]
    assert repository.successes == 1


def test_retrieval_persistence_preserves_access_and_target_metadata():
    class FakeRepository:
        async def persist_success(self, **kwargs):
            self.kwargs = kwargs
            return {"duplicate_content_suppressed": 0, "sources_persisted": 2}

    repository = FakeRepository()
    cache = retrieval_grounding.RetrievalCache(repository)
    result = cache.persist_success(
        user_id="fund-a", query="Acme", category="company", time_range=None, days=None,
        provider="fake", diagnostics={}, max_results=10,
        target_company_id="company-1", target_person_id="person-1",
        sources=[
            {"url": "https://public.example", "snippet": "public", "access_class": "public"},
            {"url": "https://private.example", "snippet": "private", "access_class": "tenant_private"},
        ],
    )
    assert result["sources_persisted"] == 2
    assert repository.kwargs["target_company_id"] == "company-1"
    assert repository.kwargs["target_person_id"] == "person-1"
    assert [row["access_class"] for row in repository.kwargs["sources"]] == ["public", "tenant_private"]
