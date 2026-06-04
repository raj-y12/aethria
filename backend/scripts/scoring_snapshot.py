#!/usr/bin/env python3
"""Deterministic scoring snapshot — before/after comparison harness.

Phase 0 guardrail (P0.2) for the scoring remediation tracked in
``docs/scoring-remediation-checklist.md``.

The deterministic engine is pure, so the same inputs always produce the same scores.
This tool renders the scores for a fixed set of representative fixtures as stable
JSON, so you can capture a baseline before a change and diff it afterwards:

  # before a change
  python scripts/scoring_snapshot.py > /tmp/before.json
  # ... make the change ...
  python scripts/scoring_snapshot.py > /tmp/after.json
  diff <(jq -S . /tmp/before.json) <(jq -S . /tmp/after.json)

You can also score a single payload from a JSON file containing {"scout": {...},
"review": {...}}:

  python scripts/scoring_snapshot.py --payload my_company.json

This is intentionally dependency-light (no LLM, no Supabase) so it runs anywhere the
scoring layer imports.
"""
import argparse
import json
import os
import sys
from pathlib import Path

# Ensure backend root is on path (matches scripts/clear_data.py convention).
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# Keep output clean and deterministic regardless of local env.
os.environ.setdefault("DEBUG_SCORING", "0")

from services.scoring.scoring_engine import DeterministicScoringEngine  # noqa: E402

DIMENSIONS = ("market", "product", "technical", "execution", "defensibility")

# Same representative fixtures used by tests/test_scoring_golden_snapshot.py.
FIXTURES = {
    "strong_saas": (
        {
            "one_line": "AI compliance copilot for healthcare",
            "problem": "Manual compliance is costly.",
            "solution": "Model-driven automation with proprietary compliance datasets.",
            "target_users": "Mid-market healthcare",
            "why_now": "Regulatory burden rising 45%.",
            "est_tam": "$12B",
        },
        {
            "competition_analysis": ["Crowded incumbent market."],
            "team_analysis": ["Ex-Epic and ex-Palantir operators."],
            "business_model_analysis": ["Early revenue, repeatable outbound."],
            "market_reasoning": ["Rapid demand growth."],
            "product_reasoning": ["Sticky daily usage."],
            "technical_reasoning": ["Scalable robust infra."],
            "defensibility_reasoning": ["Strong switching costs and data moat."],
            "market_confidence": "high",
            "product_confidence": "medium",
            "technical_confidence": "medium",
            "execution_confidence": "medium",
            "defensibility_confidence": "medium",
        },
    ),
    "weak_thin": (
        {"one_line": "A social app", "problem": "People are bored.", "solution": "Another feed.", "est_tam": "$200M"},
        {
            "market_confidence": "low",
            "product_confidence": "low",
            "technical_confidence": "low",
            "execution_confidence": "low",
            "defensibility_confidence": "low",
        },
    ),
    "all_missing": ({}, {}),
    "structured_signals": (
        {},
        {
            "structured_signals": {
                "market": {
                    "tam": {"value": "$3B", "confidence": 0.8},
                    "growth_rate": {"value": "24%", "confidence": 0.8},
                    "urgency": {"label": "high", "confidence": 0.7},
                    "timing": {"label": "favorable", "confidence": 0.7},
                    "competition": {"label": "moderate", "confidence": 0.6},
                },
                "execution": {
                    "traction": {"label": "early_revenue", "confidence": 0.7},
                    "team_execution": {"label": "credible_team", "confidence": 0.7},
                },
            }
        },
    ),
}


def _round(value):
    return round(float(value), 4) if value is not None else None


def snapshot_one(engine, scout, review):
    result = engine.score(scout, review)
    return {
        "overall_score": _round(result.get("overall_score")),
        "overall_confidence": _round(result.get("overall_confidence")),
        "dims": {
            d: {
                "score": _round(result[d]["score"]),
                "confidence": _round(result[d].get("confidence")),
            }
            for d in DIMENSIONS
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--payload", help="JSON file with {'scout': {...}, 'review': {...}} to score.")
    args = parser.parse_args()

    engine = DeterministicScoringEngine()

    if args.payload:
        data = json.loads(Path(args.payload).read_text())
        out = {"payload": snapshot_one(engine, data.get("scout", {}), data.get("review", {}))}
    else:
        out = {name: snapshot_one(engine, scout, review) for name, (scout, review) in FIXTURES.items()}

    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
