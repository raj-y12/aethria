"""Provider-neutral search interface: categories, routing, and registration."""
from typing import Any, Dict, List, Optional

import pytest

from utils.search_providers import (
    SEARCH_CATEGORIES,
    TavilySearchProvider,
    get_provider,
    normalize_category,
    provider_name,
    provider_search,
    register_provider,
    reset_providers,
)


@pytest.fixture(autouse=True)
def _restore_registry(monkeypatch):
    """Every test starts from the default Tavily-everywhere routing."""
    for category in SEARCH_CATEGORIES:
        monkeypatch.delenv(f"SEARCH_PROVIDER_{category.upper()}", raising=False)
    reset_providers()
    yield
    reset_providers()


class _RecordingProvider:
    def __init__(self, name: str, categories=SEARCH_CATEGORIES, rows=None):
        self.name = name
        self.supported_categories = frozenset(categories)
        self.calls: List[Dict[str, Any]] = []
        self._rows = rows if rows is not None else [
            {"title": "t", "url": "https://example.com", "snippet": "s"}
        ]

    def search(
        self,
        query: str,
        *,
        max_results: int,
        category: str = "general",
        time_range: Optional[str] = None,
        days: Optional[int] = None,
    ):
        self.calls.append(
            {
                "query": query,
                "max_results": max_results,
                "category": category,
                "time_range": time_range,
                "days": days,
            }
        )
        return list(self._rows)


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #


def test_the_four_categories_exist():
    assert set(SEARCH_CATEGORIES) == {"general", "news", "company", "people"}


@pytest.mark.parametrize("value", ["general", "news", "company", "people"])
def test_known_categories_round_trip(value):
    assert normalize_category(value) == value


@pytest.mark.parametrize("value", [None, "", "nonsense", "  "])
def test_unknown_categories_fall_back_to_general(value):
    assert normalize_category(value) == "general"


def test_category_normalization_is_case_insensitive():
    assert normalize_category("People") == "people"


# --------------------------------------------------------------------------- #
# Tavily stays the default for every category
# --------------------------------------------------------------------------- #


def test_tavily_is_the_default_for_every_category():
    for category in SEARCH_CATEGORIES:
        assert provider_name(category) == "tavily"
        assert isinstance(get_provider(category), TavilySearchProvider)


def test_tavily_maps_news_category_to_the_news_topic(monkeypatch):
    seen: Dict[str, Any] = {}

    def fake_tavily(query, max_results, time_range=None, topic=None, days=None):
        seen.update({"topic": topic, "days": days})
        return []

    monkeypatch.setattr("utils.search_providers.tavily_search", fake_tavily)
    TavilySearchProvider().search("q", max_results=5, category="news", days=30)
    assert seen == {"topic": "news", "days": 30}


@pytest.mark.parametrize("category", ["general", "company", "people"])
def test_tavily_maps_non_news_categories_to_the_general_topic(monkeypatch, category):
    seen: Dict[str, Any] = {}

    def fake_tavily(query, max_results, time_range=None, topic=None, days=None):
        seen.update({"topic": topic, "days": days})
        return []

    monkeypatch.setattr("utils.search_providers.tavily_search", fake_tavily)
    TavilySearchProvider().search("q", max_results=5, category=category, days=30)
    # `days` is a news-only control and must not leak into other categories.
    assert seen == {"topic": "general", "days": None}


# --------------------------------------------------------------------------- #
# Routing
# --------------------------------------------------------------------------- #


def test_people_search_is_independently_routable():
    people = _RecordingProvider("people-co", categories=["people"])
    register_provider(people, categories=["people"])

    assert provider_name("people") == "people-co"
    # Every other category is untouched.
    for category in ("general", "news", "company"):
        assert provider_name(category) == "tavily"


def test_routed_provider_receives_the_category():
    people = _RecordingProvider("people-co", categories=["people"])
    register_provider(people, categories=["people"])
    provider_search("who founded acme", max_results=4, category="people")
    assert people.calls[0]["category"] == "people"
    assert people.calls[0]["max_results"] == 4


def test_registering_without_categories_covers_all_supported():
    everything = _RecordingProvider("everything")
    register_provider(everything)
    for category in SEARCH_CATEGORIES:
        assert provider_name(category) == "everything"


