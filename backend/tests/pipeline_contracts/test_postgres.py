"""Exercise the adapter against the existing real-Postgres pipeline harness."""
import os

import pytest
from pydantic_core import to_jsonable_python

from evaluation_v2.repository import EvaluationRepository
from pipeline_contracts.adapters import adapt_current_evaluation_to_validation_result, project_current_payload
from pipeline_contracts.models import Lineage
from tests.evaluation_v2.test_phase0_provenance_postgres import test_postgres_roundtrip_and_tenant_isolation as walk_pipeline


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL required")
@pytest.mark.asyncio
async def test_adapter_on_real_evaluation_and_manual_pipeline(monkeypatch):
    original = EvaluationRepository.evaluate
    observed = []

    async def observe(self, **kwargs):
        result = await original(self, **kwargs)
        uid = kwargs["user_id"]
        contract = adapt_current_evaluation_to_validation_result(
            user_id=uid, payload=result,
            lineage=Lineage(user_id=uid, opportunity_id=kwargs["opportunity_id"]),
        )
        assert project_current_payload(user_id=uid, contract=contract) == to_jsonable_python(result)
        assert [item.validated_score for item in contract.assessments] == [item["score"] for item in result["criteria"]]
        assert all(item.reviewer_assessment_id is None for item in contract.assessments)
        observed.append(contract)
        return result

    monkeypatch.setattr(EvaluationRepository, "evaluate", observe)
    await walk_pipeline()
    assert len(observed) >= 2
    assert all(item.lineage.evaluation_run_id for item in observed)
