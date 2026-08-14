from uuid import uuid4

from evidence.models import EvidencePlanRecord
from utils.db_rows import db_row


def test_evidence_plan_db_uuid_values_are_normalized_for_domain_model():
    payload = db_row(
        {
            "evidence_plan_id": uuid4(),
            "user_id": "user_test",
            "opportunity_id": uuid4(),
            "trigger_type": "new_observation",
            "status": "planned",
            "missing_evidence": [],
            "search_questions": [],
            "max_artifacts": 1,
            "budget_usd": 0,
            "plan_hash": "hash-1234",
        }
    )

    record = EvidencePlanRecord.model_validate(payload)

    assert isinstance(record.evidence_plan_id, str)
    assert isinstance(record.opportunity_id, str)
