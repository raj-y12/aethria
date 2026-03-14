"""
Supabase-backed storage for the startups table only.

Same interface as utils.storage.Storage; uses Supabase client and user_id for RLS.
"""
import logging
from typing import Any, Callable, List, Optional

from models import Startup, ScoutInfo, ReviewInfo, PartnerInfo, Financials
from utils.reference_validation import is_generic_reference

logger = logging.getLogger(__name__)

TABLE = "startups"


def _row_to_dict(row: dict) -> dict:
    """Map Supabase row to Startup dict shape (for Startup.from_dict)."""
    return {
        "startup_id": row.get("startup_id"),
        "scout_info": row.get("scout_info") or {},
        "review_info": row.get("review_info"),
        "partner_info": row.get("partner_info"),
        "financials": row.get("financials") or {},
        "version": row.get("version", 1),
        "human_resolution": row.get("human_resolution"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _dict_to_row(d: dict, user_id: str) -> dict:
    """Map Startup.to_dict() shape to Supabase row (user_id required)."""
    return {
        "user_id": user_id,
        "startup_id": d.get("startup_id"),
        "scout_info": d.get("scout_info") or {},
        "review_info": d.get("review_info"),
        "partner_info": d.get("partner_info"),
        "financials": d.get("financials") or {},
        "version": d.get("version", 1),
        "human_resolution": d.get("human_resolution"),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
    }


class SupabaseStartupsStorage:
    """
    Storage implementation for the startups table in Supabase.
    Uses the same interface as utils.storage.Storage.
    """

    def __init__(self, client: Any, user_id: str) -> None:
        self._client = client
        self._user_id = user_id
        self.logger = logger

    def _fetch_all_raw(self) -> List[dict]:
        """Return all startups for this user as list of dicts (Startup shape)."""
        try:
            r = self._client.table(TABLE).select("*").eq("user_id", self._user_id).execute()
        except Exception as e:
            self.logger.warning(f"Supabase select failed: {e}")
            return []
        rows = (r.data or []) if hasattr(r, "data") else []
        return [_row_to_dict(row) for row in rows]

    def _replace_all_raw(self, items: List[dict]) -> None:
        """Replace all startups for this user with the given list."""
        self._client.table(TABLE).delete().eq("user_id", self._user_id).execute()
        for d in items:
            row = _dict_to_row(d, self._user_id)
            self._client.table(TABLE).insert(row).execute()

    def _atomic_update(self, updater: Callable[[List[dict]], List[dict]]) -> None:
        """Read all, run updater, write back (same semantics as file Storage)."""
        data = self._fetch_all_raw()
        new_data = updater(data)
        if not isinstance(new_data, list):
            raise TypeError("updater must return a list of dicts")
        self._replace_all_raw(new_data)

    def add_startup(self, scout_info: ScoutInfo) -> str:
        startup = Startup(
            startup_id=scout_info.startup_id,
            scout_info=scout_info,
            financials=Financials(),
        )
        data = self._fetch_all_raw()
        new_name = (startup.scout_info.name or "").strip().lower()
        for existing in data:
            if existing.get("startup_id") == startup.startup_id:
                self.logger.warning(f"Startup {startup.startup_id} already exists; skipping add")
                return startup.startup_id
            es = existing.get("scout_info") or {}
            existing_name = str(es.get("name") or "").strip().lower()
            if existing_name and existing_name == new_name:
                self.logger.info(
                    f"Duplicate company name detected in storage; skipping add: {startup.scout_info.name}"
                )
                return startup.startup_id
        data.append(startup.to_dict())
        self._replace_all_raw(data)
        self.logger.info(f"Added startup: {startup.scout_info.name} ({startup.startup_id})")
        return startup.startup_id

    def add_review(self, startup_id: str, review_info: ReviewInfo) -> bool:
        found = False

        def updater(data: List[dict]) -> List[dict]:
            nonlocal found
            for i, item in enumerate(data):
                if item.get("startup_id") != startup_id:
                    continue
                try:
                    startup = Startup.from_dict(item)
                except Exception as e:
                    self.logger.error(f"Invalid startup {startup_id} in storage: {e}")
                    return data
                startup.review_info = review_info
                startup.update_timestamp()
                data[i] = startup.to_dict()
                found = True
                return data
            return data

        self._atomic_update(updater)
        if found:
            self.logger.info(f"Added review for startup {startup_id}")
        else:
            self.logger.error(f"Startup {startup_id} not found for review")
        return found

    def add_partner_decision(self, startup_id: str, partner_info: PartnerInfo) -> bool:
        found = False

        def updater(data: List[dict]) -> List[dict]:
            nonlocal found
            for i, item in enumerate(data):
                if item.get("startup_id") != startup_id:
                    continue
                try:
                    startup = Startup.from_dict(item)
                except Exception as e:
                    self.logger.error(f"Invalid startup {startup_id} in storage: {e}")
                    return data
                startup.partner_info = partner_info
                startup.update_timestamp()
                data[i] = startup.to_dict()
                found = True
                return data
            return data

        self._atomic_update(updater)
        if found:
            self.logger.info(f"Added partner decision for startup {startup_id}")
        else:
            self.logger.error(f"Startup {startup_id} not found for partner decision")
        return found

    def update_financials(self, startup_id: str, financials: Financials) -> bool:
        found = False

        def updater(data: List[dict]) -> List[dict]:
            nonlocal found
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
                found = True
                return data
            return data

        self._atomic_update(updater)
        if found:
            self.logger.info(f"Updated financials for startup {startup_id}")
        else:
            self.logger.error(f"Startup {startup_id} not found")
        return found

    def get_startup(self, startup_id: str) -> Optional[Startup]:
        try:
            r = (
                self._client.table(TABLE)
                .select("*")
                .eq("user_id", self._user_id)
                .eq("startup_id", startup_id)
                .limit(1)
                .execute()
            )
        except Exception as e:
            self.logger.warning(f"Supabase get_startup failed: {e}")
            return None
        rows = (r.data or []) if hasattr(r, "data") else []
        if not rows:
            return None
        try:
            return Startup.from_dict(_row_to_dict(rows[0]))
        except Exception as e:
            self.logger.error(f"Invalid startup {startup_id}: {e}")
            return None

    def get_all_startups(self, skip_invalid: bool = False) -> List[Startup]:
        raw = self._fetch_all_raw()
        out: List[Startup] = []
        for i, item in enumerate(raw):
            try:
                out.append(Startup.from_dict(item))
            except Exception as e:
                if skip_invalid:
                    self.logger.warning(
                        f"Skipping invalid entry at index {i} (id={item.get('startup_id')}): {e}"
                    )
                else:
                    raise
        return out

    def get_unreviewed(self, limit: Optional[int] = None, skip_invalid: bool = True) -> List[Startup]:
        unreviewed = [
            s for s in self.get_all_startups(skip_invalid=skip_invalid) if s.review_info is None
        ]
        if limit is not None:
            unreviewed = unreviewed[:limit]
        return unreviewed

    def get_undecided(self, limit: Optional[int] = None, skip_invalid: bool = True) -> List[Startup]:
        undecided = [
            s
            for s in self.get_all_startups(skip_invalid=skip_invalid)
            if s.review_info is not None and s.partner_info is None
        ]
        if limit is not None:
            undecided = undecided[:limit]
        return undecided

    def get_startups_with_review(self, limit: Optional[int] = None) -> List[Startup]:
        with_review = [s for s in self.get_all_startups() if s.review_info is not None]
        if limit is not None:
            with_review = with_review[:limit]
        return with_review

    def get_startups_with_decision(
        self,
        decision: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Startup]:
        with_decision = [s for s in self.get_all_startups() if s.partner_info is not None]
        if decision is not None:
            with_decision = [s for s in with_decision if s.partner_info.decision == decision]
        if limit is not None:
            with_decision = with_decision[:limit]
        return with_decision

    def get_startups_requiring_human_review(self, limit: Optional[int] = None) -> List[Startup]:
        need_review = [
            s
            for s in self.get_all_startups()
            if s.partner_info is not None and s.partner_info.human_review_required
        ]
        if limit is not None:
            need_review = need_review[:limit]
        return need_review

    def count_unreviewed(self) -> int:
        return sum(
            1 for s in self.get_all_startups(skip_invalid=True) if s.review_info is None
        )

    def count_undecided(self) -> int:
        return sum(
            1
            for s in self.get_all_startups(skip_invalid=True)
            if s.review_info is not None and s.partner_info is None
        )

    def replace_all(self, items: List[dict]) -> None:
        if not isinstance(items, list):
            raise TypeError("items must be a list of dicts")
        self._replace_all_raw(items)

    def reset_to_empty(self) -> None:
        self._replace_all_raw([])
        self.logger.info("Storage reset to empty")

    def remove_startups_without_references(self) -> int:
        removed: List[str] = []

        def updater(data: List[dict]) -> List[dict]:
            kept: List[dict] = []
            for item in data:
                scout = (item or {}).get("scout_info") or {}
                refs = scout.get("references")
                if not refs or not isinstance(refs, list):
                    removed.append(item.get("startup_id") or "?")
                    continue
                valid = [
                    r
                    for r in refs
                    if isinstance(r, str) and r.strip() and not is_generic_reference(r)
                ]
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
        return self.get_startup(startup_id) is not None

    def validate_and_parse(self, raw: dict) -> Startup:
        return Startup.from_dict(raw)

    def get_undecided_entries(self, limit: Optional[int] = None) -> List[dict]:
        return [s.to_dict() for s in self.get_undecided(limit=limit)]

    def add_discovery(self, scout_output: dict) -> str:
        from utils.adapters import scout_output_to_scout_info
        scout_info = scout_output_to_scout_info(scout_output)
        return self.add_startup(scout_info)

    def get_unreviewed_entries(self, limit: Optional[int] = None) -> List[dict]:
        return [s.to_dict() for s in self.get_unreviewed(limit=limit)]

    def get_all(self) -> List[dict]:
        return [s.to_dict() for s in self.get_all_startups(skip_invalid=True)]

    def get_by_id(self, entry_id: str) -> Optional[dict]:
        startup = self.get_startup(entry_id)
        return startup.to_dict() if startup else None
