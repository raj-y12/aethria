# Investment analysis: runtime ownership and verification

## Runtime architecture

The active core is `backend/investment_analysis/repository.py` and `service.py`:

1. Establish tenant-scoped company/opportunity identity.
2. Reuse canonical factual evidence, or perform bounded retrieval when needed.
3. Give Reviewer the factual snapshot and fund context.
4. Allow one targeted research pass; repeat Reviewer only for changed facts.
5. Validate Reviewer proposals against evidence eligibility and policy caps.
6. Ask Partner to choose ADVANCE, PASS, MONITOR or MORE_DILIGENCE.
7. Apply explicit safety/mandate constraints to the operational outcome, retaining
   Partner's original judgment.
8. Atomically persist immutable analysis, criteria, recommendation and compatible
   startup projections after checking evidence and concurrent completion.

This is the live authority boundary. Historical score engines remain callable
for replay tests, but no production entry point uses them as a second authority.
`evaluation_v2` supplies evidence policy and persistence, not a pre-Reviewer
investment recommendation.

## Scout

Scout retains its discovery personas, identity, external references and retrieval
infrastructure. The v2 contract requests facts, unknowns and factual conflicts.
Fixed factual instructions also apply to tenant-promoted Scout prompts. Investment
hypotheses are excluded from new payloads; v1 historical records remain readable.

New snippet-derived Scout claims are unverified. Exact quotations from verified
source items can be retained as attributed `source_statement` claims. Verification
of a quotation is not verification of every assertion made by its publisher.
Source reliability remains separate. The retained periodic `confidence` field is
a historical structured mandate-fit projection, not factual certainty; it no
longer gates Reviewer admission.

## Reviewer and scoring

One evidence-first Reviewer replaces the three live scoring personas. Composable
sections cover team, market, product, technology, execution, defensibility and
other relevant investment questions without requiring artificial completeness.
Material reasoning separates FACT, INFERENCE, ASSUMPTION, OPINION and UNKNOWN.
Factual and inferential units require attribution to supplied claims. Foreign or
unlinked claim/evidence/source IDs are rejected.

Reviewer proposes each score with rationale, limitations and unknowns. Validation
checks the cited claims using existing verification, source quality, freshness,
confidence and contradiction policy. Unsupported proposals remain unscored;
eligible proposals may be capped. Proposed and validated values remain distinct
and explainable. Partner never computes another dimension score.

The original source excerpt and URI travel with the snapshot. Legacy stored score
bands and Scout investment opinions are removed from the factual model packet.
Retired score-to-action settings are excluded from both model contexts. Prior
recommendations are omitted from Reviewer input; Partner may consider them as
historical decision context.

Reviewer may request up to five targeted research questions in one bounded pass.
Existing usable evidence is reused; no material change means no second Reviewer
call. Unanswered questions remain explicit diligence priorities.

## Partner and constraints

Partner receives completed review, validated assessments, strongest available
evidence, uncertainties, fund thesis, mandate, recent portfolio context and
attributed analyst rulings. It must reference actual Reviewer assessments.
Equal scores can produce different recommendations because Partner judges the
investment case, uncertainty and fund context.

Verified hard exclusions/critical risks can constrain the operational outcome to
PASS. Explicit structured sector exclusions require eligible, uncontradicted
sector evidence and exact matching. Missing/conflicting classifications require
diligence before ADVANCE. Preferences are not silently made into exclusions.
Missing required evidence, insufficient scored coverage and unresolved conflicts
also constrain advancement. Original action, constraints and operational action
are recorded separately. ADVANCE requires human review; it is not an executed
investment. Existing human rulings and closed opportunity lifecycle states are
preserved.

## Entry paths and reruns

| Entry | Actual behavior |
| --- | --- |
| Periodic discovery | Thesis gate → Scout → identity admission → shared core. Both Reviewer and Partner toggles must permit analysis. Duplicate observations produce one attempt per opportunity per cycle. |
| Named/manual lookup | Named identity/evidence entry → shared core once. Failed analysis terminates with a named failure/block. |
| `/api/opportunities/manual-lookup` | OpportunityPipeline delegates investment analysis to the same repository; remaining adapters are projections. |
| Full rerun/operator review | Refresh shared analysis, reusing available factual evidence. No retired persona or score mapper. |
| Partner-only refresh | Reuse compatible Reviewer reasoning/assessment IDs, revalidate freshness, then call Partner once. Changed Reviewer dependencies require full refresh. |
| Thesis reprocessing | Existing missing-thesis backfill calls the shared core without Scout rediscovery. Other stale reviews can be refreshed explicitly. |
| Durable jobs | Existing handlers/checkpoints dispatch the same runner/core. No independent job scoring authority. |
| Local/dev | The shared PostgreSQL dependency is required for authoritative investment analysis. Missing infrastructure blocks; there is no legacy scoring fallback. |

