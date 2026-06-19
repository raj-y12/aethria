"""
ScoutReweighter — adjusts scout run frequencies based on performance.
Backed by Supabase meta_scout_weights and meta_mutation_log (explicit user_id).
"""
import logging
import os
from typing import Dict, Any, List
from datetime import datetime
from utils.timeutil import utcnow

from supabase_doc_store import doc_get, doc_set, list_append_only

logger = logging.getLogger(__name__)

_WEIGHTS_TABLE = "meta_scout_weights"
_MUTATION_LOG_TABLE = "meta_mutation_log"

DEFAULT_WEIGHTS = {
    "MarketDrivenScout": 0.25,
    "BuilderTechnicalScout": 0.25,
    "PainPointScout": 0.25,
    "ContrarianScout": 0.25,
}

WEIGHT_FLOOR = 0.05
DAMPENING_FACTOR = 0.7
MIN_DELTA_THRESHOLD = 0.03


def load_weights(user_id: str) -> Dict[str, float]:
    """Load current scout weights from Supabase for this tenant."""
    data = doc_get(_WEIGHTS_TABLE, user_id=user_id)
    if isinstance(data, dict) and data:
        return data
    return dict(DEFAULT_WEIGHTS)


class ScoutReweighter:
    """Adjusts scout type run weights based on acceptance rates."""

    def __init__(self, signal_summary: Dict[str, Any], cycle_number: int, user_id: str):
        self.signal = signal_summary
        self.cycle_number = cycle_number
        self.user_id = user_id
        self.logger = logging.getLogger("meta.reweighter")

    def decide(self) -> List[Dict]:
        scout_perf = self.signal.get("scout_performance", {})
        current_weights = {
            name: perf.get("current_weight", 0.25)
            for name, perf in scout_perf.items()
        }
        if not current_weights:
            current_weights = dict(DEFAULT_WEIGHTS)

        raw_scores = {}
        for name, perf in scout_perf.items():
            raw_scores[name] = perf.get("acceptance_rate", 0.0) + 0.1

        for name in DEFAULT_WEIGHTS:
            if name not in raw_scores:
                raw_scores[name] = 0.1

        # Portfolio churn penalty: high churn in market-driven companies reduces MarketDrivenScout weight
        churn_signals = self.signal.get("portfolio_churn_signals", {})
        market_churn_rate = float(churn_signals.get("market_driven_churn_rate", 0.0) or 0.0)
        _CHURN_THRESHOLD = 0.30   # 30% churn rate triggers penalty
        _MAX_CHURN_PENALTY = 0.50  # cap at halving the raw score
        if market_churn_rate > _CHURN_THRESHOLD:
            churn_penalty = min(_MAX_CHURN_PENALTY, market_churn_rate - _CHURN_THRESHOLD)
            raw_scores["MarketDrivenScout"] = raw_scores.get("MarketDrivenScout", 0.1) * (
                1.0 - churn_penalty
            )
            self.logger.info(
                "[Reweighter] Churn penalty on MarketDrivenScout: churn_rate=%.2f penalty=%.2f",
                market_churn_rate,
                churn_penalty,
            )

        total = sum(raw_scores.values())
        new_weights = {name: score / total for name, score in raw_scores.items()}

        dampened = {}
        for name in new_weights:
            curr = current_weights.get(name, 0.25)
            dampened[name] = DAMPENING_FACTOR * curr + (1 - DAMPENING_FACTOR) * new_weights[name]

        for name in dampened:
            if dampened[name] < WEIGHT_FLOOR:
                dampened[name] = WEIGHT_FLOOR

        total_d = sum(dampened.values())
        dampened = {name: w / total_d for name, w in dampened.items()}

        max_delta = max(
            abs(dampened[name] - current_weights.get(name, 0.25))
            for name in dampened
        )

        if max_delta < MIN_DELTA_THRESHOLD:
            self.logger.info("[Reweighter] Weights stable, no reweighting needed")
            return []

        now = utcnow().isoformat()
        updates = []
        for name in dampened:
            prev = current_weights.get(name, 0.25)
            new_w = round(dampened[name], 4)
            delta = new_w - prev
            direction = "increased" if delta > 0 else "decreased"
            updates.append({
                "scout_type": name,
                "previous_weight": round(prev, 4),
                "new_weight": new_w,
                "reasoning": (
                    f"Acceptance rate {scout_perf.get(name, {}).get('acceptance_rate', 0.0):.2f} "
                    f"-> weight {direction} by {abs(delta):.4f}"
                ),
                "applied_at": now,
                "cycle_number": self.cycle_number,
            })

        return updates

    def apply(self, updates: List[Dict]) -> None:
        if not updates:
            return
        new_weights = {u["scout_type"]: u["new_weight"] for u in updates}
        doc_set(_WEIGHTS_TABLE, new_weights, user_id=self.user_id)
        for u in updates:
            list_append_only(
                _MUTATION_LOG_TABLE,
                {
                    "type": "scout_weight_update",
                    "agent_target": u["scout_type"],
                    "cycle_number": u["cycle_number"],
                    "applied_at": u["applied_at"],
                    "previous_weight": u["previous_weight"],
                    "new_weight": u["new_weight"],
                    "reasoning": u["reasoning"],
                },
                user_id=self.user_id,
            )
