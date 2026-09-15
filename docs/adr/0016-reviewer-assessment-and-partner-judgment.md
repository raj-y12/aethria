# ADR-0016: Reviewer assessment and Partner judgment

Status: Accepted. Runtime entry points use the shared investment-analysis core.

## Context

The historical evaluator chose scores and a recommendation before Reviewer.
Reviewer personas and Partner thresholds also produced competing scores. Phase 0
freezes that behavior for historical replay; Phase 1 provides typed contracts.

## Decision

Live evaluation entry points use `InvestmentAnalysisRepository`. It reads the
tenant's canonical factual snapshot and published fund context, releases its
database connection, prepares missing factual evidence, then calls Reviewer,
validates the cited assessment against evidence policy, and calls Partner once.
Reviewer may request one bounded research pass; it reviews again only when the
factual snapshot changes. Otherwise unresolved questions remain diligence items.
Partner chooses ADVANCE, PASS,
MONITOR or MORE_DILIGENCE. Evidence safety rules constrain the operational action;
the original Partner judgment remains recorded separately.

The existing evaluation transaction persists the completed contracts in
`judgment_audit.investment_analysis`, criteria and recommendation. It verifies the
evidence snapshot and expected current evaluation while holding the opportunity
lock. Published context is checked again after model calls. A context publication
between that check and transaction commit remains a concurrency limitation.
New snapshots also retain the linked source excerpt, URI and artifact identity.
Reviewer can cite only sources linked to its cited claims, and excerpt changes
invalidate the snapshot. Historical snapshots lacking those fields keep their
original shape and hash for replay.

Scout v2 preserves company facts, sources, unknowns and factual contradictions.
It neither requests nor emits legacy investment hypotheses. Current prompts carry
a fixed factual-authority instruction, including promoted tenant prompts.
The v1 schema and historical hypothesis readers remain available.
Live extraction retains exact, tenant-scoped verified source quotations as
attributed `source_statement` claims. Their confidence concerns faithful copying;
source reliability remains separately represented by evidence policy. No live
extractor chooses an investment score or normalizes a claim into a score band.
The previous scored extractor remains only for historical tests/replay.
Snippet-derived Scout claims remain `unverified`, matching their evidence items;
matching a source excerpt does not constitute independent verification. This is
an intentional correction for newly ingested facts, not a historical rewrite.

Explicit structured fund sector exclusions are checked against eligible,
uncontradicted sector claims. A confirmed exact match constrains the operational
action to PASS while retaining Partner's original judgment. Missing or conflicting
sector classifications require diligence before ADVANCE. Preferred stages and
sectors remain analytical context; they are not silently converted into hard
exclusions. Free-text sector taxonomy mapping is not a deterministic assertion.

## Consequences

- No new database schema is required for this boundary.
- Failed model or budget dependencies never fall back to old decision authorities.
- The prior startup memo and stage projections are archived before invalidation.
- Analysts see proposed versus validated scores and evidence limitations. Raw
  lineage remains in authenticated API audit data and development tooling.
  The method popup distinguishes historical evidence scoring from new Reviewer
  proposals and no longer displays policy/rubric identifiers.
- Periodic shared analysis requires both Reviewer and Partner toggles. Scout-only
  discovery still establishes facts. Explicit lookup retains its entry behavior.
  Named lookup completes its bounded evidence retrieval before one investment
  analysis. Budget, lifecycle and malformed-model failures terminate that lookup;
  they cannot fall through to stage callbacks that reuse older analysis.
- Historical evaluators and Phase 0 golden fixtures remain unchanged for replay.
- Partner-only API/operator refresh reuses compatible Reviewer assessments and
  revalidates at the current freshness clock. Changed evidence or policy requires
  a full review. Portfolio positions and analyst rulings are scoped and captured.
- Operator triage overrides use the shared core; standalone legacy engine mains
  are retired. Historical persona prompt previews remain experimental and never
  write authoritative review scores.
- Dependency reads mark historical reviews stale when evidence, support, thesis,
  policy or prompt versions change. They never mutate historical scores. Full
  refresh is deliberately conservative for all policy changes; selective
  revalidation across policy versions is not implemented.
- Active Partner rules v5 version the authority change without changing v4's
  numerical evidence/safety limits. Legacy decision bands remain in compatible
  stored configuration but are omitted from both model contexts and Settings.
  Reviewer also does not receive a prior recommendation as analytical input.
- Same-cycle periodic failures are deduplicated and cannot fall through to older
  projections or prevent other candidates from finishing.

## Frozen-company comparisons

The original Phase 0 JSON remains unchanged. New deterministic model mocks in
`tests/investment_analysis/test_baseline_comparison.py` separately establish:

- Strong verified evidence accepts a Reviewer proposal of 8 and Partner ADVANCE.
- Unverified or missing evidence stays unscored and constrains advancement.
- Contradictions retain supported scores but require diligence before advancement.
- Missing execution remains null; no negative factual claim or zero is invented.
- The old out-of-mandate fixture only contains a legacy thesis-fit opinion. A new
  Partner PASS is tested separately from factual mandate enforcement; that old
  opinion is not promoted into a verified exclusion claim.
- Historical canonical 6 versus legacy 9 stays frozen. A fresh Reviewer proposal
  of 9 validates as 9 with the fixture's strong evidence, independently of both
  stored legacy numbers. This is an intentional authority change.

These mocks verify authority and constraints, not live-model analytical quality.

## Alternatives considered

Replacing canonical persistence would discard working evidence, tenancy, history
and outbox infrastructure. Keeping the pre-Reviewer recommendation authoritative
would leave Partner as a mapper. Both conflict with the requested migration.
