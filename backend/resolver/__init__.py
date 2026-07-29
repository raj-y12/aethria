"""
Resolver layer: identify the real company (and its founders) behind a typed name
BEFORE any scout/enrichment/scoring runs. Never silently drops weak matches — it
returns an explicit resolution status instead.
"""
from resolver.company_resolver import (
    CompanyResolution,
    ResolutionStatus,
    resolve_company,
)
from resolver.founder_resolver import (
    FounderCandidate,
    FounderEvidence,
    FounderFieldConflict,
    FounderResolution,
    FounderResolutionStatus,
    resolve_founders,
)

__all__ = [
    "CompanyResolution",
    "ResolutionStatus",
    "resolve_company",
    "FounderCandidate",
    "FounderEvidence",
    "FounderFieldConflict",
    "FounderResolution",
    "FounderResolutionStatus",
    "resolve_founders",
]
