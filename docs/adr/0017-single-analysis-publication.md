# ADR-0017: One investment-analysis publication boundary

Status: Accepted. Consolidates the persistence boundary established in ADR-0016.

## Context

The live InvestmentAnalysisRepository inherited EvaluationRepository. The base
repository could either publish a completed analysis or execute the historical
score-based evaluator when no analysis was supplied. No live entry point needed
that alternative, but it remained an accidental execution path. The two packages
also imported each other's types.

## Decision

InvestmentAnalysisRepository owns immutable publication and reads directly. Its
public evaluate operation prepares evidence and invokes the current analysis
service. A private _publish operation requires a completed AnalysisResult and
its evidence clock. There is no optional-analysis branch or evaluator fallback.
The old evaluation_v2.repository module is removed; lifecycle errors now belong
to the current repository.

Publication retains opportunity locking, expected-current-evaluation comparison,
evidence snapshot comparison, lifecycle checks, authority fencing, transactional
assessment/recommendation writes, current-pointer updates and outbox events.
Model work remains outside the publication transaction. Published fund context
is rechecked after model work; the previously documented check-to-commit window
is unchanged, not claimed to be fixed by this consolidation.

Existing database tables, IDs, immutable triggers, record shapes and read
behaviour remain unchanged. Historical records can be read without executing
the engine that produced them. Startup projections remain necessary for current
product reads and are not removed in this change.

Unused scoring presentation/consistency modules and their implementation-only
tests are removed. The unreachable score-to-action body in the old Partner is
removed; its reachable compatibility behaviour is preserved.

The unused `pipeline_contracts.adapters` conversion/replay framework is removed.
Its only live dependency was dimension mapping, now owned by analysis validation.
Shared model schemas and compatibility enum values remain readable.

The historical `evaluate_snapshot` engine and its score-aggregation helpers are
removed after transferring safety coverage to the current analysis path. Frozen
baseline JSON is retained as data, with fixture construction separated from old
execution. Policy, eligibility, snapshot and recommendation-change helpers remain
in `evaluation_v2`; deleting an engine does not delete these live dependencies.

Runtime callers name `InvestmentAnalysisRepository` directly. The runner no
longer imports retired Reviewer/Partner classes, constructs unused context
providers or carries an unreachable persona-manifest capture branch. Current
analysis still records its executed prompt/model/dependency identity.

The standalone `partner.engine` is removed. Its completed-analysis consumer
already lives in `investment_analysis.stages`; it never decides from legacy
scores. The identity resolver's JSON parser moved unchanged to the existing
OpenAI utility so it no longer imports legacy Partner implementation.

## Verification

Persistence tests now publish completed current analyses rather than invoking
the historical evaluator. Their checks retain tenant isolation, frozen source
provenance, null scores, lifecycle protection, stale-completion rejection,
historical memo capture, change attribution and real PostgreSQL manual lookup.
Legacy record JSON decoding remains covered separately.

Current safety tests drive a mocked Partner requesting ADVANCE through the real
analysis service. They cover unsupported evidence, missing dimensions,
contradictions, exact/malformed decisive values, risk/exclusion constraints,
expiry, source-quality and confidence caps, operator attribution, null scores
and human review. Current stage tests retain no-work, missing-analysis, blocked
and failed-candidate accounting; projection tests preserve Partner provenance,
action mapping and tenant isolation. Historical manifest data/reader tests remain,
while the unused persona constructor and old Partner-engine payload tests retire.
Snapshot hashing and materiality tests remain unchanged in
meaning. Model-contract tests retain serialization and tenancy checks.

Retired tests enforced historical score-to-action thresholds, minimum-anchor
selection, generated rationale strings and lossless unused-adapter replay. Those
are not current product contracts. Existing live semantics deliberately differ:
Partner owns the action even when assessments are capped; grounded exclusions
precede missing dimensions; ADVANCE requires human review. A zero confidence cap
is preserved in validation without the old aggregator's division. This change
does not modify those semantics or any published decision policy.

## Remaining boundaries

The old Partner engine and its decision/schema/rationale helpers have been
removed. Reviewer persona promotion is blocked because those prompts do not
control the current Reviewer; preview remains available against frozen current
analyses. Policy compilation, startup projections, and runner callbacks remain
while their live callers depend on them. No new analytical capability is introduced.
