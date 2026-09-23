"""Frozen historical inputs/data for current-analysis and compatibility tests.

No historical engine is executed. Golden JSON remains an immutable comparison.
"""
from datetime import datetime, timezone
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[3] / "resources" / "config"
GOLDEN = Path(__file__).with_name("phase0_golden_pipeline.json")
CLOCK = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)
DIMENSIONS = ("market", "product", "technical", "execution", "defensibility")


def _inputs(case):
    claims = [
        {
            "claim_id": f"{case}-{dimension}",
            "claim_type": dimension,
            "normalized_value": {"criterion_score": 8.0, "score_band": "high"},
            "display_text": f"Verified {dimension} evidence for synthetic startup {case}.",
            "assertion_class": "externally_verified",
            "status": "current",
            "confidence": 0.9,
        }
        for dimension in DIMENSIONS
    ]
    links = [
        {
            "claim_id": claim["claim_id"],
            "evidence_item_id": f"source-{claim['claim_id']}",
            "relationship": "supports",
            "support_strength": 0.9,
            "verification_state": "verified",
            "source_quality": 0.9,
            "trust_class": "independent",
            "untrusted_input": False,
            "prompt_injection_detected": False,
            "evidence_effective_at": "2026-09-01T00:00:00+00:00",
            "evidence_expires_at": "2027-01-01T00:00:00+00:00",
            "artifact_effective_at": "2026-09-01T00:00:00+00:00",
            "retrieved_at": "2026-09-01T01:00:00+00:00",
        }
        for claim in claims
    ]
    review = {
        "verdict": "STRONG",
        **{f"{dimension}_score": 9.0 for dimension in DIMENSIONS},
        "key_risks": [],
        "assumption_feedback": [],
        "score_reasoning": {},
        "team_analysis": ["Synthetic founder operating history."],
        "business_model_analysis": ["Synthetic annual contracts."],
        "thesis_alignment_score": 0.9,
        "thesis_alignment_confidence": 0.9,
    }
    if case == "B_strong_looking_unverified":
        for link in links:
            link["verification_state"] = "unverified"
    elif case == "C_contradictory":
        links.append({**links[0], "evidence_item_id": "source-market-contradiction", "relationship": "contradicts"})
    elif case == "D_missing_dimension":
        claims = [claim for claim in claims if claim["claim_type"] != "execution"]
        links = [link for link in links if not link["claim_id"].endswith("-execution")]
    elif case == "E_out_of_mandate":
        review["thesis_alignment_score"] = 0.1
    elif case == "F_legacy_canonical_diverge":
        for claim in claims:
            claim["normalized_value"] = {"criterion_score": 6.0, "score_band": "mid"}
    elif case == "G_insufficient_evidence":
        claims, links = [], []
    return claims, links, review
