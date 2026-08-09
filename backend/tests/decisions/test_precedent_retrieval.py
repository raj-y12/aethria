import json

from decisions.precedent import _first_ruling, rank_precedents


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _RepositoryConnection:
    def __init__(self, target, fetches):
        self.target = target
        self.fetches = list(fetches)
        self.calls = []

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return self.target

    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args))
        return self.fetches.pop(0)


class _RepositoryPool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _Acquire(self.connection)


def _case(
    evaluation_id,
    *,
    opportunity_id="opportunity-a",
    company_id="company-a",
    sector="infrastructure",
    stage="pre-seed",
    geography="uk",
    thesis_version_id="thesis-1",
    scores=None,
    recommendation="advance",
    ruling="invest",
    override_type="founder_judgment",
    evidence_coverage=0.8,
    decision_time="2026-01-01T00:00:00+00:00",
    outcomes=None,
    unpaired_rulings=0,
):
    if scores is None:
        scores = {"technical": 8.0, "distribution": 4.0}
    claims = [
        {"claim_id": f"{evaluation_id}-sector", "claim_type": "sector", "normalized_value": sector},
        {"claim_id": f"{evaluation_id}-stage", "claim_type": "stage", "normalized_value": stage},
        {"claim_id": f"{evaluation_id}-geo", "claim_type": "geography", "normalized_value": geography},
    ]
    return {
        "opportunity": {"opportunity_id": opportunity_id, "company_id": company_id, "context_key": "primary"},
        "cases": [{
            "decision_time": decision_time,
            "evaluation": {
                "evaluation_id": evaluation_id,
                "thesis_version_id": thesis_version_id,
                "policy_version_id": f"policy-{thesis_version_id}",
                "claim_snapshot": claims,
            },
            "criteria": [
                {"criterion": name, "score": score, "confidence": 0.8}
                for name, score in scores.items()
            ],
            "recommendation": {"recommendation_id": f"rec-{evaluation_id}", "recommended_state": recommendation},
            "rulings": ([{
                "ruling_id": f"ruling-{evaluation_id}",
                "recommendation_id": f"rec-{evaluation_id}",
                "decision": ruling,
                "override_type": override_type,
                "interpretation": {"evidence_influence": {"status": "explicit"}},
            }] if ruling else []),
        }],
        "outcomes": outcomes or [],
        "unpaired_rulings": [{} for _ in range(unpaired_rulings)],
    }


def test_rank_precedents_excludes_self_and_explains_structural_match():
    target = _case("evaluation-target")
    candidates = [
        target,
        _case("evaluation-match", opportunity_id="opportunity-b"),
        _case("evaluation-different", opportunity_id="opportunity-c", company_id="company-b", sector="healthcare", stage="series-a", geography="us", scores={"technical": 2.0}),
    ]

    results = rank_precedents(target, candidates, limit=10)

    assert [item["evaluation_id"] for item in results] == ["evaluation-match"]
    match = results[0]
    assert match["score"] > 0
    assert match["component_scores"]["sector"] > 0
    assert match["component_scores"]["criterion_profile"] > 0
    assert any("pre-seed infrastructure" in reason.lower() for reason in match["match_reasons"])
    assert "outcome" not in " ".join(match["scoring_dimensions"]).lower()


def test_rank_precedents_makes_mandate_drift_visible_and_reduces_score():
    target = _case("evaluation-target", thesis_version_id="thesis-current")
    same = _case("evaluation-same", thesis_version_id="thesis-current")
    drifted = _case("evaluation-drifted", thesis_version_id="thesis-old")

    results = rank_precedents(target, [same, drifted], limit=10)

    assert [item["evaluation_id"] for item in results] == ["evaluation-same", "evaluation-drifted"]
    assert results[0]["component_scores"]["mandate"] > results[1]["component_scores"]["mandate"]
    assert any("mandate" in reason.lower() for reason in results[1]["limitations"] + results[1]["match_reasons"])


def test_rank_precedents_flags_incomplete_cases_and_keeps_outcomes_as_context_only():
    target = _case("evaluation-target")
    incomplete = _case(
        "evaluation-incomplete", recommendation=None, ruling=None,
        unpaired_rulings=1, outcomes=[{"outcome_type": "financing", "valence": "positive"}],
    )

    results = rank_precedents(target, [incomplete], limit=10)

    assert len(results) == 1
    result = results[0]
    assert result["incomplete"] is True
    assert result["later_outcomes"] == incomplete["outcomes"]
    assert result["outcome_context_used_for_scoring"] is False
    assert any("unpaired" in item.lower() for item in result["limitations"])