GET evaluation performs a read-only dependency check. Material evidence changes,
changed evidence support, thesis/policy changes and changed analysis instructions
mark the recorded review stale. Memo readers see a refresh notice while historical
scores remain intact. The check is a point-in-time observation, not a continuous
background monitor. All policy-version changes conservatively require full review;
selective validation-only reuse across changed policy versions is not implemented.
Portfolio/analyst-context changes can be handled by explicit Partner-only refresh.

## Persistence, lineage and history

Existing companies, opportunities, artifacts, evidence items, claims and claim
links remain authoritative factual infrastructure. Completed contracts are stored
in immutable evaluation `judgment_audit.investment_analysis`. Existing criterion
assessments and recommendation records hold the projection of those contracts.
Startup JSON is a compatibility projection, not an independent authority.
There are no new database migrations or historical backfills.

Decision → assessment → reasoning unit → claim → evidence item → source references
are tenant-scoped and preserved. The audit captures models, prompt hashes, policy,
thesis, snapshot, original Partner judgment, constraints and stage trace. Research
audit includes the initial review and whether facts changed. Previous memo/stage
projections are archived before cache invalidation. Criteria record previous score
and reasoning plus change flags.

## Analyst experience

Scorecards show validated score, proposed score when constrained, reasoning,
evidence limitations and changes from the prior review. The method explanation
describes Reviewer proposal and evidence checks. Memo evidence links, conflicts,
unknowns and Partner rationale remain investment-focused. Stale reviews show a
plain-language refresh message. Settings describes Partner judgment rather than
exposing retired automatic INVEST/PASS sliders.

Raw IDs and hashes remain in authenticated typed API audit fields and the
development-only provenance inspector. They are not added to ordinary analyst
prose. Historical records retain their original score origin and explanations.
Legacy startup action projections still spell ADVANCE as INVEST and map diligence
to MONITOR; canonical recommendation state and the memo's evidence state preserve
the distinction. Those strings are compatibility values, not separate decisions.

## Intentional differences from Phase 0

- Scout no longer emits investment hypotheses; unverified snippets cannot be
  promoted to verified factual claims merely by matching their text.
- Reviewer proposes the analytical score; old deterministic score bands do not.
- Partner chooses the action after review; upstream recommendation mapping and
  old Partner thresholds no longer choose it.
- Unsupported scores remain null, with explicit support/cap explanations.
- Historical canonical 6 / legacy 9 stays unchanged in the Phase 0 fixture. A new
  Reviewer proposal of 9 on the same strong evidence validates to 9. This is a
  separate intentional authority-change test, not a rewritten golden baseline.
- New missing/unverified cases require diligence; contradictory and missing
  dimensions remain visible. Confirmed exclusions constrain original judgment.
- Live research is bounded and source retention does not make an extraction LLM
  call. One Reviewer replaces the three live personas.
- New reads can report stale dependencies; history is never silently recalculated.
- Active rubric v4 and Partner rules v5 identify the migration. Numerical safety
  limits in Partner v5 are identical to v4; old versions remain unchanged.

## Verification

Verified locally on 6 September 2026, using a separate PostgreSQL 16 database:

| Command / suite | Result |
| --- | --- |
| `TEST_DATABASE_URL=… python3 -m pytest -o asyncio_mode=auto` | 2,590 passed, 4 skipped; one Starlette/httpx deprecation warning. Includes PostgreSQL contracts, tenant isolation, Phase 0 golden replay and new pipeline integration. |
| App `npm run lint` | Passed, no warnings. |
| App `npm test` | 516 passed across 100 files. |
| App `npm run build` / `npm run check:bundle` | Passed, 65 assets within budget. Demo emits the existing large-chunk advisory. |
| App `npm run test:e2e` | 2 passed: app shell and unauthenticated sign-in. |
| Marketing lint/build/bundle/marketing checks | Passed; 52 assets and 17 marketing checks. |
| Marketing `npm run check:waitlist` | Passed. |
| Both `npm audit --omit=dev --audit-level=high` | Gate passed; existing moderate advisories remain. |
| `python3 -m pip_audit -r backend/requirements.lock` | No known vulnerabilities. |
| Backend API import | Passed. |
| `docker build -f backend/Dockerfile …` | Passed using Python 3.12 image. |
| PostgreSQL migration runner | No new migrations; existing migration chain applied. |
| `git diff --check` | Passed. |

New behavioral tests cover factual Scout boundaries, citation scope, source
retention, evidence reuse/research, scoring/caps, independent Partner judgment,
mandates, failures, current-path convergence, stale dependencies, concurrent
completion, history and actual PostgreSQL round trips. The original seven golden
companies remain frozen, with separate new-authority comparison tests.

