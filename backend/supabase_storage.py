"""
Supabase-backed storage for the startups table only.

Row-level upserts and targeted selects (no full-table delete+rewrite).
Requires migrations 20260401000001_startups_list_projection_and_indexes.sql and
20260401000002_startups_lookup_id_projection.sql for list projection columns (including lookup_id).
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from models import Startup, ScoutInfo, ReviewInfo, PartnerInfo, Financials
from pipeline_state import pipeline_stage_log, upsert_pipeline_state
from utils.reference_validation import is_generic_reference
from utils.storage import _merge_startup_dict_patch

logger = logging.getLogger(__name__)

TABLE = "startups"

_LIST_SELECT = (
    "startup_id, display_name, list_one_line, list_sector, list_scout_type, list_origin_type, "
    "list_lookup_id, list_lookup_query, list_lookup_website, list_confidence, list_score, list_verdict, "
    "list_consensus_verdict, list_reviewer_disagreement, list_reviewed_at, list_partnered_at, "
    "short_summary, partner_decision, partner_human_review_required, created_at, updated_at"
)
_MEMO_PARTIAL_SELECT = (
    "startup_id, scout_info, review_info, partner_info, investment_memo_markdown"
)


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
        "investment_memo_markdown": row.get("investment_memo_markdown"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _dict_to_row(d: dict, user_id: str) -> dict:
    """Map Startup.to_dict() shape to Supabase row (user_id required)."""
    row = {
        "user_id": user_id,
        "startup_id": d.get("startup_id"),
        "scout_info": d.get("scout_info") or {},
        "review_info": d.get("review_info"),
        "partner_info": d.get("partner_info"),
        "financials": d.get("financials") or {},
        "version": d.get("version", 1),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
    }
    row["investment_memo_markdown"] = d.get("investment_memo_markdown")
    return row


class SupabaseStartupsStorage:
    """
    Storage implementation for the startups table in Supabase.
    Same public surface as utils.storage.Storage where used by the pipeline/API.
    """

    def __init__(self, client: Any, user_id: str) -> None:
        self._client = client
        self._user_id = user_id
        self.logger = logger

    def _fetch_page_raw(self, offset: int, limit: int) -> List[dict]:
        try:
            r = (
                self._client.table(TABLE)
                .select("*")
                .eq("user_id", self._user_id)
                .order("updated_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
        except Exception as e:
            self.logger.warning("Supabase select page failed: %s", e)
            return []
        rows = (r.data or []) if hasattr(r, "data") else []
        return [_row_to_dict(row) for row in rows]

    def _fetch_all_raw(self) -> List[dict]:
        """Paginated full fetch (memory-safe vs single giant response)."""
        page_size = 500
        out: List[dict] = []
        offset = 0
        while True:
            chunk = self._fetch_page_raw(offset, page_size)
            if not chunk:
                break
            out.extend(chunk)
            if len(chunk) < page_size:
                break
            offset += page_size
        return out

    def upsert_startup_dict(self, d: dict) -> None:
        """Single-row upsert on (user_id, startup_id)."""
        row = _dict_to_row(d, self._user_id)
        try:
            self._client.table(TABLE).upsert(row, on_conflict="user_id,startup_id").execute()
        except Exception as e:
            self.logger.error("Supabase upsert failed for %s: %s", row.get("startup_id"), e)
            raise

    def update_startup_partial(self, startup_id: str, patch: dict) -> bool:
        """Read-merge-write one row; patch keys are top-level startup fields (shallow merge for JSON blobs)."""
        st = self.get_startup(startup_id)
        if st is None:
            return False
        base = st.to_dict()
        _merge_startup_dict_patch(base, patch)
        try:
            merged = Startup.from_dict(base)
        except Exception as e:
            self.logger.error("Invalid startup after patch %s: %s", startup_id, e)
            return False
        merged.update_timestamp()
        self.upsert_startup_dict(merged.to_dict())
        return True

    def get_list_projection_rows(self) -> Optional[List[dict]]:
        """Thin columns for GET /api/startups list (low egress).

        Returns None if the query failed (caller must not fall back to full-row fetch).
        Returns [] when the query succeeded but the tenant has no rows.
        """
        try:
            r = (
                self._client.table(TABLE)
                .select(_LIST_SELECT)
                .eq("user_id", self._user_id)
                .order("updated_at", desc=True)
                .execute()
            )
        except Exception as e:
            self.logger.warning("List projection select failed (run latest migrations?): %s", e)
            return None
        return list((r.data or []) if hasattr(r, "data") else [])

    def get_startup_id_name_map(self) -> Dict[str, str]:
        """startup_id -> display name for attaching labels without full rows."""
        try:
            r = (
                self._client.table(TABLE)
                .select("startup_id, display_name")
                .eq("user_id", self._user_id)
                .execute()
            )
        except Exception as e:
            self.logger.warning("startup_id name map failed: %s", e)
            return {}
        rows = (r.data or []) if hasattr(r, "data") else []
        return {
            str(row["startup_id"]): (row.get("display_name") or "").strip()
            for row in rows
            if row.get("startup_id")
        }

    def get_startups_paginated(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[dict], int]:
        """
        Offset pagination on updated_at desc.
        Returns (rows as Startup dicts, next_offset). next_offset is -1 when no further pages.
        """
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        try:
            r = (
                self._client.table(TABLE)
                .select("*")
                .eq("user_id", self._user_id)
                .order("updated_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
        except Exception as e:
            self.logger.warning("Paginated startups failed: %s", e)
            return [], -1
        rows = list((r.data or []) if hasattr(r, "data") else [])
        out = [_row_to_dict(x) for x in rows]
        if len(rows) < limit:
            return out, -1
        return out, offset + len(rows)

    def query_pending_escalations_raw(self) -> List[dict]:
        """Partner human_review_required; exclude rows already resolved (resolved_at set)."""
        try:
            r = (
                self._client.table(TABLE)
                .select("startup_id, scout_info, partner_info, human_resolution")
                .eq("user_id", self._user_id)
                .eq("partner_human_review_required", True)
                .execute()
            )
        except Exception as e:
            self.logger.warning("query_pending_escalations_raw failed: %s", e)
            return []
        rows = (r.data or []) if hasattr(r, "data") else []
        out: List[dict] = []
        for row in rows:
            raw = _row_to_dict(row)
            hr = raw.get("human_resolution")
            if hr and isinstance(hr, dict) and hr.get("resolved_at"):
                continue
            out.append(raw)
        return out

    def add_startup(self, scout_info: ScoutInfo, *, pipeline_run_id: Optional[str] = None) -> str:
        startup = Startup(
            startup_id=scout_info.startup_id,
            scout_info=scout_info,
            financials=Financials(),
        )
        pr = (pipeline_run_id or "").strip() or None
        try:
            r = (
                self._client.table(TABLE)
                .select("startup_id, display_name")
                .eq("user_id", self._user_id)
                .execute()
            )
            existing_rows = (r.data or []) if hasattr(r, "data") else []
        except Exception as e:
            self.logger.warning("Duplicate check select failed: %s", e)
            existing_rows = []

        new_name = (startup.scout_info.name or "").strip().lower()
        for row in existing_rows:
            if row.get("startup_id") == startup.startup_id:
                self.logger.warning("Startup %s already exists; skipping add", startup.startup_id)
                return startup.startup_id
            dn = (row.get("display_name") or "").strip().lower()
            if dn and dn == new_name:
                self.logger.info(
                    "Duplicate company name detected in storage; skipping add: %s",
                    startup.scout_info.name,
                )
                return startup.startup_id

        sid = startup.startup_id
        if pr:
            pipeline_stage_log(
                pr, startup_id=sid, user_id=self._user_id, stage="scouting", phase="STARTED"
            )
            upsert_pipeline_state(
                self._client,
                user_id=self._user_id,
                startup_id=sid,
                pipeline_run_id=pr,
                status="scouting",
            )
        try:
            self.upsert_startup_dict(startup.to_dict())
        except Exception as e:
            if pr:
                upsert_pipeline_state(
                    self._client,
                    user_id=self._user_id,
                    startup_id=sid,
                    pipeline_run_id=pr,
                    status="failed",
                    error=f"scout upsert failed: {e}"[:500],
                )
            raise
        if pr:
            pipeline_stage_log(
                pr, startup_id=sid, user_id=self._user_id, stage="scouting", phase="DONE"
            )
            upsert_pipeline_state(
                self._client,
                user_id=self._user_id,
                startup_id=sid,
                pipeline_run_id=pr,
                status="pending",
            )
        self.logger.info("Added startup: %s (%s)", startup.scout_info.name, startup.startup_id)
        return startup.startup_id

    def add_review(
        self, startup_id: str, review_info: ReviewInfo, *, pipeline_run_id: Optional[str] = None
    ) -> bool:
        pr = (pipeline_run_id or "").strip() or None
        if pr:
            pipeline_stage_log(
                pr, startup_id=startup_id, user_id=self._user_id, stage="processing_signals", phase="STARTED"
            )
            upsert_pipeline_state(
                self._client,
                user_id=self._user_id,
                startup_id=startup_id,
                pipeline_run_id=pr,
                status="processing_signals",
            )
        st = self.get_startup(startup_id)
        if st is None:
            self.logger.error("Startup %s not found for review", startup_id)
            if pr:
                upsert_pipeline_state(
                    self._client,
                    user_id=self._user_id,
                    startup_id=startup_id,
                    pipeline_run_id=pr,
                    status="failed",
                    error="startup not found for review",
                )
            return False
        st.review_info = review_info
        st.update_timestamp()
        try:
            self.upsert_startup_dict(st.to_dict())
        except Exception as e:
            if pr:
                upsert_pipeline_state(
                    self._client,
                    user_id=self._user_id,
                    startup_id=startup_id,
                    pipeline_run_id=pr,
                    status="failed",
                    error=f"review upsert failed: {e}"[:500],
                )
            raise
        if pr:
            pipeline_stage_log(
                pr, startup_id=startup_id, user_id=self._user_id, stage="processing_signals", phase="DONE"
            )
            upsert_pipeline_state(
                self._client,
                user_id=self._user_id,
                startup_id=startup_id,
                pipeline_run_id=pr,
                status="pending",
            )
        self.logger.info("Added review for startup %s", startup_id)
        return True

    def add_partner_decision(
        self,
        startup_id: str,
        partner_info: PartnerInfo,
        *,
        investment_memo_markdown: Optional[str] = None,
        pipeline_run_id: Optional[str] = None,
    ) -> bool:
        pr = (pipeline_run_id or "").strip() or None
        st = self.get_startup(startup_id)
        if st is None:
            self.logger.error("Startup %s not found for partner decision", startup_id)
            if pr:
                upsert_pipeline_state(
                    self._client,
                    user_id=self._user_id,
                    startup_id=startup_id,
                    pipeline_run_id=pr,
                    status="failed",
                    error="startup not found for partner",
                )
            return False
        st.partner_info = partner_info
        if investment_memo_markdown is not None:
            st.investment_memo_markdown = investment_memo_markdown
        st.update_timestamp()
        try:
            self.upsert_startup_dict(st.to_dict())
        except Exception as e:
            if pr:
                upsert_pipeline_state(
                    self._client,
                    user_id=self._user_id,
                    startup_id=startup_id,
                    pipeline_run_id=pr,
                    status="failed",
                    error=f"partner upsert failed: {e}"[:500],
                )
            raise
        self.logger.info("Added partner decision for startup %s", startup_id)
        if pr and investment_memo_markdown is not None:
            pipeline_stage_log(
                pr, startup_id=startup_id, user_id=self._user_id, stage="writing_memo", phase="DONE"
            )
            upsert_pipeline_state(
                self._client,
                user_id=self._user_id,
                startup_id=startup_id,
                pipeline_run_id=pr,
                status="ready",
            )
        return True

    def update_financials(self, startup_id: str, financials: Financials) -> bool:
        st = self.get_startup(startup_id)
        if st is None:
            self.logger.error("Startup %s not found", startup_id)
            return False
        st.financials = financials
        st.update_timestamp()
        self.upsert_startup_dict(st.to_dict())
        self.logger.info("Updated financials for startup %s", startup_id)
        return True

    def get_startup(self, startup_id: str, select_columns: str = "*") -> Optional[Startup]:
        try:
            r = (
                self._client.table(TABLE)
                .select(select_columns)
                .eq("user_id", self._user_id)
                .eq("startup_id", startup_id)
                .limit(1)
                .execute()
            )
        except Exception as e:
            self.logger.warning("Supabase get_startup failed: %s", e)
            return None
        rows = (r.data or []) if hasattr(r, "data") else []
        if not rows:
            return None
        try:
            return Startup.from_dict(_row_to_dict(rows[0]))
        except Exception as e:
            self.logger.error("Invalid startup %s: %s", startup_id, e)
            return None

    def get_startup_for_memo(self, startup_id: str) -> Optional[Startup]:
        """Memo endpoint projection: only fields needed for memo readiness/partial payload."""
        return self.get_startup(startup_id, select_columns=_MEMO_PARTIAL_SELECT)

    def get_startup_by_id(self, startup_id: str) -> Optional[Startup]:
        """Alias for get_startup (explicit API for callers)."""
        return self.get_startup(startup_id)

    def get_all_startups(self, skip_invalid: bool = False) -> List[Startup]:
        raw = self._fetch_all_raw()
        out: List[Startup] = []
        for i, item in enumerate(raw):
            try:
                out.append(Startup.from_dict(item))
            except Exception as e:
                if skip_invalid:
                    self.logger.warning(
                        "Skipping invalid entry at index %s (id=%s): %s",
                        i,
                        item.get("startup_id"),
                        e,
                    )
                else:
                    raise
        return out

    def _rows_to_startups(self, rows_raw: List[dict], skip_invalid: bool = True) -> List[Startup]:
        out: List[Startup] = []
        for i, row in enumerate(rows_raw):
            try:
                out.append(Startup.from_dict(_row_to_dict(row)))
            except Exception as e:
                if skip_invalid:
                    self.logger.warning(
                        "Skipping invalid row %s (id=%s): %s",
                        i,
                        row.get("startup_id"),
                        e,
                    )
                else:
                    raise
        return out

    def get_startups_missing_thesis(self, limit: int = 1000) -> List[str]:
        """
        startup_ids for rows with review_info present and no fund_thesis_version_id in review_info.
        Paginates until `limit` ids are collected or rows are exhausted.
        """
        limit = max(1, min(int(limit), 2000))
        out: List[str] = []
        page_size = min(250, limit)
        offset = 0
        while len(out) < limit:
            try:
                r = (
                    self._client.table(TABLE)
                    .select("startup_id,review_info")
                    .eq("user_id", self._user_id)
                    .not_.is_("review_info", "null")
                    .order("updated_at", desc=True)
                    .range(offset, offset + page_size - 1)
                    .execute()
                )
            except Exception as e:
                self.logger.warning("get_startups_missing_thesis page failed: %s", e)
                break
            rows = (r.data or []) if hasattr(r, "data") else []
            if not rows:
                break
            for row in rows:
                ri = row.get("review_info")
                if not isinstance(ri, dict):
                    continue
                vid = ri.get("fund_thesis_version_id")
                if vid is not None and str(vid).strip():
                    continue
                sid = row.get("startup_id")
                if sid:
                    out.append(str(sid))
                    if len(out) >= limit:
                        break
            if len(rows) < page_size:
                break
            offset += page_size
        return out[:limit]

    def get_unreviewed(self, limit: Optional[int] = None, skip_invalid: bool = True) -> List[Startup]:
        lim = limit if limit is not None else 1000
        lim = max(1, min(lim, 500))
        try:
            r = (
                self._client.table(TABLE)
                .select("*")
                .eq("user_id", self._user_id)
                .is_("review_info", "null")
                .order("updated_at", desc=False)
                .limit(lim)
                .execute()
            )
        except Exception as e:
            self.logger.warning("get_unreviewed query failed: %s", e)
            return []
        rows = (r.data or []) if hasattr(r, "data") else []
        startups = self._rows_to_startups(rows, skip_invalid=skip_invalid)
        startups.sort(
            key=lambda s: s.scout_info.discovered_at.timestamp() if s.scout_info.discovered_at else 0.0
        )
        if limit is not None:
            return startups[:limit]
        return startups

    def get_undecided(self, limit: Optional[int] = None, skip_invalid: bool = True) -> List[Startup]:
        lim = limit if limit is not None else 1000
        lim = max(1, min(lim, 500))
        try:
            r = (
                self._client.table(TABLE)
                .select("*")
                .eq("user_id", self._user_id)
                .not_.is_("review_info", "null")
                .is_("partner_info", "null")
                .order("updated_at", desc=True)
                .limit(lim)
                .execute()
            )
        except Exception as e:
            self.logger.warning("get_undecided query failed: %s", e)
            return []
        rows = (r.data or []) if hasattr(r, "data") else []
        startups = self._rows_to_startups(rows, skip_invalid=skip_invalid)
        if limit is not None:
            return startups[:limit]
        return startups

    def get_startups_with_review(self, limit: Optional[int] = None) -> List[Startup]:
        lim = limit if limit is not None else 500
        try:
            r = (
                self._client.table(TABLE)
                .select("*")
                .eq("user_id", self._user_id)
                .not_.is_("review_info", "null")
                .order("updated_at", desc=True)
                .limit(lim)
                .execute()
            )
        except Exception as e:
            self.logger.warning("get_startups_with_review failed: %s", e)
            return []
        rows = (r.data or []) if hasattr(r, "data") else []
        return self._rows_to_startups(rows, skip_invalid=True)

    def get_startups_with_decision(
        self,
        decision: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Startup]:
        lim = limit if limit is not None else 500
        try:
            q = (
                self._client.table(TABLE)
                .select("*")
                .eq("user_id", self._user_id)
                .not_.is_("partner_info", "null")
                .order("updated_at", desc=True)
                .limit(lim)
            )
            if decision is not None:
                q = q.eq("partner_decision", decision)
            r = q.execute()
        except Exception as e:
            self.logger.warning("get_startups_with_decision failed: %s", e)
            return self._legacy_get_startups_with_decision(decision, limit)
        rows = (r.data or []) if hasattr(r, "data") else []
        startups = self._rows_to_startups(rows, skip_invalid=True)
        if decision is not None:
            startups = [s for s in startups if s.partner_info and s.partner_info.decision == decision]
        if limit is not None:
            startups = startups[:limit]
        return startups

    def _legacy_get_startups_with_decision(
        self, decision: Optional[str], limit: Optional[int]
    ) -> List[Startup]:
        with_decision = [s for s in self.get_all_startups(skip_invalid=True) if s.partner_info is not None]
        if decision is not None:
            with_decision = [s for s in with_decision if s.partner_info.decision == decision]
        if limit is not None:
            with_decision = with_decision[:limit]
        return with_decision

    def get_startups_requiring_human_review(self, limit: Optional[int] = None) -> List[Startup]:
        lim = limit if limit is not None else 200
        try:
            r = (
                self._client.table(TABLE)
                .select("*")
                .eq("user_id", self._user_id)
                .eq("partner_human_review_required", True)
                .order("updated_at", desc=True)
                .limit(lim)
                .execute()
            )
        except Exception as e:
            self.logger.warning("get_startups_requiring_human_review failed: %s", e)
            return [
                s
                for s in self.get_all_startups(skip_invalid=True)
                if s.partner_info is not None and s.partner_info.human_review_required
            ][: (limit or 200)]
        rows = (r.data or []) if hasattr(r, "data") else []
        startups = self._rows_to_startups(rows, skip_invalid=True)
        if limit is not None:
            startups = startups[:limit]
        return startups

    def count_unreviewed(self) -> int:
        try:
            r = (
                self._client.table(TABLE)
                .select("startup_id", count="exact")
                .eq("user_id", self._user_id)
                .is_("review_info", "null")
                .execute()
            )
            return int(r.count or 0) if hasattr(r, "count") and r.count is not None else 0
        except Exception as e:
            self.logger.warning("count_unreviewed failed: %s", e)
            return sum(1 for s in self.get_all_startups(skip_invalid=True) if s.review_info is None)

    def count_undecided(self) -> int:
        try:
            r = (
                self._client.table(TABLE)
                .select("startup_id", count="exact")
                .eq("user_id", self._user_id)
                .not_.is_("review_info", "null")
                .is_("partner_info", "null")
                .execute()
            )
            return int(r.count or 0) if hasattr(r, "count") and r.count is not None else 0
        except Exception as e:
            self.logger.warning("count_undecided failed: %s", e)
            return sum(
                1
                for s in self.get_all_startups(skip_invalid=True)
                if s.review_info is not None and s.partner_info is None
            )

    def replace_all(self, items: List[dict]) -> None:
        if not isinstance(items, list):
            raise TypeError("items must be a list of dicts")
        try:
            self._client.table(TABLE).delete().eq("user_id", self._user_id).execute()
        except Exception as e:
            self.logger.error("replace_all delete failed: %s", e)
            raise
        chunk = 80
        for i in range(0, len(items), chunk):
            batch = [_dict_to_row(d, self._user_id) for d in items[i : i + chunk]]
            if not batch:
                continue
            try:
                self._client.table(TABLE).upsert(batch, on_conflict="user_id,startup_id").execute()
            except Exception as e:
                self.logger.error("replace_all upsert chunk failed: %s", e)
                raise

    def reset_to_empty(self) -> None:
        try:
            self._client.table(TABLE).delete().eq("user_id", self._user_id).execute()
        except Exception as e:
            self.logger.error("reset_to_empty failed: %s", e)
            raise
        self.logger.info("Storage reset to empty")

    def remove_startups_without_references(self) -> int:
        try:
            r = (
                self._client.table(TABLE)
                .select("startup_id, scout_info")
                .eq("user_id", self._user_id)
                .execute()
            )
        except Exception as e:
            self.logger.warning("remove_startups_without_references select failed: %s", e)
            return 0
        rows = (r.data or []) if hasattr(r, "data") else []
        bad_ids: List[str] = []
        for row in rows:
            sid = row.get("startup_id") or "?"
            scout = row.get("scout_info") or {}
            refs = scout.get("references")
            if not refs or not isinstance(refs, list):
                bad_ids.append(str(sid))
                continue
            valid = [x for x in refs if isinstance(x, str) and x.strip() and not is_generic_reference(x)]
            if not valid:
                bad_ids.append(str(sid))
        if not bad_ids:
            return 0
        try:
            self._client.table(TABLE).delete().eq("user_id", self._user_id).in_("startup_id", bad_ids).execute()
        except Exception as e:
            self.logger.error("remove_startups_without_references delete failed: %s", e)
            return 0
        self.logger.info("Removed %s startup(s) without valid references: %s", len(bad_ids), bad_ids)
        return len(bad_ids)

    def exists(self, startup_id: str) -> bool:
        try:
            r = (
                self._client.table(TABLE)
                .select("startup_id")
                .eq("user_id", self._user_id)
                .eq("startup_id", startup_id)
                .limit(1)
                .execute()
            )
        except Exception as e:
            self.logger.warning("exists() failed: %s", e)
            return False
        rows = (r.data or []) if hasattr(r, "data") else []
        return len(rows) > 0

    def validate_and_parse(self, raw: dict) -> Startup:
        return Startup.from_dict(raw)

    def get_undecided_entries(self, limit: Optional[int] = None) -> List[dict]:
        return [s.to_dict() for s in self.get_undecided(limit=limit)]

    def add_discovery(
        self, scout_output: dict, *, pipeline_run_id: Optional[str] = None
    ) -> str:
        from utils.adapters import scout_output_to_scout_info

        scout_info = scout_output_to_scout_info(scout_output)
        return self.add_startup(scout_info, pipeline_run_id=pipeline_run_id)

    def get_unreviewed_entries(self, limit: Optional[int] = None) -> List[dict]:
        return [s.to_dict() for s in self.get_unreviewed(limit=limit)]

    def get_all(self) -> List[dict]:
        return [s.to_dict() for s in self.get_all_startups(skip_invalid=True)]

    def get_by_id(self, entry_id: str) -> Optional[dict]:
        startup = self.get_startup(entry_id)
        return startup.to_dict() if startup else None

    def _atomic_update(self, updater: Callable[[List[dict]], List[dict]]) -> None:
        """
        Legacy helper: read-merge-write full table. Prefer update_startup_partial.
        Still used by file Storage and a few code paths; implemented for compatibility.
        """
        data = self._fetch_all_raw()
        new_data = updater(data)
        if not isinstance(new_data, list):
            raise TypeError("updater must return a list of dicts")
        self.replace_all(new_data)
