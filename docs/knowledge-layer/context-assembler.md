# Criterion Context Assembler

Step 7 adds a bounded, deterministic context boundary between canonical claims/evidence and Reviewer prompts.

`ContextAssembler` is a facts-only component. It selects claim types for one decision criterion, joins source-linked evidence, preserves supporting and contradictory relationships, filters expired or disallowed evidence, and returns explicit unknowns when coverage is insufficient. It does not score, judge, infer, or generate narrative.

The shared provider resolves a legacy Scout startup through the tenant-scoped identity projection, loads its canonical evidence ledger, enriches claim links with evidence-item and artifact provenance, and produces packets for:

- regulatory;
- founder/team;
- funding;
- traction/revenue;
- market;
- product/technical capability.

Regulatory and founder context retain their existing Reviewer packets and grounding semantics during this migration. Shared canonical packets are additive when canonical coverage exists, so the Scout JSON contract remains intact. Competition and business model deliberately remain on the legacy path until their canonical claim models are established.

No schema or embedding migration is required for this step. The provider reuses the existing tenant-scoped identity, evidence, artifact, and claim-link records. Reviewer prompt assembly records the size of the canonical packet; prompt reduction is intentionally deferred until legacy parity is demonstrated.
