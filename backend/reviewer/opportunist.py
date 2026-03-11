"""Opportunist Reviewer — market-first evaluation lens."""
from reviewer.base import Reviewer
from reviewer.schema import ReviewerOutput
from typing import Optional


class OpportunistReviewer(Reviewer):
    """Market-first reviewer. Weights market size and timing, gives benefit of doubt on early-stage."""
    
    OPPORTUNIST_ADDENDUM = """

REVIEWER PERSONA: OPPORTUNIST / MARKET-FIRST
Your additional lens:
- Weight market_score and timing (why_now) most heavily
- For early-stage (Pre-Seed/Seed): give benefit of doubt on missing team data
- Look for asymmetric upside — a 10x outcome potential can offset execution risk
- Be more generous with scores when market timing is exceptional
- Identify hidden optionality (platform potential, adjacent markets)
- Your role is to find the next breakout opportunity before consensus forms"""

    def __init__(self, api_key: str, model: str = "gpt-5-nano"):
        super().__init__(api_key, model=model)
        self.SYSTEM_PROMPT = self.SYSTEM_PROMPT + self.OPPORTUNIST_ADDENDUM
        self.reviewer_type = "opportunist"
