"""Fund thesis domain: the per-user investment mandate.

Consolidates what were three top-level modules (fund_thesis.py, fund_thesis_ops.py,
fund_thesis_repository.py) into one package. External code should import from
`fund_thesis` directly (`from fund_thesis import get_active_thesis`); the
submodule split below (core / ops / repository) is an internal detail.

- core: active-thesis lookup, caching, bootstrap, rule-based alignment scoring.
- ops: OpenAI-backed parse + embed for fund thesis versions (API / admin paths).
- repository: asyncpg-backed FundThesisRepository (tenant-scoped, read-oriented).
"""
from __future__ import annotations

from fund_thesis.core import (
    ActiveThesis,
    ActiveThesisMeta,
    DEFAULT_THESIS_PARSED_JSON,
    FundThesisError,
    FundThesisIncompleteError,
    FundThesisMissingError,
    FundThesisQueryError,
    _bootstrap_default_thesis_or_raise,
    _review_thesis_fields,
    bootstrap_default_thesis_with_repository,
    compute_structured_thesis_fit,
    compute_thesis_alignment_stats,
    get_active_thesis,
    get_active_thesis_from_repository,
    get_active_thesis_metadata,
    insert_thesis_pipeline_link,
    invalidate_thesis_cache,
    rule_based_thesis_alignment,
    thesis_context_has_embeddings,
    thesis_has_embeddings,
)
from fund_thesis.ops import (
    activate_fund_thesis_version_with_repository,
    backfill_thesis_embeddings_with_repository,
    create_fund_thesis_version_for_user,
    create_fund_thesis_version_with_repository,
    sync_fund_config_to_active_thesis,
    sync_fund_config_to_active_thesis_with_repository,
)
from fund_thesis.repository import FundThesisRepository

__all__ = [
    "ActiveThesis",
    "ActiveThesisMeta",
    "DEFAULT_THESIS_PARSED_JSON",
    "FundThesisError",
    "FundThesisIncompleteError",
    "FundThesisMissingError",
    "FundThesisQueryError",
    "FundThesisRepository",
    "_bootstrap_default_thesis_or_raise",
    "_review_thesis_fields",
    "activate_fund_thesis_version_with_repository",
    "backfill_thesis_embeddings_with_repository",
    "bootstrap_default_thesis_with_repository",
    "compute_structured_thesis_fit",
    "compute_thesis_alignment_stats",
    "create_fund_thesis_version_for_user",
    "create_fund_thesis_version_with_repository",
    "get_active_thesis",
    "get_active_thesis_from_repository",
    "get_active_thesis_metadata",
    "insert_thesis_pipeline_link",
    "invalidate_thesis_cache",
    "rule_based_thesis_alignment",
    "sync_fund_config_to_active_thesis",
    "sync_fund_config_to_active_thesis_with_repository",
    "thesis_context_has_embeddings",
    "thesis_has_embeddings",
]