Manual browser inspection opened the local illustrative demo's Flow and memo.
Its historical mock API lacks canonical evaluation data and displays the explicit
unavailable state. It is not a successful authenticated production-shaped analyst
smoke test. New score and memo behavior is covered by component tests; live provider
and authenticated deployment acceptance remain necessary.

The PostgreSQL job test was made clock-safe: due time comes from PostgreSQL rather
than the host clock, and cleanup now covers assertion failures. Its locking and
tenant assertions are unchanged. Settings label tests and the active-policy test
were updated for intentional product/version changes; historical goldens were not.

## Significant files

| File(s) | Responsibility |
| --- | --- |
| `backend/investment_analysis/models.py` | Typed live Reviewer/Partner drafts and completed analysis. |
| `backend/investment_analysis/prompts.py` | Evidence-first Reviewer and senior Partner instructions/version hashes. |
| `backend/investment_analysis/service.py` | Reviewer → research → validation → Partner authority and trace. |
| `backend/investment_analysis/validation.py` | Evidence eligibility, proposal caps and support explanations. |
| `backend/investment_analysis/mandate.py` | Explicit factual sector exclusion checks. |
| `backend/investment_analysis/model_gateway.py` | Tenant/budget-scoped, schema-checked provider calls. |
| `backend/investment_analysis/repository.py` | Shared reads, released DB connections, context and atomic persistence boundary. |
| `backend/investment_analysis/evidence.py` | Bounded shared factual preparation/research. |
| `backend/investment_analysis/dependencies.py` | Read-only dependency validity. |
| `backend/investment_analysis/projection.py` | One-way historical DTO compatibility. |
| `backend/investment_analysis/stages.py` | Runner callbacks; no legacy score authority. |
| `backend/evidence/factual.py` | Exact scoped source quotations and deduplication. |
| `backend/scout/{base,engine,schema,scouts}.py` | Factual Scout contract/prompts and preserved discovery infrastructure. |
| `backend/context/scout_claims.py` | Honest unverified status for snippet claims. |
| `backend/evaluation_v2/{repository,service,evidence_projection,partner_rules}.py` | Immutable contracts/history, source snapshots and v5 parser. |
| `backend/pipeline_runner.py`, `backend/api.py`, `backend/opportunity_pipeline.py` | Production entry-point convergence. |
| `backend/routers/{evaluations,opportunities,meta}.py` | Scoped refresh, operator convergence and named blocks. |
| `backend/reviewer/engine.py`, `backend/partner/engine.py`, `backend/meta/mutator.py` | Retired standalone authorities; historical preview/replay compatibility. |
| `backend/scripts/backfill_evidence_extraction.py` | Backfill uses factual retention and shared analysis. |
| `backend/models.py` | Additive compatibility metadata and absent legacy verdict support. |
| `app-front-end/src/api/evaluations.ts`, `src/types/startup.ts` | Typed new provenance, support and dependency fields. |
| `app-front-end/src/lib/{canonicalScoring,memoDecisionBrief}.ts` | One displayed score source and honest Partner attribution. |
| `app-front-end/src/components/scoring/AssessmentScorecard.tsx` | Proposed/validated explanations and review changes. |
| `app-front-end/src/components/memo/MemoDecisionBrief.tsx`, `src/hooks/useMemoDecisionBrief.ts` | Analyst evidence attribution and stale review notice. |
| `app-front-end/src/settings/SettingsPage.tsx`, `src/settings/settingsModel.ts` | Retire misleading live threshold controls. |
| `backend/tests/investment_analysis/` and affected backend/frontend tests | Behavioral, integration, historical and UI verification described above. |
| `resources/contracts/schemas/scout_output_v2.json`, `resources/manifest.json` | New factual Scout contract; v1 retained. |
| `resources/config/evaluation_rubric/v4.json`, `partner_rules/v5.json`, `active.json` | Version the new authority without mutating published policy. |
| `docs/adr/0016-reviewer-assessment-and-partner-judgment.md`, `ARCHITECTURE.md`, `API.md` | Current ownership, runtime/API contracts and deliberate tradeoffs. |

Phase 0 provenance and Phase 1 contract changes were already present in the working
tree and remain intact. Pre-existing `HomePage.tsx` and its test were not edited by
this migration. No commit, push, branch operation or deployment was performed.

## Costs, limits and production acceptance

The normal analytical path makes one Reviewer and one Partner call. A material
research update adds at most one Reviewer call. Retrieval is reused when eligible
canonical evidence exists. Model budgets remain enforced; a denied budget blocks
rather than activating a legacy fallback. Dependency inspection adds scoped reads
and deterministic eligibility work to memo evaluation requests, not model calls.

Remaining risks are explicit:

- Mocked evaluations prove authority, not exceptional live-model investment
  quality. Representative live-provider evaluation and authenticated analyst
  acceptance are still required before production certification.
