"""
Strict output schema for Reviewer.
All Reviewers must emit JSON matching this structure exactly.
"""
from typing import Any, TypedDict, Literal, Dict, List


class ReviewerOutput(TypedDict, total=False):
    """Strict schema for Reviewer evaluations (legacy - use ReviewInfo from models.py)."""
    overall_summary: str
    key_risks: list[str]
    verdict: Literal["STRONG", "MEDIUM", "WEAK"]
    diligence_red_flags: list[str]  # Must align with versioned reviewer_rules policy
    assumption_feedback: list[str]  # Comments on Scout assumptions; critical unknowns
    reviewer_agent_id: str  # Optional: Agent identifier for performance tracking
    # VC qualitative fields (optional; use [MISSING] when info absent)
    team_analysis: list[str]  # Founders, roles, experience, unfair advantage
    competition_analysis: list[str]  # Competitors, market position, differentiation, SWOT
    business_model_analysis: list[str]  # Monetization, pricing, growth plan, unit economics
    investment_thesis: list[str]  # Bullet points why to invest + core assumptions
    risk_mitigation: list[str]  # Actionable strategies per diligence_red_flags
    improvement_to_9: list[str]
    market_reasoning: list[str]
    market_weaknesses: list[str]
    market_confidence: Literal["low", "medium", "high"]
    product_reasoning: list[str]
    product_weaknesses: list[str]
    product_confidence: Literal["low", "medium", "high"]
    technical_reasoning: list[str]
    technical_weaknesses: list[str]
    technical_confidence: Literal["low", "medium", "high"]
    execution_reasoning: list[str]
    execution_weaknesses: list[str]
    execution_confidence: Literal["low", "medium", "high"]
    defensibility_reasoning: list[str]
    defensibility_weaknesses: list[str]
    defensibility_confidence: Literal["low", "medium", "high"]
    thesis_alignment_score: float
    thesis_matches_fund: bool
    thesis_fit_points: list[str]
    thesis_deviation_points: list[str]
    thesis_alignment_confidence: float
    fund_thesis_alignment_score: float  # optional at runtime; validated when present
    # Investment read (reviewer_rules v2+). Narrative only: never an input to scores
    # or verdict. Each is omitted (empty) when the evidence bar is not met.
    founder_fluency: List[Dict[str, Any]]  # [{founder, prior_domain, fluent_in[], unlocks[], evidence}]
    capability_slope: Dict[str, Any]  # {hardest_instance, downhill[], blocked_by[], evidence}
    reframe: Dict[str, str]  # {obvious_question, why_it_misleads, real_question}


_READ_MAX_BULLETS = 4
_READ_MAX_FOUNDERS = 4


def _read_str(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) else ""


def _read_list(value: Any, cap: int = _READ_MAX_BULLETS) -> List[str]:
    if not isinstance(value, list):
        return []
    cleaned = [_read_str(item) for item in value]
    return [item for item in cleaned if item][:cap]


def normalize_investment_read(data: dict, allowed_founders: Any = None) -> dict:
    """Normalize the reviewer_rules v2 investment-read fields, failing closed.

    An entry missing the evidence it is required to carry is dropped, never
    completed by inference (ADR-0010). `allowed_founders` — when a non-empty
    collection of resolved founder names is supplied — restricts founder_fluency
    to founders the identity layer actually resolved, so the read cannot invent
    a person.
    """
    allowed = {name.strip().lower() for name in (allowed_founders or []) if _read_str(name)}

    fluency: List[Dict[str, Any]] = []
    for raw in (data.get("founder_fluency") or []) if isinstance(data.get("founder_fluency"), list) else []:
        if not isinstance(raw, dict):
            continue
        founder = _read_str(raw.get("founder"))
        prior_domain = _read_str(raw.get("prior_domain"))
        evidence = _read_str(raw.get("evidence"))
        fluent_in = _read_list(raw.get("fluent_in"))
        unlocks = _read_list(raw.get("unlocks"))
        if not (founder and prior_domain and evidence and (fluent_in or unlocks)):
            continue
        if allowed and founder.lower() not in allowed:
            continue
        fluency.append({
            "founder": founder,
            "prior_domain": prior_domain,
            "fluent_in": fluent_in,
            "unlocks": unlocks,
            "evidence": evidence,
        })
    data["founder_fluency"] = fluency[:_READ_MAX_FOUNDERS]

    slope_raw = data.get("capability_slope")
    slope: Dict[str, Any] = {}
    if isinstance(slope_raw, dict):
        hardest = _read_str(slope_raw.get("hardest_instance"))
        downhill = _read_list(slope_raw.get("downhill"))
        # A slope needs a demonstrated hardest instance AND something downhill of
        # it; a roadmap with neither is an ambition, not a slope.
        if hardest and downhill:
            slope = {
                "hardest_instance": hardest,
                "downhill": downhill,
                "blocked_by": _read_list(slope_raw.get("blocked_by")),
                "evidence": _read_str(slope_raw.get("evidence")),
            }
    data["capability_slope"] = slope

    reframe_raw = data.get("reframe")
    reframe: Dict[str, str] = {}
    if isinstance(reframe_raw, dict):
        obvious = _read_str(reframe_raw.get("obvious_question"))
        misleads = _read_str(reframe_raw.get("why_it_misleads"))
        real = _read_str(reframe_raw.get("real_question"))
        # All three or nothing — a reframe missing its counter-question is a jab.
        if obvious and misleads and real:
            reframe = {
                "obvious_question": obvious,
                "why_it_misleads": misleads,
                "real_question": real,
            }
    data["reframe"] = reframe
    return data


