"""Idempotent compatibility projection linkage and replay."""

from __future__ import annotations

from typing import Any

from identity.models import IdentityAdmission, IdentityStatus
from tenant_context import require_user_id


async def link_admission_projection(
    repository: Any,
    *,
    admission: IdentityAdmission,
    legacy_startup_id: str,
) -> Any:
    if admission.status is not IdentityStatus.RESOLVED or not admission.opportunity_id:
        raise ValueError("Only a resolved opportunity can link a legacy projection")
    return await repository.link_legacy_projection(
        user_id=admission.user_id,
        opportunity_id=admission.opportunity_id,
        legacy_startup_id=legacy_startup_id,
    )


async def replay_projection(
    repository: Any,
    *,
    user_id: str,
    observation_id: str,
    legacy_startup_id: str,
) -> Any:
    uid = require_user_id(user_id, context="identity.projection.replay_projection")
    admission = await repository.get_admission_for_observation(
        user_id=uid, observation_id=observation_id
    )
    if admission is None:
        raise LookupError("Resolved observation admission not found for tenant")
    return await link_admission_projection(
        repository,
        admission=admission,
        legacy_startup_id=legacy_startup_id,
    )
