"""
Persistence layer for AETHRIA DealFlow OS.

Uses Pydantic models (ScoutInfo, ReviewInfo, PartnerInfo, Financials, Startup)
with strict validation. Persists to JSON with atomic, thread-safe read/write.
Supports backward compatibility with old ScoutOutput/ReviewerOutput/PartnerOutput dicts.
"""
import json
import logging
import time
from pathlib import Path
from typing import List, Optional, Callable, Any, Dict

import fcntl
import os

from models import Startup, ScoutInfo, ReviewInfo, PartnerInfo, Financials
import env_config
from utils.reference_validation import is_generic_reference
from utils.partner_codes import normalize_recommendation


logger = logging.getLogger(__name__)

# Retry and lock defaults
_READ_RETRIES = 5
_READ_RETRY_DELAY = 0.1
_WRITE_RETRIES = 5
_WRITE_RETRY_DELAY = 0.1


def _merge_startup_dict_patch(base: dict, patch: Dict[str, Any]) -> None:
    """Shallow-merge patch into startup dict; nested merge for scout/review/partner/financials blobs."""
    merge_keys = ("scout_info", "review_info", "partner_info", "financials", "conviction_state")
    for k, v in patch.items():
        if k in merge_keys and isinstance(v, dict) and isinstance(base.get(k), dict):
            merged = dict(base[k])
            merged.update(v)
            base[k] = merged
        else:
            base[k] = v