- Citation validation proves reference membership and evidence eligibility, not
  semantic entailment of every inference. Reviewer quality remains consequential.
- Database RLS is still absent on the existing portable schema. App-layer tenancy
  tests pass; this does not replace a database isolation backstop.
- Published context can change between the final context recheck and transaction
  commit. Evidence/current-evaluation races are checked under the opportunity lock.
- Source-statement deduplication is not atomic across simultaneous retention calls.
- Sector exclusion matching is exact. Broader free-text mandate interpretation is
  Partner context, not an invented deterministic taxonomy.
- Policy changes conservatively require a full review. Bulk thesis backfill still
  targets missing thesis versions; it is not an automatic all-stale scheduler.
- Historical DTOs, policy fields and preview helpers remain for compatibility and
  replay. They are explicitly retired as live scoring/decision authorities.
- Existing moderate dependency advisories and the noted build/deprecation warnings
  were not hidden by changing dependencies or verification gates.

The runtime implements Scout factual discovery, Reviewer investment assessment,
evidence validation and Partner decision ownership. The repository is not yet
certified production-ready solely on the basis of this deterministic verification.

## Live ProVerum verification — 8 September 2026

The original ProVerum dispatch failed repeatedly at the model-output boundary.
The gateway requested JSON mode, which did not enforce the supplied Pydantic
schema. It now uses the OpenAI SDK structured-output `parse` operation for both
Reviewer and Partner. Refusal and output truncation produce named blocks; consumed
tokens remain accounted for. Provider-boundary tests use the real installed SDK
with mocked HTTP responses, including refusal and truncation cases.

The original job completed on attempt 9. Inspection of that immutable review
uncovered another defect: reasoning downgraded to UNKNOWN after invalid citations
could still support a numerical score through a remaining valid claim reference.
Two regression tests reproduced the erroneous 7. Validation now takes numerical
support only from FACT and INFERENCE units, while still checking all reference
IDs against the supplied snapshot. UNKNOWN, ASSUMPTION and OPINION remain context.
No historical evaluation was rewritten and no policy threshold was changed.

After restarting the local application, an authenticated browser dispatch of
ProVerum completed on its first attempt:

- Job: `7d3c87ae-4578-44ab-95d4-38989368f559`.
- Evaluation: `46b34bfe-ce4f-4d11-94f2-1702d071ea31`.
- Completion: `2026-09-08 06:10:07 UTC`.
- Checkpoints: Scout, identity, evaluation, Reviewer, Partner, projection and
  `lookup_result=lookup_completed` all succeeded.
- Immutable trace: Reviewer → targeted research → Reviewer → validation → Partner.
- Partner judgment and operational outcome: MORE_DILIGENCE, confidence 0.60,
  human review required.
- Proposed scores: Market 7, Product 8, Execution 8, Defensibility 7; Technology
  was not assessed. All validated scores were null because no FACT/INFERENCE
  reasoning supplied usable score support. The authenticated memo displayed
  Not scored / Limited evidence and the new Partner rationale.

This proves live execution success, not sufficient investment-analysis quality.
The final assessment reasoning was all UNKNOWN after binding; citation quality
remains poor despite valid output structure. The memo still displayed the suspect
historical founder label "CFx Strategy" while its narrative described credible
founder-led execution. Regulatory and patent assertions require better attribution.
The earlier memo displayed long scraped boilerplate in claim provenance; the new
one correctly has no scored supporting claims. The dispatch progress text lagged
behind the actual backend stage, and the filtered docket search did not locate
the company even though its completed memo opened through dispatch. These are
unresolved quality/UX findings, not suppressed exceptions or successful diligence.
Firecrawl returned 403/429 warnings; retrieval continued through the existing
provider path without treating unavailable material as verified evidence.

Verification after the fixes:

- Focused investment-analysis, Partner-rule and Phase 0 golden suites:
  **348 passed, 1 skipped** without PostgreSQL.
- Full backend without PostgreSQL: **2,527 passed, 80 skipped**.
- Full backend with a separate PostgreSQL 16 database and all 31 migrations:
  **2,603 passed, 4 skipped**. Tenant and persistence contracts included.
- App lint, **516 tests / 100 files**, build and bundle check passed (65 assets).
- Marketing lint, build, bundle (52 assets) and marketing checks (17) passed.
- `git diff --check` and compilation of the changed runtime modules passed.
- Existing Starlette deprecation, React test `act` warnings and demo bundle
  advisory remain. No new dependency or migration was added.

The follow-up touched `model_gateway.py`, `validation.py`, gateway tests,
authority regression tests and this report. Other dispatch-task changes to
prompts, reference aliases and runner behavior were preserved. No commit or
deployment was made. Local runtime output is captured at
`/tmp/aethria-proverum-runtime.log`; test summaries are in
`/tmp/aethria-proverum-postgres-tests.log` and
`/tmp/aethria-proverum-backend.log`.

