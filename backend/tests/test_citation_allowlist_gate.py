"""Citation allowlist enforcement is independent of empty-retrieval behaviour.

These were one setting (`scout_fail_closed_on_empty_retrieval`), so turning off
the empty-retrieval gate silently also turned off citation grounding: the model
could cite anything it liked as long as *some* source had been retrieved.
"""
import pytest

from scout.base import Scout
from utils.settings_loader import (
    DEFAULT_SETTINGS,
    is_scout_citation_allowlist_enforced,
    is_scout_fail_closed_on_empty_retrieval,
)


class DummyScout(Scout):
    pass


@pytest.fixture
def scout():
    return DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )


def _payload(references):
    return {
        "name": "Acme Robotics",
        "one_line": "Warehouse robotics automation",
        "sector": "Robotics",
        "problem": "Manual warehouse workflows are brittle.",
        "solution": "Acme automates picking and routing.",
        "target_users": "Warehouse operators",
        "why_now": "Labor shortages make automation urgent.",
        "confidence": 0.8,
        "primary_thesis": "Automation wedge.",
        "key_assumptions": ["Demand persists", "Deployments stay economical"],
        "biggest_unknown": "Enterprise sales cycles.",
        "references": list(references),
    }


_RETRIEVED = {
    "url_allowlist": {"https://acmerobotics.com"},
    "sources": [{"url": "https://acmerobotics.com", "title": "Official site", "snippet": ""}],
}
_EMPTY_PACK = {"url_allowlist": set(), "sources": []}


# --------------------------------------------------------------------------- #
# Defaults
# --------------------------------------------------------------------------- #


def test_the_two_settings_are_separate_keys():
    agent_config = DEFAULT_SETTINGS["agent_config"]
    assert "scout_citation_allowlist_enforced" in agent_config
    assert "scout_fail_closed_on_empty_retrieval" in agent_config


def test_citations_are_fail_closed_by_default():
    assert is_scout_citation_allowlist_enforced("user_test_123") is True


def test_empty_retrieval_is_fail_closed_by_default():
    assert is_scout_fail_closed_on_empty_retrieval("user_test_123") is True


# --------------------------------------------------------------------------- #
# Enforcement when sources were retrieved
# --------------------------------------------------------------------------- #


def test_non_retrieved_citation_is_rejected_when_enforced(monkeypatch, scout):
    monkeypatch.setenv("SKIP_REFERENCE_URL_VERIFY", "1")
    out = scout._postprocess_scout_dict(
        _payload(["Acme team - https://www.linkedin.com/company/acme-robotics/"]),
        _RETRIEVED,
        grounded_enabled=True,
        enforce_citation_allowlist=True,
    )
    assert out is None


def test_retrieved_citation_survives_enforcement(monkeypatch, scout):
    monkeypatch.setenv("SKIP_REFERENCE_URL_VERIFY", "1")
    out = scout._postprocess_scout_dict(
        _payload(["Acme official site - https://acmerobotics.com"]),
        _RETRIEVED,
        grounded_enabled=True,
        enforce_citation_allowlist=True,
    )
    assert out is not None
    assert "acmerobotics.com" in "\n".join(out["references"])


def test_enforcement_can_be_turned_off_independently(monkeypatch, scout):
    monkeypatch.setenv("SKIP_REFERENCE_URL_VERIFY", "1")
    out = scout._postprocess_scout_dict(
        _payload(["Acme team - https://www.linkedin.com/company/acme-robotics/"]),
        _RETRIEVED,
        grounded_enabled=True,
        enforce_citation_allowlist=False,
    )
    assert out is not None
    assert "linkedin.com/company/acme-robotics" in "\n".join(out["references"])


def test_enforcement_does_not_apply_when_grounding_is_off(monkeypatch, scout):
    monkeypatch.setenv("SKIP_REFERENCE_URL_VERIFY", "1")
    out = scout._postprocess_scout_dict(
        _payload(["Acme team - https://www.linkedin.com/company/acme-robotics/"]),
        _RETRIEVED,
        grounded_enabled=False,
        enforce_citation_allowlist=True,
    )
    assert out is not None


def test_no_allowlist_means_nothing_to_enforce_against(monkeypatch, scout):
    """An empty pack must not be read as "the model cited something unretrieved".

    Whether generation should have happened at all with an empty pack is the
    empty-retrieval gate's decision, made before the model is ever called.
    """
    monkeypatch.setenv("SKIP_REFERENCE_URL_VERIFY", "1")
    out = scout._postprocess_scout_dict(
        _payload(["Acme official site - https://acmerobotics.com"]),
        _EMPTY_PACK,
        grounded_enabled=True,
        enforce_citation_allowlist=True,
    )
    assert out is not None
    assert out["references"]


# --------------------------------------------------------------------------- #
# The gates are wired independently at the call sites
# --------------------------------------------------------------------------- #


def _patch_pack(monkeypatch, sources):
    monkeypatch.setattr(
        "scout.base.retrieve_source_pack_merged",
        lambda **kwargs: {
            "provider": "exa" if sources else "none",
            "retrieval_outcome": "sources_found" if sources else "no_results",
            "provider_diagnostics": [],
            "sources": list(sources),
            "url_allowlist": {s["url"] for s in sources},
        },
    )


@pytest.mark.parametrize("enforce", [True, False])
def test_empty_retrieval_gate_is_read_separately_from_the_citation_gate(
    monkeypatch, scout, enforce
):
    """Citation enforcement must not change whether empty retrieval blocks generation."""
    monkeypatch.setattr("scout.base.is_scout_grounded_citations_enabled", lambda user_id: True)
    monkeypatch.setattr("scout.base.is_scout_fail_closed_on_empty_retrieval", lambda user_id: True)
    monkeypatch.setattr(
        "scout.base.is_scout_citation_allowlist_enforced", lambda user_id: enforce
    )
    _patch_pack(monkeypatch, [])

    calls: list = []

    class _Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            raise AssertionError("model must not be called on empty retrieval")

    scout.client = type(
        "C", (), {"chat": type("Chat", (), {"completions": _Completions()})()}
    )()

    assert scout._call_llm_sync() is None
    assert not calls
    assert scout.last_discovery_diagnostic["kind"] == "retrieval_no_results"
