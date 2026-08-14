"""Temporary Supabase policy-upgrade adapter isolated for the 5D cleanup."""

from __future__ import annotations

from typing import Any, Callable, Dict


def apply_upgrade_transaction(
    *,
    service_client_factory: Callable[[], Any],
    user_id: str,
    expected_policy_id: str,
    expected_policy_hash: str,
    policy_record: Dict[str, Any],
    settings_patch: Dict[str, Any],
) -> Dict[str, Any]:
    params = {
        "p_user_id": user_id,
        "p_expected_policy_id": expected_policy_id or None,
        "p_expected_policy_hash": expected_policy_hash or None,
        "p_new_policy_id": policy_record["policy_version_id"],
        "p_new_policy_hash": policy_record["policy_hash"],
        "p_policy_record": policy_record,
        "p_settings_data": settings_patch,
    }
    response = service_client_factory().rpc(
        "upgrade_fund_policy", params
    ).execute()
    data = getattr(response, "data", None)
    if isinstance(data, list) and len(data) == 1:
        data = data[0]
    if not isinstance(data, dict) or data.get("status") != "applied":
        raise RuntimeError(
            "Published policy compatibility transaction returned an invalid result"
        )
    return data
