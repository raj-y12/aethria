"""
Company Resolver layer: identify the real company behind a typed name BEFORE
any scout/enrichment/scoring runs. Never silently drops weak matches — it
returns an explicit resolution status instead.
"""
from resolver.company_resolver import (
    CompanyResolution,
    ResolutionStatus,
    resolve_company,
)

__all__ = ["CompanyResolution", "ResolutionStatus", "resolve_company"]
