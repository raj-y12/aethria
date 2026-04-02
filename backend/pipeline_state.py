"""
Deterministic pipeline state for startup memo readiness (Supabase only).
Explicit user_id on every call; pipeline_run_id for cross-service tracing.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from tenant_context import require_user_id

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
    phase: Literal["STARTED", "DONE"],
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
    try:
        client.table(_TABLE).upsert(row, on_conflict="user_id,startup_id").execute()
    except Exception as e:
        logger.warning("upsert_pipeline_state failed startup_id=%s: %s", sid, e)


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
    try:
        r = (
            client.table(_TABLE)
            .select("pipeline_run_id,status,updated_at,error")
            .eq("user_id", uid)
            .eq("startup_id", sid)
            .limit(1)
            .execute()
        )
    except Exception as e:
        logger.warning("get_pipeline_state_row failed: %s", e)
        return None
    rows = (r.data or []) if hasattr(r, "data") else []
    if not rows:
        return None
    return rows[0]


def api_memo_status_label(db_status: Optional[str]) -> str:
    """Map DB status to API `status` field (generating | ready | failed)."""
    if db_status == "ready":
        return "ready"
    if db_status == "failed":
        return "failed"
    if db_status in (None, ""):
        return "generating"
    return "generating"
