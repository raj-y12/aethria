# Canonical Manual Lookup Vertical Slice

## Goal

Make a manual lookup a canonical, tenant-scoped path from observation through identity admission, evidence ingestion, immutable evaluation/recommendation, and decision-view handoff.

## Completed

1. Add `OpportunityPipeline` orchestration with identity, thesis/policy, evidence, and evaluation gates.
2. Add canonical opportunity queue and decision-view repository queries and API routes.
3. Add an authenticated manual-lookup endpoint and typed frontend API/query hooks.
4. Verify ordering and fail-closed identity behavior with targeted tests, then run one focused review and full verification.

## Deferred

- Portfolio side effects for INVEST rulings remain a later slice; this path stops at recommendation/ruling handoff.
- Legacy startup UI migration remains a later canonical-read cutover slice.