def test_registering_an_unsupported_category_is_rejected():
    people = _RecordingProvider("people-co", categories=["people"])
    with pytest.raises(ValueError, match="does not support"):
        register_provider(people, categories=["news"])


def test_provider_must_have_a_name_and_search():
    class Nameless:
        name = ""
        supported_categories = frozenset(["people"])

        def search(self, *a, **k):
            return []

    with pytest.raises(ValueError):
        register_provider(Nameless())

    class NotSearchable:
        name = "broken"
        supported_categories = frozenset(["people"])
        search = None

    with pytest.raises(TypeError):
        register_provider(NotSearchable())


def test_env_override_routes_a_category_to_a_registered_provider(monkeypatch):
    people = _RecordingProvider("people-co", categories=["people"])
    register_provider(people, categories=["people"])
    # Registered but not routed; the env var selects it for `company`.
    monkeypatch.setenv("SEARCH_PROVIDER_COMPANY", "people-co")
    assert provider_name("company") == "people-co"


def test_unknown_env_override_falls_back_to_the_registry(monkeypatch):
    monkeypatch.setenv("SEARCH_PROVIDER_PEOPLE", "does-not-exist")
    assert provider_name("people") == "tavily"


def test_reset_restores_defaults():
    register_provider(_RecordingProvider("everything"))
    reset_providers()
    assert provider_name("people") == "tavily"


# --------------------------------------------------------------------------- #
# Failure handling
# --------------------------------------------------------------------------- #


def test_a_raising_provider_degrades_to_empty_results_with_diagnostics():
    class Exploding:
        name = "exploding"
        supported_categories = frozenset(SEARCH_CATEGORIES)

        def search(self, *a, **k):
            raise RuntimeError("upstream down")

    register_provider(Exploding())
    rows = provider_search("q", max_results=3, category="people")
    assert list(rows) == []
    assert rows.diagnostics["outcome"] == "error"
    assert rows.diagnostics["provider"] == "exploding"


# --------------------------------------------------------------------------- #
# Integration with retrieval grounding
# --------------------------------------------------------------------------- #


def test_retrieval_grounding_routes_through_the_category_provider():
    from utils.retrieval_grounding import retrieve_source_pack

    company = _RecordingProvider(
        "company-co",
        categories=["company"],
        rows=[{"title": "Acme", "url": "https://acme.com", "snippet": "x"}],
    )
    register_provider(company, categories=["company"])

    pack = retrieve_source_pack(query="acme", user_id="u1", category="company")
    assert pack["provider"] == "company-co"
    assert pack["category"] == "company"
    assert company.calls[0]["category"] == "company"


def test_merged_pack_sends_the_recency_query_to_the_news_provider():
    from utils.retrieval_grounding import retrieve_source_pack_merged

    news = _RecordingProvider(
        "news-co",
        categories=["news"],
        rows=[{"title": "deal", "url": "https://news.example/deal", "snippet": "x"}],
    )
    people = _RecordingProvider(
        "people-co",
        categories=["people"],
        rows=[{"title": "person", "url": "https://people.example/p", "snippet": "x"}],
    )
    register_provider(news, categories=["news"])
    register_provider(people, categories=["people"])

    retrieve_source_pack_merged(
        queries=["acme founders"],
        recency_query="acme latest news acquisition",
        user_id="u1",
        category="people",
    )
    assert [c["category"] for c in news.calls] == ["news"]
    assert [c["category"] for c in people.calls] == ["people"]


def test_founder_resolver_defaults_to_the_people_category():
    from resolver.founder_resolver import resolve_founders

    people = _RecordingProvider(
        "people-co",
        categories=["people"],
        rows=[
            {
                "title": "Team",
                "url": "https://acme.com/team",
                "snippet": "Ada Byron, Founder & CEO, joined in 2020.",
            }
        ],
    )
    register_provider(people, categories=["people"])

    resolution = resolve_founders("Acme", user_id="u1", website="acme.com")
    assert people.calls, "founder retrieval did not reach the people provider"
    assert {c["category"] for c in people.calls} == {"people"}
    assert resolution.founder_names() == ["Ada Byron"]
