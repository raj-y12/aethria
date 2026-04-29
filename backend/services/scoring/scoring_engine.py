"""Deterministic scoring orchestration."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict

from config.scoring_config import DEBUG_SCORING, DEFAULT_SCORE, DIMENSION_WEIGHTS, OVERALL_DIMENSION_WEIGHTS
from services.scoring.aggregation_layer import aggregate_all_dimensions
from services.scoring.extraction_layer import extract_structured_signals
from services.scoring.normalization_layer import (
    normalize_architecture,
    normalize_barriers,
    normalize_brand,
    normalize_complexity,
    normalize_competition,
    normalize_data_advantage,
    normalize_differentiation,
    normalize_engineering_quality,
    normalize_growth_velocity,
    normalize_gtm,
    normalize_network_effects,
    normalize_operational_velocity,
    normalize_pain_alignment,
    normalize_proprietary_data,
    normalize_retention,
    normalize_scalability,
    normalize_switching_costs,
    normalize_growth,
    normalize_tam,
    normalize_team_execution,
    normalize_traction,
    normalize_timing,
    normalize_urgency,
    normalize_ux,
    normalize_value_prop,
)


logger = logging.getLogger("scoring.engine")
MISSING_TOKEN_RE = re.compile(r"^\s*\[?\s*missing(?::[^\]]*)?\]?\s*$", re.IGNORECASE)


class DeterministicScoringEngine:
    def __init__(
        self,
        weights: Dict[str, Dict[str, float]] | None = None,
        dimension_weights: Dict[str, float] | None = None,
    ):
        self.weights = weights or DIMENSION_WEIGHTS
        self.dimension_weights = dimension_weights or OVERALL_DIMENSION_WEIGHTS
        self.debug = os.getenv("DEBUG_SCORING", str(DEBUG_SCORING)).lower() in ("1", "true", "yes")

    def _normalize_market(self, signals: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return {
            "tam": self._normalized_signal(signals.get("tam", {}), normalize_tam),
            "growth_rate": self._normalized_signal(signals.get("growth_rate", {}), normalize_growth),
            "urgency": self._normalized_signal(signals.get("urgency", {}), lambda v: normalize_urgency(v)),
            "timing": self._normalized_signal(signals.get("timing", {}), lambda v: normalize_timing(v)),
            "competition": self._normalized_signal(signals.get("competition", {}), lambda v: normalize_competition(v)),
        }

    def _normalize_execution(self, signals: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return {
            "traction": self._normalized_signal(signals.get("traction", {}), normalize_traction),
            "growth_velocity": self._normalized_signal_with_value_fallback(
                signals.get("growth_velocity", {}),
                normalize_growth_velocity,
            ),
            "gtm_effectiveness": self._normalized_signal(signals.get("gtm_effectiveness", {}), normalize_gtm),
            "team_execution": self._normalized_signal(signals.get("team_execution", {}), normalize_team_execution),
            "operational_velocity": self._normalized_signal(
                signals.get("operational_velocity", {}),
                normalize_operational_velocity,
            ),
        }

    def _normalize_product(self, signals: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return {
            "value_prop": self._normalized_signal(signals.get("value_prop", {}), normalize_value_prop),
            "pain_alignment": self._normalized_signal(signals.get("pain_alignment", {}), normalize_pain_alignment),
            "differentiation": self._normalized_signal(signals.get("differentiation", {}), normalize_differentiation),
            "ux": self._normalized_signal(signals.get("ux", {}), normalize_ux),
            "retention": self._normalized_signal_with_value_fallback(signals.get("retention", {}), normalize_retention),
        }

    def _normalize_technical(self, signals: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return {
            "complexity": self._normalized_signal(signals.get("complexity", {}), normalize_complexity),
            "engineering_quality": self._normalized_signal(
                signals.get("engineering_quality", {}),
                normalize_engineering_quality,
            ),
            "scalability": self._normalized_signal(signals.get("scalability", {}), normalize_scalability),
            "data_advantage": self._normalized_signal(signals.get("data_advantage", {}), normalize_data_advantage),
            "architecture": self._normalized_signal(signals.get("architecture", {}), normalize_architecture),
        }

    def _normalize_defensibility(self, signals: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return {
            "network_effects": self._normalized_signal(signals.get("network_effects", {}), normalize_network_effects),
            "switching_costs": self._normalized_signal(signals.get("switching_costs", {}), normalize_switching_costs),
            "proprietary_data": self._normalized_signal(
                signals.get("proprietary_data", {}),
                normalize_proprietary_data,
            ),
            "barriers": self._normalized_signal(signals.get("barriers", {}), normalize_barriers),
            "brand": self._normalized_signal(signals.get("brand", {}), normalize_brand),
        }

    @staticmethod
    def _is_missing_marker(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return True
            if MISSING_TOKEN_RE.match(text):
                return True
        return False

    @classmethod
    def _neutral_component(cls, signal: Dict[str, Any], reasoning: str = "") -> Dict[str, Any]:
        return {
            "score": float(DEFAULT_SCORE),
            "confidence": 0.2,
            "reasoning": reasoning or signal.get("reasoning", "Signal missing; neutral fallback applied."),
            "value": None,
        }

    @staticmethod
    def _normalized_signal(signal: Dict[str, Any], normalizer) -> Dict[str, Any]:
        value = signal.get("label") if signal.get("label") is not None else signal.get("value")
        if DeterministicScoringEngine._is_missing_marker(value):
            return DeterministicScoringEngine._neutral_component(signal)
        confidence = signal.get("confidence", 0.5)
        score = normalizer(value)
        normalized = {
            "score": float(score),
            "confidence": confidence,
            "reasoning": signal.get("reasoning", ""),
        }
        if signal.get("evidence") is not None:
            normalized["evidence"] = signal.get("evidence")
        if signal.get("rule") is not None:
            normalized["rule"] = signal.get("rule")
        if signal.get("label") is not None:
            normalized["label"] = signal.get("label")
        else:
            normalized["value"] = signal.get("value")
        return normalized

    @staticmethod
    def _normalized_signal_with_value_fallback(signal: Dict[str, Any], normalizer) -> Dict[str, Any]:
        value = signal.get("value")
        if value in (None, ""):
            value = signal.get("label")
        if DeterministicScoringEngine._is_missing_marker(value):
            return DeterministicScoringEngine._neutral_component(signal)
        confidence = signal.get("confidence", 0.5)
        score = normalizer(value)
        normalized = {
            "score": float(score),
            "confidence": confidence,
            "reasoning": signal.get("reasoning", ""),
        }
        if signal.get("evidence") is not None:
            normalized["evidence"] = signal.get("evidence")
        if signal.get("rule") is not None:
            normalized["rule"] = signal.get("rule")
        if signal.get("label") is not None:
            normalized["label"] = signal.get("label")
        if signal.get("value") is not None:
            normalized["value"] = signal.get("value")
        return normalized

    def _compute_overall_score(self, aggregated: Dict[str, Dict[str, Any]]) -> float:
        weighted_sum = 0.0
        weight_total = 0.0
        for dim, details in aggregated.items():
            weight = float(self.dimension_weights.get(dim, 0.0))
            weighted_sum += float(details.get("score", DEFAULT_SCORE)) * weight
            weight_total += weight
        if weight_total <= 0:
            return DEFAULT_SCORE
        return round(weighted_sum / weight_total, 2)

    def _compute_overall_confidence(self, aggregated: Dict[str, Dict[str, Any]]) -> float:
        weighted_sum = 0.0
        weight_total = 0.0
        for dim, details in aggregated.items():
            weight = float(self.dimension_weights.get(dim, 0.0))
            weighted_sum += float(details.get("confidence", 0.0)) * weight
            weight_total += weight
        if weight_total <= 0:
            return 0.0
        return round(weighted_sum / weight_total, 4)

    def score(self, scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
        extracted = extract_structured_signals(scout_output, reviewer_output)
        normalized = {
            "market": self._normalize_market(extracted.get("market", {})),
            "execution": self._normalize_execution(extracted.get("execution", {})),
            "product": self._normalize_product(extracted.get("product", {})),
            "technical": self._normalize_technical(extracted.get("technical", {})),
            "defensibility": self._normalize_defensibility(extracted.get("defensibility", {})),
        }
        aggregated = aggregate_all_dimensions(normalized, self.weights)
        output = {
            "market": aggregated.get("market", {"score": DEFAULT_SCORE, "confidence": 0.0, "components": {}}),
            "product": aggregated.get("product", {"score": DEFAULT_SCORE, "confidence": 0.0, "components": {}}),
            "technical": aggregated.get("technical", {"score": DEFAULT_SCORE, "confidence": 0.0, "components": {}}),
            "execution": aggregated.get("execution", {"score": DEFAULT_SCORE, "confidence": 0.0, "components": {}}),
            "defensibility": aggregated.get("defensibility", {"score": DEFAULT_SCORE, "confidence": 0.0, "components": {}}),
            "overall_score": self._compute_overall_score(aggregated),
            "overall_confidence": self._compute_overall_confidence(aggregated),
            "raw_signals": extracted,
        }
        missing_components: Dict[str, list[str]] = {}
        for dim, details in output.items():
            if not isinstance(details, dict):
                continue
            comps = details.get("components")
            if not isinstance(comps, dict):
                continue
            missing_in_dim = []
            for name, comp in comps.items():
                if not isinstance(comp, dict):
                    continue
                has_label = not self._is_missing_marker(comp.get("label"))
                has_value = not self._is_missing_marker(comp.get("value"))
                if not has_label and not has_value:
                    missing_in_dim.append(name)
            if missing_in_dim:
                missing_components[dim] = missing_in_dim
        if self.debug:
            logger.info("scoring_trace scout_input=%s", scout_output)
            logger.info("scoring_trace reviewer_input=%s", reviewer_output)
            logger.info("scoring_trace raw_extraction=%s", extracted)
            logger.info("scoring_trace normalized=%s", normalized)
            logger.info("scoring_trace aggregated=%s", output)
            logger.info("scoring_trace missing_components=%s", missing_components)
            print("SCORING_TRACE_INPUT_SCOUT", scout_output)
            print("SCORING_TRACE_INPUT_REVIEWER", reviewer_output)
            print("SCORING_TRACE_RAW", extracted)
            print("SCORING_TRACE_NORMALIZED", normalized)
            print("SCORING_TRACE_OUTPUT", output)
            print("SCORING_TRACE_MISSING_COMPONENTS", missing_components)
        return output
