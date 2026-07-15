"""Pure bounded-import parsing and non-causal outcome contracts."""

from __future__ import annotations

import csv
import hashlib
import io
from typing import Dict, List, Optional

from identity.normalization import normalize_domain
from outcomes.models import (
    ImportCandidate,
    ImportSource,
    OutcomeInput,
    OutcomeVerification,
)


class ImportLimitError(ValueError):
    pass


def parse_csv_candidates(
    csv_text: str,
    *,
    source: ImportSource | str,
    import_id: str,
    name_field: str,
    domain_field: Optional[str] = None,
    external_id_field: Optional[str] = None,
    verify_domains: bool = False,
    max_rows: int = 500,
) -> List[ImportCandidate]:
    text = str(csv_text or "")
    if len(text.encode("utf-8")) > 1_000_000:
        raise ImportLimitError("CSV payload exceeds 1 MB")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV header is required")
    headers = {str(item) for item in reader.fieldnames}
    if name_field not in headers:
        raise ValueError(f"Missing configured name field: {name_field}")
    for optional in (domain_field, external_id_field):
        if optional and optional not in headers:
            raise ValueError(f"Missing configured field: {optional}")
    candidates: List[ImportCandidate] = []
    for row_number, row in enumerate(reader, start=2):
        if len(candidates) >= max(1, min(int(max_rows), 500)):
            raise ImportLimitError(f"CSV contains more than {max_rows} data rows")
        name = str(row.get(name_field) or "").strip()
        if not name:
            raise ValueError(f"Row {row_number} has no company name")
        domain = normalize_domain(row.get(domain_field)) if domain_field else None
        external_id = str(row.get(external_id_field) or "").strip() if external_id_field else None
        canonical = f"{row_number}|{name.casefold()}|{domain or ''}|{external_id or ''}"
        candidates.append(
            ImportCandidate(
                row_number=row_number,
                row_key=hashlib.sha256(canonical.encode()).hexdigest(),
                observed_name=name,
                observed_domain=domain,
                external_id=external_id or None,
                source=ImportSource(source),
                import_id=import_id,
                operator_confirmed_identity=bool(verify_domains and domain),
            )
        )
    return candidates


def validate_outcome(outcome: OutcomeInput) -> None:
    if (
        outcome.verification_state is OutcomeVerification.VERIFIED
        and not outcome.evidence_artifact_ids
    ):
        raise ValueError("Verified outcomes require at least one evidence artifact")
    if len(set(outcome.evidence_artifact_ids)) != len(outcome.evidence_artifact_ids):
        raise ValueError("Outcome evidence artifact IDs must be unique")


def build_outcome_interpretation(outcome: OutcomeInput) -> Dict[str, object]:
    return {
        "summary": (
            f"Recorded {outcome.outcome_type.value.replace('_', ' ')} outcome; "
            "this later event does not establish that an earlier recommendation or ruling was correct or incorrect."
        ),
        "causal_inference_supported": False,
        "allowed_use": "context_and_monitoring",
        "limitations": [
            "Later outcomes do not establish counterfactual investment performance.",
            "Coverage may be incomplete and subject to survivorship or observation bias.",
            "Attribution to any acquisition, evidence, policy, or recommendation stage is unsupported.",
        ],
    }
