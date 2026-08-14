"""
Rejection pattern analyzer. Learns from passed deals.
Uses the provider-neutral Batch 2 snapshot in the async pipeline; falls back
to local JSON only in explicitly local/dev mode.
"""
import json
import logging
import os
import fcntl
from pathlib import Path
from typing import Dict, Any, List, Optional
from batch2.repository import Batch2State
from batch2.store import rejection_patterns_get, rejection_patterns_set
import env_config

logger = logging.getLogger(__name__)

def _empty_patterns() -> Dict[str, Any]:
    return {
        "most_common_red_flags": [],
        "rejection_by_sector": {},
        "avg_scores_at_rejection": {},
        "most_common_fail_dimensions": [],
        "scout_blind_spots": {},
        "_rejection_count": 0,
    }


class RejectionAnalyzer:
    """Analyzes rejection patterns and writes tenant-scoped storage."""

    def __init__(self, data_dir: str = "data/portfolio", user_id: Optional[str] = None, batch2_state: Optional[Batch2State] = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.user_id = (user_id or "").strip() or None
        self.batch2_state = batch2_state
        # ponytail: filename-safe tenant scoping — the fallback file must never
        # be shared across tenants (it was previously one unscoped file).
        file_suffix = f"_{self.user_id}" if self.user_id else ""
        self.patterns_file = self.data_dir / f"rejection_patterns{file_suffix}.json"
        if env_config.is_production_env() and not self.user_id:
            raise RuntimeError("RejectionAnalyzer requires explicit user_id in production")
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
        patterns = self._read_patterns()

        flag_counts = {item["flag"]: item["count"] for item in patterns.get("most_common_red_flags", [])}
        for flag in diligence_red_flags:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
        patterns["most_common_red_flags"] = sorted(
            [{"flag": f, "count": c} for f, c in flag_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:20]

        by_sector = patterns.get("rejection_by_sector", {})
        by_sector[sector] = by_sector.get(sector, 0) + 1
        patterns["rejection_by_sector"] = by_sector

        avg_scores = patterns.get("avg_scores_at_rejection", {})
        count = patterns.get("_rejection_count", 0) + 1
        for dim, score in dimension_scores.items():
            prev = avg_scores.get(dim, 0.0)
            avg_scores[dim] = prev + (score - prev) / count
        patterns["avg_scores_at_rejection"] = avg_scores
        patterns["_rejection_count"] = count

        fail_dims = {item["dimension"]: item["count"] for item in patterns.get("most_common_fail_dimensions", [])}
        lowest_dim = min(dimension_scores, key=dimension_scores.get) if dimension_scores else None
        if lowest_dim:
            fail_dims[lowest_dim] = fail_dims.get(lowest_dim, 0) + 1
        patterns["most_common_fail_dimensions"] = sorted(
            [{"dimension": d, "count": c} for d, c in fail_dims.items()],
            key=lambda x: x["count"],
            reverse=True,
        )

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
        return self._read_patterns()

    def _read_patterns(self) -> Dict[str, Any]:
        if self.user_id and self.batch2_state is None and not env_config.local_fallback_allowed():
            raise RuntimeError("RejectionAnalyzer: batch2_asyncpg_snapshot_required")
        if self.user_id and self.batch2_state is not None:
            data = rejection_patterns_get(user_id=self.user_id, state=self.batch2_state)
            return data if isinstance(data, dict) else _empty_patterns()
        if not self.patterns_file.exists():
            return _empty_patterns()
        try:
            with open(self.patterns_file, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    return json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (json.JSONDecodeError, IOError):
            return _empty_patterns()

    def _write_patterns(self, data: Dict[str, Any]) -> None:
        if self.user_id and self.batch2_state is None and not env_config.local_fallback_allowed():
            raise RuntimeError("RejectionAnalyzer: batch2_asyncpg_snapshot_required")
        if self.user_id and self.batch2_state is not None:
            rejection_patterns_set(data, user_id=self.user_id, state=self.batch2_state)
            return
        temp_path = self.patterns_file.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        temp_path.replace(self.patterns_file)
