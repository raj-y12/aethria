"""
Rejection pattern analyzer. Learns from passed deals.
Persists to Supabase (`portfolio_rejection_patterns`) when configured with tenant context;
falls back to local JSON file otherwise.
"""
import json
import logging
import os
import fcntl
from pathlib import Path
from typing import Dict, Any, List, Optional
from uuid import uuid4

from supabase_client import get_service_client
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

    def __init__(self, data_dir: str = "data/portfolio", user_id: Optional[str] = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.patterns_file = self.data_dir / "rejection_patterns.json"
        self.user_id = (user_id or "").strip() or None
        if env_config.use_supabase_storage() and not self.user_id:
            raise RuntimeError("RejectionAnalyzer requires explicit user_id when Supabase storage is enabled")
        self.logger = logging.getLogger("rejection.analyzer")

    def _using_supabase(self) -> bool:
        return bool(self.user_id and os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))

    def _supabase_client(self):
        return get_service_client()

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
        if self._using_supabase():
            try:
                r = (
                    self._supabase_client()
                    .table("portfolio_rejection_patterns")
                    .select("stats,created_at")
                    .eq("user_id", self.user_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                rows = (r.data or []) if hasattr(r, "data") else []
                if rows and isinstance(rows[0].get("stats"), dict):
                    return rows[0]["stats"]
                return _empty_patterns()
            except Exception as e:
                self.logger.warning("Supabase rejection patterns read failed; using file fallback: %s", e)
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
        if self._using_supabase():
            try:
                # Keep exactly one current row per user via update-or-insert.
                q = (
                    self._supabase_client()
                    .table("portfolio_rejection_patterns")
                    .select("id")
                    .eq("user_id", self.user_id)
                    .limit(1)
                    .execute()
                )
                rows = (q.data or []) if hasattr(q, "data") else []
                if rows:
                    row_id = rows[0].get("id")
                    self._supabase_client().table("portfolio_rejection_patterns").update(
                        {"stats": data}
                    ).eq("id", row_id).eq("user_id", self.user_id).execute()
                else:
                    self._supabase_client().table("portfolio_rejection_patterns").insert(
                        {"id": str(uuid4()), "user_id": self.user_id, "stats": data}
                    ).execute()
                return
            except Exception as e:
                self.logger.warning("Supabase rejection patterns write failed; using file fallback: %s", e)
        temp_path = self.patterns_file.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        temp_path.replace(self.patterns_file)
