"""Configuration for deterministic structured scoring."""

from __future__ import annotations

from typing import Dict


DEFAULT_SCORE = 5.0
DEBUG_SCORING = True

DIMENSION_WEIGHTS: Dict[str, Dict[str, float]] = {
    "market": {
        "tam": 0.30,
        "growth_rate": 0.20,
        "urgency": 0.15,
        "timing": 0.15,
        "competition": 0.20,
    },
    "execution": {
        "traction": 0.30,
        "growth_velocity": 0.20,
        "gtm_effectiveness": 0.20,
        "team_execution": 0.15,
        "operational_velocity": 0.15,
    },
    "product": {
        "value_prop": 0.25,
        "pain_alignment": 0.25,
        "differentiation": 0.20,
        "ux": 0.15,
        "retention": 0.15,
    },
    "technical": {
        "complexity": 0.25,
        "engineering_quality": 0.20,
        "scalability": 0.20,
        "data_advantage": 0.20,
        "architecture": 0.15,
    },
    "defensibility": {
        "network_effects": 0.25,
        "switching_costs": 0.20,
        "proprietary_data": 0.20,
        "barriers": 0.20,
        "brand": 0.15,
    },
}

OVERALL_DIMENSION_WEIGHTS: Dict[str, float] = {
    "market": 0.20,
    "execution": 0.20,
    "product": 0.20,
    "technical": 0.20,
    "defensibility": 0.20,
}

THRESHOLDS = {
    "tam_usd": {
        "xl": 10_000_000_000,
        "large": 3_000_000_000,
        "mid": 1_000_000_000,
        "small": 300_000_000,
    },
    "growth_pct": {"hyper": 40.0, "strong": 25.0, "healthy": 12.0, "slow": 5.0},
}