def test_rank_precedents_is_deterministic_with_tie_breaking_and_sparse_data_is_excluded():
    target = _case("evaluation-target")
    first = _case("evaluation-a", opportunity_id="opportunity-a")
    second = _case("evaluation-b", opportunity_id="opportunity-b")
    sparse = _case("evaluation-sparse", opportunity_id="opportunity-c", company_id="company-b", sector="", stage="", geography="", scores={})

    first_run = rank_precedents(target, [second, sparse, first], limit=10)
    second_run = rank_precedents(target, [first, second, sparse], limit=10)

    assert [item["evaluation_id"] for item in first_run] == ["evaluation-a", "evaluation-b"]
    assert [item["evaluation_id"] for item in second_run] == ["evaluation-a", "evaluation-b"]


def test_first_ruling_selects_latest_chronologically_independent_of_input_order():
    episode = {
        "rulings": [
            {"ruling_id": "ruling-new", "decision": "invest", "created_at": "2026-01-01T09:30:00+00:00"},
            {"ruling_id": "ruling-old", "decision": "pass", "created_at": "2026-01-01T10:00:00+01:00"},
        ]
    }

    assert _first_ruling(episode)["ruling_id"] == "ruling-new"
    assert _first_ruling({"rulings": list(reversed(episode["rulings"]))})["ruling_id"] == "ruling-new"


def test_precedent_scoring_uses_latest_ruling_when_episode_has_multiple_rulings():
    target = _case("evaluation-target", ruling="invest")
    candidate = _case("evaluation-candidate", opportunity_id="opportunity-b")
    candidate["cases"][0]["rulings"] = [
        {"ruling_id": "ruling-new", "decision": "invest", "created_at": "2026-02-01T00:00:00+00:00"},
        {"ruling_id": "ruling-old", "decision": "pass", "created_at": "2026-01-01T00:00:00+00:00"},
    ]

    result = rank_precedents(target, [candidate])[0]

    assert result["component_scores"]["ruling"] == 0.5


def test_precedent_repository_is_tenant_scoped_and_keeps_outcomes_out_of_score():
    target = {
        "evaluation_id": "evaluation-target", "opportunity_id": "opportunity-target",
        "company_id": "company-target", "context_key": "primary",
        "claim_snapshot": json.dumps(_case("evaluation-target")["cases"][0]["evaluation"]["claim_snapshot"]),
        "thesis_version_id": "thesis-1", "policy_version_id": "policy-1",
        "created_at": "2026-01-01T00:00:00+00:00", "completed_at": "2026-01-01T00:00:00+00:00",
    }
    candidate = {**target, "evaluation_id": "evaluation-candidate", "opportunity_id": "opportunity-candidate"}
    recommendations = [
        {"evaluation_id": "evaluation-target", "recommendation_id": "rec-target", "opportunity_id": target["opportunity_id"], "recommended_state": "advance", "created_at": target["created_at"]},
        {"evaluation_id": "evaluation-candidate", "recommendation_id": "rec-candidate", "opportunity_id": candidate["opportunity_id"], "recommended_state": "advance", "created_at": candidate["created_at"]},
    ]
    criteria = [
        {"evaluation_id": eid, "criterion": "technical", "score": 8, "confidence": 0.8}
        for eid in ("evaluation-target", "evaluation-candidate")
    ]
    rulings = [
        {"ruling_id": "ruling-target", "opportunity_id": target["opportunity_id"], "recommendation_id": "rec-target", "decision": "invest", "created_at": target["created_at"], "override_type": "timing"},
        {"ruling_id": "ruling-candidate", "opportunity_id": candidate["opportunity_id"], "recommendation_id": "rec-candidate", "decision": "invest", "created_at": candidate["created_at"], "override_type": "timing"},
    ]
    outcomes = [{"opportunity_id": candidate["opportunity_id"], "outcome_type": "financing", "valence": "positive"}]
    connection = _RepositoryConnection(
        target,
        [[candidate], recommendations, criteria, rulings, [], outcomes],
    )

    from identity.repository import IdentityRepository

    import asyncio
    result = asyncio.run(
        IdentityRepository(_RepositoryPool(connection)).get_precedents(
            user_id="user-a", evaluation_id="evaluation-target", limit=10
        )
    )

    assert result["evaluation_id"] == "evaluation-target"
    assert result["precedents"][0]["evaluation_id"] == "evaluation-candidate"
    assert result["precedents"][0]["outcome_context_used_for_scoring"] is False
    assert all(call[2][0] == "user-a" for call in connection.calls)
