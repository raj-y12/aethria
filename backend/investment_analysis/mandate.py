"""Apply explicit fund exclusions to the supplied tenant factual snapshot.

Preferences are investment context, not exclusions. Free-text taxonomy mapping
belongs in attributed analysis; this check never infers a sector from prose.
"""
from datetime import datetime

from evaluation_v2.models import EvaluationPolicy
from evaluation_v2.service import evaluate_claim_score_eligibility


def check_sector_exclusions(*, snapshot: list[dict], fund_config: dict,
                            policy: EvaluationPolicy, evaluation_at: datetime) -> tuple[list[str], list[str]]:
    mandate = fund_config.get("mandate") or {}
    excluded = {
        value.strip().casefold()
        for key in ("excludedSectorList", "excludedSectors")
        for value in (mandate.get(key) if isinstance(mandate.get(key), list) else [])
        if isinstance(value, str) and value.strip()
    }
    if not excluded:
        return [], []
    sectors = []
    uncertain = False
    for claim in snapshot:
        if claim.get("claim_type") not in {"sector", "company_sector", "industry"}:
            continue
        if claim.get("status_at_snapshot") not in {"current", "contradicted"}:
            continue
        normalized = claim.get("normalized_value") or {}
        value = normalized.get("sector") or normalized.get("value")
        eligible = evaluate_claim_score_eligibility(claim, policy=policy, evaluation_at=evaluation_at)
        if (not eligible.eligible or claim.get("status_at_snapshot") == "contradicted"
                or claim.get("contradicting_evidence_ids") or not isinstance(value, str) or not value.strip()):
            uncertain = True
            continue
        sectors.append(value.strip().casefold())
    if uncertain or not sectors or len(set(sectors)) != 1:
        return [], ["Verify the company's sector against the fund's explicit sector exclusions."]
    if sectors[0] in excluded:
        return [f"The verified company sector ({sectors[0]}) is explicitly excluded by the fund mandate."], []
    return [], []
