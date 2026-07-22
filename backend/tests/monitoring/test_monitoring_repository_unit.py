import pytest

from evaluation_v2.evidence_projection import enriched_claim_evidence_sql
from monitoring.repository import MonitoringRepository


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Connection:
    def __init__(self):
        self.calls = []

    def transaction(self):
        return _Transaction()

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        if "from public.opportunities" in sql:
            return {"current_evaluation_id": "evaluation-1"}
        if "from public.evaluation_runs" in sql:
            return {
                "evidence_materiality_digest": "materiality-1",
                "claim_snapshot": [],
            }
        if "insert into public.material_change_checks" in sql:
            return {
                "material_change_check_id": "check-1",
                "detail": {"claim_count": 0},
                "material_change": False,
            }
        raise AssertionError(f"unexpected fetchrow: {sql}")

    async def fetchval(self, sql, *args):
        self.calls.append(("fetchval", sql, args))
        return "snapshot-1"

    async def fetch(self, sql, *args):
        self.calls.append(("fetch", sql, args))
        return []


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _Acquire(self.connection)


@pytest.mark.asyncio
async def test_material_change_reads_the_immutable_evaluation_schema_columns():
    connection = _Connection()
    repository = MonitoringRepository(_Pool(connection))

    await repository.check_material_change(
        user_id="user-a",
        opportunity_id="opportunity-1",
        job_id="job-1",
        reason="human_request",
    )

    evaluation_sql = next(
        sql.lower()
        for operation, sql, _ in connection.calls
        if "evaluation_runs" in sql
    )
    assert "evidence_materiality_digest" in evaluation_sql
    assert "claim_snapshot" in evaluation_sql
    assert "evaluation_id=$2" in evaluation_sql
    assert "evaluation_run_id" not in evaluation_sql

    link_sql = next(
        sql.lower()
        for operation, sql, _ in connection.calls
        if operation == "fetch" and "claim_evidence_links" in sql
    )
    normalized = " ".join(link_sql.split())
    assert " ".join(enriched_claim_evidence_sql().lower().split()) == normalized
    assert "join public.evidence_items ei" in normalized
    assert "join public.evidence_artifacts ea" in normalized
    assert "ei.verification_state" in normalized
    assert "ei.source_quality" in normalized
    assert "ea.trust_class" in normalized
    assert "ea.prompt_injection_detected" in normalized

    insert_sql = next(
        sql.lower()
        for operation, sql, _ in connection.calls
        if operation == "fetchrow" and "material_change_checks" in sql
    )
    assert "previous_materiality_digest" in insert_sql
    assert "current_materiality_digest" in insert_sql
