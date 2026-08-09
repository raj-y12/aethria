"""
Concrete Reviewer implementation.
"""
from reviewer.base import _PersonaReviewer


class DefaultReviewer(_PersonaReviewer):
    """
    Default Reviewer implementation.
    Uses the base Reviewer with standard evaluation criteria.
    """

    REVIEWER_TYPE = "default"
