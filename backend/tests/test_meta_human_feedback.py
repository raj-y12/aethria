"""Human analyst decisions in meta_mutation_log feed MetaAnalyser.human_feedback."""
from meta.analyser import MetaAnalyser


def test_build_human_feedback_empty():
    a = MetaAnalyser("user_test")
    assert a._build_human_feedback([]) == {
        "recent_count": 0,
        "by_outcome": {},
        "disagreed_with_ai_count": 0,
        "sample_notes": [],
    }


def test_build_human_feedback_counts_and_samples():
    a = MetaAnalyser("user_test")
    log = [
        {"type": "prompt_proposal", "agent_target": "MarketDrivenScout"},
        {
            "type": "human_decision",
            "human_decision": "YES",
            "disagreed_with_ai": True,
            "notes": "Strong team",
            "resolved_at": "2026-01-02T00:00:00",
        },
        {
            "type": "human_decision",
            "human_decision": "NO",
            "disagreed_with_ai": False,
            "notes": "Sector fit weak",
            "resolved_at": "2026-01-01T00:00:00",
        },
    ]
    out = a._build_human_feedback(log)
    assert out["recent_count"] == 2
    assert out["by_outcome"] == {"YES": 1, "NO": 1, "MAYBE": 0}
    assert out["disagreed_with_ai_count"] == 1
    assert "Strong team" in (out["sample_notes"][0] if out["sample_notes"] else "")
