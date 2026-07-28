"""
Explicit tenant identity for Supabase doc/list access and agent pipelines.

Callers pass user_id or TenantContext; no implicit run_context or default tenant.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Clerk JWT `sub` for the active tenant."""

    user_id: str

    def __post_init__(self) -> None:
        uid = (self.user_id or "").strip()
        object.__setattr__(self, "user_id", uid)
        if not uid:
            raise ValueError("TenantContext.user_id must be non-empty")


def require_user_id(user_id: Optional[str], *, context: str = "tenant") -> str:
    """Fail fast when tenant is missing."""
    s = (user_id or "").strip()
    if not s:
        raise RuntimeError(f"Missing explicit user_id ({context}); unsafe execution blocked.")
    return s
