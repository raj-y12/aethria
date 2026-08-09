import json
import hashlib

from decisions.interpretation import build_ruling_interpretation_draft
from decisions.models import HumanRulingInput
from decisions.repository import DecisionRepository


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Connection:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def transaction(self):
        return _Transaction()

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return self.rows.pop(0)

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args))
        return "INSERT 0 1"


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        class Acquire:
            async def __aenter__(_self):
                return self.connection

            async def __aexit__(_self, exc_type, exc, tb):
                return False

        return Acquire()


def _context():
    return {
        "evaluation_id": "evaluation-1",
        "recommendation_id": "recommendation-1",
        "recommended_state": "advance",
        "claim_snapshot": [
            {
                "claim_id": "claim-1",
                "display_text": "customer retention is strong",
                "supporting_evidence_ids": ["evidence-1"],
                "contradicting_evidence_ids": [],
            }
        ],
        "criteria": [{"criterion_assessment_id": "criterion-1", "criterion": "retention"}],
    }


def test_interpretation_distinguishes_explicit_and_inferred_evidence_without_fabrication():
    draft = build_ruling_interpretation_draft(
        rationale=(
            "The customer retention is strong, supported by claim-1 and evidence-1. "
            "Distribution risk remains, but we accept it as the key tradeoff. "
            "claim-not-real should not be treated as evidence."
        ),
        decision="pass",
        investor_confidence=0.8,
        risk_acknowledgement="Distribution risk accepted.",
        mandate_exception=None,
        override_type="policy_disagreement",
        context=_context(),
    )

    assert draft is not None
    assert draft["agreement_with_aethria"] == "disagree"
    assert draft["positive_factors"]
    assert draft["negative_factors"]
    assert draft["accepted_risks"]
    references = draft["evidence_influence"]["references"]
    assert {item["reference_id"] for item in references} == {"claim-1", "evidence-1"}
    assert all(item["attribution"] == "explicit" for item in references)
    assert "claim-not-real" not in json.dumps(draft)


def test_interpretation_marks_matching_claim_influence_as_inferred():
    draft = build_ruling_interpretation_draft(
        rationale="Customer retention is strong and decisive for this decision.",
        decision="advance",
        investor_confidence=0.7,
        risk_acknowledgement=None,
        mandate_exception=None,
        override_type=None,
        context=_context(),
    )

    assert draft is not None
    assert draft["evidence_influence"]["status"] == "inferred"
    assert draft["evidence_influence"]["references"] == [
        {
            "reference_type": "claim",
            "reference_id": "claim-1",
            "attribution": "inferred",
            "basis": "rationale phrase matched the decision-time claim text",
        }
    ]


def test_interpretation_fails_closed_for_insufficient_rationale_or_unknown_evidence():
    assert build_ruling_interpretation_draft(
        rationale="Fine.",
        decision="pass",
        investor_confidence=0.5,
        risk_acknowledgement=None,
        mandate_exception=None,
        override_type=None,
        context=_context(),
    ) is None

    draft = build_ruling_interpretation_draft(
        rationale="The timing is not right for this fund.",
        decision="pass",
        investor_confidence=0.5,
        risk_acknowledgement=None,
        mandate_exception=None,
        override_type="timing",
        context={**_context(), "claim_snapshot": [], "criteria": []},
    )
    assert draft is not None
    assert draft["evidence_influence"] == {
        "status": "unknown",
        "references": [],
        "limitations": ["The rationale did not explicitly or reliably identify decision-time evidence."],
    }


def test_create_ruling_preserves_raw_rationale_and_stores_separate_interpretation():
    rationale = "The customer retention is strong: claim-1 supports the decision."
    connection = _Connection([
        {
            "current_ruling_id": None,
            "current_recommendation_id": "recommendation-1",
            "legacy_startup_id": None,
            "company_id": "company-1",
            "workflow_version": 1,
            "recommended_state": "advance",
            "missing_information": "[]",
        },
        {"ruling_id": "ruling-1", "rationale": rationale},
        {
            "recommendation_id": "recommendation-1",
            "recommended_state": "advance",
            "evaluation_id": "evaluation-1",
            "claim_snapshot": json.dumps(_context()["claim_snapshot"]),
        },
    ])
    repository = DecisionRepository(_Pool(connection))

    result = __import__("asyncio").run(
        repository.create_ruling(
            HumanRulingInput(
                user_id="user-a", opportunity_id="opportunity-1", decision="pass",
                rationale=rationale, investor_confidence=0.8,
            ),
            actor_id="user-a",
        )
    )

    raw_insert = next(
        call for call in connection.calls
        if call[0] == "fetchrow" and "insert into public.human_rulings" in call[1]
    )
    assert rationale in raw_insert[2]
    interpretation_insert = next(
        call for call in connection.calls
        if call[0] == "execute" and "insert into public.ruling_interpretations" in call[1]
    )
    assert rationale not in json.dumps(interpretation_insert[2])
    assert result["interpretation"]["source"] == "aethria_inferred"


