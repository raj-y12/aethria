"""
Repository resource paths. Runtime policy JSON is loaded via core.policy_resolver
(versioned resources/config/active.json + per-policy files).

Optional trace for legacy direct loads: see policy_resolver (same AETHRIA_RESOURCE_TRACE).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# active.json + default v1 layout (for dev verification scripts).
ACTIVE_JSON = "resources/config/active.json"
PARTNER_RULES_V1 = "resources/config/partner_rules/v1.json"
REVIEWER_RULES_V1 = "resources/config/reviewer_rules/v1.json"
EVALUATION_RUBRIC_V1 = "resources/config/evaluation_rubric/v1.json"
FUND_THESIS_V1 = "resources/config/fund_thesis/v1.json"

REQUIRED_CONFIG_FILES: tuple[str, ...] = (
    ACTIVE_JSON,
    PARTNER_RULES_V1,
    REVIEWER_RULES_V1,
    EVALUATION_RUBRIC_V1,
    FUND_THESIS_V1,
)


def project_root() -> Path:
    """Repository root (parent of `backend/`)."""
    return Path(__file__).resolve().parent.parent.parent


def load_partner_rules_json() -> Any:
    """Delegate to versioned policy resolver (same JSON as v1 on disk)."""
    from core.policy_resolver import get_partner_rules

    return get_partner_rules()


def load_reviewer_rules_json() -> Any:
    from core.policy_resolver import get_reviewer_rules

    return get_reviewer_rules()


def load_evaluation_rubric_json() -> Any:
    from core.policy_resolver import get_evaluation_rubric

    return get_evaluation_rubric()


def resolve_partner_rules_path() -> Path:
    from core.policy_resolver import get_policy_file_path

    return get_policy_file_path("partner_rules")


def resolve_reviewer_rules_path() -> Path:
    from core.policy_resolver import get_policy_file_path

    return get_policy_file_path("reviewer_rules")


def resolve_evaluation_rubric_path() -> Path:
    from core.policy_resolver import get_policy_file_path

    return get_policy_file_path("evaluation_rubric")
