"""Startup domain: the canonical `startups` table authority.

Consolidates four top-level modules into one package. External code should
import from `startups` directly (`from startups import StartupRepository`);
the submodule split below is an internal detail.

- repository: CRUD + projections over the canonical `startups` table (asyncpg).
- resolver: CanonicalStartupResolver — resolves an incoming identifier through
  the id-alias bridge before falling back to the repository.
- id_alias_repository: tenant-scoped `startup_id_aliases` bridge for approved
  legacy identifiers (see ARCHITECTURE.md — "Startup authority is explicit").
- id_alias_backfill: one-off reconciliation-artifact loading for the alias
  backfill script (`scripts/backfill_startup_id_aliases.py`).
"""
from __future__ import annotations

from startups.id_alias_backfill import load_reconciliation_artifact, repository_rows
from startups.id_alias_repository import StartupIdAliasConflict, StartupIdAliasRepository
from startups.repository import (
    StartupReadStorageAdapter,
    StartupRepository,
    _queue_reasons_for_startup,
    startup_dict,
)
from startups.resolver import CanonicalStartupResolver

__all__ = [
    "CanonicalStartupResolver",
    "StartupIdAliasConflict",
    "StartupIdAliasRepository",
    "StartupReadStorageAdapter",
    "StartupRepository",
    "_queue_reasons_for_startup",
    "load_reconciliation_artifact",
    "repository_rows",
    "startup_dict",
]
