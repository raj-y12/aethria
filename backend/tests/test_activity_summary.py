from api import _aggregate_activity_totals, _backend_to_frontend


def test_activity_totals_split_agent_and_human_decisions():
    totals = _aggregate_activity_totals(
        [
            {"startups_found": 2, "reviewed_count": 3, "decisions_made": 4, "escalations_count": 1},
            {"startups_found": 1, "reviewed_count": 0, "decisions_made": 2, "escalations_count": 0},
        ],
        human_reviewed=5,
        open_in_progress=7,
    )
    assert totals["decided"] == 6
    assert totals["agent_decided"] == 6
    assert totals["human_reviewed"] == 5
    assert totals["open_in_progress"] == 7


def test_backend_to_frontend_surfaces_unresolved_at():
    raw = {
        "startup_id": "s1",
        "scout_info": {
            "name": "TinyPay",
            "one_line": "Payments ops",
            "sector": "Fintech",
            "why_now": "Now",
            "confidence_score": 0.7,
            "scout_type": "market_driven",
        },
        "unresolved_at": "2026-05-12T10:00:00+00:00",
    }
    out = _backend_to_frontend(raw)
    assert out["unresolved_at"] == "2026-05-12T10:00:00+00:00"
    assert out["timestamps"]["unresolved_at"] == "2026-05-12T10:00:00+00:00"
