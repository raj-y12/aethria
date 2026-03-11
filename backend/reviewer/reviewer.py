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
    
    def __init__(self, api_key: str, model: str = "gpt-5-nano"):
        self.reviewer_type = "default"
        super().__init__(api_key, model=model)

    async def review(self, scout_output: dict) -> Optional[ReviewerOutput]:
        """Review a Scout discovery using the base implementation."""
        return await super().review(scout_output)