## ProVerum grounding and memo follow-up — 8–9 September 2026

This follow-up addresses the live quality failures described above. It does not
rewrite the Phase 0 golden fixture or historical evaluations. No new dependency,
migration, commit or deployment was made.

### Runtime changes

- Reviewer packets now select company-relevant sources, reject known non-person
  founder labels and prompt-injection material, and deduplicate repeated claims.
  Retrieval filters unrelated material before counting corroboration. Immutable
  raw evidence remains available for audit.
- Short claim handles bind model citations back to canonical claim, evidence and
  source IDs. Uncited FACT/INFERENCE prose becomes explicitly unverified UNKNOWN
  and cannot support a score. Unknown data is not converted into a negative fact.
- Partner uses short assessment handles, resolved and checked against the completed
  review before persistence. Partner-only refresh reuses Reviewer output.
- Ownership checks in this pipeline require the named company to be the subject
  of an acquisition statement. A founder's former employer being acquired no
  longer falsely constrains this company's operational outcome.
- A named re-review reuses its existing tenant-scoped identity link. A blocked
  identity retry no longer deletes an already linked startup projection.
- Postgres reruns read the freshly persisted startup before Partner handoff and
  memo generation; an old in-memory storage snapshot no longer supplies stale
  Reviewer prose to the memo.
- The Partner API projection retains provenance. Canonical diligence decisions
  render as More diligence in the memo, dispatch result, completion notice and
  selected queue badge/accessibility text. Legacy MONITOR storage remains readable.
- Incomplete evidence is labelled explicitly. Shared claim references are grouped
  across dimensions; long source excerpts are expandable with their links retained.
  Display memos show the thesis version, without its raw internal identifier.

### Live result and lineage

The live runs used the local production snapshot, not a deployed production
service. Tests used a separate disposable PostgreSQL database.

- Successful durable job: `b87fc664-5ba6-4711-982f-872094d884e9`, attempt 4.
- Pipeline: `6d8002ed-b06d-4534-9150-6442cba4d5d4`.
- Completed full evaluation: `6f072635-7d44-438e-b837-8fea5f87a74d`.
- Reused Reviewer run: `3b2a852f-c9cb-4a5e-aa43-facd482325c3`.
- Current Partner-only evaluation: `5833ca9b-05cc-450e-bc79-e90c493ac9bf`.
- Packet: 69 raw claims → 14 selected. No unrelated Proveris material or invalid
  CFx Strategy/Biomedical Engineer founder labels reached the final review.
- 59 reasoning units: 22 FACT, 11 INFERENCE, 15 UNKNOWN, 6 OPINION, 5 ASSUMPTION.
  All references were checked against the selected canonical evidence. Citation
  membership is not proof of semantic entailment or independent factual truth.
- Proposed scores: Market 7, Product 7, Technology 7, Execution 6, Defensibility 7.
  Validated: 7, 7, 7, null, 7 respectively. Execution lacks eligible support.
- Current Partner action: MORE_DILIGENCE, confidence 0.60, no ownership constraint.
  The Partner-only trace records Reviewer skipped/reused, validation and Partner
  completed. No duplicate Reviewer or research call was needed for that refresh.

The earlier live evaluation had all scores withheld after invalid citations.
The new scores reflect usable citation bindings and an updated evidence snapshot;
this is not a controlled same-input investment-quality comparison. No threshold
was relaxed to obtain these results. The synthetic Phase 0 baseline remains frozen.

### Recovery limitation

Before the identity fix, attempt 2 deleted the mutable startup projection and
pipeline state; attempt 3 then failed because the startup was absent. Canonical
identity, opportunities, evidence, evaluations and human rulings survived.
The startup was reconstructed with tenant/opportunity checks from canonical
identity and the last completed review/decision. Readable factual display fields
were subsequently recovered from existing official, MassDevice and PR source
excerpts. The internal `agent_trace.projection_recovery` records the cause, source
claims and unavailable fields. This is **not an exact restoration** of the lost
Scout, financial or queue-awareness projection. Missing founder details remain
unknown. No other startup or historical evaluation was rewritten.

### Verification and observed limits

- Full backend including PostgreSQL contracts, tenancy, persistence and Phase 0
  golden tests: **2,625 passed, 4 skipped**, one Starlette deprecation warning.
- Full app tests: **520 passed across 100 files**. The final rerun of app lint,
  build and bundle checks passed (65 assets).
- Marketing lint/build/bundle and all 17 marketing checks passed during this
  follow-up; no marketing source was changed.
- All 31 migrations were applied to the isolated test database; a second migration
  run reported no new migrations. No migration was added here.
