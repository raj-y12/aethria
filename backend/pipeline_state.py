"""
Deterministic pipeline state for startup memo readiness.
Explicit user_id on every call; pipeline_run_id for cross-service tracing.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from tenant_context import require_user_id
from batch4a.context import get_state as get_batch4a_state

logger = logging.getLogger("pipeline_state")

PipelineStatus = Literal[
    "pending",
    "ingesting",
    "scouting",
    "processing_signals",
    "generating_memo",
    "writing_memo",
    "ready",
    "failed",
]

VALID_STATUSES: tuple[str, ...] = (
    "pending",
    "ingesting",
    "scouting",
    "processing_signals",
    "generating_memo",
    "writing_memo",
    "ready",
    "failed",
)

_TABLE = "startup_pipeline_state"


def _parse_uuid(run_id: Optional[str]) -> Optional[str]:
    if not run_id or not str(run_id).strip():
        return None
    s = str(run_id).strip()
    if re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        s,
        re.I,
    ):
        return s
    return None


def pipeline_stage_log(
    pipeline_run_id: Optional[str],
    *,
    startup_id: str,
    user_id: str,
    stage: str,
    phase: Literal["STARTED", "DONE", "FAILED", "SKIPPED", "BLOCKED", "RETRIED"],
) -> None:
    rid = (pipeline_run_id or "").strip() or "—"
    uid = (user_id or "").strip()
    sid = (startup_id or "").strip()
    logger.info(
        "[%s] startup_id=%s user_id=%s stage=%s status=%s",
        rid,
        sid,
        uid[:24] if uid else "",
        stage,
        phase,
    )


def upsert_pipeline_state(
    client: Any,
    *,
    user_id: str,
    startup_id: str,
    pipeline_run_id: str,
    status: PipelineStatus,
    error: Optional[str] = None,
) -> None:
    uid = require_user_id(user_id, context="upsert_pipeline_state")
    sid = (startup_id or "").strip()
    if not sid:
        return
    pr = _parse_uuid(pipeline_run_id)
    if not pr:
        logger.warning("upsert_pipeline_state: invalid pipeline_run_id, skipping")
        return
    if status not in VALID_STATUSES:
        logger.warning("upsert_pipeline_state: invalid status %s", status)
        return
    err = (error or "").strip()[:2000] if error else None
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    row = {
        "user_id": uid,
        "startup_id": sid,
        "pipeline_run_id": pr,
        "status": status,
        "updated_at": now,
        "error": err,
    }
    state = get_batch4a_state()
    if state is not None:
        state.upsert_pipeline_state(row)
        return
    logger.warning("upsert_pipeline_state: Batch4A state unavailable, skipping startup_id=%s", sid)


def get_pipeline_state_row(
    client: Any,
    *,
    user_id: str,
    startup_id: str,
) -> Optional[dict]:
    uid = require_user_id(user_id, context="get_pipeline_state_row")
    sid = (startup_id or "").strip()
    if not sid:
        return None
    state = get_batch4a_state()
    if state is not None:
        # Batch4AState.pipeline_states is scoped by construction (loaded via
        # Batch4ARepository.load_state(user_id), filtered "where user_id=$1"
        # at the query level) -- the dict itself never holds another
        # tenant's rows. But this function accepts and validates its own
        # user_id param without ever checking it against the ambient
        # ContextVar-scoped state it actually reads from, so a future caller
        # that mismatches the two (e.g. a batched/concurrent runner passing
        # the wrong user_id against an already-set context) would silently
        # get another tenant's pipeline status with no error. Fail closed.
        if state.user_id != uid:
            logger.error(
                "get_pipeline_state_row: user_id mismatch -- requested=%s ambient_state=%s startup_id=%s",
                uid, state.user_id, sid,
            )
            return None
        return state.get_pipeline_state(sid)
    logger.warning("get_pipeline_state_row: Batch4A state unavailable, returning no state for startup_id=%s", sid)
    return None


def api_memo_status_label(db_status: Optional[str]) -> str:
    """Map DB status to API `status` field (generating | ready | failed)."""
    if db_status == "ready":
        return "ready"
    if db_status == "failed":
        return "failed"
    if db_status in (None, ""):
        return "generating"
    return "generating"
