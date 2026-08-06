"""Skeptical Reviewer — risk-first evaluation lens."""
from reviewer.base import _PersonaReviewer


class SkepticalReviewer(_PersonaReviewer):
    """Risk-first reviewer. Probes assumptions aggressively, weights execution and defensibility higher."""

    REVIEWER_TYPE = "skeptical"
    ADDENDUM = """

REVIEWER PERSONA: SKEPTICAL / RISK-FIRST
Your additional lens:
- Identify failure modes before upside
- Probe assumptions aggressively — if data is missing, assume the worst
- Weight execution_score and defensibility_score higher than market_score
- Default to LOWER scores when data is missing (don't give benefit of doubt)
- Be especially critical of TAM claims without evidence
- Flag any assumption that has not been validated with evidence
- Your role is to protect the firm from bad investments"""
