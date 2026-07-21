"""
Supabase-backed storage for the startups table only.

Row-level upserts and targeted selects (no full-table delete+rewrite).
Requires migrations 20260401000001_startups_list_projection_and_indexes.sql and
20260401000002_startups_lookup_id_projection.sql for list projection columns (including lookup_id).
"""
from __future__ import annotations

import logging
import os
import random
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from models import (
    EvaluationManifest,
    EvaluationManifestIdentity,
    Startup,
    ScoutInfo,
    ReviewInfo,
    PartnerInfo,
    Financials,
)
from pipeline_state import get_pipeline_state_row, pipeline_stage_log, upsert_pipeline_state
from agent_trace import (
    build_partner_trace,
    build_review_trace,
    build_scout_trace,
    handoff_quality_from_trace,
    merge_stage_trace,
)
from utils.reference_validation import is_generic_reference
from utils.partner_codes import normalize_recommendation
from utils.storage import _merge_startup_dict_patch

logger = logging.getLogger(__name__)

TABLE = "startups"
# errno 11 (EAGAIN, Linux) / 35 (EAGAIN/EWOULDBLOCK, macOS): transient client-side
# socket pressure under burst, not a Supabase failure (server logs stay 200). Retried
# with exponential backoff so a burst never surfaces as a failed query.
_TRANSIENT_ERRNOS = (35, 11)
_RETRY_ATTEMPTS = max(1, int(os.getenv("SUPABASE_RETRY_ATTEMPTS", "6")))
_BASE_RETRY_DELAY_SECONDS = 0.08
_MAX_RETRY_DELAY_SECONDS = float(os.getenv("SUPABASE_MAX_RETRY_DELAY_SECONDS", "1.5"))
_QUEUE_AWARENESS_COLUMNS = (
    "first_seen_at",
    "last_seen_by_user_at",
    "acknowledged_at",
    "queue_reason",
    "priority_reason",
)

_LIST_SELECT = (
    "startup_id, display_name, list_one_line, list_sector, list_location, list_scout_type, list_origin_type, "
    "list_lookup_id, list_lookup_query, list_lookup_website, list_resolution_status, list_confidence, "
    "list_score, list_verdict, "
    "list_consensus_verdict, list_reviewer_disagreement, list_reviewed_at, list_partnered_at, "
    "short_summary, partner_decision, partner_human_review_required, partner_info, human_resolution, "
    "conviction_state, unresolved_at, first_seen_at, last_seen_by_user_at, acknowledged_at, "
    "queue_reason, priority_reason, created_at, updated_at"
)
_LIST_SELECT_LEGACY_NO_UNRESOLVED = (
    "startup_id, display_name, list_one_line, list_sector, list_location, list_scout_type, list_origin_type, "
    "list_lookup_id, list_lookup_query, list_lookup_website, list_confidence, list_score, list_verdict, "
    "list_consensus_verdict, list_reviewer_disagreement, list_reviewed_at, list_partnered_at, "
    "short_summary, partner_decision, partner_human_review_required, partner_info, human_resolution, "
    "conviction_state, created_at, updated_at"
)
# Portfolio execution scan runs every pipeline cycle over all decided rows.
# review_info averages ~20KB/row and is only needed for not-yet-executed
# decisions (refetched per-row in PortfolioEngine), so it stays out of the scan.
_DECISION_SCAN_SELECT = (
    "startup_id, scout_info, partner_info, human_resolution, financials, version, "
    "conviction_state, queue_reason, priority_reason, unresolved_at, first_seen_at, "
    "last_seen_by_user_at, acknowledged_at, created_at, updated_at"
)
_MEMO_PARTIAL_SELECT = (
    "startup_id, scout_info, review_info, partner_info, conviction_state, agent_trace, investment_memo_markdown"
)


def _score_from_review(review_info: Any) -> Optional[int]:
    if not review_info:
        return None
    if hasattr(review_info, "overall_score") and getattr(review_info, "overall_score") is not None:
        try:
            return max(0, min(100, round(float(getattr(review_info, "overall_score")) * 10)))
        except (TypeError, ValueError):
            return None
    scores: List[float] = []
    for attr in ("market_score", "product_score", "technical_score", "execution_score"):
        val = getattr(review_info, attr, None)
        if val is None:
            continue
        try:
            scores.append(float(val))
        except (TypeError, ValueError):
            continue
    if not scores:
        return None
    return max(0, min(100, round((sum(scores) / len(scores)) * 10)))