- Authenticated manual memo inspection confirmed readable factual summary, the
  More diligence Partner headline, four 7/10 dimensions, unscored Execution,
  no headline aggregate, incomplete-evidence label, explicit diligence gaps,
  grouped expandable source excerpts and preserved source links.
- Existing React test act warnings and demo bundle size advisory remain.
  Final `git diff --check` passed. The optional Graphify navigation index was
  refreshed locally and remains uncommitted generated output.
  Local logs: `/tmp/aethria-proverum-final-sept9-backend.log`,
  `/tmp/aethria-proverum-final-sept9-frontend.log`,
  `/tmp/aethria-proverum-final-sept9-build.log`.

Regulatory, market and IP assertions still rely partly on industry press,
aggregators and company material. A cited claim is not independently established
merely because the source was retrieved. Primary regulatory scope, reimbursement,
patent breadth/FTO and clinical durability remain diligence needs. Current policy
can accept a 7 with source quality 0.6; this follow-up does not recalibrate it.
The company-subject ownership filter covers tested phrasings, not every possible
sentence. Claim deduplication is application-level, not an atomic uniqueness
constraint. The pre-existing database RLS gap remains. Some historical aggregate
and activity readers retain compatibility recommendation categories; a complete
retirement of those readers requires further contract work. These limitations
prevent an unqualified production-readiness claim.

### Follow-up file inventory

Paths below are relative to the repository; earlier migration changes and
unrelated pre-existing HomePage/settings work were preserved.

- `backend/investment_analysis/grounding.py`: source selection and claim aliases.
- `backend/investment_analysis/service.py`: binding, UNKNOWN fallback, Partner
  assessment aliases and company-specific ownership check.
- `backend/investment_analysis/repository.py`: website identity anchor.
- `backend/investment_analysis/prompts.py`: evidence-first attribution instructions.
- `backend/investment_analysis/projection.py`: canonical action provenance.
- `backend/evidence/retrieval.py`: relevant-source filtering before corroboration.
- `backend/context/scout_claims.py`: avoid repeated canonical claim creation.
- `backend/resolver/founder_resolver.py`, `backend/resolver/company_resolver.py`,
  `backend/people/service.py`, `backend/utils/founder_enrichment.py`: reject
  non-person founder labels before enrichment/persistence.
- `backend/api.py`: clean founder display and preserve Partner provenance.
- `backend/pipeline_runner.py`: identity reuse/preservation and fresh memo reads.
- `backend/identity/ownership_gate.py`: subject-specific ownership matching.
- `backend/memo_generator.py`: keep thesis identifiers out of display prose.
- `backend/tests/investment_analysis/{test_grounding,test_authority,test_repository_postgres}.py`:
  grounding, action projection, binding and persistence regressions.
- `backend/tests/{test_scout_claims,test_scout_claim_bridge_persistence,test_on_demand_lookup_independent,test_memo_generator_current_schema}.py`:
  deduplication, fresh reads and memo privacy.
- `backend/tests/identity/{test_autonomous_identity_admission,test_ownership_gate}.py`:
  linked-row preservation and acquisition subject tests.
- `backend/tests/evaluation_v2/test_partner_rules_contract.py`: ownership constraint
  behavior regression without changing policy thresholds.
- App `src/components/scoring/AssessmentScorecard.tsx` and its test: incomplete
  evidence label.
- App `src/lib/memoDecisionBrief.ts` and its test: grouped sources and explicit
  Partner diligence lean.
- App `src/components/memo/MemoDecisionBrief.tsx` and its test: expandable excerpts.
- App `src/lib/recommendationSemantics.ts` and its test: canonical action labels.
- App `src/components/{AppFrame,LookupReadyNotice}.tsx`,
  `src/components/memo/{MemoMasthead,memoContentHelpers}.tsx`,
  `src/components/queue/{queueRowShared.ts,QueueVerdictLine.tsx}` and
  `src/lib/productChromeMappers.ts`: use meaningful action labels in display paths.
- `API.md` and this operating guide: DTO semantics, results and unresolved risks.

The preceding structured-output follow-up additionally changed
`model_gateway.py`, `validation.py` and their gateway/authority tests, as recorded
in the previous section. No existing golden output was regenerated.

## Assiduous identity and extraction follow-up — 12 September 2026

Independent dispatch `22db3420-4bdc-4712-a8cb-fa0fb8bac846` completed with evaluation
`41d21655-2f84-474a-968b-8015777af6e2`, MORE_DILIGENCE at 0.63 confidence and
unscored validated assessments. Its saved source packet mixed several same-name
companies. The submitted `.ai` domain was not corroborated; retrieved evidence
suggested `.tech`, which the analyst had not confirmed.

Changes made without committing, deploying or rewriting that historical run:

- Unicode dash separators are removed from the parsed company name while the
  original lookup text is retained.
