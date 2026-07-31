from scout.base import Scout
import json


class DummyScout(Scout):
    pass


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]
        self.usage = None


class _FakeChatCompletions:
    def __init__(self):
        self.prompt = None

    def create(self, *, messages, **kwargs):
        self.prompt = messages[1]["content"]
        retrieved = self.prompt.split("Retrieved sources", 1)[1]
        assert "https://aethria.co" in retrieved
        payload = {
            "id": "startup-aethria",
            "scout_type": "market_driven",
            "name": "Aethria",
            "one_line": "Autonomous investment discovery and evaluation.",
            "sector": "Investment Intelligence",
            "problem": "Deal teams need faster startup discovery and evaluation.",
            "solution": "Aethria runs scouts, reviewers, and partner-grade memos.",
            "target_users": "Venture capital investors",
            "why_now": "AI agents can automate more of the deal-flow workflow.",
            "confidence": 0.8,
            "primary_thesis": "Workflow automation wedge into venture investing.",
            "key_assumptions": ["VC teams trust agentic sourcing", "Evidence quality remains high"],
            "biggest_unknown": "Whether small teams adopt autonomous diligence.",
            "funding_stage": "Unknown",
            "est_tam": None,
            "references": ["Aethria official website - https://aethria.co"],
        }
        return _FakeResponse(json.dumps(payload))


class _FakeClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": _FakeChatCompletions()})()


def test_coerce_payload_fixes_missing_name_and_target_users():
    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )
    payload = {
        "one_line": "Workflow AI for industrial inspections",
        "target_users": ["ops leaders", "field technicians"],
        "confidence": "0.84",
        "key_assumptions": "Users adopt quickly",
        "references": "Example - https://example.com",
    }
    out = scout._coerce_scout_payload(payload)
    assert isinstance(out["name"], str)
    assert out["name"] != ""
    assert isinstance(out["target_users"], str)
    assert "ops leaders" in out["target_users"]
    assert isinstance(out["confidence"], float)
    assert len(out["key_assumptions"]) >= 2
    assert isinstance(out["references"], list)


def test_call_llm_records_retrieval_no_results_separately_from_model_failure(monkeypatch):
    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )
    monkeypatch.setattr("scout.base.is_scout_grounded_citations_enabled", lambda user_id: True)
    monkeypatch.setattr("scout.base.is_scout_fail_closed_on_empty_retrieval", lambda user_id: True)
    monkeypatch.setattr(
        "scout.base.retrieve_source_pack_merged",
        lambda **kwargs: {
            "provider": "none",
            "retrieval_outcome": "no_results",
            "provider_diagnostics": [
                {"provider": "exa", "outcome": "disabled", "reason": "missing_api_key"},
                {"provider": "duckduckgo_html_fallback", "outcome": "empty", "reason": "no_usable_results"},
            ],
            "sources": [],
            "url_allowlist": set(),
        },
    )

    assert scout._call_llm_sync() is None
    assert scout.last_discovery_diagnostic == {
        "kind": "retrieval_no_results",
        "retrieval_outcome": "no_results",
        "provider_diagnostics": [
            {"provider": "exa", "outcome": "disabled", "reason": "missing_api_key"},
            {"provider": "duckduckgo_html_fallback", "outcome": "empty", "reason": "no_usable_results"},
        ],
    }


def test_empty_retrieval_gate_is_independent_of_citation_enforcement(monkeypatch):
    """The empty-retrieval gate governs generation; citations have their own gate.

    With the empty-retrieval gate fail-open, a dark provider no longer blocks
    generation — and citation enforcement stays on regardless, because there is
    simply no allowlist to enforce against when nothing was retrieved.
    """
    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )
    monkeypatch.setattr("scout.base.is_scout_grounded_citations_enabled", lambda user_id: True)
    monkeypatch.setattr("scout.base.is_scout_fail_closed_on_empty_retrieval", lambda user_id: False)
    monkeypatch.setattr("scout.base.is_scout_citation_allowlist_enforced", lambda user_id: True)
    monkeypatch.setattr(
        "scout.base.retrieve_source_pack_merged",
        lambda **kwargs: {
            "provider": "none",
            "retrieval_outcome": "no_results",
            "provider_diagnostics": [],
            "sources": [],
            "url_allowlist": set(),
        },
    )
    # The shared fake asserts on the "Retrieved sources" block, which does not
    # exist on an empty pack; record the attempt instead.
    calls: list = []

    class _RecordingCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return _FakeResponse("")

    scout.client = type(
        "C", (), {"chat": type("Chat", (), {"completions": _RecordingCompletions()})()}
    )()

    scout._call_llm_sync()
    # The empty-retrieval gate did NOT short-circuit: generation was attempted.
    assert calls, "fail-open on empty retrieval should still call the model"


