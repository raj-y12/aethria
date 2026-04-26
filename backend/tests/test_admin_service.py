from datetime import datetime, timezone


def test_build_admin_overview_combines_clerk_sessions_settings_and_stats():
    from admin_service import build_admin_overview_from_rows

    now = datetime(2026, 4, 26, 12, 30, tzinfo=timezone.utc)

    overview = build_admin_overview_from_rows(
        clerk_users=[
            {
                "id": "user_a",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "primary_email_address_id": "email_a",
                "email_addresses": [{"id": "email_a", "email_address": "ada@example.com"}],
                "created_at": 1777200000000,
            }
        ],
        sessions_by_user={
            "user_a": [
                {
                    "id": "sess_a",
                    "status": "active",
                    "last_active_at": 1777203000000,
                }
            ]
        },
        settings_rows=[
            {
                "user_id": "user_a",
                "data": {
                    "agent_config": {
                        "scouts_enabled": True,
                        "reviewers_enabled": False,
                        "partners_enabled": True,
                        "agents_status": "running",
                        "agents_last_started_at": "2026-04-26T12:00:00+00:00",
                    }
                },
            }
        ],
        startup_rows=[
            {"user_id": "user_a", "partner_decision": "INVEST"},
            {"user_id": "user_a", "partner_decision": "PASS"},
            {"user_id": "user_b", "partner_decision": None},
        ],
        pipeline_rows=[
            {
                "user_id": "user_a",
                "timestamp": "2026-04-26T12:05:00+00:00",
                "startups_found": 2,
                "reviewed_count": 1,
                "decisions_made": 1,
                "escalations_count": 0,
            },
            {
                "user_id": "user_a",
                "timestamp": "2026-04-24T12:05:00+00:00",
                "startups_found": 10,
                "reviewed_count": 10,
                "decisions_made": 10,
                "escalations_count": 2,
            },
        ],
        loop_status_by_user={"user_a": True},
        now=now,
    )

    assert overview["totals"] == {
        "users": 2,
        "active_sessions": 1,
        "users_with_agents_enabled": 1,
        "startups": 3,
        "pipeline_runs_24h": 1,
    }

    user_a = overview["users"][0]
    assert user_a["user_id"] == "user_a"
    assert user_a["email"] == "ada@example.com"
    assert user_a["display_name"] == "Ada Lovelace"
    assert user_a["is_logged_in"] is True
    assert user_a["active_sessions_count"] == 1
    assert user_a["last_active_at"] == "2026-04-26T11:30:00+00:00"
    assert user_a["agents_enabled"] is True
    assert user_a["agent_config"]["scouts_enabled"] is True
    assert user_a["agent_config"]["reviewers_enabled"] is False
    assert user_a["agent_config"]["partners_enabled"] is True
    assert user_a["agent_config"]["agents_status"] == "running"
    assert user_a["loop_alive"] is True
    assert user_a["startup_stats"]["total"] == 2
    assert user_a["startup_stats"]["partner_decisions"] == {"INVEST": 1, "PASS": 1}
    assert user_a["pipeline_stats"]["runs_24h"] == 1
    assert user_a["pipeline_stats"]["latest_activity_at"] == "2026-04-26T12:05:00+00:00"

    user_b = overview["users"][1]
    assert user_b["user_id"] == "user_b"
    assert user_b["email"] is None
    assert user_b["startup_stats"]["total"] == 1

