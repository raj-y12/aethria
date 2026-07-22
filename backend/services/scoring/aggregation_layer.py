"""Weighted aggregation and confidence computation."""

from __future__ import annotations

from typing import Any, Dict

from config.scoring_config import DEFAULT_SCORE


def _to_float(value: Any, default: float = DEFAULT_SCORE) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


_MISSING_RE = __import__("re").compile(r"^\s*\[?\s*missing(?::[^\]]*)?\]?\s*$", __import__("re").IGNORECASE)


def _has_concrete_evidence(comp: Dict[str, Any]) -> bool:
    """True only for a grounded component with a concrete value or label."""
    evidence = str(comp.get("evidence") or "").strip()
    reasoning = str(comp.get("reasoning") or "").strip()
    grounded = bool(evidence) or bool(comp.get("rule"))
    if not grounded and reasoning.lower() in {"", "speculative", "guess", "unknown"}:
        return False
    for key in ("value", "label"):
        raw = comp.get(key)
        if isinstance(raw, str) and raw.strip() and not _MISSING_RE.match(raw.strip()):
            return grounded
        if raw not in (None, "", [], {}):
            return grounded
    return False


def compute_confidence(components: Dict[str, Dict[str, Any]]) -> float:
    if not components:
        return 0.0
    confidences = []
    present = 0
    total = len(components)
    for comp in components.values():
        if _has_concrete_evidence(comp):
            present += 1
            c = max(0.0, min(1.0, _to_float(comp.get("confidence"), 0.0)))
            confidences.append(c)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    completeness = present / total if total else 0.0
    return round(avg_conf * completeness, 4)


def aggregate_dimension(
    dimension: str,
    normalized_components: Dict[str, Dict[str, Any]],
    weight_config: Dict[str, Dict[str, float]],
) -> Dict[str, Any]:
    weights = weight_config.get(dimension, {})
    if not normalized_components:
        return {
            "score": None,
            "confidence": 0.0,
            "components": {},
            "unscored": True,
            "missing_reasons": ["no_grounded_components"],
        }
    # Only components with concrete evidence contribute to the score. Missing /
    # fabricated-placeholder components are EXCLUDED and the weights renormalized over
    # the evidenced ones — a no-evidence component must never be scored as a neutral
    # 5.0 and dragged into the average. If nothing is evidenced, the dimension is
    # unscored.
    weighted_sum = 0.0
    weight_total = 0.0
    for name, component in normalized_components.items():
        if not _has_concrete_evidence(component):
            continue
        weight = float(weights.get(name, 0.0))
        weighted_sum += _to_float(component.get("score")) * weight
        weight_total += weight
    if weight_total <= 0:
        return {
            "score": None,
            "confidence": compute_confidence(normalized_components),
            "components": normalized_components,
            "unscored": True,
            "missing_reasons": ["no_grounded_components"],
        }
    score = weighted_sum / weight_total
    return {
        "score": round(max(0.0, min(10.0, score)), 2),
        "confidence": compute_confidence(normalized_components),
        "components": normalized_components,
        "unscored": False,
    }


def aggregate_all_dimensions(
    normalized: Dict[str, Dict[str, Dict[str, Any]]],
    weight_config: Dict[str, Dict[str, float]],
) -> Dict[str, Any]:
    return {
        dim: aggregate_dimension(dim, components, weight_config)
        for dim, components in normalized.items()
    }
