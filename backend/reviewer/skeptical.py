"""Skeptical Reviewer — risk-first evaluation lens."""
from reviewer.base import Reviewer, _load_reviewer_resources, _build_system_prompt
from reviewer.schema import ReviewerOutput
from typing import Any, Mapping, Optional


class SkepticalReviewer(Reviewer):
    """Risk-first reviewer. Probes assumptions aggressively, weights execution and defensibility higher."""
    
    SKEPTICAL_ADDENDUM = """

REVIEWER PERSONA: SKEPTICAL / RISK-FIRST
Your additional lens:
- Identify failure modes before upside
- Probe assumptions aggressively — if data is missing, assume the worst
- Weight execution_score and defensibility_score higher than market_score
- Default to LOWER scores when data is missing (don't give benefit of doubt)
- Be especially critical of TAM claims without evidence
- Flag any assumption that has not been validated with evidence
- Your role is to protect the firm from bad investments"""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5-nano",
        tenant_user_id: str = "",
        use_resource_fund_thesis_fallback: bool = True,
        structured_scoring_enabled: bool = False,
        structured_signal_grounding: Optional[Mapping[str, Any]] = None,
    ):
        self.reviewer_type = "skeptical"
        super().__init__(
            api_key,
            model=model,
            tenant_user_id=tenant_user_id,
            use_resource_fund_thesis_fallback=use_resource_fund_thesis_fallback,
            structured_scoring_enabled=structured_scoring_enabled,
            structured_signal_grounding=structured_signal_grounding,
        )
        self.SYSTEM_PROMPT = self.SYSTEM_PROMPT + self.SKEPTICAL_ADDENDUM
