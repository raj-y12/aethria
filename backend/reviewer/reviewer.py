"""
Concrete Reviewer implementation.
"""
from reviewer.base import Reviewer
from reviewer.schema import ReviewerOutput
from typing import Optional


class DefaultReviewer(Reviewer):
    """
    Default Reviewer implementation.
    Uses the base Reviewer with standard evaluation criteria.
    """
    
    async def review(self, scout_output: dict) -> Optional[ReviewerOutput]:
        """Review a Scout discovery using the base implementation."""
        return await super().review(scout_output)
