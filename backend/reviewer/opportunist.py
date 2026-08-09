"""Opportunist Reviewer — market-first evaluation lens."""
from reviewer.base import _PersonaReviewer


class OpportunistReviewer(_PersonaReviewer):
    """Market-first reviewer. Weights market size and timing, gives benefit of doubt on early-stage."""

    REVIEWER_TYPE = "opportunist"
    ADDENDUM = """

REVIEWER PERSONA: OPPORTUNIST / MARKET-FIRST
Your additional lens:
- Weight market_score and timing (why_now) most heavily
- For early-stage (Pre-Seed/Seed): give benefit of doubt on missing team data
- Look for asymmetric upside — a 10x outcome potential can offset execution risk
- Be more generous with scores when market timing is exceptional
- Identify hidden optionality (platform potential, adjacent markets)
- Your role is to find the next breakout opportunity before consensus forms"""
