"""Cross-tenant aggregation for the admin dashboard."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping

from admin.clerk import list_active_sessions_by_user, list_clerk_users


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _timestamp_ms_to_iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        millis = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(millis / 1000, tz=timezone.utc).isoformat()


def _primary_email(user: Mapping[str, Any]) -> str | None:
    emails = user.get("email_addresses")
    if not isinstance(emails, list):
        return None
    primary_id = user.get("primary_email_address_id")
    for email in emails:
        if isinstance(email, Mapping) and email.get("id") == primary_id:
            address = email.get("email_address")
            return str(address) if address else None
    for email in emails:
        if isinstance(email, Mapping) and email.get("email_address"):
            return str(email["email_address"])
    return None


def _display_name(user: Mapping[str, Any], fallback_user_id: str) -> str:
    pieces = [
        str(user.get("first_name") or "").strip(),
        str(user.get("last_name") or "").strip(),
    ]
    name = " ".join(piece for piece in pieces if piece).strip()
    return name or _primary_email(user) or fallback_user_id


def _agent_config(settings_data: Mapping[str, Any] | None) -> Dict[str, Any]:
    ac = settings_data.get("agent_config") if isinstance(settings_data, Mapping) else None
    ac = ac if isinstance(ac, Mapping) else {}
    return {
        "scouts_enabled": bool(ac.get("scouts_enabled")),
        "reviewers_enabled": bool(ac.get("reviewers_enabled")),
        "partners_enabled": bool(ac.get("partners_enabled")),
        "agents_status": str(ac.get("agents_status") or "stopped"),
        "agents_last_started_at": ac.get("agents_last_started_at"),
    }


def _user_ids_from_rows(*row_groups: Iterable[Mapping[str, Any]]) -> set[str]:
    out: set[str] = set()
    for rows in row_groups:
        for row in rows:
            uid = str(row.get("user_id") or "").strip()
            if uid:
                out.add(uid)
    return out


def build_admin_overview_from_rows(
    *,
    clerk_users: List[Dict[str, Any]],
    sessions_by_user: Mapping[str, List[Dict[str, Any]]],
    settings_rows: List[Dict[str, Any]],
    startup_rows: List[Dict[str, Any]],
    pipeline_rows: List[Dict[str, Any]],
    loop_status_by_user: Mapping[str, bool],
    now: datetime | None = None,
) -> Dict[str, Any]:
    generated_at = now or _now()
    generated_at = generated_at.astimezone(timezone.utc)
    cutoff_24h = generated_at - timedelta(hours=24)

    users_by_id = {
        str(user.get("id") or "").strip(): user
        for user in clerk_users
        if str(user.get("id") or "").strip()
    }
    settings_by_user = {
        str(row.get("user_id") or "").strip(): row.get("data")
        for row in settings_rows
        if str(row.get("user_id") or "").strip()
    }

    startup_counts: dict[str, int] = defaultdict(int)
    partner_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in startup_rows:
        uid = str(row.get("user_id") or "").strip()
        if not uid:
            continue
        startup_counts[uid] += 1
        decision = str(row.get("partner_decision") or "").strip()
        if decision:
            partner_counts[uid][decision] += 1

    pipeline_by_user: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in pipeline_rows:
        uid = str(row.get("user_id") or "").strip()
        if uid:
            pipeline_by_user[uid].append(row)

    all_user_ids = set(users_by_id)
    all_user_ids.update(sessions_by_user.keys())
    all_user_ids.update(settings_by_user.keys())
    all_user_ids.update(loop_status_by_user.keys())
    all_user_ids.update(_user_ids_from_rows(startup_rows, pipeline_rows))

    rows: list[Dict[str, Any]] = []
    for user_id in sorted(all_user_ids):
        clerk_user = users_by_id.get(user_id, {})
        sessions = sessions_by_user.get(user_id, [])
        active_sessions = [s for s in sessions if s.get("status") == "active"]
        last_active_at = max(
            (s.get("last_active_at") for s in active_sessions if s.get("last_active_at") is not None),
            default=None,
        )
        config = _agent_config(settings_by_user.get(user_id))
        agents_enabled = bool(
            config["scouts_enabled"] or config["reviewers_enabled"] or config["partners_enabled"]
        )

        user_pipeline_rows = pipeline_by_user.get(user_id, [])
        parsed_pipeline = [
            (parsed, row)
            for row in user_pipeline_rows
            if (parsed := _parse_iso(row.get("timestamp"))) is not None
        ]
        latest_pipeline = max((parsed for parsed, _row in parsed_pipeline), default=None)
        recent_pipeline = [(parsed, row) for parsed, row in parsed_pipeline if parsed >= cutoff_24h]

        rows.append(
            {
                "user_id": user_id,
                "email": _primary_email(clerk_user),
                "display_name": _display_name(clerk_user, user_id),
                "created_at": _timestamp_ms_to_iso(clerk_user.get("created_at")),
                "is_logged_in": bool(active_sessions),
                "active_sessions_count": len(active_sessions),
                "last_active_at": _timestamp_ms_to_iso(last_active_at),
                "agents_enabled": agents_enabled,
                "agent_config": config,
                "loop_alive": bool(loop_status_by_user.get(user_id)),
                "startup_stats": {
                    "total": startup_counts.get(user_id, 0),
                    "partner_decisions": dict(partner_counts.get(user_id, Counter())),
                },
                "pipeline_stats": {
                    "runs_24h": len(recent_pipeline),
                    "latest_activity_at": latest_pipeline.isoformat() if latest_pipeline else None,
                    "startups_found_24h": sum(int(row.get("startups_found") or 0) for _parsed, row in recent_pipeline),
                    "reviewed_24h": sum(int(row.get("reviewed_count") or 0) for _parsed, row in recent_pipeline),
                    "decisions_24h": sum(int(row.get("decisions_made") or 0) for _parsed, row in recent_pipeline),
                    "escalations_24h": sum(int(row.get("escalations_count") or 0) for _parsed, row in recent_pipeline),
                },
            }
        )

    return {
        "generated_at": generated_at.isoformat(),
        "totals": {
            "users": len(rows),
            "active_sessions": sum(row["active_sessions_count"] for row in rows),
            "users_with_agents_enabled": sum(1 for row in rows if row["agents_enabled"]),
            "startups": sum(row["startup_stats"]["total"] for row in rows),
            "pipeline_runs_24h": sum(row["pipeline_stats"]["runs_24h"] for row in rows),
        },
        "users": rows,
    }


def _fetch_rows(table: str, columns: str) -> List[Dict[str, Any]]:
    try:
        from legacy_supabase.client import get_service_client
        response = get_service_client().table(table).select(columns).execute()
        rows = response.data if hasattr(response, "data") else []
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def _known_user_ids(*row_groups: Iterable[Mapping[str, Any]], clerk_users: Iterable[Mapping[str, Any]]) -> set[str]:
    out = {
        str(user.get("id") or "").strip()
        for user in clerk_users
        if str(user.get("id") or "").strip()
    }
    out.update(_user_ids_from_rows(*row_groups))
    return out


def build_admin_overview(*, loop_status_by_user: Mapping[str, bool] | None = None, pipeline_rows: List[Dict[str, Any]] | None = None, startup_rows: List[Dict[str, Any]] | None = None, settings_rows: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    if settings_rows is None:
        settings_rows = _fetch_rows("settings", "user_id,data")
    if startup_rows is None:
        startup_rows = _fetch_rows("startups", "user_id,partner_decision")
    else:
        startup_rows = list(startup_rows)
    pipeline_rows = list(pipeline_rows or [])
    clerk_users = list_clerk_users()
    loop_status = dict(loop_status_by_user or {})
    user_ids = _known_user_ids(
        settings_rows,
        startup_rows,
        pipeline_rows,
        [{"user_id": uid} for uid in loop_status],
        clerk_users=clerk_users,
    )
    sessions_by_user = list_active_sessions_by_user(user_ids)
    return build_admin_overview_from_rows(
        clerk_users=clerk_users,
        sessions_by_user=sessions_by_user,
        settings_rows=settings_rows,
        startup_rows=startup_rows,
        pipeline_rows=pipeline_rows,
        loop_status_by_user=loop_status,
    )
