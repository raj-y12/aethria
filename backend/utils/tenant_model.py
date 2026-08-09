"""Shared Pydantic tenant-validation base for record/input models."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from tenant_context import require_user_id


class TenantScopedModel(BaseModel):
    user_id: str

    @field_validator("user_id")
    @classmethod
    def _valid_tenant(cls, value: str) -> str:
        try:
            return require_user_id(value, context=cls.__name__)
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc
