# ADR-0011 — Historical Decision Cases and Fund Intelligence authority

**Status:** Accepted

## Context

Aethria needs to learn from human decisions without turning historical records
or descriptive analysis into mutable policy. The same opportunity may be
evaluated repeatedly, and human rationale may later receive a corrected
Aethria interpretation.

## Decision

- `evaluation_id` is the immutable historical decision-event grain. A Decision
  Case is a derived read model over the canonical evaluation, recommendation,
  ruling, evidence, thesis/policy, interpretation, and later outcomes.
- The raw human ruling and rationale remain canonical. A ruling interpretation
  is Aethria-owned, append-only, versioned, and correctable derived state.
- Precedents, observations, hypotheses, proposals, and replay results are
  derived projections. Outcomes are later observations and never mutate the
  original case.
- Fund Intelligence describes observed fund behavior. Fund Learning identifies
  possible changes. Optimization measures Aethria system performance. None of
  these descriptive outputs can mutate governed policy without an explicit
  governed adaptation step.

## Consequences

Historical cases remain reproducible while corrected interpretations can be
used by current derived projections with explicit version provenance. Every
downstream analytical object must preserve tenant scope and its canonical
source references; policy authority remains separate from learning output.

## Alternatives considered

- **Mutable case snapshots.** Rejected because current opportunity state or a
  later interpretation correction could rewrite historical decision meaning.
- **Learning as policy authority.** Rejected because descriptive association
  is not governed adaptation.
