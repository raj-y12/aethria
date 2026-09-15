# ADR-0014: Provenance observes existing decision authority

Status: Accepted

## Context

The current runtime combines canonical evaluation, qualitative Reviewer output,
Partner mapping, human rulings and compatibility projections. A later pipeline
migration needs deterministic baseline fixtures and exact traceability first.
Investors need evidence and reasoning; engineering identifiers belong internally.

## Decision

Store additive pipeline binding and source-link metadata under the existing
`evaluation_runs.model_manifest.pipeline_provenance` JSON object. Keep it outside
`claim_snapshot`, its hash and all decision inputs. Expose a typed read projection
alongside the unchanged evaluation DTO. Capture claim eligibility with the same
policy and frozen evaluation clock, solely for audit.

Reuse startup `agent_trace`, strict evaluation manifests, job checkpoints and
pipeline logs. New completed stage traces receive invocation IDs; reused or
historical traces are not backfilled. Partner records its exact canonical input
and final mapped/guarded output after validation, outside model prompts/contracts.

Retain suppressed legacy values in explicitly internal API projection metadata.
Render the inspection surface only when Vite's development flag is true. Preserve
all analyst-facing score and recommendation precedence. Golden fixtures pin the
current outputs, including surprising ones. No schema or historical data migration
is required for these JSON additions.

## Consequences

Source/evidence IDs and model/rule versions are distinguishable from investment
explanations. Unknown history remains unknown. Current evaluation and Partner
state can be compared without assuming their pointers match. Stored lineage adds
JSON size and a small amount of deterministic eligibility work; no LLM calls are
added. Existing application-layer tenancy remains mandatory; this change does not
resolve the previously documented lack of RLS on the portable migration path.

## Alternatives considered

A new tracing platform or provenance tables would duplicate existing storage and
require a schema migration. Recomputing historical lineage from current policy
would fabricate provenance. Putting run IDs in the analyst scorecard would add
engineering noise without explaining the investment decision.
