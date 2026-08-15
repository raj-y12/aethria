# Reviewer section audit — scope

Date: 2026-08-15

## Audited surface

The Aethria reviewer system and its user-facing investment-memo projection:

- Backend reviewer personas, rubric prompts, evidence-coverage semantics, score enrichment, disagreement handling, schema, and persistence/projection.
- Frontend reviewer assessment rows, summaries, evidence percentages, disagreement labels, claim provenance, and the relationship between reviewer output and the canonical decision brief.
- Loading, missing-data, contradictory-evidence, read-only, responsive, focus, and print behavior on the reviewer surface.

Primary screenshot input: `Screenshot 2026-08-15 at 19.02.58.png`, especially the `Assessment` section showing Default, Skeptical, and Opportunist reviewers. The current checked-out implementation is the authoritative artifact when it differs from that screenshot.

## Primary user and task

Primary user: a venture investor or IC operator reviewing one startup.

Primary task: understand what each reviewer actually knows, how their conclusions differ, which claims and sources support those conclusions, and whether the disagreement warrants diligence or a human ruling.

## Constraints

- Preserve Aethria's paper/Oxford/burgundy visual language and existing React/FastAPI stack.
- Preserve explicit evidence provenance, tenant boundaries, versioned policy, fail-closed behavior, and authoritative human rulings.
- This turn is an investigation and audit only; do not change product behavior or implementation.
- Repository point-in-time audits belong under `docs/archive/`, not at repository root.

## References and non-goals

No competitor or reference design was supplied. The audit judges the shipped reviewer system against Dieter Rams' ten principles and the product's own evidence/authority contracts.

Out of scope: the general startup Snapshot, portfolio workflow, marketing site, and visual styling unrelated to reviewer interpretation.
