# ADR-0013 — Evidence sufficiency precedes machine recommendation

**Status:** Accepted

## Context

The canonical evaluator can derive a recommendation from an immutable evidence
snapshot. That recommendation is a machine input to diligence, not an
authoritative investment ruling: the human ruling record remains the only
authoritative decision.

Before this decision, a grounded hard exclusion or critical risk could select
`pass` before the evaluator considered a missing required criterion. A scored
criterion with contradicting evidence, or an ungrounded or malformed decisive
claim, could likewise leave a score-derived recommendation intact. A human
review flag does not make a decisive-looking machine recommendation safe when
the decision-bearing evidence is incomplete.

## Decision

- Canonical evaluation selects its existing `insufficient_evidence` state before
  either decisive or score-derived recommendations whenever required criterion
  evidence is missing, a scored criterion is contradicted, decisive evidence is
  ungrounded, or a decisive value is malformed.
- Complete, eligible hard exclusions and critical risks remain deterministic
  `pass` recommendations. This preserves their safety function once the rest of
  the decision-bearing evidence is sufficient.
- The operator presentation `Blocked by evidence` maps only to canonical
  `insufficient_evidence`; it does not add a new persisted state.
- Authority-workflow `BLOCKED` remains reserved for execution blocks. It is not
  a substitute for an evidence-sufficiency result.

## Consequences

Incomplete or contradictory evidence produces named gaps or contradiction
resolution conditions and requires human review. API response fields and enum
values are unchanged, and historical recommendations and rulings are not
rewritten. Consumers must distinguish an evidence-blocked machine
recommendation from the human ruling that may later be recorded after review.

## Alternatives considered

**Keep a decisive or score-derived recommendation and set only
`human_review_required`.** Rejected: a decisive-looking machine output is
misleading when its own decision-bearing evidence is incomplete or
contradictory.

**Use authority-workflow `BLOCKED` for insufficient evidence.** Rejected:
workflow blocks describe execution state, while `insufficient_evidence` is the
existing canonical evaluation state and preserves the boundary between machine
recommendation and human ruling.
