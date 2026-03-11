"""
Cross-agent deal memory for institutional learning.
Backed by data/memory.json. Thread-safe atomic writes.
"""
import json
import logging
import math
import os
import re
import fcntl
from collections import Counter
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "shall should may might can could of in to for on with at by from as into "
    "through during before after above below between under and but or nor not "
    "so yet both either neither each every all any few more most other some such "
    "no only own same than too very it its this that these those i we they he she".split()
)


def _tokenize(text: str) -> List[str]:
    """Lowercase, split on non-alpha, remove stop words and short tokens."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 2]


def _word_overlap_similarity(a: str, b: str) -> float:
    """Jaccard-like similarity using word overlap. Returns 0-1."""
    tokens_a = set(_tokenize(a))
    tokens_b = set(_tokenize(b))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0


class DealMemory:
    """
    Cross-agent institutional memory.
    
    Stores:
    - seen_sectors: sector -> count of times scouted
    - seen_theses: last 50 primary_thesis strings
    - failed_assumptions: last 100 assumption strings with negative feedback
    - successful_theses: last 50 primary_thesis strings from YES decisions
    """

    MAX_THESES = 50
    MAX_FAILED = 100
    MAX_SUCCESSFUL = 50
    SIMILARITY_THRESHOLD = 0.75

    def __init__(self, file_path: str = "data/memory.json"):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("deal_memory")
        if not self.file_path.exists():
            self._write({
                "seen_sectors": {},
                "seen_theses": [],
                "failed_assumptions": [],
                "successful_theses": [],
            })

    def _read(self) -> Dict[str, Any]:
        try:
            with open(self.file_path, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return data
        except (json.JSONDecodeError, IOError):
            return {"seen_sectors": {}, "seen_theses": [], "failed_assumptions": [], "successful_theses": []}

    def _write(self, data: Dict[str, Any]) -> None:
        temp_path = self.file_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        temp_path.replace(self.file_path)

    def is_duplicate_thesis(self, thesis: str) -> bool:
        """Check if thesis is too similar to any seen thesis."""
        if not thesis:
            return False
        data = self._read()
        for existing in data.get("seen_theses", []):
            if _word_overlap_similarity(thesis, existing) > self.SIMILARITY_THRESHOLD:
                self.logger.info(f"Duplicate thesis detected: '{thesis[:60]}...'")
                return True
        return False

    def record_scout_discovery(self, sector: str, primary_thesis: str) -> None:
        """Record a new scout discovery."""
        data = self._read()
        sectors = data.get("seen_sectors", {})
        sectors[sector] = sectors.get(sector, 0) + 1
        data["seen_sectors"] = sectors
        theses = data.get("seen_theses", [])
        if primary_thesis:
            theses.append(primary_thesis)
            data["seen_theses"] = theses[-self.MAX_THESES:]
        self._write(data)

    def record_failed_assumptions(self, assumptions: List[str]) -> None:
        """Record assumptions that received negative feedback."""
        if not assumptions:
            return
        data = self._read()
        failed = data.get("failed_assumptions", [])
        failed.extend(assumptions)
        data["failed_assumptions"] = failed[-self.MAX_FAILED:]
        self._write(data)

    def record_successful_thesis(self, thesis: str) -> None:
        """Record a thesis from a YES decision."""
        if not thesis:
            return
        data = self._read()
        successful = data.get("successful_theses", [])
        successful.append(thesis)
        data["successful_theses"] = successful[-self.MAX_SUCCESSFUL:]
        self._write(data)

    def get_oversaturated_sectors(self, top_n: int = 3) -> List[str]:
        """Return top N most scouted sectors."""
        data = self._read()
        sectors = data.get("seen_sectors", {})
        sorted_sectors = sorted(sectors.items(), key=lambda x: x[1], reverse=True)
        return [s[0] for s in sorted_sectors[:top_n]]

    def get_recent_failed_assumptions(self, n: int = 5) -> List[str]:
        """Return last N failed assumptions."""
        data = self._read()
        return data.get("failed_assumptions", [])[-n:]

    def get_memory_context_for_scout(self) -> str:
        """Build dynamic prompt augmentation for scouts."""
        oversaturated = self.get_oversaturated_sectors(3)
        failed = self.get_recent_failed_assumptions(5)
        parts = []
        if oversaturated:
            parts.append(f"Avoid these overexplored sectors this cycle: {', '.join(oversaturated)}.")
        if failed:
            parts.append(f"Previously failed assumptions to avoid: {'; '.join(failed)}.")
        return " ".join(parts) if parts else ""
