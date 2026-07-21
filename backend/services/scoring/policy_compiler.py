"""Compile tenant fund configuration into deterministic scoring policy."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from config.scoring_config import (
    DEFAULT_SCORE,
    DIMENSION_WEIGHTS,
    EVIDENCE_DISCOUNT,
    EVIDENCE_GATE,
    OVERALL_DIMENSION_WEIGHTS,
    OVERALL_SCORE_DIMENSIONS,
    SECTOR_TAM_THRESHOLDS,
    THRESHOLDS,
)
from services.scoring.extraction_layer import EXPECTED_COMPONENTS


PRODUCTION_DIMENSIONS = ("market", "product", "technical", "execution", "defensibility")
REQUIRED_ANCHORS = ("score3", "score5", "score7", "score9")
UI_ONLY_DIMENSIONS = {"traction", "timing", "fundFit", "fund_fit"}
DEFAULT_DECISION_THRESHOLDS = {
    "autoPass": 39.0,
    "monitor": 59.0,
    "escalation": 75.0,
    "partnerReview": 60.0,
}
DEFAULT_SCORE_BANDS = (
    {"id": "pass", "min": 0.0, "max": 59.0, "label": "Pass"},
    {"id": "monitor", "min": 60.0, "max": 79.0, "label": "Monitor"},
    {"id": "invest", "min": 80.0, "max": 100.0, "label": "Invest"},
)
SCORING_RUNTIME_SEMANTIC_VERSION = "1.1.0"


class PolicyValidationError(ValueError):
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class CompiledCriterion(BaseModel):
    id: str
    dimension: Literal["market", "product", "technical", "execution", "defensibility"]
    name: str
    description: str = ""
    weight: float = Field(gt=0)
    positive_signals: str = ""
    negative_signals: str = ""
    missing_data_behavior: str = ""
    score_anchors: Dict[str, str]
    source_components: List[str]


class CompiledDimensionPolicy(BaseModel):
    id: Literal["market", "product", "technical", "execution", "defensibility"]
    weight: float = Field(gt=0)
    criteria: List[CompiledCriterion]


class CompiledDecisionThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    autoPass: float = Field(ge=0, le=100)
    monitor: float = Field(ge=0, le=100)
    escalation: float = Field(ge=0, le=100)
    partnerReview: float = Field(ge=0, le=100)


class CompiledScoreBand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    min: float = Field(ge=0, le=100)
    max: float = Field(ge=0, le=100)
    label: str = Field(min_length=1)


class CompiledDecisionInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thresholds: CompiledDecisionThresholds
    scoreBands: List[CompiledScoreBand] = Field(min_length=1)


class RuntimeEvidenceDiscount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    floor_conf: float = Field(ge=0, le=1)
    full_conf: float = Field(ge=0, le=1)


class RuntimeEvidenceGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_completeness: float = Field(ge=0, le=1)
    min_avg_conf: float = Field(ge=0, le=1)
    cap: float = Field(ge=0, le=10)


class RuntimeCalibration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["enforced", "shadow"]
    discount: RuntimeEvidenceDiscount
    evidence_gate: RuntimeEvidenceGate


class RuntimeEvidenceGrounding(BaseModel):
    """Immutable preprocessing rules applied before deterministic scoring."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    clear_ungrounded_labels: bool
    ungrounded_confidence_cap: float = Field(ge=0, le=1)


class RuntimeOverall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimensions: List[str] = Field(min_length=1)
    weights: Dict[str, float]


class RuntimeTamThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    xl: float = Field(gt=0)
    large: float = Field(gt=0)
    mid: float = Field(gt=0)
    small: float = Field(gt=0)


class RuntimeGrowthThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hyper: float
    strong: float
    healthy: float
    slow: float


class RuntimeSectorTamBenchmark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keywords: List[str] = Field(min_length=1)
    label: str = Field(min_length=1)
    thresholds: RuntimeTamThresholds


