"""Current Scout output is factual; historical hypothesis payloads stay readable."""
import pytest
import logging
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock
from pathlib import Path

from scout.base import Scout, FACTUAL_SCOUT_BOUNDARY
from scout.schema import validate_scout_output, factual_scout_payload
from utils.adapters import scout_output_to_scout_info


def payload():
    return dict(id="synthetic", scout_type="market_driven", name="Acme",
                one_line="Workflow software", sector="Software", problem="Manual filing",
                solution="Filing automation", target_users="Operations teams",
                why_now="Company reports a 2025 launch", confidence=0.8,
                biggest_unknown="Retention is unavailable",
                references=["Acme - https://acme.example/product"],
                unknowns=["Retention is unavailable"],
                contradictions=["Company and registry report different founding years"])


def test_factual_output_needs_no_investment_hypothesis_and_preserves_limitations():
    raw = payload()
    raw.update(primary_thesis="Buy this company", key_assumptions=["Venture scale"], recommendation="INVEST", score=9)
    factual = factual_scout_payload(raw)
    assert factual["version"] == "2"
    assert not {"primary_thesis", "key_assumptions", "recommendation", "score"}.intersection(factual)
    assert factual["references"] == raw["references"]
    stored = scout_output_to_scout_info(factual)
    assert stored.unknowns == raw["unknowns"]
    assert stored.contradictions == raw["contradictions"]
    assert stored.primary_thesis is None
    assert raw["primary_thesis"] == "Buy this company", "Never mutate historical input"


def test_factual_payload_still_requires_real_identity_and_citations():
    for change in ({"name": ""}, {"references": []}):
        with pytest.raises(ValueError):
            factual_scout_payload({**payload(), **change})


def test_historical_hypothesis_contract_remains_strict_and_readable():
    old = {**payload(), "primary_thesis": "Historical thesis", "key_assumptions": ["First", "Second"]}
    assert validate_scout_output(old)["primary_thesis"] == "Historical thesis"
    with pytest.raises(ValueError, match="between 2 and 4"):
        validate_scout_output({**old, "key_assumptions": []})


@pytest.mark.asyncio
async def test_discovery_and_named_lookup_enforce_factual_output_without_extra_model_calls():
    scout = object.__new__(Scout)
    scout.logger = logging.getLogger("test.factual_scout")
    raw = {**payload(), "primary_thesis": "Unwanted investment opinion"}
    scout._call_llm = AsyncMock(return_value=raw)
    scout._call_llm_for_company_sync = lambda *args: raw
    with ThreadPoolExecutor(max_workers=1) as executor:
        scout.executor = executor
        discovery = await scout.discover()
        named = await scout.discover_company("Acme")
    for output in (discovery, named):
        assert output["version"] == "2"
        assert "primary_thesis" not in output
        assert output["contradictions"] == raw["contradictions"]
    scout._call_llm.assert_awaited_once()


def test_learned_prompt_cannot_remove_factual_authority_instruction():
    scout = object.__new__(Scout)
    scout.logger = logging.getLogger("test.factual_scout")
    scout.agent_name = "scout_a"
    scout.set_prompt("Search overlooked company sources")
    assert scout.system_prompt.endswith(FACTUAL_SCOUT_BOUNDARY)
    scout.set_prompt(scout.system_prompt)
    assert scout.system_prompt.count(FACTUAL_SCOUT_BOUNDARY) == 1


def test_missing_tenant_prompt_does_not_read_global_prompt_library(monkeypatch):
    scout = object.__new__(Scout)
    scout.logger = logging.getLogger("test.factual_scout")
    scout.agent_name = "scout_a"
    scout._tenant_user_id = "tenant-a"
    scout.system_prompt = "Tenant-safe default discovery"
    monkeypatch.setattr("meta.prompt_gating.load_prompt_active", lambda uid: {})
    monkeypatch.setattr("meta.prompt_gating.load_prompt_library", lambda uid: {})

    exists = Path.exists

    def global_read(path):
        if str(path).endswith("meta/prompt_library.json"):
            pytest.fail("A tenant must never fall back to the shared local prompt file")
        return exists(path)

    monkeypatch.setattr("scout.base.Path.exists", global_read)
    scout._load_prompt_from_library()
    assert scout.system_prompt.startswith("Tenant-safe default discovery")
