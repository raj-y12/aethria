"""Structured signal extraction from reviewer/scout payloads."""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List


MISSING_TOKEN_RE = re.compile(r"^\s*\[?\s*missing(?::[^\]]*)?\]?\s*$", re.IGNORECASE)
COMPONENT_ALIASES = {
    "market": {"growth": "growth_rate"},
    "execution": {"growth": "growth_velocity", "gtm": "gtm_effectiveness", "team": "team_execution"},
    "product": {"value": "value_prop"},
    "technical": {"engineering": "engineering_quality", "data": "data_advantage"},
    "defensibility": {"network": "network_effects", "switching": "switching_costs", "data": "proprietary_data"},
}
EXPECTED_COMPONENTS = {
    "market": ["tam", "growth_rate", "urgency", "timing", "competition"],
    "execution": ["traction", "growth_velocity", "gtm_effectiveness", "team_execution", "operational_velocity"],
    "product": ["value_prop", "pain_alignment", "differentiation", "ux", "retention"],
    "technical": ["complexity", "engineering_quality", "scalability", "data_advantage", "architecture"],
    "defensibility": ["network_effects", "switching_costs", "proprietary_data", "barriers", "brand"],
}

_SCOUT_BUNDLE_MAX = 4000


def _scout_narrative_bundle(scout_output: Dict[str, Any]) -> str:
    """
    Bounded join of scout narrative fields for keyword extractors (no raw URL dump).
    """
    chunks: List[str] = []
    caps = {
        "problem": 900,
        "solution": 900,
        "one_line": 512,
        "why_now": 700,
        "primary_thesis": 450,
        "target_users": 450,
    }
    for key, maxlen in caps.items():
        v = scout_output.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            chunks.append(s[:maxlen])
    et = scout_output.get("est_tam")
    if et and str(et).strip():
        chunks.append(str(et).strip()[:128])
    out = " ".join(chunks).strip()
    if len(out) > _SCOUT_BUNDLE_MAX:
        out = out[:_SCOUT_BUNDLE_MAX]
    return out


def _is_missing_token(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return True
        if MISSING_TOKEN_RE.match(text):
            return True
    return False


def _missing_signal(reasoning: str = "") -> Dict[str, Any]:
    return {"value": None, "confidence": 0.2, "reasoning": reasoning or "Signal missing; neutral fallback applied."}


def _signal(
    value: Any = None,
    label: str | None = None,
    confidence: float = 0.5,
    reasoning: str = "",
    rule: str = "",
) -> Dict[str, Any]:
    try:
        conf = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        conf = 0.5
    payload: Dict[str, Any] = {"confidence": conf, "reasoning": reasoning}
    if rule:
        payload["rule"] = rule
    if label is not None:
        if _is_missing_token(label):
            return _missing_signal(reasoning)
        payload["label"] = label
    else:
        if _is_missing_token(value):
            return _missing_signal(reasoning)
        payload["value"] = value
    return payload


def _join_lines(values: List[str] | None) -> str:
    return " ".join(values or [])


def _infer_growth_from_text(text: str) -> Any:
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text or "")
    return f"{match.group(1)}%" if match else None