def test_empty_retrieval_still_skips_generation_when_fail_closed(monkeypatch):
    """Default posture: a dark provider must not spend LLM calls inventing evidence."""
    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )
    monkeypatch.setattr("scout.base.is_scout_grounded_citations_enabled", lambda user_id: True)
    monkeypatch.setattr("scout.base.is_scout_fail_closed_on_empty_retrieval", lambda user_id: True)
    monkeypatch.setattr("scout.base.is_scout_citation_allowlist_enforced", lambda user_id: False)
    monkeypatch.setattr(
        "scout.base.retrieve_source_pack_merged",
        lambda **kwargs: {
            "provider": "none",
            "retrieval_outcome": "no_results",
            "provider_diagnostics": [],
            "sources": [],
            "url_allowlist": set(),
        },
    )
    scout.client = _FakeClient()

    assert scout._call_llm_sync() is None
    assert scout.last_discovery_diagnostic["kind"] == "retrieval_no_results"


def test_call_llm_records_validation_failure_when_retrieval_succeeded(monkeypatch):
    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )
    monkeypatch.setattr("scout.base.is_scout_grounded_citations_enabled", lambda user_id: True)
    monkeypatch.setattr("scout.base.is_scout_fail_closed_on_empty_retrieval", lambda user_id: True)
    monkeypatch.setattr(
        "scout.base.retrieve_source_pack_merged",
        lambda **kwargs: {
            "provider": "exa",
            "retrieval_outcome": "sources_found",
            "provider_diagnostics": [
                {"provider": "exa", "outcome": "success", "reason": None, "result_count": 1},
            ],
            "sources": [
                {
                    "source_id": "S1",
                    "title": "Aethria",
                    "url": "https://aethria.co",
                    "snippet": "Investment intelligence.",
                }
            ],
            "url_allowlist": {"https://aethria.co"},
        },
    )
    scout.client = _FakeClient()
    monkeypatch.setattr(scout, "_finalize_scout_payload_from_llm", lambda *args, **kwargs: None)

    assert scout._call_llm_sync() is None
    assert scout.last_discovery_diagnostic["kind"] == "validation_failure"
    assert scout.last_discovery_diagnostic["retrieval_outcome"] == "sources_found"


def test_postprocess_extracts_founders_from_grounded_sources_when_model_omits_them(monkeypatch):
    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )
    monkeypatch.setattr("scout.base.finalize_scout_references", lambda data, **kwargs: data)
    payload = {
        "name": "Aethria",
        "one_line": "Investment intelligence.",
        "sector": "AI",
        "problem": "Slow diligence.",
        "solution": "Automated research.",
        "target_users": "Funds",
        "why_now": "AI retrieval is mature.",
        "confidence": 0.8,
        "primary_thesis": "Strong wedge.",
        "key_assumptions": ["Demand exists", "Sources are accurate"],
        "biggest_unknown": "Conversion.",
        "references": ["Aethria - https://aethria.co"],
    }

    out = scout._postprocess_scout_dict(
        payload,
        {
            "sources": [
                {
                    "url": "https://techcrunch.com/aethria",
                    "title": "Aethria founders",
                    "snippet": "Aethria was founded by Jane Smith and John Doe.",
                }
            ],
            "url_allowlist": {"https://techcrunch.com/aethria"},
        },
        grounded_enabled=False,
        enforce_citation_allowlist=False,
    )

    assert out is not None
    assert out["founder_names"] == ["Jane Smith", "John Doe"]


def test_site_summary_from_html_extracts_title_and_description():
    html = """
    <html>
      <head>
        <title>Aethria · Investment Intelligence</title>
        <meta name="description" content="Aethria — autonomous investment discovery and evaluation. Scouts, scores, memos." />
      </head>
      <body><div id="root"></div></body>
    </html>
    """

    summary = DummyScout._site_summary_from_html(html)

    assert "Aethria · Investment Intelligence" in summary
    assert "autonomous investment discovery and evaluation" in summary


