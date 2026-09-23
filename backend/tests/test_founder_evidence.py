from typing import Any, Dict, List

import resolver.company_resolver as cr
from models import ScoutInfo
from resolver.company_resolver import EvidenceSource, resolve_company
from utils.adapters import scout_output_to_scout_info


def _pack(sources: List[Dict[str, str]]) -> Dict[str, Any]:
    return {
        "provider": "exa",
        "sources": sources,
        "url_allowlist": {source["url"] for source in sources},
    }


def test_founder_extractor_handles_team_and_role_formats():
    sources = [
        EvidenceSource(
            url="https://example.com/team",
            title="Founding team",
            snippet="Founding team: Jane Smith and John Doe.",
        ),
        EvidenceSource(
            url="https://techcrunch.com/aethria",
            title="Aethria funding",
            snippet="Jane Smith — Co-founder & CEO; John Doe — Co-founder and CTO.",
        ),
    ]

    assert cr._extract_founders(sources) == ["Jane Smith", "John Doe"]


def test_resolver_does_not_skip_founder_corroboration_when_identity_is_strong(monkeypatch):
    calls: List[List[str]] = []

    def fake_retrieve(**kwargs):
        queries = list(kwargs["queries"])
        calls.append(queries)
        if any("founder CEO" in query for query in queries):
            return _pack(
                [
                    {
                        "title": "Aethria founders",
                        "url": "https://techcrunch.com/aethria",
                        "snippet": "Aethria was founded by Jane Smith and John Doe.",
                    }
                ]
            )
        return _pack(
            [
                {
                    "title": "Aethria",
                    "url": "https://aethria.co",
                    "snippet": "Official product site.",
                },
                {
                    "title": "Aethria | LinkedIn",
                    "url": "https://linkedin.com/company/aethria",
                    "snippet": "Aethria software company.",
                },
                {
                    "title": "Aethria | Crunchbase",
                    "url": "https://crunchbase.com/organization/aethria",
                    "snippet": "Aethria company profile.",
                },
            ]
        )

    monkeypatch.setattr(cr, "retrieve_source_pack_merged", fake_retrieve)
    result = resolve_company("Aethria", user_id="user-founder-test", website_hint="aethria.co")

    assert len(calls) == 2
    assert result.founder_names == ["Jane Smith", "John Doe"]


def test_founder_names_survive_scout_adapter():
    scout = scout_output_to_scout_info(
        {
            "id": "startup-1",
            "name": "Aethria",
            "one_line": "Investment intelligence.",
            "sector": "AI",
            "problem": "Slow diligence.",
            "solution": "Automated research.",
            "target_users": "Funds",
            "why_now": "AI retrieval is mature.",
            "scout_type": "market_driven",
            "confidence": 0.8,
            "primary_thesis": "Strong wedge.",
            "key_assumptions": ["Demand exists", "Sources are accurate"],
            "biggest_unknown": "Conversion.",
            "references": ["https://aethria.co"],
            "founder_names": ["Jane Smith", "John Doe"],
        }
    )

    assert scout.founder_names == ["Jane Smith", "John Doe"]
