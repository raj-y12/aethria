"""
MetaAnalyser — reads all performance signal and produces a structured summary.
Backed by Supabase for agent_metrics, memory, scout_weights, mutation_log, concentration.
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from supabase_doc_store import doc_get, list_get_all

logger = logging.getLogger(__name__)

# Agent name to scout_type mapping
SCOUT_AGENT_NAMES = {
    "MarketDrivenScout": "market_driven",
    "BuilderTechnicalScout": "builder_technical",
    "PainPointScout": "pain_point",
    "ContrarianScout": "contrarian",
}

REVIEWER_AGENT_NAMES = ["DefaultReviewer", "SkepticalReviewer", "OpportunistReviewer"]

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _read_json(path: Path) -> Any:
    """Read JSON file, return empty structure on failure."""
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


class MetaAnalyser:
    """Reads all available signal sources and produces a structured SignalSummary."""

    def __init__(self):
        self.logger = logging.getLogger("meta.analyser")
        self.cooldown_cycles = int(os.getenv("META_AGENT_MUTATION_COOLDOWN_CYCLES", "3"))

    def analyse(self) -> Dict[str, Any]:
        """Read all signal sources and return a structured SignalSummary."""
        agent_metrics = self._read_agent_metrics()
        rejection_patterns = self._read_rejection_patterns()
        memory = self._read_memory()
        scout_weights = self._read_scout_weights()
        mutation_log = self._read_mutation_log()
        concentration = self._read_concentration()

        scout_perf = self._build_scout_performance(
            agent_metrics, rejection_patterns, scout_weights, mutation_log
        )
        reviewer_health = self._build_reviewer_health(
            agent_metrics, rejection_patterns
        )
        pipeline_health = self._build_pipeline_health(memory, concentration)
        cooldowns = self._build_cooldowns(mutation_log)

        # Count total reviews and decisions for minimum thresholds
        total_reviews = sum(
            1 for m in (agent_metrics if isinstance(agent_metrics, list) else [])
            if m.get("metric_name") == "acceptance_rate"
        )
        total_decisions_metric = [
            m for m in (agent_metrics if isinstance(agent_metrics, list) else [])
            if m.get("metric_name") == "acceptance_rate"
        ]
        total_decisions = sum(m.get("sample_size", 0) for m in total_decisions_metric)

        # Read verdict distribution for review count
        vd = reviewer_health.get("verdict_distribution", {})
        total_reviews_from_vd = sum(vd.values()) if vd else 0

        return {
            "scout_performance": scout_perf,
            "reviewer_health": reviewer_health,
            "pipeline_health": pipeline_health,
            "mutation_cooldowns": cooldowns,
            "data_sufficiency": {
                "total_reviews": max(total_reviews, total_reviews_from_vd),
                "total_decisions": total_decisions,
            },
        }

    def _read_agent_metrics(self) -> Any:
        return list_get_all("portfolio_agent_metrics")

    def _read_rejection_patterns(self) -> Dict:
        path = _BACKEND_DIR / "data" / "portfolio" / "rejection_patterns.json"
        data = _read_json(path)
        return data if isinstance(data, dict) else {}

    def _read_memory(self) -> Dict:
        data = doc_get("memory")
        return data if isinstance(data, dict) else {}

    def _read_scout_weights(self) -> Dict[str, float]:
        data = doc_get("meta_scout_weights")
        if isinstance(data, dict) and data:
            return data
        return {
            "MarketDrivenScout": 0.25,
            "BuilderTechnicalScout": 0.25,
            "PainPointScout": 0.25,
            "ContrarianScout": 0.25,
        }

    def _read_mutation_log(self) -> List[Dict]:
        return list_get_all("meta_mutation_log")

    def _read_concentration(self) -> Dict:
        data = doc_get("analytics_sector_concentration")
        return data if isinstance(data, dict) else {}

    def _build_scout_performance(
        self,
        metrics: List[Dict],
        rejection_patterns: Dict,
        weights: Dict[str, float],
        mutation_log: List[Dict],
    ) -> Dict[str, Dict]:
        scout_perf = {}
        blind_spots = rejection_patterns.get("scout_blind_spots", {})

        for agent_name, scout_type in SCOUT_AGENT_NAMES.items():
            # Find acceptance rate from metrics
            acceptance_rate = 0.0
            for m in metrics:
                if (m.get("agent_id") == f"scout_{scout_type}" and
                        m.get("metric_name") == "discovery_acceptance_rate"):
                    acceptance_rate = m.get("metric_value", 0.0)
                    break

            # Find blind spots for this scout type
            agent_blind_spots = blind_spots.get(scout_type, [])

            # Find last mutation time
            last_mutated_at = None
            for entry in reversed(mutation_log):
                if entry.get("agent_target") == agent_name:
                    last_mutated_at = entry.get("applied_at")
                    break

            scout_perf[agent_name] = {
                "acceptance_rate": acceptance_rate,
                "blind_spots": agent_blind_spots,
                "current_weight": weights.get(agent_name, 0.25),
                "last_mutated_at": last_mutated_at,
            }

        return scout_perf

    def _build_reviewer_health(
        self, metrics: List[Dict], rejection_patterns: Dict
    ) -> Dict[str, Any]:
        verdict_dist = {"STRONG": 0, "MEDIUM": 0, "WEAK": 0}
        calibration_warning = None

        for m in metrics:
            if m.get("id") == "verdict_distribution":
                verdict_dist = m.get("verdict_distribution", verdict_dist)
                calibration_warning = m.get("calibration_warning")
                break

        fail_dims = [
            item["dimension"]
            for item in rejection_patterns.get("most_common_fail_dimensions", [])
        ]

        return {
            "verdict_distribution": verdict_dist,
            "calibration_warning": calibration_warning,
            "most_common_fail_dimensions": fail_dims[:5],
        }

    def _build_pipeline_health(self, memory: Dict, concentration: Dict) -> Dict[str, Any]:
        most_oversaturated = concentration.get("most_concentrated_sector", "")
        failed_assumptions = memory.get("failed_assumptions", [])[-10:]
        successful_theses = memory.get("successful_theses", [])[-10:]

        return {
            "most_oversaturated_sector": most_oversaturated,
            "top_failed_assumptions": failed_assumptions,
            "top_successful_thesis_patterns": successful_theses,
        }

    def _build_cooldowns(self, mutation_log: List[Dict]) -> Dict[str, bool]:
        """Compute cooldown flags. An agent cannot be mutated more than once per N cycles."""
        cooldowns = {}
        if not mutation_log:
            for name in list(SCOUT_AGENT_NAMES.keys()) + REVIEWER_AGENT_NAMES:
                cooldowns[name] = False
            return cooldowns

        # Find current max cycle number
        max_cycle = max((e.get("cycle_number", 0) for e in mutation_log), default=0)

        for name in list(SCOUT_AGENT_NAMES.keys()) + REVIEWER_AGENT_NAMES:
            last_cycle = 0
            for entry in reversed(mutation_log):
                if entry.get("agent_target") == name:
                    last_cycle = entry.get("cycle_number", 0)
                    break
            cooldowns[name] = (max_cycle - last_cycle) < self.cooldown_cycles
        return cooldowns
