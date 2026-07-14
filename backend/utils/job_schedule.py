"""Atomic tenant-scoped schedule claims for reconstructed pipeline engines."""
from __future__ import annotations

from datetime import datetime
from typing import Mapping, Optional, Set

from supabase_client import get_service_client
from tenant_context import require_user_id
from utils.timeutil import ensure_aware


def claim_due_jobs(
    user_id: str,
    intervals: Mapping[str, int],
    *,
    now: Optional[datetime] = None,
) -> Set[str]:
    """Atomically claim and return tenant jobs whose interval has elapsed."""
    uid = require_user_id(user_id, context="claim_due_jobs")
    normalized = {}
    for raw_name, raw_interval in intervals.items():
        name = str(raw_name).strip()
        if name:
            normalized[name] = max(0, int(raw_interval))
    if not normalized:
        return set()

    params = {"p_user_id": uid, "p_intervals": normalized}
    if now is not None:
        params["p_now"] = ensure_aware(now).isoformat().replace("+00:00", "Z")
    response = get_service_client().rpc("claim_due_agent_jobs", params).execute()
    rows = (response.data or []) if hasattr(response, "data") else []
    due: Set[str] = set()
    for row in rows:
        value = row.get("job_name") if isinstance(row, dict) else row
        name = str(value or "").strip()
        if name:
            due.add(name)
    return due
