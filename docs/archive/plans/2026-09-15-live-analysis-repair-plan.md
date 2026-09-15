# Glitch Ads / Tines live-analysis repairs — Luna execution brief

Date: 2026-09-15. Owner: Luna. Requested by the user through Astra.

## Objective and authorization

Implement the six bounded repairs below, then verify them together. The user explicitly requested this scope and plan be given to Luna for execution. Execute in the existing checkout; do not stop after planning. Preserve Scout finds / Reviewer understands / Partner decides. These are reliability repairs to the migrated implementation, not a new architectural migration.

No commits, pushes, deployments, branches, resets, wholesale formatting, unrelated settings/HomePage changes, or direct historical-data rewrites. No new model selection, decision thresholds, second score authority, graph platform, broad RLS migration, or new retrieval provider. Retain published policy files and historical contracts. New internal structures are permitted only if necessary for these repairs; prefer existing models. Explain intentional output differences, never regenerate old goldens to hide them.

## 0. Establish the execution baseline

Read AGENTS.md, CLAUDE.md, docs/operations/investment-analysis.md, docs/operations/pipeline-provenance.md, docs/operations/pipeline-contracts.md, and ADR-0016 before editing. Record git status, diff summary, and hashes of touched pre-existing files. The checkout already contains a large uncommitted migration plus unrelated user edits. Treat all initial content as protected. Use existing code/tests as the starting point, not an older branch. Confirm nested instructions.

The observations below were made against local Aethria using live providers on September 14. The saved JSON is evidence of that run, not guaranteed current state. Inspect both files if still present:

- /tmp/glitch-refreshed-audit.json
- /tmp/tines-fresh-audit.json
- /tmp/aethria-refresh-runtime.log (provider and lifecycle logs; do not publish raw tenant data or secrets).

Trusted audit tenant: user_3AuLWhP64IrRCIZiOL4VtjIpO2J. Every query must explicitly scope tenant and object. Never infer tenant from supplied request bodies.

**Database safety:** root .env last pointed to a local production snapshot at 127.0.0.1:15432, database aethria_prod_snapshot. Do not run tests, migrations, cleanup, or broad mutations against it. Confirm the actual host/database without printing credentials. Isolated test container aethria-proverum-tests was previously available on 127.0.0.1:55439, database aethria; derive its test credentials from the existing local test setup without exposing them. Set both DATABASE_URL and TEST_DATABASE_URL explicitly for tests. Do not assume the container is running. Never apply test setup to a database whose purpose is ambiguous.

Allowed source interfaces, verified while preparing this plan:

- InvestmentAnalysisRepository.evaluate(..., pipeline_binding=None, review_mode="full", ...) in backend/investment_analysis/repository.py:95; lineage is assembled around lines 188–191.
- analyze(...) and _bind_review(...) in backend/investment_analysis/service.py:138 and :56. Generation is injected through Generate, enabling deterministic mocks.
- validate_assessments(...)->tuple[AssessmentValidationResult,list[CriterionResult]] in backend/investment_analysis/validation.py:21. It currently checks eligible cited claims and score caps; citation eligibility alone is not semantic entailment.
- reviewer_evidence(...) in backend/investment_analysis/grounding.py:27; factual_packet(...) in service.py:46.
- PipelineBinding in backend/evaluation_v2/provenance.py. Callers include pipeline_runner.py around :378, :862 and :2047. Verify each callsite before changes.
- useMemoDecisionBrief institutional query keys: opportunity-by-legacy-startup, evidence, evaluation, rulings. See app-front-end/src/hooks/useMemoDecisionBrief.ts:35–58.
- useDispatchLookup completion invalidation currently targets startup detail around :464; inspect the entire lifecycle, not just this line.
- buildPipelineProvenance in app-front-end/src/lib/pipelineProvenance.ts. Top-level opportunity ID currently reads only startup.canonical_opportunity_id.
- partnerRecommendationLabel in app-front-end/src/lib/recommendationSemantics.ts:6 already understands PARTNER_ANALYSIS plus insufficient_evidence. getVisibleRecommendation in queueAttentionDriver.ts:61 returns only the legacy INVEST/PASS/MONITOR enum. Do not repurpose that enum silently.

Line numbers are navigation hints; current source is authoritative. Reuse existing repository methods and API clients; do not invent lookup methods or access frontend storage directly.

