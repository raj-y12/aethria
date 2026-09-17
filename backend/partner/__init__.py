"""
AETHRIA Partner Layer — LEGACY / COMPATIBILITY, not the authoritative
runtime path.

The rule-based Partner implementation this package holds is retired for live
decision-making. The current, authoritative Partner phase lives in
`backend/investment_analysis/` — where it runs as the last phase of one
transactional analysis, reading an already-validated Reviewer output rather
than as an independently orchestrated agent (see that package's README and
ADR-0016). This package is kept for historical replay and because
`PartnerEngine` is still constructed as a compatibility component by
`pipeline_runner.py`/`api.py`. Do not add new product behaviour here; if you
are implementing new Partner decision logic, it belongs in
`investment_analysis/`.
"""
from partner.schema import PartnerOutput, validate_partner_output
from partner.decision import PartnerDecisionEngine
from partner.engine import PartnerEngine

__all__ = [
    "PartnerOutput",
    "validate_partner_output",
    "PartnerDecisionEngine",
    "PartnerEngine",
]
