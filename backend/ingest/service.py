"""Tenant-scoped import adapter: rows become observations, never decisions."""

from __future__ import annotations

from typing import Any, Iterable

from identity.models import SourceChannel, SourceObservationInput
from identity.service import IdentityService
from tenant_context import require_user_id


class ImportRowError(ValueError):
    pass


class CompanyImportService:
    def __init__(self, identity_repository: Any):
        self.identity_service = IdentityService(identity_repository)

    async def ingest_rows(self, *, user_id: str, rows: Iterable[dict[str, Any]], import_id: str) -> dict[str, Any]:
        uid = require_user_id(user_id, context="CompanyImportService.ingest_rows")
        rows = list(rows)
        for index, row in enumerate(rows):
            if not str(row.get("company_name") or row.get("name") or "").strip():
                raise ImportRowError(f"row {index + 1} is missing company_name")
        imported = 0
        blocked = 0
        observations = []
        for index, row in enumerate(rows):
            name = str(row.get("company_name") or row.get("name") or "").strip()
            key = f"import:{import_id}:{index}"
            observation = SourceObservationInput(
                user_id=uid, channel=SourceChannel.IMPORT,
                observed_name=name, observed_domain=row.get("website"),
                external_event_key=key,
                source_metadata={"import_id": import_id, "row_index": index},
                resolution_payload={"website": row.get("website")} if row.get("website") else None,
            )
            admission = await self.identity_service.admit(observation)
            observations.append({
                "observation_id": admission.observation_id,
                "status": admission.status.value,
                "company_id": admission.company_id,
                "opportunity_id": admission.opportunity_id,
                "blocks_evaluation": admission.blocks_evaluation,
            })
            imported += 1
            blocked += int(admission.blocks_evaluation)
        return {"import_id": import_id, "rows_processed": imported, "blocked": blocked, "observations": observations}
