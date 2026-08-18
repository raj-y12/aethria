from unittest.mock import MagicMock

import pytest

from resolver.company_resolver import EvidenceSource
from resolver.identity_disambiguation import DisambiguationResult, disambiguate_identity


def _candidates():
    return [
        EvidenceSource(
            url="https://notion.com",
            title="Notion — Home",
            snippet="Notion is a workspace for teams.",
            source_type="official_site",
            match_score=1.0,
        ),
        EvidenceSource(
            url="https://notiontechnologies.com/",
            title="Notion Technologies — Home",
            snippet="Notion Technologies builds industrial sensors.",
            source_type="official_site",
            match_score=0.85,
        ),
    ]


def _fake_client(content: str):
    client = MagicMock()
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    response.usage = MagicMock(total_tokens=123)
    client.chat.completions.create.return_value = response
    return client


def test_disambiguate_identity_returns_the_llm_pick(monkeypatch):
    content = '{"picked_url": "https://notion.com", "confidence": 0.95, "reasoning": "Matches the typed name directly."}'
    monkeypatch.setattr(
        "resolver.identity_disambiguation.build_openai_client",
        lambda *a, **k: _fake_client(content),
    )
    result = disambiguate_identity(
        "Notion", _candidates(), user_id="user-test", api_key="sk-test"
    )
    assert result.called is True
    assert result.picked_url == "https://notion.com"
    assert result.confidence == 0.95


def test_disambiguate_identity_fails_closed_on_malformed_json(monkeypatch):
    monkeypatch.setattr(
        "resolver.identity_disambiguation.build_openai_client",
        lambda *a, **k: _fake_client("not json"),
    )
    result = disambiguate_identity(
        "Notion", _candidates(), user_id="user-test", api_key="sk-test"
    )
    assert result.called is False
    assert result.picked_url is None
    assert result.confidence == 0.0


def test_disambiguate_identity_fails_closed_when_the_client_raises(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("network down")

    monkeypatch.setattr("resolver.identity_disambiguation.build_openai_client", boom)
    result = disambiguate_identity(
        "Notion", _candidates(), user_id="user-test", api_key="sk-test"
    )
    assert result.called is False
    assert result.picked_url is None


def test_disambiguate_identity_fails_closed_with_no_api_key():
    result = disambiguate_identity(
        "Notion", _candidates(), user_id="user-test", api_key=None
    )
    assert result.called is False
    assert result.picked_url is None
    assert "api key" in result.reasoning.lower()


def test_disambiguate_identity_checks_and_records_cost_controller_budget(monkeypatch):
    content = '{"picked_url": "https://notion.com", "confidence": 0.95, "reasoning": "x"}'
    monkeypatch.setattr(
        "resolver.identity_disambiguation.build_openai_client",
        lambda *a, **k: _fake_client(content),
    )
    cost_controller = MagicMock()
    cost_controller.check_budget.return_value = (True, None)
    disambiguate_identity(
        "Notion", _candidates(), user_id="user-test", api_key="sk-test",
        cost_controller=cost_controller,
    )
    cost_controller.check_budget.assert_called_once()
    cost_controller.record_usage.assert_called_once()


def test_disambiguate_identity_skips_the_call_when_budget_denies(monkeypatch):
    client = _fake_client('{"picked_url": "https://notion.com", "confidence": 0.95, "reasoning": "x"}')
    monkeypatch.setattr(
        "resolver.identity_disambiguation.build_openai_client", lambda *a, **k: client
    )
    cost_controller = MagicMock()
    cost_controller.check_budget.return_value = (False, "Daily call budget exceeded")
    result = disambiguate_identity(
        "Notion", _candidates(), user_id="user-test", api_key="sk-test",
        cost_controller=cost_controller,
    )
    assert result.called is False
    client.chat.completions.create.assert_not_called()
