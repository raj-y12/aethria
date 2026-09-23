# Internal pipeline contracts

`pipeline_contracts.models` owns the shared typed envelopes, reasoning units,
references, lineage and validation results consumed by `investment_analysis`.
`investment_analysis.models` owns current model drafts, Partner judgment and the
complete immutable `AnalysisResult`.

## Contracts

| Contract | Purpose |
|---|---|
| ScoutOutput | Identity, factual reasoning, unknowns, contradictions, sources and evidence summary; legacy hypotheses remain outside its core. |
| ReviewerInput | Scout factual/evidence context, evidence items, thesis/mandate/portfolio/analyst context and optional prior review. |
| ReviewerOutput | Assessments, composable sections, investment case, risks, unknowns, contradictions, diligence priorities and overall assessment. |
| ReviewerAssessment | Identified dimension conclusion, optional proposed score, rationale, confidence, support and reasoning units. |
| ReasoningUnit | Identified FACT/INFERENCE/ASSUMPTION/OPINION/UNKNOWN text with claim/evidence/source references. |
| AnalysisSection | Typed optional section with PRESENT/NOT_APPLICABLE/UNKNOWN/UNSUPPORTED/NOT_ASSESSED status. |
| ValidatedAssessment | Optional proposal reference, validated score, status, cap, coverage, support/contradictions, policy and evidence references. |
| AssessmentValidationResult | Tenant-scoped assessment collection, lineage, policy versions and human-review requirement. |
| PartnerInput | Identity, Reviewer output, validation, evidence/unknowns/contradictions, thesis/mandate/context, prior decision and overrides. |
| PartnerOutput | Decision, rationale, investment case, risks, next steps, conviction, policy result and assessment references. |
| Lineage / References / PolicyVersions / StageMetadata | Shared opaque identifiers and known execution/policy identity. |
| Identity / SourceReference / EvidenceItem / EvidenceSummary / ReviewContext / PolicyResult | Small reusable components. |
| LegacyExtension | Complete original JSON and explicit mapping limitations, isolated from target meaning. |

These schemas include earlier compatibility fields and enum values that may
appear in serialized records. Keeping those data shapes does not require an
executable historical evaluator or payload conversion framework.

## Live ownership

Reviewer constructs assessments and evidence references. Validation checks those
proposals against the supplied snapshot and published evidence policy. Partner
interprets the review and validated assessments. The analysis service applies
operational constraints before publication. Dimension mapping belongs to
`investment_analysis.validation`.

The old `pipeline_contracts.adapters` conversions had no runtime callers and
were removed. They replayed captured JSON rather than producing current analysis.
This removal does not affect the live `investment_analysis.projection` module
or storage adapters in `utils.adapters`; product consumers still use those.

## Tenancy and persistence

Nested envelopes reject inconsistent tenant, company and opportunity identities.
Opaque identifiers do not prove database ownership; tenant-scoped repository
reads and publication checks remain responsible for that guarantee.

Historical evaluation JSON is read by `InvestmentAnalysisRepository`. Frozen
baseline JSON remains available for comparison without rerunning the old engine.
No database schema, public API, enum value or historical record changes are
required by this consolidation. See [ADR-0017](../adr/0017-single-analysis-publication.md).

## Verification

`backend/tests/pipeline_contracts/test_models.py` preserves model serialization,
reference composition, tenant mismatch, invalid score and dangling assessment
checks. Current analysis tests cover evidence safety, assessment caps and Partner
authority. The PostgreSQL publication and tenant-isolation scenarios remain in
`tests/evaluation_v2/test_phase0_provenance_postgres.py` and
`tests/investment_analysis/test_repository_postgres.py`, including the CI database
job. Only the unused adapter replay test was removed from that job.
