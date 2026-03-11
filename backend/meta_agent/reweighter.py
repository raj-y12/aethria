"""
ScoutReweighter — adjusts scout run frequencies based on performance.
Pure arithmetic, no LLM calls.
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_WEIGHTS_PATH = _BACKEND_DIR / "data" / "meta" / "scout_weights.json"
_MUTATION_LOG_PATH = _BACKEND_DIR / "data" / "meta" / "mutation_log.json"

DEFAULT_WEIGHTS = {
    "MarketDrivenScout": 0.25,
    "BuilderTechnicalScout": 0.25,
    "PainPointScout": 0.25,
    "ContrarianScout": 0.25,
}

WEIGHT_FLOOR = 0.05
DAMPENING_FACTOR = 0.7
MIN_DELTA_THRESHOLD = 0.03


def _atomic_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with open(temp, "w") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def _append_to_json_list(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    if path.exists():
        try:
            with open(path, "r") as f:
                entries = json.load(f)
            if not isinstance(entries, list):
                entries = []
        except (json.JSONDecodeError, IOError):
            entries = []
    entries.append(entry)
    _atomic_write(path, entries)


def load_weights() -> Dict[str, float]:
    """Load current scout weights. Returns defaults if file missing."""
    if not _WEIGHTS_PATH.exists():
        return dict(DEFAULT_WEIGHTS)
    try:
        with open(_WEIGHTS_PATH, "r") as f:
            data = json.load(f)
        if isinstance(data, dict) and data:
            return data
    except (json.JSONDecodeError, IOError):
        pass
    return dict(DEFAULT_WEIGHTS)


class ScoutReweighter:
    """Adjusts scout type run weights based on acceptance rates."""

    def __init__(self, signal_summary: Dict[str, Any], cycle_number: int):
        self.signal = signal_summary
        self.cycle_number = cycle_number
        self.logger = logging.getLogger("meta.reweighter")

    def decide(self) -> List[Dict]:
        """Compute new weights. Returns list of ScoutWeightUpdate if changes exceed threshold."""
        scout_perf = self.signal.get("scout_performance", {})
        current_weights = {
            name: perf.get("current_weight", 0.25)
            for name, perf in scout_perf.items()
        }
        if not current_weights:
            current_weights = dict(DEFAULT_WEIGHTS)

        # Step 1: raw scores from acceptance rates
        raw_scores = {}
        for name, perf in scout_perf.items():
            raw_scores[name] = perf.get("acceptance_rate", 0.0) + 0.1

        # Fill in any missing scouts
        for name in DEFAULT_WEIGHTS:
            if name not in raw_scores:
                raw_scores[name] = 0.1

        # Step 2: normalise
        total = sum(raw_scores.values())
        new_weights = {name: score / total for name, score in raw_scores.items()}

        # Step 3: dampening
        dampened = {}
        for name in new_weights:
            curr = current_weights.get(name, 0.25)
            dampened[name] = DAMPENING_FACTOR * curr + (1 - DAMPENING_FACTOR) * new_weights[name]

        # Enforce floor
        for name in dampened:
            if dampened[name] < WEIGHT_FLOOR:
                dampened[name] = WEIGHT_FLOOR

        # Re-normalise after floor enforcement
        total_d = sum(dampened.values())
        dampened = {name: w / total_d for name, w in dampened.items()}

        # Step 4: check if max delta exceeds threshold
        max_delta = max(
            abs(dampened[name] - current_weights.get(name, 0.25))
            for name in dampened
        )

        if max_delta < MIN_DELTA_THRESHOLD:
            self.logger.info("[Reweighter] Weights stable, no reweighting needed")
            return []

        # Build updates
        now = datetime.now().isoformat()
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

    @staticmethod
    def apply(updates: List[Dict]) -> None:
        """Write new weights to scout_weights.json and log updates."""
        if not updates:
            return
        new_weights = {u["scout_type"]: u["new_weight"] for u in updates}
        _atomic_write(_WEIGHTS_PATH, new_weights)

        for u in updates:
            _append_to_json_list(_MUTATION_LOG_PATH, {
                "type": "scout_weight_update",
                "agent_target": u["scout_type"],
                "cycle_number": u["cycle_number"],
                "applied_at": u["applied_at"],
                "previous_weight": u["previous_weight"],
                "new_weight": u["new_weight"],
                "reasoning": u["reasoning"],
            })