- A supplied website no longer suppresses conflicting retrieved domain evidence
  when no qualifying source corroborates the hint. The resolver offers competing
  candidates through the existing picker. Canonical identity admission also opens
  a `conflicting_domain_evidence` case before treating the raw hint as verified.
  It does not silently choose `.tech` or create a company from the disputed hint.
- Source matching no longer treats a domain slug anywhere in a URL as evidence
  of identity. Company profiles need matching identity slugs or an explicit domain;
  unrelated personal profiles and expanded organization names are rejected.
  Resolver source merging, research packets and named Scout claim admission use
  this filtering. Raw historical evidence remains auditable.
- Known truncated role/organization labels are rejected in founder extraction,
  persistence/display and Reviewer claim selection.
- Firmographic extraction for a named company considers statements with that
  company as subject. The previous extractor took “founded 1962” and
  “1,000–2,000 employees” from Ahmadu Bello University in an unrelated person's
  education section. A regression test now keeps those facts out of Assiduous.
- Completed unopened results no longer keep the dispatch-running flag active.
  The dispatch list counts only non-completed chips as active; completed memo
  chips remain available to open.

The recommendation contract was already explicit in this persisted run:
`partner.provenance.recommendation_origin=PARTNER_ANALYSIS` and
`canonical_recommendation=insufficient_evidence`, with legacy `recommendation=MONITOR`.
The existing canonical-label mapper displays More diligence. The compatibility
enum has not been silently repurposed or removed; no score, policy threshold or
Partner decision was changed by this follow-up.

Read-only replay of the saved resolver sources returned `ambiguous`, with `.tech`
among the choices. Re-extraction of the saved firmographic payload returned no
supported facts instead of the university's values. Under a **hypothetical**, not
persisted, `.tech` anchor, 14 of the 16 saved resolver sources were rejected,
including Solutions, KampHire, Distributor and Home Care. That replay froze search
results but an existing enrichment fallback attempted one scrape and returned
403; it is not reported as a completely offline end-to-end run. Unit tests freeze
the dependencies they exercise.

Verification: full backend including isolated PostgreSQL contracts and Phase 0
goldens **2,636 passed, 4 skipped**. App **521 tests across 100 files**, lint/build/
bundle passed including the final dispatch-count assertion; final results are recorded
in `/tmp/assiduous-final-frontend.log` and `/tmp/assiduous-final-build.log`.
Marketing lint/build/bundle and 17 marketing checks passed. Migration runner on
the isolated database applied no new migrations. The new authority PostgreSQL
fixture now explicitly binds its synthetic company to `example.test`; its score
and lineage assertions were preserved and the Phase 0 fixture was not edited.

Files changed in this follow-up: `backend/utils/{lookup_input,source_corroboration,
traction_extraction}.py`, `backend/resolver/{company_resolver,founder_resolver}.py`,
`backend/identity/service.py`, `backend/api.py`, `backend/context/scout_claims.py`,
`backend/investment_analysis/grounding.py`; matching regressions in
`backend/tests/{test_lookup_dispatch,test_source_corroboration,test_memo_data_integrity}.py`,
`backend/tests/identity/test_identity_service.py`, and
`backend/tests/investment_analysis/{test_grounding,test_repository_postgres}.py`;
app `src/lib/lookupTracking.ts` and its test, `src/hooks/useDispatchLookup.ts`,
`src/components/DispatchCommandBar.tsx` and its test; `API.md` and this guide.

Remaining boundary: historical admitted identities are not automatically
reassigned or historical snapshots rewritten. The existing Assiduous record still
needs explicit identity confirmation and a fresh review before it is reliable for
use. No live redispatch was performed against an unconfirmed alternative domain.
Source matching and grammatical extraction are conservative deterministic checks,
not universal entity resolution or semantic entailment. They may withhold useful
evidence lacking explicit identity context. More diligence and null validated
scores remain the appropriate recorded outcome until the missing evidence and
identity are resolved.

## Glitch Ads identity lineage and compact reads — 14 September 2026

The reported run was startup `3b7b25ed-d610-4910-b9ca-b2cb34b828dc`, evaluation
`c745ffcd-c140-4482-ba6d-13f1b53c4a74`, opportunity
`6f88fa82-433a-499c-95ca-97ec4bc43d12`. The opportunity exists despite its absence
from the pasted combined inspector output. Persisted provenance confirms
PARTNER_ANALYSIS using Reviewer `e80d38ff-feaa-489a-8702-96e9fb77a171` and Partner
`98b3636f-b0db-4ffd-a2af-0b8bcff1e9e1`; this was not the retired deterministic
Partner mapping path.