Additional read-only discovery: founder_resolver.py:439 is_non_person_label is weaker than _is_person_name at :450; it admits Stack Exchange Network. The shared helper is used by api.py:1780–1791, utils/founder_enrichment.py:61, people/service.py:58 and investment_analysis/grounding.py. Reuse test_grounding.py:70 parameterized founder rejection and :94 _backend_to_frontend plus deepcopy immutability. Do not apply the restrictive extraction-name grammar indiscriminately to historical international names. evidence/retrieval.py:191 persists content[:2000] as its sole evidence excerpt; this is a candidate homepage-loss seam, not a proven root cause. utils/financials_grounding.py:99 verify_proposal provides existing quote/URL/numeric normalization ideas, but is not sufficient to establish metric/period/estimate semantics. test_grounding.py:21 claim(...) and :54 fake evidence repository are copy-ready fixture patterns; test_authority.py:51 demonstrates injected bad output and downstream validation assertions.

The saved Glitch audit confirms false canonical founder claims a0bce4f9-b423-4925-a3a8-8b9cc8a254a6 and f76b1ef6-7100-4e89-940c-1f096024900f for Stack Exchange Network. The saved Tines exaggeration exists in MARKET score_rationale, the first analysis-section reasoning unit and overall_assessment, so all three surfaces require regression assertions. Tines source anchors: 7bd50aed-824e-42fe-8d34-9fbed34cf833 reports the $39.6m annual revenue; cb74c877-4e69-4cce-b2ea-9773f39a9a8d and d1ac58f2-c461-4fe6-9425-2493e9175b98 contain the third-party estimated $60m ARR. Keep audit IDs in internal evidence only.

## Live reproduction anchors

Glitch Ads: startup 3b7b25ed-d610-4910-b9ca-b2cb34b828dc; company cf4f5898-2130-4bf6-9148-6c5be3b77bd3; opportunity 6f88fa82-433a-499c-95ca-97ec4bc43d12; refreshed evaluation aeae9304-a617-4b98-ace0-ab4742d6acfc; pipeline 7ef282d0-4532-4c26-bf38-db109c3b45da. Partner fea05079-6bc7-4ca2-bdbd-fbae39edb98f; Reviewer bb52dbba-1d19-49e1-9baf-e053cace5d25. Full rerun succeeded; 21 raw snapshot claims, targeted research and a second Reviewer call. Scores market 6/execution 4/product 7/technical 5/defensibility 4. Partner MORE_DILIGENCE, confidence .65, no operational constraint changed its decision. Prior unrelated Glitch animation/Netflix analysis disappeared from the new review. Do not undo identity/source filters to improve coverage.

Tines: startup 5db2f779-9366-4695-a1aa-6fe38c24f219; company b8a8f63c-af57-4d3a-a60f-20c8a3d979ea; opportunity 43d09588-d151-426d-bc89-cc9a5778ecc8; evaluation decf1bbd-1e9f-4814-ae5b-3ba59207cd9e; pipeline 9fbc91ff-6b18-41b0-a4e0-5ae1755d8f4f; job 2a2f2770-7eae-49de-8df2-4ed302244d10. Partner 4bb680fa-2481-49e7-a8a5-72283397ce6c; Reviewer b84ae3c1-16ed-418a-87de-be6044fbc6bd. New named lookup succeeded, 12 snapshot claims, one targeted research round. Market/execution/product/defensibility 7, technical 6; all five proposed scores accepted unchanged. Partner MORE_DILIGENCE, confidence .56. These are observed outputs, not desired fixed numbers for future live calls.

## 1. Freeze focused regressions before repairs

Create small sanitized deterministic fixtures in backend/tests/investment_analysis and frontend test conventions. Copy only relevant excerpts, shapes and relationships, not the entire tenant snapshot. Keep the Phase 0 golden JSON untouched. Use mocked generation and frozen retrieval, no paid calls in tests. Existing patterns: test_authority.py (invalid references, tenant rejection, model failure stages, judgment vs operational action); test_grounding.py; test_repository_postgres.py; frontend pipelineProvenance, recommendationSemantics, useMemoDecisionBrief and DispatchCommandBar tests.

Each repair must have a test demonstrating the current failure before implementation. Record failing and passing results. Some findings require root-cause investigation; distinguish what was observed from what a test proves.

## 2. Ground financial assertions, including prose outside reasoning units (highest priority)

Observed: Tines overall_assessment says "multi-hundred-million ARR trajectory". The snapshot contains an Irish Times excerpt reporting $39.6m annual revenue for the year to January 2025, and an explicitly third-party estimated $60m ARR. Neither establishes a current multi-hundred-million ARR. The word "trajectory" may express a projection, but no explicit assumptions/calculation are supplied. Validation accepted all scores. The overall_assessment currently passes through _bind_review as ungrounded free text; inspect conclusions, score_rationale, investment case, Partner rationale and summaries for the same issue.

