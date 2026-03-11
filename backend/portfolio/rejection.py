"""
Rejection pattern analyzer. Learns from passed deals.
"""
import json
import logging
import os
import fcntl
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class RejectionAnalyzer:
    """Analyzes rejection patterns and writes to rejection_patterns.json."""

    def __init__(self, data_dir: str = "data/portfolio"):
        self.data_dir = Path(data_dir)
        self.patterns_file = self.data_dir / "rejection_patterns.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("rejection.analyzer")

    def analyze_rejection(
        self,
        sector: str,
        avg_score: float,
        verdict: str,
        diligence_red_flags: List[str],
        dimension_scores: Dict[str, int],
        scout_type: str = "",
    ) -> None:
        """Analyze a single rejection and update patterns."""
        patterns = self._read_patterns()
        
        # Update red flag counts
        flag_counts = {item["flag"]: item["count"] for item in patterns.get("most_common_red_flags", [])}
        for flag in diligence_red_flags:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
        patterns["most_common_red_flags"] = sorted(
            [{"flag": f, "count": c} for f, c in flag_counts.items()],
            key=lambda x: x["count"], reverse=True
        )[:20]

        # Update rejection by sector
        by_sector = patterns.get("rejection_by_sector", {})
        by_sector[sector] = by_sector.get(sector, 0) + 1
        patterns["rejection_by_sector"] = by_sector

        # Update avg scores at rejection (running average)
        avg_scores = patterns.get("avg_scores_at_rejection", {})
        count = patterns.get("_rejection_count", 0) + 1
        for dim, score in dimension_scores.items():
            prev = avg_scores.get(dim, 0.0)
            avg_scores[dim] = prev + (score - prev) / count
        patterns["avg_scores_at_rejection"] = avg_scores
        patterns["_rejection_count"] = count

        # Update fail dimensions
        fail_dims = {item["dimension"]: item["count"] for item in patterns.get("most_common_fail_dimensions", [])}
        lowest_dim = min(dimension_scores, key=dimension_scores.get) if dimension_scores else None
        if lowest_dim:
            fail_dims[lowest_dim] = fail_dims.get(lowest_dim, 0) + 1
        patterns["most_common_fail_dimensions"] = sorted(
            [{"dimension": d, "count": c} for d, c in fail_dims.items()],
            key=lambda x: x["count"], reverse=True
        )

        # Track scout blind spots
        blind_spots = patterns.get("scout_blind_spots", {})
        if scout_type and diligence_red_flags:
            existing = blind_spots.get(scout_type, [])
            for flag in diligence_red_flags:
                if flag not in existing:
                    existing.append(flag)
            blind_spots[scout_type] = existing[-10:]
        patterns["scout_blind_spots"] = blind_spots

        self._write_patterns(patterns)

    def get_patterns(self) -> Dict[str, Any]:
        """Return current rejection patterns."""
        return self._read_patterns()

    def _read_patterns(self) -> Dict[str, Any]:
        if not self.patterns_file.exists():
            return {
                "most_common_red_flags": [],
                "rejection_by_sector": {},
                "avg_scores_at_rejection": {},
                "most_common_fail_dimensions": [],
                "scout_blind_spots": {},
                "_rejection_count": 0,
            }
        try:
            with open(self.patterns_file, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (json.JSONDecodeError, IOError):
            return {"most_common_red_flags": [], "rejection_by_sector": {}, "avg_scores_at_rejection": {}, "most_common_fail_dimensions": [], "scout_blind_spots": {}, "_rejection_count": 0}

    def _write_patterns(self, data: Dict[str, Any]) -> None:
        temp_path = self.patterns_file.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        temp_path.replace(self.patterns_file)
