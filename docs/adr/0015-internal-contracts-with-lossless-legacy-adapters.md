# ADR-0015: Internal target contracts with lossless legacy adapters

Status: Accepted for Phase 1

## Context

Current Scout mixes narrative facts and investment hypotheses. Canonical
assessment and recommendation precede Reviewer. The alternate manual pipeline
uses deterministic evaluation summarization and routing. Replacing their schemas
in place would change authority or silently mislabel historical data.

## Decision

Introduce `backend/pipeline_contracts` as an internal, opt-in contract layer.
Existing engine schemas, persistence, API DTOs and frontend consumers retain their
current interfaces. No runtime caller is switched to the new contracts in Phase 1.

Use composable Pydantic models for Scout, Reviewer inputs/outputs, reasoning,
assessment validation, Partner inputs/outputs and shared lineage. Missing analysis
sections are allowed; explicit status distinguishes unknown, unsupported, not
applicable and intentionally unassessed. Unknown provenance remains unknown.

Pure adapters retain the complete original JSON in a named compatibility
extension. Reverse projection replays that JSON; it never interprets target edits
as instructions to change a legacy score or decision. This is a read/replay
boundary, not a target write API. Existing persistence adapters still apply their
normal suppression and validation afterward.

Do not classify legacy Scout narrative as verified facts, copy historical Reviewer
scores into target proposed scores, label canonical scoring as Reviewer proposal
validation, or convert deterministic canonical routes into investment decisions.
Keep those mismatches explicit in compatibility metadata. Evaluation IDs remain
evaluation IDs; they are not fabricated validation run IDs.

New compatibility assessment/reasoning IDs are deterministic, tenant-scoped
content digests, marked as projection IDs. They are not persisted run identities.
Their stability is defined for the same normalized JSON and lineage; edits or a
changed lineage produce different IDs. No backfill or new database table is needed.

## Consequences

Phase 1 introduces no prompt, model, policy, scheduling, API or analyst UX change.
Current runtime paths remain frozen. Tests exercise both current payload families,
serialization, exact JSON replay, golden scores, and real PostgreSQL evaluations.

Adapters require explicit server-supplied user context and reject conflicting
embedded owners. They never resolve references. Callers must obtain payloads via
existing tenant-scoped repositories; possession of an opaque ID is not proof of
ownership. Nested target envelopes also reject conflicting tenant/company/
opportunity identities.

Later phases must choose authority and persistence deliberately. Compatibility
replay is unsuitable for saving edited target assessments. Factual extraction,
per-assessment claim attribution, validation cap semantics and decision authority
remain separate migration work.