def _queue_reasons_for_startup(startup: Startup) -> Tuple[str, str]:
    sector = (startup.scout_info.sector or "").split("/")[0].strip()
    score = _score_from_review(startup.review_info)
    priority_parts = [f"Priority {score}" if score is not None else "Priority pending"]

    human_resolution = startup.human_resolution if isinstance(startup.human_resolution, dict) else None
    if human_resolution and human_resolution.get("resolved_at"):
        decision = str(human_resolution.get("decision") or "recorded").upper()
        queue_reason = f"Human ruling recorded: {decision}."
        priority_parts.append("Human ruled")
    elif startup.partner_info and startup.partner_info.human_review_required:
        queue_reason = "Human ruling required."
        priority_parts.append("Human ruling required")
    elif startup.partner_info and startup.partner_info.recommendation:
        rec = startup.partner_info.recommendation
        queue_reason = f"Partner recommends {rec.lower()}."
        priority_parts.append(f"Partner {rec}")
    elif startup.review_info:
        queue_reason = "Reviewer output ready for partner judgement."
        priority_parts.append("Reviewed")
    else:
        queue_reason = "New discovery awaiting review."
        priority_parts.append("New signal")
    if sector:
        priority_parts.append(sector)
    return queue_reason, " · ".join(priority_parts)


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
        "conviction_state": row.get("conviction_state"),
        "agent_trace": row.get("agent_trace"),
        "investment_memo_markdown": row.get("investment_memo_markdown"),
        "unresolved_at": row.get("unresolved_at"),
        "first_seen_at": row.get("first_seen_at"),
        "last_seen_by_user_at": row.get("last_seen_by_user_at"),
        "acknowledged_at": row.get("acknowledged_at"),
        "queue_reason": row.get("queue_reason"),
        "priority_reason": row.get("priority_reason"),
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
        "human_resolution": d.get("human_resolution"),
        "conviction_state": d.get("conviction_state"),
        "agent_trace": d.get("agent_trace"),
        "unresolved_at": d.get("unresolved_at"),
        "first_seen_at": d.get("first_seen_at"),
        "last_seen_by_user_at": d.get("last_seen_by_user_at"),
        "acknowledged_at": d.get("acknowledged_at"),
        "queue_reason": d.get("queue_reason"),
        "priority_reason": d.get("priority_reason"),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
    }
    row["investment_memo_markdown"] = d.get("investment_memo_markdown")
    return row


def _is_missing_unresolved_at_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "unresolved_at" in text and (
        "does not exist" in text or "schema cache" in text or "42703" in text
    )


def _is_missing_agent_trace_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "agent_trace" in text and (
        "does not exist" in text or "schema cache" in text or "42703" in text
    )


def _is_missing_queue_awareness_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(column in text for column in _QUEUE_AWARENESS_COLUMNS) and (
        "does not exist" in text or "schema cache" in text or "42703" in text
    )


def _is_missing_resolution_status_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "list_resolution_status" in text and (
        "does not exist" in text or "schema cache" in text or "42703" in text
    )


# Columns added by later migrations that the write path tolerates (pops + retries)
# when absent. Probing for them proactively turns silent, per-write data loss into
# one loud startup signal that a migration is unapplied.
_EXPECTED_OPTIONAL_COLUMNS: tuple[str, ...] = (
    "agent_trace",
    "unresolved_at",
    *_QUEUE_AWARENESS_COLUMNS,
)


def detect_schema_drift(client, table: str = TABLE) -> List[str]:
    """Return expected-but-missing columns on the startups table.

    A proactive companion to the reactive pop-column fallbacks in this module:
    those keep the app alive but silently drop data, so drift can persist
    invisibly. This makes it legible. Never raises — probing failures (e.g. a
    transient connection error) yield an empty list rather than blocking startup.
    """
    missing: List[str] = []
    for column in _EXPECTED_OPTIONAL_COLUMNS:
        try:
            client.table(table).select(column).limit(1).execute()
        except Exception as e:  # noqa: BLE001 - classify, never propagate
            text = str(e).lower()
            if column in text and (
                "does not exist" in text or "schema cache" in text or "42703" in text
            ):
                missing.append(column)
            # Non-"missing column" errors (network/permission) are ignored here;
            # they surface through the normal request path.
    return missing


