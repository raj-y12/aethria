"""CRM export payload for the row Aethria hands a fund's CRM.

Aethria owns investment reasoning; the CRM owns records and relationships. This
payload therefore carries the decision and its rationale, never economics and
never internal-only ruling fields.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping, Optional, Sequence


_DECISION_MAP = {
    "invest": "INVEST", "yes": "INVEST", "advance": "INVEST",
    "monitor": "MONITOR", "maybe": "MONITOR",
    "pass": "PASS", "no": "PASS",
}
_CONFIDENTIAL = ("mandate_exception", "risk_acknowledgement", "override_note")


def _slug(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.strip().lower())).strip("-")


def build_crm_export_payload(
    *,
    company: Mapping[str, Any],
    ruling: Mapping[str, Any],
    position: Optional[Mapping[str, Any]],
    outcomes: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Build a reviewable CRM row without performing I/O."""
    domain = str(company.get("canonical_domain") or "").strip().lower()
    name = str(company.get("canonical_name") or "").strip()
    if not domain and not name:
        raise ValueError("CRM export requires a canonical name or domain")

    ordered = sorted(outcomes, key=lambda item: str(item.get("observed_at") or ""))
    latest = ordered[-1] if ordered else None
    payload = {
        "dedupe_key": domain or _slug(name),
        "company_name": name or domain,
        "domain": domain or None,
        "decision": _DECISION_MAP.get(str(ruling.get("decision") or "").lower(), "MONITOR"),
        "rationale": str(ruling.get("rationale") or "").strip(),
        "investor_confidence": float(ruling.get("investor_confidence") or 0.0),
        "ruled_at": str(ruling.get("created_at") or "") or None,
        "override_type": ruling.get("override_type"),
        "entered_at": (position or {}).get("entered_at"),
        "latest_outcome": (
            f"{latest.get('outcome_type')}: {latest.get('summary')}" if latest else None
        ),
        "outcome_count": len(ordered),
        "requires_approval": True,
        "external_write_performed": False,
    }
    for field in _CONFIDENTIAL:
        payload.pop(field, None)
    return payload