Implement the smallest reusable financial-assertion support boundary. Preserve metric type, value/range, currency, period, actual vs estimate vs forecast, and attribution where known. Require a material factual number to be supported by the cited evidence with the same metric/period, or explicitly present it as an assumption/projection with its basis. Do not equate revenue with ARR, funding, valuation, ad spend, or a forecast. Do not choose one inconsistent source silently. Legitimate rounding/unit conversion and correctly labelled older periods must remain allowed.

Use structured evidence/reasoning already present and server-side checks for deterministic mismatches where feasible. Prompt changes alone are insufficient for the frozen injected bad-output regression. Avoid a generic number-presence regex that would approve $125m revenue because $125m funding appears somewhere. Do not claim a deterministic checker proves arbitrary prose entailment. For unsupported material assertions, use existing unknown/unsupported/blocked behavior and retain the raw draft only internally for audit; do not pass an unqualified assertion into Partner or render it as fact. Ensure dependent scoring cannot be validated solely by unrelated eligible citations. Never fabricate replacement facts or arbitrary score penalties. Use existing policy outcomes and explain limitations. If the current schema cannot safely enforce the scope, add a minimal internal typed support field rather than redesigning all contracts.

Tests: Tines mismatch above; legitimate $39.6m annual revenue; attributed $60m ARR estimate; valuation/funding not revenue; currency and period mismatch; valid rounding; forecast explicitly labelled with assumptions; conflict retained; unsupported prose in overall summary cannot bypass the reasoning checks; a valid citation with unrelated meaning does not validate the false assertion; tenant-foreign evidence rejected before model calls. Verify downstream Partner input and analyst projection, not only helper output.

## 3. Preserve relevant customer evidence and remove invalid founder projections

Glitch homepage was fetched through analyst context and contains logos and named testimonials (including We Are Riley and Mango Media). Reviewer/Partner nevertheless asserted "no logos"/"no case studies". Trace source admission, text truncation (cookie banner precedes content), factual extraction, claim creation, deduplication, packet construction, targeted research and context admission. Ensure relevant existing company-specific customer evidence reaches Reviewer with provenance. Treat logos/testimonials as company-reported signals, not verified paying customers, retention, revenue or PMF. When unavailable in the admitted evidence, say "not established in the reviewed evidence", not a negative fact about the company. Prefer reuse of the fetched source over another search/model call. Preserve cookie/privacy processing infrastructure; eliminate boilerplate from analytical context only where safely separable.

Glitch founder section still renders "Aisling Browne, Stack Exchange Network" despite the new review. Trace canonical people evidence, Scout fields, enrichment, compatibility projection and memo rendering. Reject organization/site labels as people through the existing person-validation path, not a Glitch-specific blacklist or stricter Western-name regex. Do not discard a valid person merely because the profile is hosted on a platform. Do not assert Aisling Browne is a founder without the actual supporting relationship. Separate fresh-write prevention from safe historical read projection: historical records remain stored and auditable, invalid display candidates are omitted or explicitly unverified. A full rerun must not preserve an invalid founder just because it exists in old JSON.

Tests: homepage with long consent text followed by testimonials; logo is company-reported not independent verification; unrelated Glitch Productions remains excluded; no false "no logos" statement accepted when admitted packet has logos; organization candidate excluded, valid culturally varied personal names retained; relationship unavailable stays unknown; historical compatibility read does not emit the invalid founder as established fact; tenant safety preserved.

Also inspect the $2.43m Glitch funding claim retained from historical evidence. Its same-domain URI is not proof the cited page actually supports the number. Determine whether extraction misattributes source/metric. Add a focused regression if confirmed, using the same financial support boundary; do not delete or silently correct stored history.

## 4. Carry real Scout lineage and make debug summaries internally consistent

Both new evaluation records had scout_run_id=null, including the fresh Tines Scout run. Trace where Scout IDs are generated/stored and whether the startup trace and PipelineBinding lose them. Carry the actual known originating Scout reference through manual lookup, periodic discovery, rerun, refresh and durable checkpoints. For reused factual state, preserve the original Scout ID separately from the new pipeline run; do not stamp the rerun ID as Scout or invent IDs for historical gaps. Check retries do not accidentally create a different source lineage. No new table unless source inspection demonstrates necessity.

Inspector: resolve the opportunity from the already fetched, identity-checked opportunity/evaluation context when startup.canonical_opportunity_id is absent. Prefer a consistent single resolved context passed to the inspector. If sources disagree, expose an explicit debug mismatch; do not silently pick a foreign/stale record. Reviewer/Partner IDs should represent the current evaluation, with compatibility trace differences visible. Keep technical IDs development/audit-only. Label a projected score as a projection while preserving its underlying authoritative score origin; do not describe all historical numeric data as canonical.

