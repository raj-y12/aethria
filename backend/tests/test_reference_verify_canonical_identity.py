from research.reference_verify import filter_references_by_company_relevance, finalize_scout_references
from resolver.company_resolver import CompanyResolution
from scout.base import Scout


MANNA_IDENTITY = {
    "canonical_name": "Manna",
    "website": "https://manna.aero",
    "aliases": ["Manna Air Delivery", "Manna Drone Delivery", "Manna Aero"],
}


def test_manna_verified_canonical_domain_survives_user_facing_name_filter():
    refs = filter_references_by_company_relevance(
        ["https://manna.aero"],
        company_name="Manna Air Delivery",
        anchor_hostname=None,
        identity_context=MANNA_IDENTITY,
    )

    assert refs == ["https://manna.aero"]


def test_manna_news_paths_survive_when_the_article_has_multiple_identity_signals():
    refs = filter_references_by_company_relevance(
        [
            "https://techcrunch.com/2026/07/08/autonomous-drone-delivery-startup-manna-plots-major-u-s-expansion/",
            "https://fortune.com/2026/04/09/ark-invest-betting-on-underdog-drone-delivery-company-manna-to-beat-out-alphabet-zipline/",
        ],
        company_name="Manna Air Delivery",
        anchor_hostname=None,
        identity_context=MANNA_IDENTITY,
    )

    assert len(refs) == 2


def test_trusted_article_title_can_use_single_token_canonical_name_but_path_alone_cannot():
    refs = filter_references_by_company_relevance(
        ["Manna Series B new jobs - https://www.ucd.ie/innovation/news-and-events/2026/manna-series-b-new-jobs/"],
        company_name="Manna Air Delivery",
        anchor_hostname=None,
        identity_context=MANNA_IDENTITY,
    )

    assert refs == ["Manna Series B new jobs - https://www.ucd.ie/innovation/news-and-events/2026/manna-series-b-new-jobs/"]


def test_known_alias_matches_without_requiring_the_full_user_facing_name():
    refs = filter_references_by_company_relevance(
        ["https://techcrunch.com/2026/manna-drone-delivery-expansion/"],
        company_name="Manna Air Delivery",
        anchor_hostname=None,
        identity_context={
            "canonical_name": "Manna",
            "website": "https://manna.aero",
            "aliases": ["Manna Drone Delivery"],
        },
    )

    assert refs == ["https://techcrunch.com/2026/manna-drone-delivery-expansion/"]


def test_path_only_single_token_coincidence_is_rejected():
    refs = filter_references_by_company_relevance(
        ["https://techcrunch.com/2026/manna-competitor-funding/"],
        company_name="Manna Air Delivery",
        anchor_hostname=None,
        identity_context=MANNA_IDENTITY,
    )

    assert refs == []


def test_explicit_anchor_domain_remains_authoritative():
    refs = filter_references_by_company_relevance(
        ["https://manna.aero/about"],
        company_name="Manna Air Delivery",
        anchor_hostname="manna.aero",
        identity_context=None,
    )

    assert refs == ["https://manna.aero/about"]


def test_finalization_uses_persisted_company_resolution_context():
    output = {
        "name": "Manna Air Delivery",
        "company_resolution": MANNA_IDENTITY,
        "references": [
            "https://manna.aero",
            "https://techcrunch.com/2026/07/08/autonomous-drone-delivery-startup-manna-plots-major-u-s-expansion/",
        ],
    }

    finalized = finalize_scout_references(
        output,
        company_name="Manna Air Delivery",
        probe_timeout=0.01,
    )

    assert finalized["references"] == output["references"]


def test_same_public_identity_is_deterministic_across_tenant_callers():
    refs = ["https://manna.aero", "https://techcrunch.com/2026/manna-drone-delivery-expansion/"]
    first = filter_references_by_company_relevance(
        refs, company_name="Manna Air Delivery", anchor_hostname=None, identity_context=MANNA_IDENTITY
    )
    second = filter_references_by_company_relevance(
        refs, company_name="Manna Air Delivery", anchor_hostname=None, identity_context=MANNA_IDENTITY
    )

    assert first == second


def test_company_lookup_passes_resolver_identity_before_reference_finalization(monkeypatch):
    scout = Scout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )
    resolution = CompanyResolution(
        query="Manna Air Delivery",
        canonical_name="Manna",
        website="https://manna.aero",
        confidence=1.0,
        resolution_status="FOUND",
    )
    payload = {
        "scout_type": "market_driven",
        "name": "Manna Air Delivery",
        "references": ["https://manna.aero"],
    }
    captured = {}

    class Message:
        content = __import__("json").dumps(payload)

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]
        usage = None

    class Completions:
        def create(self, **kwargs):
            return Response()

    scout.client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    monkeypatch.setattr(
        "scout.base.retrieve_source_pack_merged",
        lambda **_: {"sources": [], "url_allowlist": set(), "retrieval_outcome": "sources_found"},
    )

    def finalize(raw_data, *args, **kwargs):
        captured["raw_data"] = raw_data
        return dict(raw_data)

    monkeypatch.setattr(scout, "_finalize_scout_payload_from_llm", finalize)
    result = scout._call_llm_for_company_sync("Manna Air Delivery", "manna.aero", resolution)

    assert result is not None
    assert captured["raw_data"]["company_resolution"]["canonical_name"] == "Manna"