def extract_traction(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    bundle = _scout_narrative_bundle(scout_output)
    text = (
        _join_lines(reviewer_output.get("business_model_analysis"))
        + " "
        + str(scout_output.get("one_line") or "")
        + " "
        + bundle
    )
    lower = text.lower()
    if any(k in lower for k in ("strong scale", "scaled", "100m", "enterprise contracts")):
        return _signal(label="strong_scale", confidence=0.75, reasoning="Signals indicate scaled commercial traction.", rule="keyword match: strong scale/scaled/enterprise contracts")
    if any(k in lower for k in ("scaling", "series b", "series c", "rapid expansion")):
        return _signal(label="scaling", confidence=0.7, reasoning="Language indicates scaling phase.", rule="keyword match: scaling/series b+/rapid expansion")
    if any(k in lower for k in ("paying customer", "paying customers", "enterprise customer", "active users", "customers", "deployments", "deployment", "production workload", "live in production")):
        return _signal(label="early_adoption", confidence=0.63, reasoning="Customer or deployment usage language found.", rule="keyword match: customers/users/deployments/production")
    if any(k in lower for k in ("revenue", "paying customers", "arr", "mrr")):
        return _signal(label="early_revenue", confidence=0.68, reasoning="Revenue language found.", rule="keyword match: revenue/paying customers/ARR/MRR")
    if any(k in lower for k in ("mvp", "pilot", "beta")):
        return _signal(label="mvp", confidence=0.6, reasoning="MVP/pilot indicators found.", rule="keyword match: MVP/pilot/beta")
    if any(k in lower for k in ("pre-product", "idea stage", "prototype only")):
        return _signal(label="pre-product", confidence=0.65, reasoning="Pre-product wording detected.", rule="keyword match: pre-product/idea stage/prototype only")
    return _missing_signal("No explicit traction evidence.")


def extract_growth_velocity(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    combined = (
        f"{scout_output.get('why_now') or ''} {_join_lines(reviewer_output.get('market_reasoning'))} "
        f"{_scout_narrative_bundle(scout_output)}"
    )
    pct = _infer_growth_from_text(combined)
    if pct:
        return _signal(value=pct, confidence=0.65, reasoning="Growth percentage extracted from narrative.")
    lower = combined.lower()
    if any(k in lower for k in ("hypergrowth", "explosive")):
        return _signal(label="hyper", confidence=0.7, reasoning="Hypergrowth wording detected.")
    if any(k in lower for k in ("fast growth", "rapid growth", "accelerating")):
        return _signal(label="fast", confidence=0.68, reasoning="Fast growth language detected.")
    if any(k in lower for k in ("steady", "moderate growth")):
        return _signal(label="moderate", confidence=0.6, reasoning="Moderate growth indicators found.")
    if any(k in lower for k in ("slow growth", "early adoption")):
        return _signal(label="slow", confidence=0.58, reasoning="Slow growth indicators found.")
    return _signal(label="flat", confidence=0.45, reasoning="No clear growth momentum found.")


def classify_gtm_effectiveness(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    text = (
        _join_lines(reviewer_output.get("business_model_analysis"))
        + " "
        + str(scout_output.get("target_users") or "")
        + " "
        + _scout_narrative_bundle(scout_output)
    )
    lower = text.lower()
    if any(k in lower for k in ("repeatable", "efficient cac", "channel fit", "strong distribution")):
        return _signal(label="strong_edge", confidence=0.72, reasoning="Strong GTM edge indicators present.")
    if any(k in lower for k in ("repeatable", "proven channel", "scalable channel")):
        return _signal(label="repeatable", confidence=0.7, reasoning="Repeatable GTM signs found.")
    if any(k in lower for k in ("partnership", "outbound", "paid", "community")):
        return _signal(label="some_channels", confidence=0.62, reasoning="Some GTM channels mentioned.")
    return _signal(label="unclear", confidence=0.48, reasoning="No clear GTM effectiveness evidence.")


def extract_team_execution(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    text = _join_lines(reviewer_output.get("team_analysis")) + " " + _scout_narrative_bundle(scout_output)
    lower = text.lower()
    if any(k in lower for k in ("elite", "serial founder", "exited", "world-class")):
        return _signal(label="elite", confidence=0.75, reasoning="Exceptional team markers present.")
    if any(k in lower for k in ("strong", "experienced", "domain expertise")):
        return _signal(label="strong", confidence=0.68, reasoning="Strong team evidence found.")
    founder_exec_markers = (
        "founder",
        "co-founder",
        "cofounder",
        "ceo",
        "cto",
        "coo",
        "chief executive",
        "chief technology",
        "chief product",
        "vp engineering",
        "vp of engineering",
        "head of engineering",
        "technical lead",
        "engineering lead",
        "previously at",
        "prior role",
        "ex-google",
        "ex google",
        "ex-meta",
        "ex meta",
        "ex-amazon",
        "ex amazon",
        "ex-microsoft",
        "ex microsoft",
        "alumni",
        "stanford phd",
        "mit phd",
        "professor",
        "built at",
        "years at",
    )
    if any(k in lower for k in founder_exec_markers):
        return _signal(
            label="credible_team",
            confidence=0.64,
            reasoning="Founder or executive-team markers found in scout/reviewer text.",
            rule="keyword match: founder/executive/previously-at",
        )
    if any(k in lower for k in ("decent", "capable", "solid")):
        return _signal(label="decent", confidence=0.62, reasoning="Baseline team capability indicated.")
    if "[missing" in lower or not lower.strip():
        return _signal(label="weak", confidence=0.52, reasoning="Team data missing.")
    return _signal(label="decent", confidence=0.55, reasoning="Defaulting to decent with sparse evidence.")


def extract_operational_velocity(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    text = (
        f"{scout_output.get('why_now') or ''} {_join_lines(reviewer_output.get('execution_reasoning'))} "
        f"{_scout_narrative_bundle(scout_output)}"
    )
    lower = text.lower()
    if any(k in lower for k in ("exceptional velocity", "weekly releases", "breakneck")):
        return _signal(label="exceptional", confidence=0.72, reasoning="Exceptional operational cadence language found.")
    if any(k in lower for k in ("fast", "rapid iteration", "quickly shipping")):
        return _signal(label="fast", confidence=0.66, reasoning="Fast execution signals detected.")
    if any(k in lower for k in ("moderate", "steady")):
        return _signal(label="moderate", confidence=0.58, reasoning="Moderate execution pace language found.")
    return _signal(label="slow", confidence=0.45, reasoning="No strong operational speed evidence.")


def classify_value_prop(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    one_line = str(scout_output.get("one_line") or "").strip()
    if len(one_line) > 120:
        return _signal(label="vague", confidence=0.58, reasoning="Overly long one-line often indicates unclear value proposition.")
    if len(one_line) > 70:
        return _signal(label="understandable", confidence=0.62, reasoning="One-line is understandable but not sharp.")
    if len(one_line) > 25:
        return _signal(label="clear", confidence=0.68, reasoning="Concise one-line suggests clear value proposition.")
    if one_line:
        return _signal(label="exceptional", confidence=0.6, reasoning="Very concise one-line may indicate crisp value proposition.")
    return _signal(label="vague", confidence=0.45, reasoning="No clear value proposition text.")


def classify_pain_alignment(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    problem = str(scout_output.get("problem") or "").lower()
    if any(k in problem for k in ("critical", "urgent", "expensive", "compliance")):
        return _signal(label="critical", confidence=0.7, reasoning="Problem appears mission-critical.")
    if any(k in problem for k in ("pain", "manual", "inefficient")):
        return _signal(label="strong", confidence=0.66, reasoning="Strong pain indicators found.")
    if any(k in problem for k in ("nice to have", "optional")):
        return _signal(label="weak", confidence=0.62, reasoning="Problem appears non-critical.")
    return _signal(label="moderate", confidence=0.55, reasoning="Moderate pain alignment inferred.")


def classify_differentiation(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    text = _join_lines(reviewer_output.get("competition_analysis")) + " " + str(scout_output.get("solution") or "")
    lower = text.lower()
    if any(k in lower for k in ("unique", "proprietary", "10x", "patent")):
        return _signal(label="strong", confidence=0.7, reasoning="Strong differentiation claims present.")
    if any(k in lower for k in ("different", "better", "focused")):
        return _signal(label="clear", confidence=0.65, reasoning="Clear differentiation evidence found.")
    if any(k in lower for k in ("slightly better", "incremental")):
        return _signal(label="slight", confidence=0.58, reasoning="Only slight differentiation found.")
    return _signal(label="none", confidence=0.5, reasoning="No meaningful differentiation evidence.")


def classify_ux(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    text = _join_lines(reviewer_output.get("product_reasoning")).lower()
    if any(k in text for k in ("exceptional ux", "delightful", "best-in-class")):
        return _signal(label="exceptional", confidence=0.7, reasoning="Exceptional UX descriptors found.")
    if any(k in text for k in ("smooth", "intuitive", "frictionless")):
        return _signal(label="smooth", confidence=0.66, reasoning="Positive UX indicators found.")
    if any(k in text for k in ("usable", "adequate")):
        return _signal(label="usable", confidence=0.6, reasoning="Usable but not standout UX.")
    return _signal(label="clunky", confidence=0.48, reasoning="No positive UX evidence found.")


def extract_retention(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    text = _join_lines(reviewer_output.get("business_model_analysis")) + " " + _join_lines(reviewer_output.get("product_reasoning"))
    lower = text.lower()
    pct = _infer_growth_from_text(text)
    if pct:
        return _signal(value=pct, confidence=0.58, reasoning="Retention proxy extracted from percentage mention.")
    if any(k in lower for k in ("high retention", "sticky", "low churn")):
        return _signal(label="very_strong", confidence=0.7, reasoning="Strong retention language found.")
    if any(k in lower for k in ("retained", "repeat usage")):
        return _signal(label="strong", confidence=0.64, reasoning="Retention signal appears strong.")
    if any(k in lower for k in ("some churn", "early retention")):
        return _signal(label="moderate", confidence=0.58, reasoning="Moderate retention signals.")
    if any(k in lower for k in ("high churn", "low retention")):
        return _signal(label="weak", confidence=0.62, reasoning="Weak retention indicators.")
    return _missing_signal("Retention data not available.")


def classify_complexity(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    solution = str(scout_output.get("solution") or "").lower()
    if any(k in solution for k in ("ai model", "robotics", "biotech", "deep learning", "compiler")):
        return _signal(label="deeptech", confidence=0.7, reasoning="Deep technical complexity markers detected.", rule="keyword match: ai model/robotics/biotech/deep learning/compiler")
    if any(k in solution for k in ("distributed", "real-time", "multi-tenant")):
        return _signal(label="complex", confidence=0.66, reasoning="Complex systems indicators found.", rule="keyword match: distributed/real-time/multi-tenant")
    if any(k in solution for k in ("workflow", "automation", "dashboard")):
        return _signal(label="moderate", confidence=0.58, reasoning="Moderate product complexity inferred.", rule="keyword match: workflow/automation/dashboard")
    return _signal(label="simple", confidence=0.5, reasoning="Simple implementation profile inferred.", rule="fallback: no complexity markers detected")


def classify_engineering_quality(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    text = _join_lines(reviewer_output.get("technical_reasoning")).lower()
    if any(k in text for k in ("elite", "excellent engineering", "high reliability")):
        return _signal(label="elite", confidence=0.72, reasoning="Elite engineering quality markers found.")
    if any(k in text for k in ("strong", "good architecture", "well engineered")):
        return _signal(label="strong", confidence=0.66, reasoning="Strong engineering quality described.")
    if any(k in text for k in ("decent", "adequate")):
        return _signal(label="decent", confidence=0.58, reasoning="Decent engineering quality described.")
    return _signal(label="weak", confidence=0.48, reasoning="No strong engineering quality evidence.")


def classify_scalability(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    text = _join_lines(reviewer_output.get("technical_reasoning")).lower()
    if any(k in text for k in ("planet-scale", "extreme scale", "millions of rps")):
        return _signal(label="extreme", confidence=0.72, reasoning="Extreme scalability signals found.")
    if any(k in text for k in ("scalable", "high scale", "elastic")):
        return _signal(label="high", confidence=0.66, reasoning="High scalability evidence present.")
    if any(k in text for k in ("can scale", "moderate scale")):
        return _signal(label="medium", confidence=0.58, reasoning="Moderate scalability indicators.")
    return _signal(label="low", confidence=0.5, reasoning="Low scalability evidence.")


def classify_data_advantage(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    text = (_join_lines(reviewer_output.get("defensibility_reasoning")) + " " + str(scout_output.get("solution") or "")).lower()
    if any(k in text for k in ("proprietary dataset", "exclusive data", "data moat")):
        return _signal(label="strong", confidence=0.7, reasoning="Strong proprietary data advantage.")
    if any(k in text for k in ("data flywheel", "growing dataset")):
        return _signal(label="growing", confidence=0.64, reasoning="Growing data advantage signals.")
    if any(k in text for k in ("some data", "limited data")):
        return _signal(label="limited", confidence=0.56, reasoning="Limited data edge.")
    return _signal(label="none", confidence=0.48, reasoning="No data advantage evidence.")


def classify_architecture(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    text = _join_lines(reviewer_output.get("technical_reasoning")).lower()
    if any(k in text for k in ("robust architecture", "fault tolerant", "resilient")):
        return _signal(label="robust", confidence=0.72, reasoning="Robust architecture traits present.")
    if any(k in text for k in ("mature architecture", "modular")):
        return _signal(label="mature", confidence=0.66, reasoning="Mature architecture indicators.")
    if any(k in text for k in ("early architecture", "initial architecture")):
        return _signal(label="early", confidence=0.58, reasoning="Early architecture stage.")
    return _signal(label="prototype", confidence=0.5, reasoning="Prototype architecture inferred.")


def classify_network_effects(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    text = _join_lines(reviewer_output.get("defensibility_reasoning")).lower()
    if any(k in text for k in ("network effects", "flywheel", "liquidity network")):
        return _signal(label="strong", confidence=0.7, reasoning="Strong network effect indicators.")
    if any(k in text for k in ("community", "two-sided")):
        return _signal(label="moderate", confidence=0.62, reasoning="Moderate network effects implied.")
    if any(k in text for k in ("weak network", "limited network")):
        return _signal(label="weak", confidence=0.56, reasoning="Weak network effects.")
    return _signal(label="none", confidence=0.5, reasoning="No network effects evidence.")


def classify_switching_costs(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    text = _join_lines(reviewer_output.get("defensibility_reasoning")).lower()
    if any(k in text for k in ("very high switching cost", "mission critical lock-in")):
        return _signal(label="very_high", confidence=0.7, reasoning="Very high switching costs indicated.")
    if any(k in text for k in ("high switching cost", "workflow lock-in", "integration depth")):
        return _signal(label="high", confidence=0.66, reasoning="High switching costs implied.")
    if any(k in text for k in ("some switching cost", "moderate lock-in")):
        return _signal(label="medium", confidence=0.58, reasoning="Moderate switching costs.")
    return _signal(label="low", confidence=0.5, reasoning="Low switching costs.")


def classify_proprietary_data(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    text = (_join_lines(reviewer_output.get("defensibility_reasoning")) + " " + str(scout_output.get("solution") or "")).lower()
    if any(k in text for k in ("dominant dataset", "exclusive rights")):
        return _signal(label="dominant", confidence=0.72, reasoning="Dominant proprietary data position.")
    if any(k in text for k in ("proprietary data", "exclusive data")):
        return _signal(label="strong", confidence=0.66, reasoning="Strong proprietary data position.")
    if any(k in text for k in ("some proprietary", "limited proprietary")):
        return _signal(label="some", confidence=0.58, reasoning="Some proprietary data.")
    return _signal(label="none", confidence=0.5, reasoning="No proprietary data evidence.")


def classify_barriers(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    text = _join_lines(reviewer_output.get("defensibility_reasoning")).lower()
    if any(k in text for k in ("very hard to replicate", "regulatory moat", "capital intensive moat")):
        return _signal(label="very_hard", confidence=0.72, reasoning="Very high barriers to entry.")
    if any(k in text for k in ("hard to replicate", "significant barriers")):
        return _signal(label="hard", confidence=0.66, reasoning="Strong barriers to entry.")
    if any(k in text for k in ("some barrier", "moderate barrier")):
        return _signal(label="some", confidence=0.58, reasoning="Some barriers exist.")
    return _signal(label="easy", confidence=0.5, reasoning="Low barriers to entry.")


def classify_brand(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    text = (_join_lines(reviewer_output.get("market_reasoning")) + " " + _join_lines(reviewer_output.get("product_reasoning"))).lower()
    if any(k in text for k in ("category leader", "top brand", "household")):
        return _signal(label="leader", confidence=0.72, reasoning="Brand leadership signals.")
    if any(k in text for k in ("recognized", "known brand", "trusted brand")):
        return _signal(label="recognized", confidence=0.66, reasoning="Brand recognition present.")
    if any(k in text for k in ("emerging brand", "early brand")):
        return _signal(label="emerging", confidence=0.58, reasoning="Emerging brand signals.")
    return _signal(label="unknown", confidence=0.5, reasoning="No brand strength evidence.")


def _extract_market_signals(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    why_now = str(scout_output.get("why_now") or "")
    bundle = _scout_narrative_bundle(scout_output)
    growth_src = f"{why_now} {bundle}"
    competition_text = _join_lines(reviewer_output.get("competition_analysis")) + " " + bundle
    return {
        "tam": _signal(value=scout_output.get("est_tam"), confidence=0.6, reasoning="TAM from scout payload."),
        "growth_rate": _signal(
            value=_infer_growth_from_text(growth_src),
            confidence=0.55,
            reasoning="Growth inferred from scout narrative and why_now.",
        ),
        "urgency": _signal(label=("high" if "urgent" in why_now.lower() else "important"), confidence=0.6, reasoning="Urgency inferred from why_now wording."),
        "timing": _signal(label=("favorable" if "tailwind" in why_now.lower() else "neutral"), confidence=0.6, reasoning="Timing inferred from why_now."),
        "competition": _signal(
            label=("crowded" if "crowded" in competition_text.lower() else "moderate"),
            confidence=0.55,
            reasoning="Competition inferred from competition analysis and scout narrative.",
        ),
    }


def _fill_defaults(signals: Dict[str, Any], expected: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in expected:
        value = signals.get(key)
        if isinstance(value, dict):
            out[key] = value
        else:
            out[key] = _missing_signal(f"Missing extracted signal: {key}.")
    return out


def _sanitize_component(component: Any) -> Dict[str, Any]:
    if not isinstance(component, dict):
        return _missing_signal("Invalid component payload.")
    cleaned = copy.deepcopy(component)
    label = cleaned.get("label")
    value = cleaned.get("value")
    if _is_missing_token(label):
        cleaned.pop("label", None)
        cleaned["value"] = None
        cleaned["confidence"] = 0.2
    elif _is_missing_token(value):
        cleaned["value"] = None
        cleaned["confidence"] = 0.2
    if "confidence" not in cleaned:
        cleaned["confidence"] = 0.2 if cleaned.get("value") is None and cleaned.get("label") is None else 0.5
    return cleaned


def _attach_dimension_evidence(signals: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    dim_reasoning_field = {
        "market": "market_reasoning",
        "execution": "execution_reasoning",
        "product": "product_reasoning",
        "technical": "technical_reasoning",
        "defensibility": "defensibility_reasoning",
    }
    for dim, field in dim_reasoning_field.items():
        evidence_list = reviewer_output.get(field)
        if not isinstance(evidence_list, list):
            continue
        evidence = " ".join(str(x).strip() for x in evidence_list if str(x).strip())
        if not evidence:
            continue
        components = signals.get(dim)
        if not isinstance(components, dict):
            continue
        for comp in components.values():
            if not isinstance(comp, dict):
                continue
            existing = str(comp.get("evidence") or "").strip()
            if existing:
                continue
            comp["evidence"] = evidence
    return signals


def _component_has_substantive_evidence(comp: Any) -> bool:
    """True when LLM (or sanitizer) left at least one usable label or value."""
    if not isinstance(comp, dict):
        return False
    if not _is_missing_token(comp.get("label")):
        return True
    if not _is_missing_token(comp.get("value")):
        return True
    return False


def _provided_has_substantive_signal(structured: Dict[str, Any]) -> bool:
    """Allow merge path when any slot has label-only OR value-only evidence (most slots use one)."""
    for dim in structured.values():
        if not isinstance(dim, dict):
            continue
        for comp in dim.values():
            if _component_has_substantive_evidence(comp):
                return True
    return False


def _sanitize_provided_structured_signals(provided: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for dim, components in provided.items():
        if not isinstance(components, dict):
            continue
        aliases = COMPONENT_ALIASES.get(dim, {})
        out[dim] = {}
        for name, comp in components.items():
            canonical = aliases.get(name, name)
            out[dim][canonical] = _sanitize_component(comp)
    return out


def _merge_with_defaults(provided: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """
    Per component: keep LLM signal only when it carries substantive label/value;
    otherwise fall back to deterministic extraction so sparse LLM grids do not wipe scout-grounded defaults.
    """
    merged: Dict[str, Any] = {}
    for dim, expected_components in EXPECTED_COMPONENTS.items():
        base = defaults.get(dim, {}) if isinstance(defaults.get(dim), dict) else {}
        incoming = provided.get(dim, {}) if isinstance(provided.get(dim), dict) else {}
        combined: Dict[str, Any] = {}
        for component in expected_components:
            inc = incoming.get(component)
            base_comp = base.get(component) if isinstance(base.get(component), dict) else None
            if isinstance(inc, dict) and _component_has_substantive_evidence(inc):
                combined[component] = inc
            elif base_comp is not None:
                combined[component] = base_comp
            else:
                combined[component] = _missing_signal(f"Missing extracted signal: {dim}.{component}.")
        merged[dim] = combined
    return merged


def extract_structured_signals(scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
    """Build deterministic structured signals with safe fallbacks."""
    defaults = {
        "market": _extract_market_signals(scout_output, reviewer_output),
        "execution": _fill_defaults(
            {
                "traction": extract_traction(scout_output, reviewer_output),
                "growth_velocity": extract_growth_velocity(scout_output, reviewer_output),
                "gtm_effectiveness": classify_gtm_effectiveness(scout_output, reviewer_output),
                "team_execution": extract_team_execution(scout_output, reviewer_output),
                "operational_velocity": extract_operational_velocity(scout_output, reviewer_output),
            },
            ["traction", "growth_velocity", "gtm_effectiveness", "team_execution", "operational_velocity"],
        ),
        "product": _fill_defaults(
            {
                "value_prop": classify_value_prop(scout_output, reviewer_output),
                "pain_alignment": classify_pain_alignment(scout_output, reviewer_output),
                "differentiation": classify_differentiation(scout_output, reviewer_output),
                "ux": classify_ux(scout_output, reviewer_output),
                "retention": extract_retention(scout_output, reviewer_output),
            },
            ["value_prop", "pain_alignment", "differentiation", "ux", "retention"],
        ),
        "technical": _fill_defaults(
            {
                "complexity": classify_complexity(scout_output, reviewer_output),
                "engineering_quality": classify_engineering_quality(scout_output, reviewer_output),
                "scalability": classify_scalability(scout_output, reviewer_output),
                "data_advantage": classify_data_advantage(scout_output, reviewer_output),
                "architecture": classify_architecture(scout_output, reviewer_output),
            },
            ["complexity", "engineering_quality", "scalability", "data_advantage", "architecture"],
        ),
        "defensibility": _fill_defaults(
            {
                "network_effects": classify_network_effects(scout_output, reviewer_output),
                "switching_costs": classify_switching_costs(scout_output, reviewer_output),
                "proprietary_data": classify_proprietary_data(scout_output, reviewer_output),
                "barriers": classify_barriers(scout_output, reviewer_output),
                "brand": classify_brand(scout_output, reviewer_output),
            },
            ["network_effects", "switching_costs", "proprietary_data", "barriers", "brand"],
        ),
    }

    provided = reviewer_output.get("structured_signals")
    if isinstance(provided, dict) and provided:
        sanitized = _sanitize_provided_structured_signals(provided)
        if _provided_has_substantive_signal(sanitized):
            return _attach_dimension_evidence(_merge_with_defaults(sanitized, defaults), reviewer_output)

    return _attach_dimension_evidence(defaults, reviewer_output)