The company record was named only “Glitch” while its domain was `glitchads.ai`
and its startup display name was “Glitch Ads”. That shortened brand admitted
Glitch Productions/Studios, developer-platform and protocol evidence. These
misattributed claims carried the same company ID, so tenant/foreign-key checks
alone could not identify the error.

The live analysis boundary now uses the more specific factual display name only
when its normalized spelling matches the exact website brand and extends the
canonical name. It does not rewrite canonical identity or historical data. Source
matching requires a contiguous company phrase; unrelated “Glitch” and “ads” words
elsewhere in an article no longer satisfy “Glitch Ads”. Reviewer and Partner use
the admitted evidence packet. Validation, mandate and ownership checks also use
the admitted subset, preventing excluded evidence from influencing downstream
constraints. Partner-only reuse is blocked when evidence admission differs, and
prior decision context is omitted when its review used a different identity name.
Full snapshot hashes/history remain retained for audit.

Storage joins additionally require claim/artifact company and opportunity IDs to
agree within the tenant. Raw claims must agree with their opportunity's company.
Contradictory embedded tenant/company/opportunity IDs are rejected before model
calls. The PostgreSQL regression deliberately changes an artifact's company inside
a rolled-back savepoint and proves its links are excluded. This addresses malformed
legacy references without broadening access or introducing a migration.

Analyst reads now have an explicit compact view, selected by the production typed
clients. The default full API view remains backward compatible and development
inspection retains it. Investment scores, rationale, evidence limitations and
source-link keys remain; duplicated audit/snapshot payloads are omitted. Partner
model inputs also omit Reviewer/validation lineage, policy-version and metadata
envelopes. This change does not make Partner a deterministic mapper.

Read-only verification against the saved Glitch run:

- Full evaluation JSON: **189,992 bytes**; compact analyst JSON: **16,069 bytes**,
  about **92% smaller** (serialized with Python JSON defaults).
- Saved snapshot: **14 claims → 1 admitted**. Netflix, Amazon, 421-million views,
  merchandise, Glitch Studios and Glitch Protocol markers are absent from the
  resulting model packet. The retained funding statement still needs ordinary
  evidence validation; admission alone is not proof of truth.
- Dependency inspection returns **stale / identity_context_changed** for the old
  review. It explicitly warns against relying on those historical conclusions.
  No live model call, replacement evaluation or historical rewrite was performed.

Verification: full backend with isolated PostgreSQL **2,643 passed, 4 skipped**;
app **521 tests / 100 files**, lint, type/build and bundle passed (65 assets);
marketing lint/build/bundle (52 assets) and 17 marketing checks passed. Migration
runner applied no new migrations. Diff whitespace check passed. Existing
Starlette deprecation, React act warnings and demo bundle advisory remain.
Logs: `/tmp/glitch-final-backend.log`, `/tmp/glitch-frontend.log`,
`/tmp/glitch-build.log`, `/tmp/glitch-marketing.log`.

Exact files changed for this follow-up:

- `backend/investment_analysis/grounding.py`: precise domain-matched identity label.
- `backend/research/source_corroboration.py`: contiguous company-phrase matching.
- `backend/investment_analysis/repository.py`: company-scoped claim reads,
  identity label selection, stale historical identity detection and prior-context guard.
- `backend/evaluation_v2/evidence_projection.py`: same-company/opportunity evidence joins.
- `backend/investment_analysis/service.py`: embedded ownership checks, admitted-only
  validation/policy context, Partner reuse guard and smaller model metadata envelopes.
- `backend/routers/evaluations.py`, `backend/routers/evidence.py`: compact analyst views.
- `app-front-end/src/api/evaluations.ts`, `app-front-end/src/api/evidence.ts`:
  production compact-view requests and optional audit metadata types.
- `app-front-end/src/lib/pipelineProvenance.ts`: tolerate omitted audit criteria.
- `backend/tests/investment_analysis/test_grounding.py`: Glitch Ads versus Studios
  and creator-IP evidence, with immutable input checks.
- `backend/tests/investment_analysis/test_authority.py`: both model payloads exclude
  contamination; foreign ownership fails before any model call; cautious outcome.
- `backend/tests/investment_analysis/test_repository_postgres.py`: real mismatched
  company evidence-link regression inside rollback.
- `backend/tests/evaluation_v2/test_evaluation_endpoints.py`: compact response
  preserves explanations, reduces size and leaves full audit input unchanged.
- `backend/tests/evidence/test_evidence_endpoints.py`: compact evidence keeps
  restricted sources private and passes the verified tenant to storage.
- `API.md` and this operating guide: view contracts, measurements and remaining limits.

No commit, deployment or migration was made. Pre-existing changes and Phase 0
goldens were preserved. The contaminated historical memo is not repaired by
response slimming: a full refreshed review is still required. Semantic entailment
inside a source remains a separate quality concern; matching a company phrase and
database ownership is not a universal proof that every sentence is about it.
