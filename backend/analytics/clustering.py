"""
Sector clustering and concentration tracking.
Backed by Supabase analytics_sector_concentration table.
"""
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from utils.timeutil import utcnow

from supabase_doc_store import doc_get, doc_set

logger = logging.getLogger(__name__)

_CONCENTRATION_TABLE = "analytics_sector_concentration"

_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "shall should may might can could of in to for on with at by from as into "
    "through during before after above below between under and but or nor not "
    "so yet both either neither each every all any few more most other some such "
    "no only own same than too very it its this that these those".split()
)


def _extract_keywords(text: str) -> List[str]:
    """Extract meaningful keywords from text."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 3]


class ClusterAnalyzer:
    """Analyzes sector concentration and theme clusters. Backed by Supabase."""

    def __init__(self, user_id: str, output_file: str = "data/analytics/sector_concentration.json"):
        self.user_id = user_id
        self.logger = logging.getLogger("cluster.analyzer")

    def analyze(self, startups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze startups for sector concentration and theme clusters."""
        if not startups:
            result = {
                "by_sector": {},
                "by_theme": {},
                "most_concentrated_sector": "",
                "most_concentrated_theme": "",
                "last_updated": utcnow().isoformat(),
            }
            self._write(result)
            return result

        total = len(startups)

        # By sector
        by_sector: Dict[str, Dict[str, Any]] = {}
        sector_groups: Dict[str, List[Dict]] = defaultdict(list)
        for s in startups:
            scout = s.get("scout_info") or {}
            sector = scout.get("sector", "Unknown")
            sector_groups[sector].append(s)

        for sector, entries in sector_groups.items():
            confidences = [
                (e.get("scout_info") or {}).get("confidence_score", 0.5)
                for e in entries
            ]
            review_scores = []
            for e in entries:
                ri = e.get("review_info")
                if ri:
                    avg = (ri.get("market_score", 0) + ri.get("product_score", 0) +
                           ri.get("technical_score", 0) + ri.get("execution_score", 0)) / 4.0
                    review_scores.append(avg)
            by_sector[sector] = {
                "count": len(entries),
                "pct_of_total": round(len(entries) / total * 100, 1),
                "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
                "avg_review_score": round(sum(review_scores) / len(review_scores), 1) if review_scores else None,
            }

        # Theme clustering (keyword overlap)
        startup_keywords: Dict[str, List[str]] = {}
        for s in startups:
            sid = s.get("startup_id", "")
            scout = s.get("scout_info") or {}
            text = (scout.get("one_line", "") + " " + scout.get("solution", ""))
            startup_keywords[sid] = _extract_keywords(text)

        # Group by shared keywords (>=3 overlap)
        by_theme: Dict[str, Dict[str, Any]] = {}
        processed = set()
        for sid_a, kw_a in startup_keywords.items():
            if sid_a in processed:
                continue
            cluster = [sid_a]
            kw_set_a = set(kw_a)
            for sid_b, kw_b in startup_keywords.items():
                if sid_b == sid_a or sid_b in processed:
                    continue
                overlap = kw_set_a & set(kw_b)
                if len(overlap) >= 3:
                    cluster.append(sid_b)
            if len(cluster) >= 2:
                all_kws = []
                for sid in cluster:
                    all_kws.extend(startup_keywords.get(sid, []))
                most_common = Counter(all_kws).most_common(1)
                label = most_common[0][0] if most_common else "unknown"
                by_theme[label] = {"count": len(cluster), "startup_ids": cluster}
                processed.update(cluster)

        most_concentrated_sector = max(by_sector, key=lambda k: by_sector[k]["count"]) if by_sector else ""
        most_concentrated_theme = max(by_theme, key=lambda k: by_theme[k]["count"]) if by_theme else ""

        result = {
            "by_sector": by_sector,
            "by_theme": by_theme,
            "most_concentrated_sector": most_concentrated_sector,
            "most_concentrated_theme": most_concentrated_theme,
            "last_updated": utcnow().isoformat(),
        }
        self._write(result)
        return result

    def get_oversaturated_sectors(self, threshold: int = 5) -> List[str]:
        """Return sectors with more than threshold startups."""
        data = self._read()
        return [
            sector for sector, info in data.get("by_sector", {}).items()
            if info.get("count", 0) > threshold
        ]

    def _read(self) -> Dict[str, Any]:
        data = doc_get(_CONCENTRATION_TABLE, user_id=self.user_id)
        return data if isinstance(data, dict) else {}

    def _write(self, data: Dict[str, Any]) -> None:
        doc_set(_CONCENTRATION_TABLE, data, user_id=self.user_id)