class RuntimeNormalization(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_score: float = Field(ge=0, le=10)
    default_tam_benchmark_label: str = Field(min_length=1)
    tam_thresholds: RuntimeTamThresholds
    growth_thresholds: RuntimeGrowthThresholds
    sector_tam_benchmarks: Dict[str, RuntimeSectorTamBenchmark]


class ScoringRuntimeContract(BaseModel):
    """Complete immutable configuration consumed by deterministic scoring v1."""

    model_config = ConfigDict(extra="forbid")

    semantic_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    calibration: RuntimeCalibration
    evidence_grounding: RuntimeEvidenceGrounding
    component_weights: Dict[str, Dict[str, float]]
    overall: RuntimeOverall
    normalization: RuntimeNormalization


class CompiledScoringPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version_id: str
    policy_hash: str
    generated_at: str
    dimensions: Dict[str, CompiledDimensionPolicy]
    decision_inputs: CompiledDecisionInputs
    scoring_runtime: ScoringRuntimeContract
    scoring_runtime_hash: str
    warnings: List[str] = Field(default_factory=list)
    id: Optional[str] = None
    published_at: Optional[str] = None


def _stable_hash(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _slug(value: Any, fallback: str) -> str:
    text = str(value or "").strip().lower()
    out = []
    previous_sep = False
    for ch in text:
        if ch.isalnum():
            out.append(ch)
            previous_sep = False
        elif not previous_sep:
            out.append("_")
            previous_sep = True
    slug = "".join(out).strip("_")
    return slug or fallback


def _dimension_weights(fund_config: Dict[str, Any]) -> Dict[str, float]:
    weights = {dim: float(OVERALL_DIMENSION_WEIGHTS.get(dim, 0.2) * 100.0) for dim in PRODUCTION_DIMENSIONS}
    for entry in fund_config.get("scoringWeights") or []:
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        if key not in PRODUCTION_DIMENSIONS:
            continue
        try:
            weight = float(entry.get("weight"))
        except (TypeError, ValueError):
            continue
        if weight > 0:
            weights[str(key)] = weight
    return weights


def _default_scoring_runtime(
    dimension_weights: Dict[str, float],
) -> Dict[str, Any]:
    """Return a stable default independent of process environment.

    Environment flags may still control legacy, unpublished scorer instances. A
    published decision bundle always records an explicit mode and never inherits a
    process-local toggle.
    """

    return {
        "semantic_version": SCORING_RUNTIME_SEMANTIC_VERSION,
        "calibration": {
            "mode": "enforced",
            "discount": deepcopy(EVIDENCE_DISCOUNT),
            "evidence_gate": deepcopy(EVIDENCE_GATE),
        },
        "evidence_grounding": {
            "enabled": True,
            "clear_ungrounded_labels": True,
            "ungrounded_confidence_cap": 0.2,
        },
        "component_weights": deepcopy(DIMENSION_WEIGHTS),
        "overall": {
            "dimensions": list(OVERALL_SCORE_DIMENSIONS),
            "weights": {
                dimension: float(dimension_weights[dimension])
                for dimension in OVERALL_SCORE_DIMENSIONS
            },
        },
        "normalization": {
            "default_score": float(DEFAULT_SCORE),
            "default_tam_benchmark_label": "General (default benchmark)",
            "tam_thresholds": deepcopy(THRESHOLDS["tam_usd"]),
            "growth_thresholds": deepcopy(THRESHOLDS["growth_pct"]),
            "sector_tam_benchmarks": deepcopy(SECTOR_TAM_THRESHOLDS),
        },
    }


def _validate_scoring_runtime_shape(runtime: Dict[str, Any]) -> None:
    if runtime["semantic_version"] != SCORING_RUNTIME_SEMANTIC_VERSION:
        raise ValueError(
            "unsupported scoring runtime semantic_version "
            f"{runtime['semantic_version']!r}"
        )

    discount = runtime["calibration"]["discount"]
    if discount["full_conf"] <= discount["floor_conf"]:
        raise ValueError("calibration discount full_conf must exceed floor_conf")

    component_weights = runtime["component_weights"]
    if set(component_weights) != set(PRODUCTION_DIMENSIONS):
        raise ValueError("component_weights must exactly match production dimensions")
    for dimension in PRODUCTION_DIMENSIONS:
        weights = component_weights[dimension]
        expected = set(EXPECTED_COMPONENTS[dimension])
        if set(weights) != expected:
            raise ValueError(
                f"component_weights.{dimension} must exactly match scorer components"
            )
        if any(
            isinstance(value, bool)
            or not math.isfinite(float(value))
            or float(value) <= 0
            for value in weights.values()
        ):
            raise ValueError(
                f"component_weights.{dimension} values must be positive and finite"
            )

    overall = runtime["overall"]
    dimensions = overall["dimensions"]
    if len(set(dimensions)) != len(dimensions):
        raise ValueError("overall.dimensions must be unique")
    if any(dimension not in PRODUCTION_DIMENSIONS for dimension in dimensions):
        raise ValueError("overall.dimensions contains an unknown dimension")
    if set(overall["weights"]) != set(dimensions):
        raise ValueError("overall.weights must exactly match overall.dimensions")
    if any(
        isinstance(value, bool)
        or not math.isfinite(float(value))
        or float(value) <= 0
        for value in overall["weights"].values()
    ):
        raise ValueError("overall.weights must be positive and finite")

    normalization = runtime["normalization"]
    if normalization["default_score"] != float(DEFAULT_SCORE):
        raise ValueError(
            "normalization.default_score is fixed by scoring runtime 1.1.0"
        )
    tam = normalization["tam_thresholds"]
    if not tam["xl"] > tam["large"] > tam["mid"] > tam["small"]:
        raise ValueError("normalization.tam_thresholds must be strictly descending")
    growth = normalization["growth_thresholds"]
    if not (
        growth["hyper"]
        > growth["strong"]
        > growth["healthy"]
        > growth["slow"]
    ):
        raise ValueError(
            "normalization.growth_thresholds must be strictly descending"
        )
    for name, benchmark in normalization["sector_tam_benchmarks"].items():
        if not str(name).strip():
            raise ValueError("sector TAM benchmark names must be non-empty")
        thresholds = benchmark["thresholds"]
        if not (
            thresholds["xl"]
            > thresholds["large"]
            > thresholds["mid"]
            > thresholds["small"]
        ):
            raise ValueError(
                f"sector TAM benchmark {name!r} thresholds must be strictly descending"
            )


def normalize_scoring_runtime_contract(runtime: Any) -> Dict[str, Any]:
    """Strictly normalize a complete runtime contract; no partial merging."""

    validated = ScoringRuntimeContract.model_validate(runtime).model_dump()
    _validate_scoring_runtime_shape(validated)
    return validated


def scoring_runtime_hash(runtime: Dict[str, Any]) -> str:
    return _stable_hash(normalize_scoring_runtime_contract(runtime))


def _normalize_decision_inputs(
    fund_config: Dict[str, Any], errors: List[str]
) -> Dict[str, Any]:
    raw_thresholds = (
        fund_config.get("thresholds")
        if isinstance(fund_config.get("thresholds"), dict)
        else {}
    )
    thresholds: Dict[str, float] = {}
    for key, default in DEFAULT_DECISION_THRESHOLDS.items():
        raw = raw_thresholds.get(key, default)
        if isinstance(raw, bool):
            errors.append(f"thresholds.{key} must be numeric")
            raw = default
        try:
            value = float(raw)
        except (TypeError, ValueError):
            errors.append(f"thresholds.{key} must be numeric")
            value = default
        if not math.isfinite(value) or not 0 <= value <= 100:
            errors.append(f"thresholds.{key} must be finite and between 0 and 100")
            value = default
        thresholds[key] = value
    if thresholds["partnerReview"] > thresholds["escalation"]:
        errors.append("thresholds.partnerReview must not exceed thresholds.escalation")

    raw_bands = fund_config.get("scoreBands")
    source_bands = raw_bands if isinstance(raw_bands, list) and raw_bands else DEFAULT_SCORE_BANDS
    bands: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(source_bands):
        if not isinstance(raw, dict):
            errors.append(f"scoreBands[{index}] must be an object")
            continue
        band_id = str(raw.get("id") or "").strip()
        label = str(raw.get("label") or "").strip()
        try:
            minimum = float(raw.get("min"))
            maximum = float(raw.get("max"))
        except (TypeError, ValueError):
            errors.append(f"scoreBands[{index}] min/max must be numeric")
            continue
        if not band_id or not label:
            errors.append(f"scoreBands[{index}] id and label are required")
            continue
        if band_id in seen_ids:
            errors.append(f"scoreBands[{index}].id must be unique")
        seen_ids.add(band_id)
        if (
            not math.isfinite(minimum)
            or not math.isfinite(maximum)
            or not 0 <= minimum <= maximum <= 100
        ):
            errors.append(
                f"scoreBands[{index}] bounds must be finite and ordered within 0..100"
            )
            continue
        bands.append(
            {"id": band_id, "min": minimum, "max": maximum, "label": label}
        )
    bands.sort(key=lambda band: (band["min"], band["max"], band["id"]))
    if not bands:
        errors.append("scoreBands must contain at least one valid band")
        bands = [dict(band) for band in DEFAULT_SCORE_BANDS]
    return CompiledDecisionInputs.model_validate(
        {"thresholds": thresholds, "scoreBands": bands}
    ).model_dump()


def policy_hash_for_bundle(
    dimensions: Dict[str, Any],
    decision_inputs: Dict[str, Any],
    scoring_runtime: Dict[str, Any],
) -> str:
    """Hash every normalized tenant input consumed by governed decisions."""
    return _stable_hash(
        {
            "dimensions": dimensions,
            "decision_inputs": decision_inputs,
            "scoring_runtime": scoring_runtime,
        }
    )


def validate_compiled_policy_bundle(policy: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and hash-check a complete persisted policy record."""
    try:
        validated = CompiledScoringPolicy.model_validate(policy).model_dump(
            exclude_none=True
        )
    except Exception as exc:
        raise PolicyValidationError(
            ["Published policy is missing its complete decision-input bundle"]
        ) from exc
    expected = policy_hash_for_bundle(
        validated["dimensions"],
        validated["decision_inputs"],
        validated["scoring_runtime"],
    )
    if expected != validated["policy_hash"]:
        raise PolicyValidationError(
            ["Published policy hash does not match its complete decision-input bundle"]
        )
    expected_runtime_hash = scoring_runtime_hash(validated["scoring_runtime"])
    if expected_runtime_hash != validated["scoring_runtime_hash"]:
        raise PolicyValidationError(
            ["Published policy scoring runtime hash does not match its runtime bundle"]
        )
    return validated


def _default_criterion(dimension: str) -> Dict[str, Any]:
    from config.scoring_config import CANONICAL_DIMENSIONS, DIMENSION_SCORE_BANDS

    canonical = CANONICAL_DIMENSIONS.get(dimension, {})
    label = canonical.get("label", dimension.replace("_", " ").title())
    description = canonical.get("description", f"Default {label.lower()} scoring policy from deterministic backend signals.")
    bands = DIMENSION_SCORE_BANDS.get(dimension, {})
    return {
        "id": f"{dimension}_default",
        "dimension": dimension,
        "name": f"{label} conviction",
        "description": description,
        "weight": 100.0,
        "positive_signals": "Evidence-backed signal that compounds with the fund mandate.",
        "negative_signals": "Unresolved weakness, shallow evidence, or signal that contradicts the mandate.",
        "missing_data_behavior": "Treat as diligence debt and reduce confidence until evidence is supplied.",
        "score_anchors": {
            "score3": bands.get(3, "Below threshold. Significant gaps in evidence or capability."),
            "score5": bands.get(5, "Promising but incomplete validation. Further diligence needed."),
            "score7": bands.get(7, "Strong opportunity with evidence-backed signals."),
            "score9": bands.get(9, "Exceptional opportunity with multiple reinforcing signals."),
        },
        "source_components": list(EXPECTED_COMPONENTS[dimension]),
    }


def _normalize_criterion(raw: Dict[str, Any], index: int, errors: List[str]) -> Dict[str, Any] | None:
    raw_dimension = str(raw.get("dimension") or "").strip()
    if raw_dimension in UI_ONLY_DIMENSIONS:
        errors.append(
            f"rubric[{index}].dimension '{raw_dimension}' is UI-only; map it to one of {', '.join(PRODUCTION_DIMENSIONS)}"
        )
        return None
    if raw_dimension not in PRODUCTION_DIMENSIONS:
        errors.append(f"rubric[{index}].dimension must be one of {', '.join(PRODUCTION_DIMENSIONS)}")
        return None

    try:
        weight = float(raw.get("weight", 100))
    except (TypeError, ValueError):
        weight = 0
    if weight <= 0:
        errors.append(f"rubric[{index}].weight must be positive")

    examples = raw.get("examples") if isinstance(raw.get("examples"), dict) else {}
    missing_anchors = [key for key in REQUIRED_ANCHORS if not str(examples.get(key) or "").strip()]
    if missing_anchors:
        errors.append(f"rubric[{index}] missing score anchor(s): {', '.join(missing_anchors)}")

    cid = _slug(raw.get("id") or raw.get("name"), f"{raw_dimension}_criterion_{index + 1}")
    return {
        "id": cid,
        "dimension": raw_dimension,
        "name": str(raw.get("name") or cid.replace("_", " ").title()).strip(),
        "description": str(raw.get("description") or "").strip(),
        "weight": weight if weight > 0 else 100.0,
        "positive_signals": str(raw.get("positiveSignals") or raw.get("positive_signals") or "").strip(),
        "negative_signals": str(raw.get("negativeSignals") or raw.get("negative_signals") or "").strip(),
        "missing_data_behavior": str(raw.get("missingDataBehavior") or raw.get("missing_data_behavior") or "").strip(),
        "score_anchors": {key: str(examples.get(key) or "").strip() for key in REQUIRED_ANCHORS},
        "source_components": list(EXPECTED_COMPONENTS[raw_dimension]),
    }


def compile_policy_from_fund_config(
    fund_config: Dict[str, Any] | None,
    *,
    require_publish_ready: bool = False,
) -> Dict[str, Any]:
    """Return normalized policy dict. Raises PolicyValidationError when publish validation fails."""
    fc = fund_config if isinstance(fund_config, dict) else {}
    errors: List[str] = []
    warnings: List[str] = []
    raw_rubric = fc.get("rubric") if isinstance(fc.get("rubric"), list) else []
    dim_weights = _dimension_weights(fc)
    criteria_by_dimension: Dict[str, List[Dict[str, Any]]] = {dim: [] for dim in PRODUCTION_DIMENSIONS}

    if raw_rubric:
        for index, raw in enumerate(raw_rubric):
            if not isinstance(raw, dict):
                errors.append(f"rubric[{index}] must be an object")
                continue
            criterion = _normalize_criterion(raw, index, errors)
            if criterion is not None:
                criteria_by_dimension[criterion["dimension"]].append(criterion)
    else:
        warnings.append("No rubric draft supplied; using default backend scoring policy.")
        for dim in PRODUCTION_DIMENSIONS:
            criteria_by_dimension[dim].append(_default_criterion(dim))

    for dim in PRODUCTION_DIMENSIONS:
        if not criteria_by_dimension[dim]:
            if raw_rubric:
                warnings.append(f"No configured criteria for {dim}; using default {dim} criterion.")
            criteria_by_dimension[dim].append(_default_criterion(dim))

    canonical_dimensions: Dict[str, Any] = {}
    for dim in PRODUCTION_DIMENSIONS:
        canonical_dimensions[dim] = {
            "id": dim,
            "weight": float(dim_weights[dim]),
            "criteria": criteria_by_dimension[dim],
        }

    decision_inputs = _normalize_decision_inputs(fc, errors)
    raw_runtime = fc.get("scoringRuntime", fc.get("scoring_runtime"))
    if raw_runtime is None:
        scoring_runtime = normalize_scoring_runtime_contract(
            _default_scoring_runtime(dim_weights)
        )
    else:
        try:
            scoring_runtime = normalize_scoring_runtime_contract(raw_runtime)
        except Exception as exc:
            errors.append(f"scoringRuntime must be a complete valid contract: {exc}")
            scoring_runtime = normalize_scoring_runtime_contract(
                _default_scoring_runtime(dim_weights)
            )
    runtime_hash = scoring_runtime_hash(scoring_runtime)
    policy_hash = policy_hash_for_bundle(
        canonical_dimensions, decision_inputs, scoring_runtime
    )
    version_id = str(fc.get("activePolicyVersionId") or "").strip() or f"draft_{policy_hash}"
    payload = {
        "policy_version_id": version_id,
        "policy_hash": policy_hash,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dimensions": canonical_dimensions,
        "decision_inputs": decision_inputs,
        "scoring_runtime": scoring_runtime,
        "scoring_runtime_hash": runtime_hash,
        "warnings": warnings,
    }

    if require_publish_ready and errors:
        raise PolicyValidationError(errors)
    if errors:
        payload["warnings"] = warnings + errors

    return CompiledScoringPolicy.model_validate(payload).model_dump(exclude_none=True)
