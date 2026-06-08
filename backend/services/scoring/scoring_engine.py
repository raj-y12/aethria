"""Deterministic scoring orchestration."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict

from config.scoring_config import (
    DEBUG_SCORING,
    DEFAULT_SCORE,
    DIMENSION_WEIGHTS,
    OVERALL_DRIVER_WEIGHTS,
    OVERALL_SCORE_DIMENSIONS,
    QUALITATIVE_COMPONENTS,
    resolve_stage_cohort,
    resolve_tam_benchmark,
)
from services.scoring.aggregation_layer import aggregate_all_dimensions
from services.scoring.extraction_layer import extract_structured_signals
from services.scoring.policy_compiler import compile_policy_from_fund_config
from services.scoring.normalization_layer import (
    is_unrecognized,
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
        policy: Dict[str, Any] | None = None,
    ):
        self.weights = weights or DIMENSION_WEIGHTS
        self.dimension_weights = dimension_weights or OVERALL_DRIVER_WEIGHTS
        self.policy = policy or compile_policy_from_fund_config({})
        self.debug = os.getenv("DEBUG_SCORING", str(DEBUG_SCORING)).lower() in ("1", "true", "yes")

    def _normalize_market(
        self, signals: Dict[str, Dict[str, Any]], tam_thresholds: Dict[str, Any] | None = None
    ) -> Dict[str, Dict[str, Any]]:
        return {
            "tam": self._normalized_signal(
                signals.get("tam", {}), lambda v: normalize_tam(v, tam_thresholds)
            ),
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

    _HIGH_LABELS = frozenset({
        "high", "very_high", "very high", "strong", "rapid", "fast", "hyper",
        "explosive", "excellent", "exceptional", "critical", "elite",
        "extreme", "dominant", "world_class", "world class", "top",
        "significant", "substantial", "robust", "mature", "complex",
        "deeptech", "scaling", "strong_scale",
    })

    _LOW_LABELS = frozenset({
        "low", "weak", "none", "minimal", "slow", "flat", "poor",
        "unknown", "clunky", "simple", "easy", "vague", "unclear",
    })

    @staticmethod
    def _check_label_score_contradiction(
        label: Any, score: float, confidence: float
    ) -> tuple[float, float, str]:
        """Detect when a label's semantic meaning contradicts the numeric score.

        Returns (adjusted_score, adjusted_confidence, reasoning_suffix).
        """
        if not isinstance(label, str):
            return score, confidence, ""
        key = label.strip().lower()
        if not key:
            return score, confidence, ""

        if key in DeterministicScoringEngine._HIGH_LABELS and score <= DEFAULT_SCORE + 0.5:
            return score, min(confidence, 0.35), (
                f"Label '{label}' suggests strong performance but evidence is insufficient "
                f"to support a score above {score:.1f}. Verification required."
            )
        if key in DeterministicScoringEngine._LOW_LABELS and score >= 7.0:
            return score, min(confidence, 0.35), (
                f"Label '{label}' suggests weak performance but score reads {score:.1f}. "
                f"Evidence should be reviewed for accuracy."
            )
        return score, confidence, ""

    @classmethod
    def _neutral_component(cls, signal: Dict[str, Any], reasoning: str = "") -> Dict[str, Any]:
        return {
            "score": float(DEFAULT_SCORE),
            "confidence": 0.2,
            "reasoning": reasoning or signal.get("reasoning", "Evidence not available. Diligence required to establish baseline."),
            "value": None,
        }

    @classmethod
    def _unrecognized_component(cls, signal: Dict[str, Any], value: Any) -> Dict[str, Any]:
        """A label outside the recognized vocabulary is treated as no-evidence: a
        placeholder score is kept (no NaN leaks to consumers) but value/label are
        cleared so aggregation excludes it (audit C2 / off-vocabulary)."""
        return {
            "score": float(DEFAULT_SCORE),
            "confidence": 0.2,
            "reasoning": f"Label '{value}' is outside the recognized vocabulary; treated as no evidence.",
            "value": None,
            "unrecognized_label": True,
        }

    @staticmethod
    def _normalized_signal(signal: Dict[str, Any], normalizer) -> Dict[str, Any]:
        value = signal.get("label") if signal.get("label") is not None else signal.get("value")
        if DeterministicScoringEngine._is_missing_marker(value):
            return DeterministicScoringEngine._neutral_component(signal)
        confidence = signal.get("confidence", 0.5)
        score = normalizer(value)
        if is_unrecognized(score):
            return DeterministicScoringEngine._unrecognized_component(signal, value)
        score, confidence, reasoning_suffix = DeterministicScoringEngine._check_label_score_contradiction(
            value, score, confidence
        )
        base_reasoning = signal.get("reasoning", "")
        if reasoning_suffix:
            base_reasoning = f"{base_reasoning} {reasoning_suffix}".strip() if base_reasoning else reasoning_suffix
        normalized = {
            "score": float(score),
            "confidence": confidence,
            "reasoning": base_reasoning,
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
        if is_unrecognized(score):
            return DeterministicScoringEngine._unrecognized_component(signal, value)
        score, confidence, reasoning_suffix = DeterministicScoringEngine._check_label_score_contradiction(
            value, score, confidence
        )
        base_reasoning = signal.get("reasoning", "")
        if reasoning_suffix:
            base_reasoning = f"{base_reasoning} {reasoning_suffix}".strip() if base_reasoning else reasoning_suffix
        normalized = {
            "score": float(score),
            "confidence": confidence,
            "reasoning": base_reasoning,
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
        # Only the core driver dimensions contribute to the overall; defensibility is
        # a separate risk/moat modifier (OVERALL_SCORE_DIMENSIONS). This makes the
        # engine's overall identical to utils.scoring.compute_overall_score, which the
        # partner decision already uses (resolves A3/A4). Per-dimension fund weights
        # among the four still apply.
        weighted_sum = 0.0
        weight_total = 0.0
        for dim in OVERALL_SCORE_DIMENSIONS:
            details = aggregated.get(dim)
            if details is None:
                continue
            dim_score = details.get("score")
            # Unscored dimensions (no evidence) are excluded from the overall so a
            # no-data dimension never drags the headline toward a neutral placeholder.
            if dim_score is None or details.get("unscored"):
                continue
            weight = float(self.dimension_weights.get(dim, 0.0))
            weighted_sum += float(dim_score) * weight
            weight_total += weight
        if weight_total <= 0:
            return None
        return round(weighted_sum / weight_total, 2)

    def _compute_overall_dispersion(self, aggregated: Dict[str, Dict[str, Any]]) -> Dict[str, Any] | None:
        """Spread of the evidenced driver scores (audit: a blended 7 from flat 7s and one
        from [9,9,3,9] are very different bets). Returns the standard deviation plus the
        min/max range across the *evidenced* core drivers, so the memo can flag a lopsided
        profile the headline average hides. None when fewer than two drivers are scored
        (spread is undefined for a single point)."""
        scores = [
            float(details["score"])
            for dim in OVERALL_SCORE_DIMENSIONS
            if (details := aggregated.get(dim)) is not None
            and details.get("score") is not None
            and not details.get("unscored")
        ]
        if len(scores) < 2:
            return None
        mean = sum(scores) / len(scores)
        std = (sum((s - mean) ** 2 for s in scores) / len(scores)) ** 0.5
        return {
            "std": round(std, 2),
            "min": round(min(scores), 2),
            "max": round(max(scores), 2),
            "range": round(max(scores) - min(scores), 2),
        }

    def _compute_overall_confidence(self, aggregated: Dict[str, Dict[str, Any]]) -> float:
        weighted_sum = 0.0
        weight_total = 0.0
        for dim in OVERALL_SCORE_DIMENSIONS:
            details = aggregated.get(dim)
            if details is None:
                continue
            weight = float(self.dimension_weights.get(dim, 0.0))
            weighted_sum += float(details.get("confidence", 0.0)) * weight
            weight_total += weight
        if weight_total <= 0:
            return 0.0
        return round(weighted_sum / weight_total, 4)

    @staticmethod
    def _component_has_evidence(component: Dict[str, Any]) -> bool:
        value = component.get("value")
        label = component.get("label")
        if value is None and label is None:
            return False
        if isinstance(value, str) and DeterministicScoringEngine._is_missing_marker(value):
            return False
        if isinstance(label, str) and DeterministicScoringEngine._is_missing_marker(label):
            return False
        if value in ("", [], {}):
            return label not in (None, "")
        return True

    def _aggregate_policy_criteria(self, dimension: str, details: Dict[str, Any]) -> Dict[str, Any]:
        dim_policy = ((self.policy.get("dimensions") or {}).get(dimension) or {})
        criteria = dim_policy.get("criteria") if isinstance(dim_policy.get("criteria"), list) else []
        components = details.get("components") if isinstance(details.get("components"), dict) else {}
        if not criteria or not components:
            return details

        out_criteria: Dict[str, Dict[str, Any]] = {}
        for criterion in criteria:
            if not isinstance(criterion, dict):
                continue
            source_components = [
                str(name)
                for name in (criterion.get("source_components") or [])
                if str(name) in components
            ]
            if not source_components:
                source_components = list(components.keys())
            weighted_sum = 0.0
            weight_total = 0.0
            confidences = []
            present = 0
            for name in source_components:
                component = components.get(name) or {}
                try:
                    confidences.append(max(0.0, min(1.0, float(component.get("confidence", 0.0)))))
                except (TypeError, ValueError):
                    confidences.append(0.0)
                # Only components with concrete evidence contribute to the criterion score.
                # A missing component must NOT be folded in at its neutral 5.0 placeholder —
                # that reintroduces the very leak aggregate_dimension excludes (audit C2 /
                # Layer 3). Weights are renormalized over the evidenced components.
                if self._component_has_evidence(component):
                    present += 1
                    component_weight = float(self.weights.get(dimension, {}).get(name, 1.0))
                    weighted_sum += float(component.get("score", DEFAULT_SCORE)) * component_weight
                    weight_total += component_weight
            score = weighted_sum / weight_total if weight_total > 0 else DEFAULT_SCORE
            completeness = present / len(source_components) if source_components else 0.0
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            evidence_status = "complete" if completeness >= 1.0 else "partial" if completeness > 0 else "missing"
            criterion_id = str(criterion.get("id") or criterion.get("name") or f"{dimension}_criterion")

            from config.scoring_config import DIMENSION_SCORE_BANDS, get_confidence_level, MISSING_EVIDENCE_ITEMS

            rounded_score = max(1, min(10, round(score)))
            band_text = DIMENSION_SCORE_BANDS.get(dimension, {}).get(rounded_score, "")
            conf_level = get_confidence_level(avg_confidence * completeness)

            strong_signals = []
            weak_signals = []
            missing_signal_names = []
            for name in source_components:
                component = components.get(name) or {}
                comp_reasoning = str(component.get("reasoning") or "").strip()
                comp_score = float(component.get("score", DEFAULT_SCORE))
                if not self._component_has_evidence(component):
                    missing_signal_names.append(name.replace("_", " "))
                elif comp_reasoning and comp_score >= 7.0:
                    strong_signals.append(comp_reasoning)
                elif comp_reasoning and comp_score < 5.0:
                    weak_signals.append(comp_reasoning)

            reason_parts: list[str] = []
            if band_text:
                reason_parts.append(band_text)
            if strong_signals:
                reason_parts.append(f"Evidence: {' '.join(strong_signals[:2])}")
            if weak_signals:
                reason_parts.append(f"Concerns: {' '.join(weak_signals[:2])}")
            if missing_signal_names:
                dim_missing = MISSING_EVIDENCE_ITEMS.get(dimension, [])
                missing_items = dim_missing[:len(missing_signal_names)] if dim_missing else missing_signal_names
                reason_parts.append(f"Missing: {', '.join(missing_items[:3])}")
            if conf_level != "high":
                reason_parts.append(f"Confidence is {conf_level}. Additional diligence could shift this assessment.")
            reason = " ".join(reason_parts) if reason_parts else band_text or criterion.get("description") or ""

            out_criteria[criterion_id] = {
                "score": round(max(0.0, min(10.0, score)), 2),
                "confidence": round(avg_confidence * completeness, 4),
                "weight": float(criterion.get("weight", 100.0)),
                "evidence_status": evidence_status,
                "missing_data_applied": evidence_status != "complete",
                "reasoning": reason,
                "source_components": source_components,
                "name": criterion.get("name") or criterion_id,
                "description": criterion.get("description") or "",
            }

        if not out_criteria:
            return details
        criterion_weighted_sum = 0.0
        criterion_weight_total = 0.0
        criterion_conf_weighted_sum = 0.0
        for criterion in out_criteria.values():
            # A criterion with no evidenced components carries only a placeholder score;
            # excluding it keeps the dimension score evidence-only and consistent with
            # aggregate_dimension (a no-evidence criterion never drags the dimension toward 5.0).
            if criterion.get("evidence_status") == "missing":
                continue
            weight = float(criterion.get("weight", 0.0))
            criterion_weighted_sum += float(criterion.get("score", DEFAULT_SCORE)) * weight
            criterion_conf_weighted_sum += float(criterion.get("confidence", 0.0)) * weight
            criterion_weight_total += weight
        updated = dict(details)
        if criterion_weight_total > 0:
            updated["score"] = round(
                max(0.0, min(10.0, criterion_weighted_sum / criterion_weight_total)),
                2,
            )
            updated["confidence"] = round(criterion_conf_weighted_sum / criterion_weight_total, 4)
        updated["criteria"] = out_criteria
        return updated

    def score(self, scout_output: Dict[str, Any], reviewer_output: Dict[str, Any]) -> Dict[str, Any]:
        extracted = extract_structured_signals(scout_output, reviewer_output)
        # Sector-relative TAM benchmark (P6.3) and stage cohort (P6.1). Scores stay on the
        # absolute 1–10 scale; only the TAM band thresholds shift by sector, and the
        # cohort is surfaced so maturity-dependent criteria read in context.
        tam_benchmark = resolve_tam_benchmark(scout_output.get("sector"))
        stage_cohort = resolve_stage_cohort(scout_output.get("funding_stage"))
        normalized = {
            "market": self._normalize_market(extracted.get("market", {}), tam_benchmark["thresholds"]),
            "execution": self._normalize_execution(extracted.get("execution", {})),
            "product": self._normalize_product(extracted.get("product", {})),
            "technical": self._normalize_technical(extracted.get("technical", {})),
            "defensibility": self._normalize_defensibility(extracted.get("defensibility", {})),
        }
        aggregated = aggregate_all_dimensions(normalized, self.weights)
        aggregated = {
            dim: self._aggregate_policy_criteria(dim, details)
            for dim, details in aggregated.items()
        }
        output = {
            "market": aggregated.get("market", {"score": DEFAULT_SCORE, "confidence": 0.0, "components": {}}),
            "product": aggregated.get("product", {"score": DEFAULT_SCORE, "confidence": 0.0, "components": {}}),
            "technical": aggregated.get("technical", {"score": DEFAULT_SCORE, "confidence": 0.0, "components": {}}),
            "execution": aggregated.get("execution", {"score": DEFAULT_SCORE, "confidence": 0.0, "components": {}}),
            "defensibility": aggregated.get("defensibility", {"score": DEFAULT_SCORE, "confidence": 0.0, "components": {}}),
            "overall_score": self._compute_overall_score(aggregated),
            "overall_confidence": self._compute_overall_confidence(aggregated),
            "overall_dispersion": self._compute_overall_dispersion(aggregated),
            "raw_signals": extracted,
            "policy_version_id": self.policy.get("policy_version_id"),
            "policy_hash": self.policy.get("policy_hash"),
            # Comparability context for the memo (P6.1 / P6.3): the cohort the maturity
            # criteria should be read against, and the sector TAM benchmark the Market
            # score was graded on.
            "stage_cohort": stage_cohort["cohort"],
            "stage_cohort_label": stage_cohort["label"],
            "sector_tam_benchmark": tam_benchmark["label"],
        }
        # Stamp the qualitative flag (P3.4) so the memo can distinguish a qualitative 8
        # (judgment, no objective anchor) from an evidence-backed 8. Classification is the
        # SSOT in config.scoring_config; value/fact-derived components are left unflagged.
        for comp_key in QUALITATIVE_COMPONENTS:
            dim, _, comp_name = comp_key.partition(".")
            dim_details = output.get(dim)
            if not isinstance(dim_details, dict):
                continue
            comps = dim_details.get("components")
            if isinstance(comps, dict) and isinstance(comps.get(comp_name), dict):
                comps[comp_name]["qualitative"] = True

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
        return output