def validate_reviewer_output(data: dict) -> ReviewerOutput:
    def _validate_string_list(field: str, min_items: int, max_items: int) -> None:
        val = data.get(field)
        if val is None:
            data[field] = []
            return
        if not isinstance(val, list):
            raise ValueError(f"{field} must be a list")
        cleaned = [str(item).strip() for item in val if str(item).strip()]
        # Be tolerant of LLM list-length drift: never fail reviewer output
        # solely because optional explanatory lists are shorter/longer than target.
        if len(cleaned) > max_items:
            cleaned = cleaned[:max_items]
        data[field] = cleaned

    def _validate_confidence(field: str) -> None:
        val = data.get(field)
        if val is None:
            data[field] = "medium"
            return
        v = str(val).strip().lower()
        if v not in ("low", "medium", "high"):
            raise ValueError(f"{field} must be one of ['low', 'medium', 'high']")
        data[field] = v

    """
    Validate that a dictionary matches the ReviewerOutput schema.
    Raises ValueError if validation fails.
    """
    required_fields = {
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
    
    # Numeric reviewer assessments and their trace payloads are retired.  Drop
    # them even if a model or an old prompt emits them; canonical evaluation is
    # the sole score-producing system.
    for field in (
        "market_score", "product_score", "technical_score", "execution_score",
        "defensibility_score", "overall_score", "confidence_adjusted_score",
        "score_reasoning", "score_source", "structured_signals",
        "structured_scoring", "score_breakdown", "derived_verdict",
    ):
        data.pop(field, None)
    
    # Normalize common LLM verdict aliases before strict validation.
    # This prevents otherwise valid reviews from failing on label drift.
    verdict_aliases = {
        "PROMISING": "MEDIUM",
        "AVERAGE": "MEDIUM",
        "MODERATE": "MEDIUM",
        "STRONG BUY": "STRONG",
        "WEAK PASS": "WEAK",
    }
    raw_verdict = str(data.get("verdict", "")).strip().upper()
    if raw_verdict in verdict_aliases:
        data["verdict"] = verdict_aliases[raw_verdict]

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

    for dim in ("market", "product", "technical", "execution", "defensibility"):
        _validate_string_list(f"{dim}_reasoning", min_items=2, max_items=4)
        _validate_string_list(f"{dim}_weaknesses", min_items=1, max_items=3)
        _validate_confidence(f"{dim}_confidence")

    _validate_string_list("improvement_to_9", min_items=1, max_items=5)

    # Optional fund thesis fields (when mandate present in reviewer prompt)
    if "thesis_alignment_score" in data and data["thesis_alignment_score"] is not None:
        try:
            ts = float(data["thesis_alignment_score"])
        except (TypeError, ValueError):
            raise ValueError("thesis_alignment_score must be a number")
        if not 0.0 <= ts <= 1.0:
            raise ValueError("thesis_alignment_score must be between 0 and 1")
        data["thesis_alignment_score"] = ts
    if "thesis_alignment_confidence" in data and data["thesis_alignment_confidence"] is not None:
        try:
            tc = float(data["thesis_alignment_confidence"])
        except (TypeError, ValueError):
            raise ValueError("thesis_alignment_confidence must be a number")
        if not 0.0 <= tc <= 1.0:
            raise ValueError("thesis_alignment_confidence must be between 0 and 1")
        data["thesis_alignment_confidence"] = tc
    if "thesis_matches_fund" in data and data["thesis_matches_fund"] is not None:
        if not isinstance(data["thesis_matches_fund"], bool):
            raise ValueError("thesis_matches_fund must be a boolean")
    for fld in ("thesis_fit_points", "thesis_deviation_points"):
        if fld in data and data[fld] is not None:
            if not isinstance(data[fld], list):
                raise ValueError(f"{fld} must be a list")
            for item in data[fld]:
                if not isinstance(item, str):
                    raise ValueError(f"All items in {fld} must be strings")

    if "fund_thesis_alignment_score" in data and data["fund_thesis_alignment_score"] is not None:
        try:
            fs = float(data["fund_thesis_alignment_score"])
        except (TypeError, ValueError):
            raise ValueError("fund_thesis_alignment_score must be a number")
        if not 0.0 <= fs <= 1.0:
            raise ValueError("fund_thesis_alignment_score must be between 0 and 1")
        data["fund_thesis_alignment_score"] = fs

    normalize_investment_read(data)

    return ReviewerOutput(**data)