Tests: fresh lookup has actual Scout ID linked to evaluation; periodic and full rerun propagation; rerun retains source Scout identity; historical missing stays null with truthful missing state; cross-tenant/company references rejected; inspector top-level ID correct without startup ID field; conflicting IDs flagged; Partner current-evaluation comparison correct. Source snapshot and admitted subset must remain distinguishable in audit, not silently conflated.

## 5. Refresh memo dependencies and unify recommendation presentation

Glitch persisted a new evaluation while the open memo showed old animation analysis and briefly "opportunity-to-decision record link unavailable". Reloading restored the current review. Reproduce with mocked queries and a completed rerun changing evaluation IDs. Inspect query invalidation, query enablement, partial-memo merge, stale closure/local state, race ordering and old terminal states. On actual completion invalidate/refetch the affected opportunity, evaluation, evidence and startup projection, using existing keys from useMemoDecisionBrief. Avoid global polling, broad cache resets, or invalidating all tenants. Do not consider an old Partner recommendation proof the new rerun finished. Do not mix an old review with a new decision. During refresh clearly retain a labelled prior result or show pending state until coherent current data is available.

Queue says Monitor while Partner operational action is MORE_DILIGENCE. Reuse recommendationSemantics/partnerRecommendationLabel as the presentation boundary across queue badges, accessibility labels, dispatch completion, memo and inspector. Preserve human-ruling precedence and distinction between Partner judgment and mandate-constrained operational outcome. Historical true MONITOR remains Monitor. Do not merely replace all MONITOR text. Inspect canonicalOpportunityToStartup in api/startups.ts: its existing pass->PASS / everything else->MONITOR compatibility mapping cannot become the authoritative displayed label. Preserve old API fields; add meaningful semantic fields if needed and update API.md/types together. A score or recommendation must not change merely because the label is fixed.

Tests: open memo updates old->new evaluation without page reload; delayed/out-of-order requests do not revert it; failed rerun retains identifiable prior history; completion requires current run; More diligence consistent in queue/memo/ready notification/accessibility; true Monitor stays Monitor; human override wins; policy-constrained action displayed with distinction from Partner judgment; old records without new metadata remain readable; no raw engineering IDs added to production analyst components.

## 6. Integration and acceptance

Run targeted tests after each bounded change, then the repository gate once after integration. Include the frozen Phase 0 fixtures, pipeline contract tests and PostgreSQL integration coverage. Compare old/new fixture outputs explicitly. Financial unsupportedness may intentionally change affected validation and decision eligibility; label those changes and preserve valid supported controls. Do not demand the same live score from nondeterministic providers.

Commands (verify repository CI for additional requirements):

    python3 -m pytest -o asyncio_mode=auto
    cd app-front-end && npm run lint && npm test && npm run build && npm run check:bundle
    cd web-front-end && npm run lint && npm run build && npm run check:bundle && npm run check:marketing
    git diff --check

Run PostgreSQL contract/integration tests explicitly against the isolated DB, including jobs, investment_analysis and provenance tests; report skips and unavailable dependencies separately. Run migration checks if schema changes are necessary, on isolated DB only. No full-suite run against root .env database. New SQL must be append-only, backward compatible, include appropriate RLS and CI coverage; prefer no schema migration for this scope.

Finish with one full Glitch rerun and one Tines rerun in the already authorized local verification environment if live providers and authenticated UI are available. Do not retry paid calls repeatedly to obtain a desired answer. First capture existing history, then use supported routes/UI, never SQL rewrite. Verify the actual development inspector and analyst memo, not just persisted JSON. Scraper 403/429 failures were observed: retain named limitations and report provider blockers honestly. Browser tabs and running processes may have closed since September 14; inspect first, restart only the required local application, do not kill unrelated processes. If live verification is blocked, complete deterministic checks and state exactly what remains unverified.

Acceptance: no unsupported financial exaggeration reaches authoritative analysis as fact; customer evidence remains attributed and discoverable; invalid founder site names no longer appear as established people; real new Scout lineage is retained; inspector agrees with resolved evaluation identity; reruns refresh coherent memo state without browser reload; More diligence is not displayed as Monitor; old history remains readable; tenancy remains enforced; all applicable checks pass.

Final report to user: per-issue cause, files changed, test failing-before/passing-after evidence, full suite results, old/new live or deterministic comparison, retained historical limitations, provider failures, performance/call-count impact, and exact remaining risks. Do not claim production readiness merely because jobs succeed. Send a concise completion/blocker summary back to Astra task 01a06ee0-b061-7011-bacd-4ac5e2bff054. Keep execution in Luna; no other task or subagent is needed unless a concrete independent verification task justifies it.
