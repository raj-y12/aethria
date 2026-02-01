"""
Strict output schema for Reviewer.
All Reviewers must emit JSON matching this structure exactly.
"""
from typing import TypedDict, Literal, Dict


class ReviewerOutput(TypedDict, total=False):
    """Strict schema for Reviewer evaluations (legacy - use ReviewInfo from models.py)."""
    market_score: int  # 1-10
    product_score: int  # 1-10
    technical_score: int  # 1-10
    execution_score: int  # 1-10
    defensibility_score: int  # 1-10
    overall_summary: str
    key_risks: list[str]
    verdict: Literal["STRONG", "MEDIUM", "WEAK"]
    diligence_red_flags: list[str]  # Must align with /resources/reviewer_rules.json
    assumption_feedback: list[str]  # Comments on Scout assumptions; critical unknowns
    reviewer_agent_id: str  # Optional: Agent identifier for performance tracking
    # VC qualitative fields (optional; use [MISSING] when info absent)
    team_analysis: list[str]  # Founders, roles, experience, unfair advantage
    competition_analysis: list[str]  # Competitors, market position, differentiation, SWOT
    business_model_analysis: list[str]  # Monetization, pricing, growth plan, unit economics
    investment_thesis: list[str]  # Bullet points why to invest + core assumptions
    risk_mitigation: list[str]  # Actionable strategies per diligence_red_flags
    score_reasoning: Dict[str, str]  # Optional: per-dimension concise reasoning, e.g. {"market_score": "...", "product_score": "..."}


def validate_reviewer_output(data: dict) -> ReviewerOutput:
    """
    Validate that a dictionary matches the ReviewerOutput schema.
    Raises ValueError if validation fails.
    """
    required_fields = {
        "market_score": int,
        "product_score": int,
        "technical_score": int,
        "execution_score": int,
        "overall_summary": str,
        "key_risks": list,
        "verdict": str,
    }
    
    # Check all required fields exist
    for field, field_type in required_fields.items():
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
        if not isinstance(data[field], field_type):
            raise ValueError(
                f"Field '{field}' must be of type {field_type.__name__}, "
                f"got {type(data[field]).__name__}"
            )
    
    # Validate scores are 1-10
    score_fields = ["market_score", "product_score", "technical_score", "execution_score"]
    for field in score_fields:
        if not (1 <= data[field] <= 10):
            raise ValueError(f"{field} must be between 1 and 10, got {data[field]}")
    
    # Optional defensibility_score: if present, must be 1-10
    if "defensibility_score" in data and data["defensibility_score"] is not None:
        d = data["defensibility_score"]
        if not isinstance(d, int) or not (1 <= d <= 10):
            raise ValueError(f"defensibility_score must be an int between 1 and 10, got {d}")
    
    # Validate verdict
    valid_verdicts = ["STRONG", "MEDIUM", "WEAK"]
    if data["verdict"] not in valid_verdicts:
        raise ValueError(
            f"verdict must be one of {valid_verdicts}, got {data['verdict']}"
        )
    
    # Validate key_risks is a list of strings
    if not isinstance(data["key_risks"], list):
        raise ValueError("key_risks must be a list")
    for risk in data["key_risks"]:
        if not isinstance(risk, str):
            raise ValueError("All items in key_risks must be strings")
    
    # Optional diligence_red_flags: if present, must be list of strings
    if "diligence_red_flags" in data:
        drf = data["diligence_red_flags"]
        if not isinstance(drf, list):
            raise ValueError("diligence_red_flags must be a list")
        for flag in drf:
            if not isinstance(flag, str):
                raise ValueError("All items in diligence_red_flags must be strings")
    
    # Optional assumption_feedback: if present, must be list of strings; default []
    if "assumption_feedback" not in data:
        data = {**data, "assumption_feedback": []}
    else:
        af = data["assumption_feedback"]
        if not isinstance(af, list):
            raise ValueError("assumption_feedback must be a list")
        for item in af:
            if not isinstance(item, str):
                raise ValueError("All items in assumption_feedback must be strings")

    # Optional VC qualitative fields: if present, must be list of strings
    for field in ("team_analysis", "competition_analysis", "business_model_analysis", "investment_thesis", "risk_mitigation"):
        if field in data and data[field] is not None:
            val = data[field]
            if not isinstance(val, list):
                raise ValueError(f"{field} must be a list")
            for item in val:
                if not isinstance(item, str):
                    raise ValueError(f"All items in {field} must be strings")

    # Optional score_reasoning: if present, must be dict of str -> str
    if "score_reasoning" in data and data["score_reasoning"] is not None:
        sr = data["score_reasoning"]
        if not isinstance(sr, dict):
            raise ValueError("score_reasoning must be a dict")
        for k, v in sr.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ValueError("score_reasoning keys and values must be strings")
    
    return ReviewerOutput(**data)
