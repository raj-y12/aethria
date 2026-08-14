"""On-demand lookups must be able to produce grounded financials.

The lookup prompt used to stop at `references`, omitting the `financials` object
that the open-discovery prompt documents. The model was therefore never asked for
funding/valuation/traction figures on a lookup, so `ground_financials` always
received `{}` and every looked-up company persisted with empty Financials.
"""
import json

import pytest

from scout.base import Scout


class DummyScout(Scout):
    pass


class _CapturingCompletions:
    """Captures the rendered prompt and replies with a fixed payload."""

    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    def create(self, **kwargs):
        self.prompts.append(kwargs["messages"][1]["content"])
        content = json.dumps(self.payload)

        class _Msg:
            def __init__(self, c):
                self.content = c

        class _Choice:
            def __init__(self, c):
                self.message = _Msg(c)

        class _Resp:
            def __init__(self, c):
                self.choices = [_Choice(c)]
                self.usage = None

        return _Resp(content)


def _client(payload):
    completions = _CapturingCompletions(payload)
    client = type(
        "C", (), {"chat": type("Chat", (), {"completions": completions})()}
    )()
    return client, completions


_SOURCE = {
    "source_id": "S1",
    "title": "Acme raises $5M",
    "url": "https://techcrunch.com/acme",
    "snippet": "Acme raised a $5M Series A led by Index in 2024.",
}


def _payload(financials=None):
    payload = {
        "id": "startup-acme",
        "scout_type": "market_driven",
        "name": "Acme",
        "one_line": "Warehouse robotics",
        "sector": "Robotics",
        "problem": "Manual workflows.",
        "solution": "Automation.",
        "target_users": "Operators",
        "why_now": "Labor shortages.",
        "confidence": 0.8,
        "primary_thesis": "Automation wedge.",
        "key_assumptions": ["Demand persists", "Deployments stay economical"],
        "biggest_unknown": "Sales cycles.",
        "references": ["[S1] Acme raises $5M - https://techcrunch.com/acme"],
    }
    if financials is not None:
        payload["financials"] = financials
    return payload


@pytest.fixture
def scout(monkeypatch):
    monkeypatch.setenv("SKIP_REFERENCE_URL_VERIFY", "1")
    monkeypatch.setattr(
        "scout.base.retrieve_source_pack_merged",
        lambda **kwargs: {
            "provider": "exa",
            "retrieval_outcome": "sources_found",
            "provider_diagnostics": [],
            "sources": [dict(_SOURCE)],
            "url_allowlist": {_SOURCE["url"]},
        },
    )
    return DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )


def test_lookup_prompt_documents_the_financials_object(scout):
    client, completions = _client(_payload())
    scout.client = client

    scout._call_llm_for_company_sync("Acme")

    prompt = completions.prompts[0]
    assert '"financials"' in prompt
    for field in ("funding_history", "valuation_est", "traction_metrics", "ip_status"):
        assert field in prompt
    # The verbatim-quote contract must travel with the schema.
    assert "quote" in prompt and "source_url" in prompt
    assert "Never estimate" in prompt


def test_lookup_produces_grounded_financials(scout):
    client, _ = _client(
        _payload(
            {
                "funding_history": {
                    "value": "$5M Series A (2024)",
                    "quote": "Acme raised a $5M Series A led by Index in 2024.",
                    "source_url": "https://techcrunch.com/acme",
                }
            }
        )
    )
    scout.client = client

    out = scout._call_llm_for_company_sync("Acme")

    assert out is not None
    assert out["financials_grounded"]["funding_history"] == "$5M Series A (2024)"
    assert out["financials_grounded"]["funding_missing"] is False


def test_lookup_drops_a_figure_the_quote_does_not_support(scout):
    client, _ = _client(
        _payload(
            {
                "funding_history": {
                    "value": "$50M Series B (2024)",
                    "quote": "Acme raised a $5M Series A led by Index in 2024.",
                    "source_url": "https://techcrunch.com/acme",
                }
            }
        )
    )
    scout.client = client

    out = scout._call_llm_for_company_sync("Acme")

    assert out is not None
    assert out["financials_grounded"]["funding_history"] is None
    assert out["financials_grounded"]["funding_missing"] is True


def test_lookup_drops_a_figure_cited_to_an_unretrieved_source(scout):
    client, _ = _client(
        _payload(
            {
                "valuation_est": {
                    "value": "$20M post-money",
                    "quote": "Acme is valued at $20M post-money.",
                    "source_url": "https://not-retrieved.example/acme",
                }
            }
        )
    )
    scout.client = client

    out = scout._call_llm_for_company_sync("Acme")

    assert out is not None
    assert out["financials_grounded"]["valuation_est"] is None
    assert out["financials_grounded"]["valuation_missing"] is True


def test_lookup_without_financials_still_succeeds(scout):
    """Financials stay optional — omitting them must not fail the lookup."""
    client, _ = _client(_payload())
    scout.client = client

    out = scout._call_llm_for_company_sync("Acme")

    assert out is not None
    assert out["financials_grounded"]["funding_history"] is None
    assert out["financials_grounded"]["funding_missing"] is True


def test_grounded_financials_reach_the_persisted_model(scout):
    from utils.adapters import financials_from_scout_output

    client, _ = _client(
        _payload(
            {
                "traction_metrics": {
                    "value": "$5M",
                    "quote": "Acme raised a $5M Series A led by Index in 2024.",
                    "source_url": "https://techcrunch.com/acme",
                }
            }
        )
    )
    scout.client = client

    out = scout._call_llm_for_company_sync("Acme")
    financials = financials_from_scout_output(out)

    assert financials.traction_metrics == "$5M"
    assert financials.revenue_missing is False