class SupabaseStartupsStorage:
    """
    Storage implementation for the startups table in Supabase.
    Same public surface as utils.storage.Storage where used by the pipeline/API.
    """

    def __init__(self, client: Any, user_id: str) -> None:
        self._client = client
        self._user_id = user_id
        self.logger = logger

    def _is_transient_error(self, exc: BaseException) -> bool:
        if isinstance(exc, OSError) and getattr(exc, "errno", None) in _TRANSIENT_ERRNOS:
            return True
        return isinstance(exc, ConnectionError)

    def _execute_with_retry(self, fn: Callable[[], Any]) -> Any:
        last_exc: BaseException | None = None
        for attempt in range(_RETRY_ATTEMPTS + 1):
            try:
                return fn()
            except Exception as exc:
                last_exc = exc
                if attempt < _RETRY_ATTEMPTS and self._is_transient_error(exc):
                    sleep_for = min(
                        _BASE_RETRY_DELAY_SECONDS * (2**attempt), _MAX_RETRY_DELAY_SECONDS
                    ) + random.uniform(0, 0.04)
                    time.sleep(sleep_for)
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    def _settings_for_trace(self) -> dict:
        try:
            from utils.settings_loader import load_settings

            return load_settings(self._user_id)
        except Exception as e:
            self.logger.debug("agent_trace settings unavailable: %s", e)
            return {}

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
        legacy = dict(row)
        warned: set[str] = set()
        for _ in range(4):
            try:
                self._client.table(TABLE).upsert(
                    legacy, on_conflict="user_id,startup_id", returning="minimal"
                ).execute()
                return
            except Exception as e:
                if _is_missing_agent_trace_error(e) and "agent_trace" in legacy:
                    legacy.pop("agent_trace", None)
                    if "agent_trace" not in warned:
                        warned.add("agent_trace")
                        self.logger.warning(
                            "Supabase agent_trace column missing; retrying upsert without trace. "
                            "Apply the startup_agent_trace migration to persist handoff traces."
                        )
                    continue
                if _is_missing_unresolved_at_error(e) and "unresolved_at" in legacy:
                    legacy.pop("unresolved_at", None)
                    if "unresolved_at" not in warned:
                        warned.add("unresolved_at")
                        self.logger.warning(
                            "Supabase unresolved_at column missing; retrying upsert without unresolved state. "
                            "Apply migration 20260512000001_unresolved_state.sql to persist unresolved dates."
                        )
                    continue
                if _is_missing_queue_awareness_error(e) and any(c in legacy for c in _QUEUE_AWARENESS_COLUMNS):
                    for column in _QUEUE_AWARENESS_COLUMNS:
                        legacy.pop(column, None)
                    if "queue_awareness" not in warned:
                        warned.add("queue_awareness")
                        self.logger.warning(
                            "Supabase queue awareness columns missing; retrying upsert without queue state. "
                            "Apply migration 20260521000002_startup_queue_awareness.sql."
                        )
                    continue
                self.logger.error("Supabase upsert failed for %s: %s", row.get("startup_id"), e)
                raise
        self.logger.error("Supabase upsert failed after legacy column retries for %s", row.get("startup_id"))
        raise RuntimeError("Supabase upsert failed after legacy column retries")

    def record_scoring_trail(self, startup_id: str, trace: dict) -> bool:
        """Append a per-decision scoring trail row (P7.1).

        Stores the full deterministic scoring trace (facts/labels/component scores) plus
        denormalized columns for cheap calibration queries. Append-only — never updates.
        Returns True on insert, False on any failure (a trail-write must NEVER break the
        review pipeline). Safe no-op if the `scoring_trails` table is absent.
        """
        if not isinstance(trace, dict) or not startup_id:
            return False
        row = {
            "user_id": self._user_id,
            "startup_id": str(startup_id),
            "rubric_version": trace.get("rubric_version"),
            "policy_version_id": trace.get("policy_version_id"),
            "policy_hash": trace.get("policy_hash"),
            "overall_score": trace.get("overall_score"),
            "overall_confidence": trace.get("overall_confidence"),
            "stage_cohort": trace.get("stage_cohort"),
            "sector_tam_benchmark": trace.get("sector_tam_benchmark"),
            "trail": trace,
        }
        try:
            self._execute_with_retry(
                lambda: self._client.table("scoring_trails").insert(row, returning="minimal").execute()
            )
            return True
        except Exception as e:
            self.logger.warning(
                "Supabase scoring_trails insert failed for %s: %s. "
                "Apply migration 20260604000002_scoring_trail.sql if the table is missing.",
                startup_id,
                e,
            )
            return False

    def record_evaluation_manifest(
        self,
        startup_id: str,
        manifest: EvaluationManifest,
        *,
        manifest_identity: EvaluationManifestIdentity | Dict[str, Any],
    ) -> bool:
        """Merge one portable evaluation manifest into the startup's agent trace."""
        if not startup_id:
            return False
        from evaluation.manifest import validate_evaluation_manifest_for_persistence

        validated = validate_evaluation_manifest_for_persistence(
            manifest,
            manifest_identity=manifest_identity,
            user_id=self._user_id,
        )
        st = self.get_startup(startup_id)
        if st is None:
            self.logger.error("Startup %s not found for evaluation manifest", startup_id)
            return False
        trace = dict(st.agent_trace) if isinstance(st.agent_trace, dict) else {}
        trace["evaluation_manifest"] = validated.model_dump(mode="json")
        st.agent_trace = trace
        st.update_timestamp()
        self._update_startup_columns(
            startup_id,
            self._changed_row_columns(st, ("agent_trace", "updated_at")),
        )
        return True

    def _update_startup_columns(self, startup_id: str, columns: dict) -> None:
        """Targeted UPDATE of specific columns on one row.

        Unlike upsert_startup_dict (which rewrites the entire row, including large
        unchanged JSONB such as review_info), this writes only the columns that
        actually changed. Postgres keeps the existing TOAST pointers for columns
        not in the SET list, avoiding rewriting/​re-indexing big blobs on every
        stage handoff. Mirrors upsert_startup_dict's legacy-column fallback so it
        degrades gracefully on not-yet-migrated schemas.
        """
        # Keep None values (e.g. clearing unresolved_at); only strip identity/immutable keys.
        payload = {
            k: v
            for k, v in columns.items()
            if k not in ("user_id", "startup_id", "created_at")
        }
        if not payload:
            return
        warned: set[str] = set()
        for _ in range(4):
            if not payload:
                return
            try:
                (
                    self._client.table(TABLE)
                    .update(payload, returning="minimal")
                    .eq("user_id", self._user_id)
                    .eq("startup_id", startup_id)
                    .execute()
                )
                return
            except Exception as e:
                if _is_missing_agent_trace_error(e) and "agent_trace" in payload:
                    payload.pop("agent_trace", None)
                    if "agent_trace" not in warned:
                        warned.add("agent_trace")
                        self.logger.warning(
                            "Supabase agent_trace column missing; retrying update without trace. "
                            "Apply the startup_agent_trace migration to persist handoff traces."
                        )
                    continue
                if _is_missing_unresolved_at_error(e) and "unresolved_at" in payload:
                    payload.pop("unresolved_at", None)
                    if "unresolved_at" not in warned:
                        warned.add("unresolved_at")
                        self.logger.warning(
                            "Supabase unresolved_at column missing; retrying update without unresolved state. "
                            "Apply migration 20260512000001_unresolved_state.sql."
                        )
                    continue
                if _is_missing_queue_awareness_error(e) and any(c in payload for c in _QUEUE_AWARENESS_COLUMNS):
                    for column in _QUEUE_AWARENESS_COLUMNS:
                        payload.pop(column, None)
                    if "queue_awareness" not in warned:
                        warned.add("queue_awareness")
                        self.logger.warning(
                            "Supabase queue awareness columns missing; retrying update without queue state. "
                            "Apply migration 20260521000002_startup_queue_awareness.sql."
                        )
                    continue
                self.logger.error("Supabase column update failed for %s: %s", startup_id, e)
                raise
        self.logger.error("Supabase column update failed after legacy column retries for %s", startup_id)
        raise RuntimeError("Supabase column update failed after legacy column retries")

    def _changed_row_columns(self, st: Startup, keys: Tuple[str, ...]) -> dict:
        """Project a Startup into the subset of row columns named in keys."""
        row = _dict_to_row(st.to_dict(), self._user_id)
        return {k: row[k] for k in keys if k in row}

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
        changed_keys = set(patch.keys())
        if "queue_reason" not in patch and "priority_reason" not in patch:
            merged.queue_reason, merged.priority_reason = _queue_reasons_for_startup(merged)
            changed_keys.update(("queue_reason", "priority_reason"))
        merged.update_timestamp()
        changed_keys.add("updated_at")
        # Targeted write: only the patched columns (+ recomputed queue + updated_at),
        # so unrelated heavy JSONB (e.g. review_info) is not rewritten.
        self._update_startup_columns(startup_id, self._changed_row_columns(merged, tuple(changed_keys)))
        return True

    def get_list_projection_rows(
        self,
        *,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> Optional[List[dict]]:
        """Thin columns for GET /api/startups list (low egress).

        Returns None if the query failed (caller must not fall back to full-row fetch).
        Returns [] when the query succeeded but the tenant has no rows.
        """
        lim = max(1, min(int(limit if limit is not None else 500), 500))
        off = max(0, int(offset or 0))
        try:
            r = self._execute_with_retry(
                lambda: (
                    self._client.table(TABLE)
                    .select(_LIST_SELECT)
                    .eq("user_id", self._user_id)
                    .order("updated_at", desc=True)
                    .range(off, off + lim - 1)
                    .execute()
                )
            )
        except Exception as e:
            if _is_missing_resolution_status_error(e):
                # Resolution-status migration not applied yet; retry with the same
                # projection minus that column so queue awareness is preserved.
                self.logger.warning(
                    "list_resolution_status column missing; apply the resolution status "
                    "projection migration to badge lookup resolution states in the list."
                )
                try:
                    no_resolution_select = _LIST_SELECT.replace("list_resolution_status, ", "")
                    r = self._execute_with_retry(
                        lambda: (
                            self._client.table(TABLE)
                            .select(no_resolution_select)
                            .eq("user_id", self._user_id)
                            .order("updated_at", desc=True)
                            .range(off, off + lim - 1)
                            .execute()
                        )
                    )
                    return list((r.data or []) if hasattr(r, "data") else [])
                except Exception as retry_e:
                    e = retry_e
            if _is_missing_unresolved_at_error(e) or _is_missing_queue_awareness_error(e):
                self.logger.warning(
                    "List projection queue column missing; using legacy projection. "
                    "Apply unresolved/queue awareness migrations to enable full queue state."
                )
                try:
                    r = self._execute_with_retry(
                        lambda: (
                            self._client.table(TABLE)
                            .select(_LIST_SELECT_LEGACY_NO_UNRESOLVED)
                            .eq("user_id", self._user_id)
                            .order("updated_at", desc=True)
                            .range(off, off + lim - 1)
                            .execute()
                        )
                    )
                except Exception as legacy_e:
                    self.logger.warning("Legacy list projection select failed: %s", legacy_e)
                    return None
                return list((r.data or []) if hasattr(r, "data") else [])
            self.logger.warning("List projection select failed: %s", e)
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

    def prepare_rerun_startup(
        self,
        startup_id: str,
        *,
        operator_context: str,
        lookup_id: Optional[str] = None,
        pipeline_run_id: Optional[str] = None,
    ) -> Optional[str]:
        """Prepare an EXISTING row for a post-hoc re-review with operator context.

        The scout profile, company resolution, and sources are kept EXACTLY as-is —
        no re-discovery. The operator context (private facts + fetched link content)
        is stamped on scout_info where the reviewer prompt reads it. Existing
        review/partner/memo/human ruling are deliberately preserved until the
        replacement stages finish; `force_rerun=True` bypasses the old downstream
        data without making cancel/retry hide the startup from the queue.
        Full-row upsert on purpose: it also refreshes every derived list_*
        projection column, which a partial patch would leave stale.
        """
        sid = (startup_id or "").strip()
        existing = self.get_startup(sid) if sid else None
        if existing is None:
            self.logger.warning("prepare_rerun_startup: no existing row for %s; skipping", sid)
            return None
        pr = (pipeline_run_id or "").strip() or None
        scout_info = existing.scout_info
        scout_info.operator_context = operator_context
        if lookup_id:
            # New lookup correlation id so the UI's pending-match keys on the re-run.
            scout_info.lookup_id = lookup_id
        startup = existing
        startup.scout_info = scout_info
        startup.update_timestamp()
        # Scout stage did not run — keep its original trace for provenance.
        startup.agent_trace = existing.agent_trace
        startup.queue_reason, startup.priority_reason = _queue_reasons_for_startup(startup)
        if pr:
            upsert_pipeline_state(
                self._client,
                user_id=self._user_id,
                startup_id=sid,
                pipeline_run_id=pr,
                status="ingesting",
            )
        self.upsert_startup_dict(startup.to_dict())
        self.logger.info(
            "Prepared re-review in place (scout kept): %s (%s)", scout_info.name, sid
        )
        return sid

    def mark_existing_rerun_cancelled(self, lookup_id: str) -> Optional[str]:
        """Restore memo readiness for a cancelled in-place re-review.

        Re-reviews preserve the previous partner/memo while a replacement run is
        pending. If the user cancels after `prepare_rerun_startup`, mark the
        pipeline state ready again so the memo endpoint serves the preserved memo
        instead of reporting an endless generating state.
        """
        lid = (lookup_id or "").strip()
        if not lid:
            return None
        try:
            r = (
                self._client.table(TABLE)
                .select("startup_id, partner_info, investment_memo_markdown")
                .eq("user_id", self._user_id)
                .eq("list_lookup_id", lid)
                .limit(1)
                .execute()
            )
        except Exception as e:
            self.logger.warning("mark_existing_rerun_cancelled select failed: %s", e)
            return None
        rows = (r.data or []) if hasattr(r, "data") else []
        if not rows:
            return None
        row = rows[0]
        sid = str(row.get("startup_id") or "").strip()
        if not sid:
            return None
        # Only restore readiness for existing decided/memo-bearing rows. Fresh
        # on-demand lookups can legitimately be cancelled before any decision.
        if not row.get("partner_info") and not row.get("investment_memo_markdown"):
            return None
        state = get_pipeline_state_row(self._client, user_id=self._user_id, startup_id=sid)
        pr = str((state or {}).get("pipeline_run_id") or "").strip()
        if pr:
            upsert_pipeline_state(
                self._client,
                user_id=self._user_id,
                startup_id=sid,
                pipeline_run_id=pr,
                status="ready",
            )
        return sid

    def add_startup(
        self,
        scout_info: ScoutInfo,
        *,
        pipeline_run_id: Optional[str] = None,
        financials: Optional[Financials] = None,
    ) -> str:
        pr = (pipeline_run_id or "").strip() or None
        startup = Startup(
            startup_id=scout_info.startup_id,
            scout_info=scout_info,
            financials=financials or Financials(),
        )
        startup.agent_trace = merge_stage_trace(
            startup.agent_trace,
            "scout",
            build_scout_trace(
                scout_info.model_dump(mode="json"),
                pipeline_run_id=pr,
                active_thesis=None,
                settings=self._settings_for_trace(),
            ),
        )
        startup.unresolved_at = startup.created_at
        startup.first_seen_at = startup.created_at
        startup.queue_reason, startup.priority_reason = _queue_reasons_for_startup(startup)
        try:
            r = (
                self._client.table(TABLE)
                .select("startup_id")
                .eq("user_id", self._user_id)
                .eq("startup_id", startup.startup_id)
                .limit(1)
                .execute()
            )
            if ((r.data or []) if hasattr(r, "data") else []):
                self.logger.warning("Startup %s already exists; skipping add", startup.startup_id)
                return str(r.data[0].get("startup_id") or startup.startup_id)
        except Exception as e:
            self.logger.warning("Duplicate id check select failed: %s", e)

        new_name = (startup.scout_info.name or "").strip()
        existing_name_id = self._find_startup_id_by_name(new_name)
        if existing_name_id:
            self.logger.info(
                "Duplicate company name detected in storage; skipping add: %s",
                startup.scout_info.name,
            )
            return existing_name_id

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
            # The normalized tenant/name unique index closes the preflight race.
            # If another lookup won between SELECT and INSERT, continue with its
            # canonical row instead of surfacing a phantom failure.
            existing_name_id = self._find_startup_id_by_name(new_name)
            if existing_name_id and existing_name_id != sid:
                if pr:
                    try:
                        self._client.table("startup_pipeline_state").delete().eq(
                            "user_id", self._user_id
                        ).eq("startup_id", sid).execute()
                    except Exception as cleanup_error:
                        self.logger.warning(
                            "Could not remove raced lookup pipeline state %s: %s",
                            sid,
                            cleanup_error,
                        )
                self.logger.info(
                    "Concurrent duplicate resolved to existing startup %s", existing_name_id
                )
                return existing_name_id
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

    def _find_startup_id_by_name(self, company_name: str) -> Optional[str]:
        """Return a case-insensitive exact tenant/name match, if one exists."""
        name = (company_name or "").strip()
        if not name:
            return None
        try:
            response = (
                self._client.table(TABLE)
                .select("startup_id,display_name")
                .eq("user_id", self._user_id)
                .ilike("display_name", name)
                .limit(20)
                .execute()
            )
        except Exception as exc:
            self.logger.warning("Duplicate name check select failed: %s", exc)
            return None
        normalized = name.casefold()
        rows = (response.data or []) if hasattr(response, "data") else []
        for row in rows:
            if str(row.get("display_name") or "").strip().casefold() == normalized:
                startup_id = str(row.get("startup_id") or "").strip()
                if startup_id:
                    return startup_id
        return None

    def add_review(
        self,
        startup_id: str,
        review_info: ReviewInfo,
        *,
        pipeline_run_id: Optional[str] = None,
        enrichment_review_output: Optional[Dict[str, Any]] = None,
        enrichment_gap_reference_urls: Optional[List[str]] = None,
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
        if enrichment_review_output is not None:
            from utils.scout_post_review_enrichment import merge_scout_info_enrichment

            st.scout_info = merge_scout_info_enrichment(
                st.scout_info,
                review_output=enrichment_review_output,
                gap_reference_urls=enrichment_gap_reference_urls,
            )
        st.review_info = review_info
        review_payload = (
            dict(enrichment_review_output)
            if isinstance(enrichment_review_output, dict)
            else review_info.model_dump(mode="json")
        )
        st.agent_trace = merge_stage_trace(
            st.agent_trace,
            "reviewer",
            build_review_trace(
                review_payload,
                scout=st.scout_info.model_dump(mode="json"),
                pipeline_run_id=pr,
                gap_reference_urls=enrichment_gap_reference_urls,
                settings=self._settings_for_trace(),
            ),
        )
        st.queue_reason, st.priority_reason = _queue_reasons_for_startup(st)
        st.update_timestamp()
        try:
            # Only review-stage columns change; leave partner_info/financials/etc. untouched.
            self._update_startup_columns(
                startup_id,
                self._changed_row_columns(
                    st,
                    ("scout_info", "review_info", "agent_trace", "queue_reason", "priority_reason", "updated_at"),
                ),
            )
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
        evaluation_manifest_identity: Optional[
            EvaluationManifestIdentity | Dict[str, Any]
        ] = None,
    ) -> bool:
        pr = (pipeline_run_id or "").strip() or None
        if pr and evaluation_manifest_identity is None:
            raise ValueError(
                "evaluation_manifest_identity is required for governed persistence"
            )
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
        handoff_quality = handoff_quality_from_trace(st.agent_trace)
        st.agent_trace = merge_stage_trace(
            st.agent_trace,
            "partner",
            build_partner_trace(
                partner_info.model_dump(mode="json"),
                scout=st.scout_info.model_dump(mode="json"),
                review=st.review_info.model_dump(mode="json") if st.review_info else {},
                pipeline_run_id=pr,
                handoff_quality=handoff_quality,
                settings=self._settings_for_trace(),
            ),
        )
        if pr:
            from evaluation.manifest import (
                build_evaluation_manifest,
                validate_evaluation_manifest_for_persistence,
            )

            if str(getattr(st.scout_info, "operator_context", None) or "").strip():
                evaluation_path = "rerun"
            elif getattr(st.scout_info, "origin_type", None) == "on_demand_lookup":
                evaluation_path = "manual_lookup"
            else:
                evaluation_path = "autonomous_discovery"
            manifest = build_evaluation_manifest(
                st,
                pipeline_run_id=pr,
                evaluation_path=evaluation_path,
                manifest_identity=evaluation_manifest_identity,
            )
            manifest = validate_evaluation_manifest_for_persistence(
                manifest,
                manifest_identity=evaluation_manifest_identity,
                user_id=self._user_id,
            )
            trace = dict(st.agent_trace) if isinstance(st.agent_trace, dict) else {}
            trace["evaluation_manifest"] = manifest.model_dump(mode="json")
            st.agent_trace = trace
        st.unresolved_at = partner_info.partnered_at if partner_info.human_review_required else None
        st.queue_reason, st.priority_reason = _queue_reasons_for_startup(st)
        cols = ["partner_info", "agent_trace", "unresolved_at", "queue_reason", "priority_reason", "updated_at"]
        if investment_memo_markdown is not None:
            st.investment_memo_markdown = investment_memo_markdown
            cols.append("investment_memo_markdown")
        st.update_timestamp()
        try:
            # Only partner-stage columns change; review_info (large) is not rewritten.
            self._update_startup_columns(startup_id, self._changed_row_columns(st, tuple(cols)))
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
        if pr:
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
        self._update_startup_columns(startup_id, self._changed_row_columns(st, ("financials", "updated_at")))
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

    def remove_startup(self, startup_id: str) -> bool:
        """Delete one tenant-scoped compatibility row blocked by identity review."""
        sid = str(startup_id or "").strip()
        if not sid:
            return False
        try:
            response = (
                self._client.table(TABLE)
                .delete(returning="representation")
                .eq("user_id", self._user_id)
                .eq("startup_id", sid)
                .execute()
            )
        except Exception as exc:
            self.logger.error("remove_startup failed for %s: %s", sid, exc)
            raise
        return bool(getattr(response, "data", None) or [])

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
                # Project only the version-id sub-field instead of the full review_info
                # blob (large, multi-review JSON) — this only needs to know if it's set.
                r = (
                    self._client.table(TABLE)
                    .select("startup_id,vid:review_info->>fund_thesis_version_id")
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
                vid = row.get("vid")
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
        recommendation = normalize_recommendation(decision)
        if decision is not None and recommendation is None:
            return []
        lim = limit if limit is not None else 500
        try:
            q = (
                self._client.table(TABLE)
                .select(_DECISION_SCAN_SELECT)
                .eq("user_id", self._user_id)
                .not_.is_("partner_info", "null")
                .order("updated_at", desc=True)
                .limit(lim)
            )
            if recommendation is not None:
                q = q.eq("partner_decision", recommendation)
            r = q.execute()
        except Exception as e:
            self.logger.warning("get_startups_with_decision failed: %s", e)
            return self._legacy_get_startups_with_decision(decision, limit)
        rows = (r.data or []) if hasattr(r, "data") else []
        startups = self._rows_to_startups(rows, skip_invalid=True)
        if recommendation is not None:
            startups = [
                s for s in startups
                if s.partner_info and s.partner_info.recommendation == recommendation
            ]
        if limit is not None:
            startups = startups[:limit]
        return startups

    def _legacy_get_startups_with_decision(
        self, decision: Optional[str], limit: Optional[int]
    ) -> List[Startup]:
        with_decision = [s for s in self.get_all_startups(skip_invalid=True) if s.partner_info is not None]
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
            self.logger.debug("count_undecided failed; falling back to local count: %s", e)
            return sum(
                1
                for s in self.get_all_startups(skip_invalid=True)
                if s.review_info is not None and s.partner_info is None
            )

    def replace_all(self, items: List[dict]) -> None:
        """Make the tenant's rows exactly ``items``.

        Upsert-first, prune-after — NOT delete-everything-then-reinsert. The old
        order ran a DELETE of all rows up front, so any failure (EAGAIN, OOM, a
        bad row mid-batch) between the delete and the re-insert left the tenant
        with a partial or empty table and no rollback. Supabase's HTTP client has
        no multi-statement transaction, so instead we (1) upsert every new row,
        and only once they all succeed (2) delete the rows that are no longer
        present. A failure during step 1 leaves the existing data intact.
        """
        if not isinstance(items, list):
            raise TypeError("items must be a list of dicts")
        chunk = 80
        new_ids: set[str] = set()
        # 1) Upsert all new/updated rows first.
        for i in range(0, len(items), chunk):
            batch = [_dict_to_row(d, self._user_id) for d in items[i : i + chunk]]
            for row in batch:
                sid = row.get("startup_id")
                if sid:
                    new_ids.add(str(sid))
            if not batch:
                continue
            try:
                self._client.table(TABLE).upsert(
                    batch, on_conflict="user_id,startup_id", returning="minimal"
                ).execute()
            except Exception as e:
                self.logger.error("replace_all upsert chunk failed: %s", e)
                raise
        # 2) Only after all upserts succeed, prune rows that are no longer present.
        try:
            r = (
                self._client.table(TABLE)
                .select("startup_id")
                .eq("user_id", self._user_id)
                .execute()
            )
            existing_ids = {
                str(row.get("startup_id"))
                for row in (getattr(r, "data", None) or [])
                if isinstance(row, dict) and row.get("startup_id")
            }
        except Exception as e:
            self.logger.error("replace_all prune scan failed (existing data left intact): %s", e)
            raise
        stale = list(existing_ids - new_ids)
        for i in range(0, len(stale), chunk):
            ids = stale[i : i + chunk]
            try:
                self._client.table(TABLE).delete().eq("user_id", self._user_id).in_(
                    "startup_id", ids
                ).execute()
            except Exception as e:
                self.logger.error("replace_all prune delete failed: %s", e)
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
            # User-intentional lookups are never pruned: weak evidence is a visible
            # PARTIAL/NEEDS_REVIEW state in the UI, not grounds for deletion.
            if str(scout.get("origin_type") or "").strip().lower() == "on_demand_lookup":
                continue
            if scout.get("company_resolution") or scout.get("resolution_status"):
                continue
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
        from utils.adapters import scout_output_to_scout_info, financials_from_scout_output

        scout_info = scout_output_to_scout_info(scout_output)
        financials = financials_from_scout_output(scout_output)
        return self.add_startup(
            scout_info, pipeline_run_id=pipeline_run_id, financials=financials
        )

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