def test_postprocess_fail_open_keeps_valid_non_allowlisted_references(monkeypatch):
    monkeypatch.setenv("SKIP_REFERENCE_URL_VERIFY", "1")
    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )
    payload = {
        "name": "Acme Robotics",
        "one_line": "Warehouse robotics automation",
        "sector": "Robotics",
        "problem": "Manual warehouse workflows are brittle.",
        "solution": "Acme automates picking and routing.",
        "target_users": "Warehouse operators",
        "why_now": "Labor shortages make automation urgent.",
        "confidence": 0.81,
        "primary_thesis": "Automation wedge into warehouse labor.",
        "key_assumptions": ["Demand persists", "Deployments stay economical"],
        "biggest_unknown": "Sales cycles with enterprise buyers.",
        "references": [
            "Acme Robotics official site - https://acmerobotics.com",
            "Acme Robotics team - https://www.linkedin.com/company/acme-robotics/",
        ],
    }
    out = scout._postprocess_scout_dict(
        payload,
        source_pack={
            "url_allowlist": {"https://acmerobotics.com"},
            "sources": [{"url": "https://acmerobotics.com", "title": "Official site", "snippet": ""}],
        },
        grounded_enabled=True,
        enforce_citation_allowlist=False,
        explicit_website="https://acmerobotics.com",
    )
    assert out is not None
    refs = "\n".join(out["references"])
    assert "acmerobotics.com" in refs
    assert "linkedin.com/company/acme-robotics" in refs


def test_postprocess_fail_closed_still_enforces_allowlist(monkeypatch):
    monkeypatch.setenv("SKIP_REFERENCE_URL_VERIFY", "1")
    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )
    payload = {
        "name": "Acme Robotics",
        "one_line": "Warehouse robotics automation",
        "sector": "Robotics",
        "problem": "Manual warehouse workflows are brittle.",
        "solution": "Acme automates picking and routing.",
        "target_users": "Warehouse operators",
        "why_now": "Labor shortages make automation urgent.",
        "confidence": 0.81,
        "primary_thesis": "Automation wedge into warehouse labor.",
        "key_assumptions": ["Demand persists", "Deployments stay economical"],
        "biggest_unknown": "Sales cycles with enterprise buyers.",
        "references": [
            "Acme Robotics team - https://www.linkedin.com/company/acme-robotics/",
        ],
    }
    out = scout._postprocess_scout_dict(
        payload,
        source_pack={
            "url_allowlist": {"https://acmerobotics.com"},
            "sources": [{"url": "https://acmerobotics.com", "title": "Official site", "snippet": ""}],
        },
        grounded_enabled=True,
        enforce_citation_allowlist=True,
        explicit_website=None,
    )
    assert out is None


def test_company_lookup_includes_explicit_website_in_citable_sources(monkeypatch):
    monkeypatch.setenv("SKIP_REFERENCE_URL_VERIFY", "1")
    monkeypatch.setattr("scout.base.is_scout_grounded_citations_enabled", lambda user_id: True)
    monkeypatch.setattr("scout.base.is_scout_fail_closed_on_empty_retrieval", lambda user_id: False)
    monkeypatch.setattr(
        DummyScout,
        "_fetch_explicit_website_snippet",
        lambda self, url: "Title: Aethria · Investment Intelligence Description: Autonomous investment discovery.",
    )
    monkeypatch.setattr(
        "scout.base.retrieve_source_pack_merged",
        lambda **kwargs: {
            "provider": "exa",
            "sources": [
                {
                    "source_id": "S1",
                    "title": "Aether Secures Funding",
                    "url": "https://example.com/aether",
                    "snippet": "A similarly named company.",
                }
            ],
            "url_allowlist": {"https://example.com/aether"},
        },
    )
    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )
    scout.client = _FakeClient()

    out = scout._call_llm_for_company_sync("Aethria", website="aethria.co")

    assert out is not None
    assert out["name"] == "Aethria"
    assert any("https://aethria.co" in ref for ref in out["references"])


def test_explicit_website_source_pack_discards_non_anchor_sources():
    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )

    out = scout._add_explicit_website_source(
        {
            "provider": "exa",
            "sources": [
                {
                    "source_id": "S1",
                    "title": "Aethria Solutions",
                    "url": "https://aethriasolutions.com",
                    "snippet": "A different similarly named services company.",
                },
                {
                    "source_id": "S2",
                    "title": "Aethria product",
                    "url": "https://aethria.co",
                    "snippet": "The official product site.",
                },
            ],
            "url_allowlist": {"https://aethriasolutions.com", "https://aethria.co"},
        },
        company_name="Aethria",
        website_hint="aethria.co",
    )

    urls = [source["url"] for source in out["sources"]]
    assert urls == ["https://aethria.co"]
    assert out["url_allowlist"] == {"https://aethria.co"}