def _parse_list(raw: Any) -> List[dict]:
    """Return a list of dicts from raw file data. Handles null, non-list, empty."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    logger.warning("Storage file root is not a list; treating as empty")
    return []


class Storage:
    """
    Thread-safe storage using Pydantic models.

    - Atomic read-modify-write under exclusive lock to avoid lost updates.
    - Robust handling of missing/corrupt JSON (retries, optional skip-invalid).
    - Duplicate detection by startup_id; optional warning by (name, sector).
    - Full support for PartnerInfo: MAYBE, human_review_required, next_action, etc.
    - Backward compatibility: add_discovery, get_unreviewed_entries, get_all/get_by_id dicts.
    - Meta-Agent–friendly: get_startups_with_review, get_startups_requiring_human_review, validate_and_parse.
    """

    def __init__(self, file_path: str = "data/startups.json") -> None:
        if not env_config.local_fallback_allowed():
            raise RuntimeError(
                "Storage: local_storage_disabled; use Supabase-backed storage outside local/dev mode"
            )
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("storage")
        if not self.file_path.exists():
            with open(self.file_path, "w") as f:
                json.dump([], f)
                f.flush()
                os.fsync(f.fileno())

    def _read_file(self) -> List[dict]:
        """Read startups file with shared lock. Retries on JSONDecodeError. Returns [] on empty/corrupt if recoverable."""
        for attempt in range(_READ_RETRIES):
            try:
                with open(self.file_path, "r") as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    try:
                        data = json.load(f)
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return _parse_list(data)
            except (json.JSONDecodeError, IOError, OSError) as e:
                self.logger.warning(f"Storage read attempt {attempt + 1}/{_READ_RETRIES} failed: {e}")
                if attempt == _READ_RETRIES - 1:
                    # Last attempt: if file exists and is small, try returning [] to recover from partial write
                    try:
                        with open(self.file_path, "r") as f:
                            raw = f.read()
                        if not raw.strip():
                            return []
                    except Exception as e:
                        self.logger.debug("Empty-file probe failed: %s", e)
                    raise ValueError(f"Failed to read storage after {_READ_RETRIES} retries") from e
                time.sleep(_READ_RETRY_DELAY * (attempt + 1))
        return []

    def _atomic_update(self, updater: Callable[[List[dict]], List[dict]]) -> None:
        """
        Read file under exclusive lock, call updater(data), write to temp, fsync, rename.
        Lock is held from read through rename so no lost updates.
        """
        temp_path = self.file_path.with_suffix(".tmp")
        for attempt in range(_WRITE_RETRIES):
            try:
                with open(self.file_path, "r") as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    try:
                        try:
                            data = json.load(f)
                        except json.JSONDecodeError:
                            data = []
                        data = _parse_list(data)
                        new_data = updater(data)
                        if not isinstance(new_data, list):
                            raise TypeError("updater must return a list of dicts")
                        with open(temp_path, "w") as out:
                            json.dump(new_data, out, indent=2)
                            out.flush()
                            os.fsync(out.fileno())
                        temp_path.replace(self.file_path)
                    finally:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return
            except (IOError, OSError) as e:
                self.logger.warning(f"Storage write attempt {attempt + 1}/{_WRITE_RETRIES} failed: {e}")
                if attempt == _WRITE_RETRIES - 1:
                    raise
                time.sleep(_WRITE_RETRY_DELAY * (attempt + 1))
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception as e:
                        self.logger.debug("Temp file cleanup failed: %s", e)

    def add_startup(
        self,
        scout_info: ScoutInfo,
        *,
        pipeline_run_id: Optional[str] = None,
        financials: Optional[Financials] = None,
    ) -> str:
        """
        Add a new startup from Scout discovery.
        Duplicate detection by startup_id; logs warning if same ID already exists.
        Optional duplicate hint by (name, sector).
        """
        startup = Startup(
            startup_id=scout_info.startup_id,
            scout_info=scout_info,
            financials=financials or Financials(),
        )
        persisted_id: List[str] = [startup.startup_id]

        def updater(data: List[dict]) -> List[dict]:
            new_name = (startup.scout_info.name or "").strip().lower()
            for existing in data:
                # Duplicate by startup_id
                if existing.get("startup_id") == startup.startup_id:
                    self.logger.warning(f"Startup {startup.startup_id} already exists; skipping add")
                    persisted_id[0] = startup.startup_id
                    return data
                # Duplicate by company name (case-insensitive)
                es = existing.get("scout_info") or {}
                existing_name = str(es.get("name") or "").strip().lower()
                if existing_name and existing_name == new_name:
                    self.logger.info(
                        f"Duplicate company name detected in storage; skipping add: {startup.scout_info.name}"
                    )
                    persisted_id[0] = str(existing.get("startup_id") or startup.startup_id)
                    return data
            data.append(startup.to_dict())
            return data

        self._atomic_update(updater)
        self.logger.info(f"Added startup: {startup.scout_info.name} ({startup.startup_id})")
        return persisted_id[0]

    def add_review(
        self,
        startup_id: str,
        review_info: ReviewInfo,
        *,
        pipeline_run_id: Optional[str] = None,
        enrichment_review_output: Optional[Dict[str, Any]] = None,
        enrichment_gap_reference_urls: Optional[List[str]] = None,
    ) -> bool:
        """Add review to existing startup. Updates updated_at. Returns False if not found."""
        found_ref: List[bool] = [False]

        def updater(data: List[dict]) -> List[dict]:
            for i, item in enumerate(data):
                if item.get("startup_id") != startup_id:
                    continue
                try:
                    startup = Startup.from_dict(item)
                except Exception as e:
                    self.logger.error(f"Invalid startup {startup_id} in storage: {e}")
                    return data
                if enrichment_review_output is not None:
                    from utils.scout_post_review_enrichment import merge_scout_info_enrichment

                    startup.scout_info = merge_scout_info_enrichment(
                        startup.scout_info,
                        review_output=enrichment_review_output,
                        gap_reference_urls=enrichment_gap_reference_urls,
                    )
                startup.review_info = review_info
                startup.update_timestamp()
                data[i] = startup.to_dict()
                found_ref[0] = True
                return data
            return data

        self._atomic_update(updater)
        if found_ref[0]:
            self.logger.info(f"Added review for startup {startup_id}")
        else:
            self.logger.error(f"Startup {startup_id} not found for review")
        return found_ref[0]

    def add_partner_decision(
        self,
        startup_id: str,
        partner_info: PartnerInfo,
        *,
        investment_memo_markdown: Optional[str] = None,
        pipeline_run_id: Optional[str] = None,
        evaluation_manifest_identity: Optional[Any] = None,
        partner_execution_prompt_version: Optional[str] = None,
    ) -> bool:
        """Add partner decision (YES/NO/MAYBE, human_review_required, next_action, etc.). Updates updated_at."""
        found_ref: List[bool] = [False]

        def updater(data: List[dict]) -> List[dict]:
            for i, item in enumerate(data):
                if item.get("startup_id") != startup_id:
                    continue
                try:
                    startup = Startup.from_dict(item)
                except Exception as e:
                    self.logger.error(f"Invalid startup {startup_id} in storage: {e}")
                    return data
                startup.partner_info = partner_info
                if investment_memo_markdown is not None:
                    startup.investment_memo_markdown = investment_memo_markdown
                startup.update_timestamp()
                data[i] = startup.to_dict()
                found_ref[0] = True
                return data
            return data

        self._atomic_update(updater)
        if found_ref[0]:
            self.logger.info(f"Added partner decision for startup {startup_id}")
        else:
            self.logger.error(f"Startup {startup_id} not found for partner decision")
        return found_ref[0]

    def update_financials(self, startup_id: str, financials: Financials) -> bool:
        """Update financials for existing startup. Updates updated_at."""
        found_ref: List[bool] = [False]

        def updater(data: List[dict]) -> List[dict]:
            for i, item in enumerate(data):
                if item.get("startup_id") != startup_id:
                    continue
                try:
                    startup = Startup.from_dict(item)
                except Exception as e:
                    self.logger.error(f"Invalid startup {startup_id} in storage: {e}")
                    return data
                startup.financials = financials
                startup.update_timestamp()
                data[i] = startup.to_dict()
                found_ref[0] = True
                return data
            return data

        self._atomic_update(updater)
        if found_ref[0]:
            self.logger.info(f"Updated financials for startup {startup_id}")
        else:
            self.logger.error(f"Startup {startup_id} not found")
        return found_ref[0]

    def update_startup_partial(self, startup_id: str, patch: Dict[str, Any]) -> bool:
        """Merge top-level fields into one startup record (file-backed atomic update)."""
        found_ref: List[bool] = [False]

        def updater(data: List[dict]) -> List[dict]:
            for i, item in enumerate(data):
                if item.get("startup_id") != startup_id:
                    continue
                try:
                    startup = Startup.from_dict(item)
                except Exception as e:
                    self.logger.error(f"Invalid startup {startup_id} in storage: {e}")
                    return data
                base = startup.to_dict()
                _merge_startup_dict_patch(base, patch)
                try:
                    merged = Startup.from_dict(base)
                except Exception as e:
                    self.logger.error(f"Invalid startup after patch {startup_id}: {e}")
                    return data
                merged.update_timestamp()
                data[i] = merged.to_dict()
                found_ref[0] = True
                return data
            return data

        self._atomic_update(updater)
        return found_ref[0]

    def get_startup(self, startup_id: str) -> Optional[Startup]:
        """Get startup by ID. Returns None if not found. Validates via Startup.from_dict."""
        for item in self._read_file():
            if item.get("startup_id") == startup_id:
                try:
                    return Startup.from_dict(item)
                except Exception as e:
                    self.logger.error(f"Invalid startup {startup_id}: {e}")
                    return None
        return None

    def remove_startup(self, startup_id: str) -> bool:
        """Remove one compatibility row after an institutional identity block."""
        removed: List[bool] = [False]

        def updater(data: List[dict]) -> List[dict]:
            kept = []
            for item in data:
                if item.get("startup_id") == startup_id:
                    removed[0] = True
                else:
                    kept.append(item)
            return kept

        self._atomic_update(updater)
        return removed[0]

    def get_all_startups(self, skip_invalid: bool = False) -> List[Startup]:
        """
        Get all startups with full Pydantic validation.
        If skip_invalid is True, invalid entries are skipped and logged; otherwise first validation error is raised.
        """
        raw = self._read_file()
        out: List[Startup] = []
        for i, item in enumerate(raw):
            try:
                out.append(Startup.from_dict(item))
            except Exception as e:
                if skip_invalid:
                    self.logger.warning(f"Skipping invalid entry at index {i} (id={item.get('startup_id')}): {e}")
                else:
                    raise
        return out

    def get_unreviewed(self, limit: Optional[int] = None, skip_invalid: bool = True) -> List[Startup]:
        """Get startups without reviews. Uses skip_invalid=True by default so one bad entry does not break the pipeline."""
        unreviewed = [s for s in self.get_all_startups(skip_invalid=skip_invalid) if s.review_info is None]
        if limit is not None:
            unreviewed = unreviewed[:limit]
        return unreviewed

    def get_undecided(self, limit: Optional[int] = None, skip_invalid: bool = True) -> List[Startup]:
        """Get startups with reviews but no partner decision. Uses skip_invalid=True by default."""
        undecided = [
            s for s in self.get_all_startups(skip_invalid=skip_invalid)
            if s.review_info is not None and s.partner_info is None
        ]
        if limit is not None:
            undecided = undecided[:limit]
        return undecided

    def get_startups_with_review(self, limit: Optional[int] = None) -> List[Startup]:
        """Get startups that have review_info (for Meta-Agent or downstream)."""
        with_review = [s for s in self.get_all_startups() if s.review_info is not None]
        if limit is not None:
            with_review = with_review[:limit]
        return with_review

    def get_startups_with_decision(
        self,
        decision: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Startup]:
        """Get decided startups, accepting canonical or legacy filter codes."""
        with_decision = [s for s in self.get_all_startups() if s.partner_info is not None]
        if decision is not None:
            recommendation = normalize_recommendation(decision)
            if recommendation is None:
                return []
            with_decision = [
                s for s in with_decision
                if s.partner_info and s.partner_info.recommendation == recommendation
            ]
        if limit is not None:
            with_decision = with_decision[:limit]
        return with_decision

    def get_startups_requiring_human_review(self, limit: Optional[int] = None) -> List[Startup]:
        """Get startups where partner_info.human_review_required is True (MAYBE edge-cases, etc.)."""
        need_review = [
            s for s in self.get_all_startups()
            if s.partner_info is not None and s.partner_info.human_review_required
        ]
        if limit is not None:
            need_review = need_review[:limit]
        return need_review

    def count_unreviewed(self) -> int:
        """Count startups without reviews."""
        return sum(1 for s in self.get_all_startups(skip_invalid=True) if s.review_info is None)

    def count_undecided(self) -> int:
        """Count startups with review but no partner decision."""
        return sum(
            1 for s in self.get_all_startups(skip_invalid=True)
            if s.review_info is not None and s.partner_info is None
        )

    def replace_all(self, items: List[dict]) -> None:
        """
        Replace entire storage with a new list of startup dicts.
        Atomic write. Use for migration or bulk load. Each item must be serializable to Startup.
        """
        if not isinstance(items, list):
            raise TypeError("items must be a list of dicts")
        self._atomic_update(lambda _: items)

    def reset_to_empty(self) -> None:
        """
        Wipe storage and initialize with an empty list.
        Atomic, thread-safe. Use to reset startups.json for fresh data.
        """
        self._atomic_update(lambda _: [])
        self.logger.info("Storage reset to empty")

    def remove_startups_without_references(self) -> int:
        """
        Remove startups that have no valid references.
        Valid = at least one non-generic reference (URL, news, Crunchbase, etc.)
        that proves the company exists. Generic placeholders like
        "General domain knowledge; no specific external sources" are treated as invalid.
        Returns the number of startups removed.
        """
        removed: List[str] = []

        def updater(data: List[dict]) -> List[dict]:
            kept: List[dict] = []
            for item in data:
                scout = (item or {}).get("scout_info") or {}
                # On-demand lookups are never pruned: weak evidence is a visible
                # PARTIAL/NEEDS_REVIEW state, not grounds for deletion.
                if str(scout.get("origin_type") or "").strip().lower() == "on_demand_lookup" or (
                    scout.get("company_resolution") or scout.get("resolution_status")
                ):
                    kept.append(item)
                    continue
                refs = scout.get("references")
                if not refs or not isinstance(refs, list):
                    removed.append(item.get("startup_id") or "?")
                    continue
                valid = [r for r in refs if isinstance(r, str) and r.strip() and not is_generic_reference(r)]
                if not valid:
                    removed.append(item.get("startup_id") or "?")
                else:
                    kept.append(item)
            return kept

        self._atomic_update(updater)
        if removed:
            self.logger.info(f"Removed {len(removed)} startup(s) without valid references: {removed}")
        return len(removed)

    def exists(self, startup_id: str) -> bool:
        """Return True if startup_id exists in storage."""
        for item in self._read_file():
            if item.get("startup_id") == startup_id:
                return True
        return False

    def validate_and_parse(self, raw: dict) -> Startup:
        """
        Validate a dict against Startup schema and return a Startup instance.
        For Meta-Agent: ensures inputs are consistent and fully validated (timestamps, enums, nested models).
        Raises if validation fails.
        """
        return Startup.from_dict(raw)

    def get_undecided_entries(self, limit: Optional[int] = None) -> List[dict]:
        """Backward compatibility: undecided startups as dicts."""
        return [s.to_dict() for s in self.get_undecided(limit=limit)]

    def add_discovery(
        self, scout_output: dict, *, pipeline_run_id: Optional[str] = None
    ) -> str:
        """Backward compatibility: add from old ScoutOutput dict."""
        from utils.adapters import scout_output_to_scout_info, financials_from_scout_output
        scout_info = scout_output_to_scout_info(scout_output)
        financials = financials_from_scout_output(scout_output)
        return self.add_startup(
            scout_info, pipeline_run_id=pipeline_run_id, financials=financials
        )

    def get_unreviewed_entries(self, limit: Optional[int] = None) -> List[dict]:
        """Backward compatibility: unreviewed startups as dicts."""
        return [s.to_dict() for s in self.get_unreviewed(limit=limit)]

    def get_all(self) -> List[dict]:
        """Backward compatibility: all startups as dicts (same shape as get_by_id)."""
        return [s.to_dict() for s in self.get_all_startups(skip_invalid=True)]

    def get_by_id(self, entry_id: str) -> Optional[dict]:
        """Backward compatibility: single startup as dict or None."""
        startup = self.get_startup(entry_id)
        return startup.to_dict() if startup else None
