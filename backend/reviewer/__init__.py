"""
AETHRIA Reviewer Layer

The Reviewer layer evaluates Scout discoveries and provides
structured assessments of quality, realism, and fundability.
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
