"""
AETHRIA Reviewer Layer — LEGACY / COMPATIBILITY, not the authoritative
runtime path.

The three-persona Reviewer implementation this package holds is retired for
live decision-making. The current, authoritative Reviewer phase lives in
`backend/investment_analysis/` (see its README and ADR-0016). This package
is kept for historical replay, Phase-0 golden fixtures, and because
`ReviewerEngine` is still constructed as a compatibility component by
`pipeline_runner.py`/`api.py`. Do not add new product behaviour here; if you
are implementing a new Reviewer capability, it belongs in
`investment_analysis/`.
"""
from reviewer.base import Reviewer
from reviewer.gap_retrieval import enrich_scout_for_reviewer_llm
from reviewer.schema import ReviewerOutput, validate_reviewer_output
from reviewer.reviewer import DefaultReviewer
from reviewer.skeptical import SkepticalReviewer
from reviewer.opportunist import OpportunistReviewer
from reviewer.structured_signals_clamp import clamp_structured_signals_evidence

__all__ = [
    "Reviewer",
    "ReviewerOutput",
    "validate_reviewer_output",
    "DefaultReviewer",
    "SkepticalReviewer",
    "OpportunistReviewer",
    "clamp_structured_signals_evidence",
    "enrich_scout_for_reviewer_llm",
]