def test_create_ruling_does_not_create_interpretation_for_insufficient_rationale():
    connection = _Connection([
        {
            "current_ruling_id": None,
            "current_recommendation_id": "recommendation-1",
            "legacy_startup_id": None,
            "company_id": "company-1",
            "workflow_version": 1,
            "recommended_state": "advance",
            "missing_information": "[]",
        },
        {"ruling_id": "ruling-1", "rationale": "Fine."},
        {
            "recommendation_id": "recommendation-1",
            "recommended_state": "advance",
            "evaluation_id": "evaluation-1",
            "claim_snapshot": "[]",
        },
    ])
    repository = DecisionRepository(_Pool(connection))

    result = __import__("asyncio").run(
        repository.create_ruling(
            HumanRulingInput(
                user_id="user-a", opportunity_id="opportunity-1", decision="pass",
                rationale="Fine.",
            ),
            actor_id="user-a",
        )
    )

    assert result["interpretation"] is None
    assert not any(
        call[0] == "execute" and "insert into public.ruling_interpretations" in call[1]
        for call in connection.calls
    )


def test_correction_appends_version_and_preserves_rationale_hash():
    rationale = "The customer retention is strong: claim-1 supports the decision."
    previous = {
        "interpretation_id": "interpretation-1",
        "version": 1,
    }
    connection = _Connection([
        {
            "ruling_id": "ruling-1", "opportunity_id": "opportunity-1",
            "recommendation_id": "recommendation-1", "rationale": rationale,
            "evaluation_id": "evaluation-1",
        },
        previous,
        {
            "recommendation_id": "recommendation-1", "recommended_state": "advance",
            "evaluation_id": "evaluation-1",
            "claim_snapshot": json.dumps(_context()["claim_snapshot"]),
        },
    ])
    repository = DecisionRepository(_Pool(connection))

    correction = {
        "positive_factors": ["Retention was decisive."],
        "negative_factors": [],
        "accepted_risks": [],
        "decisive_factors": ["Retention"],
        "overridden_criteria": [],
        "strategic_exception": None,
        "agreement_with_aethria": "disagree",
        "human_confidence": 0.8,
        "evidence_influence": {
            "status": "explicit",
            "references": [{
                "reference_type": "claim", "reference_id": "claim-1",
                "attribution": "explicit", "basis": "operator correction",
            }],
            "limitations": [],
        },
        "correction_note": "Corrected the decisive factor wording.",
    }
    result = __import__("asyncio").run(
        repository.correct_ruling_interpretation(
            user_id="user-a", ruling_id="ruling-1", correction=correction
        )
    )

    assert result["version"] == 2
    assert result["supersedes_interpretation_id"] == "interpretation-1"
    assert result["rationale_sha256"] == hashlib.sha256(rationale.encode()).hexdigest()
    insert = next(
        call for call in connection.calls
        if call[0] == "execute" and "insert into public.ruling_interpretations" in call[1]
    )
    assert "ruling-1" in insert[2]


def test_correction_rejects_fabricated_evidence_reference():
    connection = _Connection([
        {
            "ruling_id": "ruling-1", "opportunity_id": "opportunity-1",
            "recommendation_id": "recommendation-1", "rationale": "Strong evidence.",
            "evaluation_id": "evaluation-1",
        },
        {"interpretation_id": "interpretation-1", "version": 1},
        {
            "recommendation_id": "recommendation-1", "recommended_state": "advance",
            "evaluation_id": "evaluation-1", "claim_snapshot": "[]",
        },
    ])
    repository = DecisionRepository(_Pool(connection))
    correction = {
        "agreement_with_aethria": "agree",
        "evidence_influence": {
            "status": "explicit",
            "references": [{
                "reference_type": "claim", "reference_id": "claim-fabricated",
                "attribution": "explicit", "basis": "operator correction",
            }],
        },
        "correction_note": "Attempted unsupported reference.",
    }

    try:
        __import__("asyncio").run(
            repository.correct_ruling_interpretation(
                user_id="user-a", ruling_id="ruling-1", correction=correction
            )
        )
    except ValueError as exc:
        assert "outside the decision-time snapshot" in str(exc)
    else:
        raise AssertionError("fabricated evidence reference was accepted")
