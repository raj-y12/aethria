# Aethria Evidence and Decision Platform

**Date:** 2026-07-15  
**Status:** Approved product direction; detailed implementation planning pending  
**Initial customer:** Solo GPs and emerging venture funds  
**Decision model:** Aethria recommends and prioritizes; the investor makes the authoritative ruling

## 1. Executive summary

Aethria should evolve from an agent-centred startup evaluation pipeline into an evidence-centred investment decision and institutional memory platform.

The current system contains valuable foundations: autonomous sourcing, company resolution, reference validation, versioned fund theses, deterministic scoring, rule-first partner recommendations, human escalation resolution, decision history, portfolio monitoring, and early calibration machinery. These foundations are ahead of a typical AI memo generator. However, the present Scout → Reviewer → Partner → Portfolio → Meta architecture is not yet suitable as the institutional backbone of an investment process.

The central limitation is not model quality alone. Identity, source observations, claims, evidence, evaluations, recommendations, human decisions, workflow actions, and learning signals are not yet represented as independent durable records with explicit lifecycles. Too much authority remains in generated JSON. Reviewer personas simulate investment-committee disagreement without necessarily improving truth. The MetaAgent may mutate prompts, reweight scouts, and recalibrate thresholds before Aethria has enough attributable feedback or mature outcome data to justify autonomous optimization.

The recommended product direction is therefore:

    Discover or ingest
      → Resolve canonical identity
      → Build a claims and evidence ledger
      → Evaluate against versioned fund policy
      → Produce a traceable recommendation
      → Capture the GP's ruling and reasoning
      → Trigger bounded diligence or monitoring actions
      → Learn through governed, human-approved policy proposals

The first product promise is:

> Aethria continuously finds and evaluates companies against your fund strategy, shows the evidence behind every recommendation, and learns from how you actually invest—without taking judgment away from you.

The target is institutional-grade process for a small fund, not enterprise CRM breadth. Institutional-grade means that material claims have provenance, missing evidence remains visible, policy and model versions are recorded, past decisions are immutable, failures are recoverable, costs are bounded, and learning cannot silently alter production behaviour.

## 2. Goals

### 2.1 Customer goals

A solo GP or emerging manager should be able to:

1. Configure an explicit investment mandate and scoring policy.
2. Receive a small, ranked queue of relevant companies from autonomous and manual sources.
3. Understand why each company was surfaced.
4. Inspect the evidence behind every material conclusion.
5. Distinguish verified facts, founder assertions, operator observations, model inferences, contradictions, stale information, and unknowns.
6. Decide whether to advance, monitor, or pass.
7. Record a disagreement with Aethria quickly and precisely.
8. Generate an appropriate next diligence action.
9. Return later and see what the system has learned from repeated rulings.

### 2.2 Product goals

- Make the decision record, not the memo, the atomic unit of value.
- Make evidence and uncertainty structural rather than prompt conventions.
- Separate company identity from the fund's opportunity and decision history.
- Make every evaluation reproducible from a versioned policy and evidence snapshot.
- Learn from immediate, attributable human overrides before attempting long-horizon outcome learning.
- Allow new sourcing and ingestion channels without changing downstream evaluation contracts.
- Preserve Aethria's autonomous sourcing advantage while reducing its authority over investment conclusions.
- Create a migration path that keeps the current product usable.

### 2.3 Engineering goals

- Preserve explicit user_id tenancy on every read, write, constructor, job, and event.
- Replace fragile in-memory execution with durable, idempotent, retryable work.
- Bound model, search, storage, and monitoring costs per tenant and opportunity.
- Keep Pydantic models as the authoritative backend contracts.
- Continue row-level Supabase operations and add new migrations rather than modifying existing ones.
- Make model-dependent work replaceable behind bounded interfaces.
- Provide stable read projections so the frontend need not consume normalized internal tables directly.

## 3. Non-goals

The initial product will not:

- Make an irreversible INVEST or PASS decision without a human ruling.
- Replace Affinity, Attio, or a general-purpose CRM.
- Synchronize a user's entire email or contact graph.
- Provide a native relationship intelligence graph.
- Identify diligence experts without a credible, authorized expert or relationship dataset.
- Continuously re-enrich every historical company.
- Claim that a later funding round proves an earlier pass was wrong.
- Infer founder charisma, obsession, magnetism, or personality as objective facts.
- Automatically activate MetaAgent prompt, weight, threshold, or policy mutations.
- Introduce multi-partner IC voting in the first delivery.
- Create a cross-tenant global company database.
- Treat more agents, more personas, or more generated prose as a proxy for quality.

## 4. Strategic directions considered

There are three credible product directions. An autonomy-first fourth direction was considered and rejected.

### 4.1 Direction 1 — harden the current agent pipeline

This direction retains Scout personas, Reviewer personas, the PartnerEngine, PortfolioEngine, and MetaAgent, then adds stronger citations, versioning, testing, durable jobs, canonical identity, cost controls, and approval gates.

#### Positives

- Lowest migration risk.
- Fastest route to visible reliability improvements.
- Reuses most of the existing implementation.
- Preserves the current product experience and sourcing demo.
- Improvements can ship incrementally.
- Existing partner rules and evidence-calibrated scoring remain valuable.

#### Negatives

- Scout personas continue to combine discovery, research, framing, and persuasion.
- Reviewer personas simulate an investment committee rather than represent a fund's actual decision process.
- Multiple LLM opinions can create correlated confidence rather than independent evidence.
- Evidence remains subordinate to generated analyses.
- The startup row remains responsible for identity, opportunity state, review, recommendation, and history.
- Learning attribution remains unclear across scout selection, extraction, reviewer scoring, mandate gates, partner rules, and human overrides.
- Each new channel must conform to a scout-oriented payload rather than a channel-neutral observation contract.
- The result could be a reliable implementation of the wrong conceptual architecture.

#### Assessment

This is a useful transitional execution strategy but not the recommended long-term product architecture.

### 4.2 Direction 2 — evidence and decision platform

This direction makes canonical identity, claims, evidence, policy evaluation, recommendations, rulings, actions, outcomes, and learning proposals first-class records. Agents become replaceable workers inside the system rather than the system's source of authority.

#### Positives

- Strongest alignment with institutional trust requirements.
- Gives all five desired capabilities one coherent substrate.
- Differentiates Aethria from memo generators, sourcing databases, and CRMs.
- Reduces dependence on specific models, prompts, and persona designs.
- Makes uncertainty, staleness, contradiction, and missing data visible.
- Turns overrides into immediate institutional learning.
- Supports new channels without rewriting evaluation.
- Creates a credible decision-memory moat.
- Provides a foundation for later multi-user IC workflows.

#### Negatives

- Largest conceptual and data-model change.
- Requires careful dual-write and backfill migration.
- Produces less immediate visual novelty than another autonomous agent.
- Makes some current code transitional or obsolete.
- Requires strict boundaries between extraction, verification, policy evaluation, and recommendation.
- Institutional learning initially produces governed observations, not automatic self-improvement.
- Canonical identity always requires an ambiguity path.
- More schema, contract, and evaluation work precedes the full customer-visible benefit.

#### Assessment

This is the selected product direction. It should be delivered through an incremental strangler migration that retains useful parts of the current system.

### 4.3 Direction 3 — workflow-first venture operating system

This direction prioritizes email and deck ingestion, pipeline stages, notes, tasks, reminders, founder communication, CRM features, assignments, IC voting, and portfolio workflow. AI sourcing and evaluation become embedded features.

#### Positives

- Easy for customers to understand.
- Encourages frequent engagement.
- Captures more proprietary operating data.
- Creates natural workflow orchestration.
- Offers familiar per-seat or per-fund pricing.
- Could eventually replace fragmented tools.

#### Negatives

- Competes directly with established CRM and relationship products.
- Email, permissions, contacts, notes, tasks, and integrations become table stakes.
- Solo GPs may not need extensive workflow administration.
- It does not fix the current pipeline's trust limitations.
- The distinctive evidence-and-decision position becomes diluted.
- Engineering shifts toward commodity workflow infrastructure.
- The likely outcome is a weaker CRM with an AI scorer.

#### Assessment

Workflow is an expansion layer, not the initial category. Aethria should export to systems of record rather than replace them.

### 4.4 Rejected direction — autonomous agent fund

This direction would increase the authority of Scout, Reviewer, Partner, and Meta agents and market Aethria as an autonomous investment decision-maker.

The appeal is a dramatic demo, a strong automation narrative, and minimal human effort. The disadvantages are decisive: unverifiable founder judgment, weak accountability, false precision, limited outcome data, unsafe self-modification, poor auditability, and a mismatch with how serious investors accept responsibility. This direction is rejected for the initial market.

## 5. Target architecture

The target architecture has seven domain layers and three cross-cutting control layers.

### 5.1 Domain flow

    Acquisition channels
      → Source observations
      → Identity resolution
      → Canonical companies and opportunities
      → Claims and evidence
      → Fund-policy evaluation
      → System recommendation
      → Human ruling
      → Actions, monitoring, and outcomes
      → Fund Intelligence proposals
      → Human-approved policy versions

### 5.2 Domain layers

1. **Acquisition:** receives discoveries, lookups, imports, referrals, and later inbound artifacts.
2. **Identity:** resolves observations to canonical tenant-scoped companies.
3. **Evidence:** stores source artifacts, bounded evidence items, claims, contradiction, and provenance.
4. **Evaluation:** applies an immutable evidence snapshot to versioned fund policy.
5. **Decision:** separates system recommendation from authoritative human ruling.
6. **Action and lifecycle:** creates bounded next steps and cost-aware monitoring.
7. **Fund Intelligence:** analyzes decisions and outcomes and proposes governed changes.

### 5.3 Cross-cutting control layers

1. **Durable orchestration:** jobs, retries, leases, idempotency, dead letters, and stage observability.
2. **Governance:** tenant isolation, policy versions, model manifests, audit events, approval gates, and retention.
3. **Read models:** stable queue, company, decision-record, evidence, action, and intelligence projections for frontend consumption.

## 6. Institutional design principles

1. No material assertion without provenance.
2. Missing evidence is represented explicitly and never converted into invented certainty.
3. Company identity, opportunity state, recommendation, and ruling are distinct.
4. Completed evaluations and rulings are immutable; later records supersede rather than overwrite.
5. Every production policy is versioned and attributable.
6. Models may extract and reason; deterministic policy owns repeatable calculations.
7. Learning may propose but cannot activate changes.
8. Ambiguous identity cannot be silently merged.
9. Enrichment requires a lifecycle reason and cost budget.
10. Every stage is idempotent, observable, retryable, and tenant-scoped.
11. New channels enter through the same observation and identity contracts.
12. The system must explain the difference between any two recommendations.
13. Confidential or user-supplied content is untrusted input.
14. A failed refresh cannot erase the last successful decision record.
15. A system recommendation never overwrites a GP's ruling.

## 7. Core domain model

### 7.1 Company

A Company represents the best-known identity of a business within one tenant.

Important fields:

- company_id and user_id
- canonical_name and canonical_domain
- description, headquarters, founded_year, and operating_status
- identity_status and identity_confidence
- current_profile_version
- merged_into_company_id
- created_at and updated_at

Canonical name is display data, not an identity key. Canonical domain is the strongest default key when verified, but must coexist with external identifiers and aliases.

### 7.2 CompanyIdentifier

Identifiers include registrable domains, former domains, LinkedIn company IDs, provider IDs, government registration numbers, CRM IDs, and product domains.

Each identifier records type, normalized value, verification status, confidence, validity dates, source evidence, and whether it is primary. A tenant-scoped unique constraint on user_id, identifier_type, and normalized_value protects verified identifiers.

### 7.3 Person and CompanyPerson

Person records exist only to support evidenced investment-relevant professional history. CompanyPerson represents a person's role, founder status, tenure, relationship status, verification state, and supporting evidence.

Subjective human observations belong in attributed operator notes. They do not become inferred person traits.

### 7.4 SourceObservation

A SourceObservation records how Aethria encountered a possible company. It includes channel, submitted name and domain, external reference, source attribution, submitted context, raw artifact reference, discovery hypothesis, timestamps, idempotency key, resolution state, and resolved company pointer.

Resolution states are PENDING, RESOLVING, RESOLVED, AMBIGUOUS, NOT_FOUND, CONFLICTED, and REJECTED. Observations are preserved even after deduplication so source attribution is never lost.

### 7.5 IdentityResolutionCase

Ambiguous or conflicting observations create an operator-visible case with candidates, match reasons, conflicts, confidence values, resolver version, final resolution, and rationale.

Operator actions are:

- Match an existing company.
- Create a new company.
- Mark insufficient information.
- Mark irrelevant or not a company.
- Merge two companies.
- Preserve two separate companies.

Merges create a tombstone and durable audit event. They never delete historical observations or decisions.

### 7.6 Opportunity

A Company is the business. An Opportunity is the fund's decision context for that company at a given financing or review moment.

Important fields:

- opportunity_id, user_id, and company_id
- opened_at and closed_at
- financing_stage, round_context, and check_context
- fund_thesis_version_id_at_open
- process_state and decision_state
- attention_priority
- current evaluation, recommendation, and ruling pointers
- next_review_at
- creating source observation

One open opportunity per user/company is the normal constraint. Later rounds can create later opportunities without erasing the earlier decision.

Process state is separate from decision state. A failed evaluation is not a pass, and a completed pipeline is not an investment decision.

### 7.7 EvidenceArtifact and EvidenceItem

An EvidenceArtifact is a source container such as a web page, database response, pitch deck, email, interview note, GP context, or news article. It records provenance, content hash, storage reference, trust class, access class, retention policy, parser version, and whether it is untrusted input.

An EvidenceItem is a bounded passage or structured fact extracted from an artifact. It records a normalized value, display excerpt, source location, relevant dates, verification state, source quality, extraction confidence, extractor version, and operator attribution where applicable.

Correct extraction does not make an assertion true. Evidence quality and assertion truth remain separate.

### 7.8 Claim and ClaimEvidenceLink

A Claim is an investment-relevant proposition about a company, person, market, or opportunity. Claims contain a typed value, unit, period, text, assertion class, status, confidence, and supersession link.

Assertion classes are:

- EXTERNALLY_VERIFIED
- FOUNDER_ASSERTED
- OPERATOR_ASSERTED
- MODEL_INFERRED
- CONFLICTED
- UNVERIFIED

Claim status is CURRENT, STALE, CONTRADICTED, SUPERSEDED, or WITHDRAWN.

ClaimEvidenceLink records whether a specific evidence item supports, contradicts, contextualizes, or partially establishes the claim. It includes support strength and a link rationale. A related citation that does not support the actual proposition is not sufficient.

### 7.9 EvaluationRun and CriterionAssessment

An EvaluationRun is an immutable evaluation of one opportunity using a specific evidence and policy snapshot. It records:

- Trigger type and actor.
- Evidence snapshot hash and claim set.
- Thesis, scoring-policy, and partner-rule versions.
- Model and prompt manifests.
- Status and failure information.
- Start and completion timestamps.
- The prior evaluation it supersedes.

CriterionAssessment stores a score when evidence permits one, confidence, evidence sufficiency, reasoning, supporting and contradicting claims, missing evidence, quality flags, and deterministic adjustments.

A criterion can remain unscored. The system must distinguish a strongly evidenced low score from the absence of evidence.

### 7.10 Recommendation

A Recommendation contains:

- Recommended state: ADVANCE, MONITOR, PASS, or INSUFFICIENT_EVIDENCE.
- Attention priority.
- Confidence.
- Decision drivers and principal risks.
- Mandate conflicts.
- Missing information.
- Conditions that would change the recommendation.
- Human-review requirement.

Recommendations are immutable and always reference one EvaluationRun.

### 7.11 HumanRuling and OverrideSignal

A HumanRuling is the authoritative fund decision. It records decision, rationale, recommendation seen, risk acknowledgement, mandate exception, investor confidence, timestamp, and any prior ruling it supersedes.

When the ruling materially differs from the recommendation, Aethria creates an OverrideSignal. Override types include evidence correction, missing private evidence, policy disagreement, founder judgment, market judgment, timing, strategic exception, relationship context, and confidence disagreement.

Not every override is a model failure. The classification is essential for useful learning.

### 7.12 WorkflowAction

Initial action types are:

- PREPARE_DILIGENCE_QUESTIONS
- DRAFT_INFORMATION_REQUEST
- REFRESH_EVIDENCE
- SCHEDULE_MONITOR_REVIEW
- EXPORT_TO_CRM
- GENERATE_DECISION_PACK
- RESOLVE_IDENTITY

Actions record trigger, status, generated and approved content, due and completion times, external destination, external reference, and failures. External communication requires explicit approval in the initial version.

### 7.13 OutcomeObservation

Outcome observations record factual later events such as financing, commercial milestones, launches, acquisitions, shutdowns, leadership changes, and follow-on decisions. Each observation has evidence, effective and observation dates, verification state, and materiality.

A later funding round is an observation, not proof that an earlier pass was a mistake.

### 7.14 PolicyProposal

A PolicyProposal contains a detected pattern, supporting overrides or outcomes, sample size, confidence, limitations, proposed policy patch, estimated historical effect, status, reviewer rationale, and resulting policy version when accepted.

Statuses are DRAFT, READY_FOR_REVIEW, ACCEPTED, EDITED_AND_ACCEPTED, REJECTED, DEFERRED, and EXPIRED. No proposal can activate itself.

## 8. Record lifecycles

### 8.1 Autonomous discovery

    Scout strategy returns a candidate and URLs
      → SourceObservation is inserted idempotently
      → Identity worker resolves or opens an ambiguity case
      → Company is matched or created
      → Open Opportunity is reused or created
      → Evidence plan is created from known gaps
      → Artifacts, evidence items, and claims are persisted
      → EvaluationRun snapshots the eligible claims
      → Recommendation is produced
      → GP records a ruling
      → Action or monitoring policy is created

Scout output is a hypothesis and source pack, not an authoritative company assessment.

### 8.2 Manual lookup

The GP enters a company name, domain, and optional context. A cheap, LLM-free resolution preview runs first. Ambiguity is resolved before expensive enrichment begins. Once resolved, the lookup uses the same Opportunity, evidence, evaluation, recommendation, and ruling contracts as autonomous discovery.

### 8.3 New evidence

New evidence creates or changes claims. If the evidence snapshot differs from the current EvaluationRun, the Opportunity is marked as having new evidence. Re-evaluation occurs only when trigger policy and cost budget allow it.

The previous EvaluationRun remains valid as a historical statement of what Aethria knew at that time. A failed refresh leaves the last successful recommendation visible with a stale or refresh-failed indicator.

### 8.4 Human correction

When the GP marks a claim or evidence link as incorrect:

1. The correction event is recorded.
2. The claim is withdrawn, contradicted, or superseded.
3. The current evaluation is marked stale.
4. A priority re-evaluation is queued.
5. The correction becomes a high-quality learning signal.

The system must never edit an old completed evaluation to make it appear as though it used the corrected evidence.

### 8.5 Human ruling

The recommendation is shown with decisive evidence, uncertainty, risks, and missing information. The GP selects ADVANCE, MONITOR, or PASS and adds a concise rationale. Agreement or override is classified. The ruling is appended and the Opportunity's current ruling pointer is updated.

### 8.6 Policy change

A draft policy is validated and shown with a bounded impact preview. Publishing creates a new immutable version. Current and historical evaluations keep their original policy references. Selected active Opportunities become eligible for re-evaluation, but publishing never launches an unbounded replay automatically.

### 8.7 Monitor review

When a monitor condition becomes due:

1. The cost gate confirms eligibility.
2. A gap-oriented evidence plan is created.
3. Relevant evidence is refreshed.
4. A material-change detector compares evidence snapshots.
5. A new evaluation runs only when required.
6. The GP sees a recommendation delta rather than a wholly rewritten memo.

### 8.8 Company re-entry

A company returning with a materially new financing or context creates a new Opportunity linked to the same Company. Still-valid company evidence is reusable. Prior decisions appear as precedent, not as an automatic score anchor.

## 9. Pipeline execution design

### 9.1 Acquisition stage

The acquisition interface accepts a typed AcquisitionCandidate:

- tenant user ID
- channel and source attribution
- submitted company anchors
- source URLs or artifact references
- discovery hypothesis
- operator context
- idempotency key
- requested service level

Current scout personas may initially implement this interface. Over time they become search strategies with distinct query policies rather than quasi-investment analysts.

Acquisition success means that a valid SourceObservation exists. It does not require a successful company evaluation.

### 9.2 Identity stage

Resolution proceeds in descending confidence:

1. Exact verified provider identifier.
2. Exact verified registrable domain.
3. Verified alias or former domain.
4. Multiple corroborating anchors such as name, founder, location, and external profile.
5. Candidate similarity with an operator decision.

Name-only matching cannot auto-merge. Conflicting verified identifiers cannot auto-resolve.

Identity success means the observation is attached to a Company or an explicit ambiguity case exists. Unresolved identity blocks evaluation because evidence cannot be safely attributed.

### 9.3 Evidence-planning stage

Before searching, an EvidencePlanner evaluates what is already known and what the active policy requires. It emits a bounded plan:

- identity gaps
- company-profile gaps
- founder-history gaps
- policy-critical market, product, technical, execution, and defensibility gaps
- stale claims
- contradictory claims
- maximum queries, artifacts, tokens, and spend

This prevents each model from independently searching for everything and allows enrichment to focus on decision-relevant uncertainty.

### 9.4 Retrieval stage

Retrieval gathers artifacts through approved providers and source-specific adapters. It deduplicates by canonical URL and content hash, records provider and query attribution, applies tenant cost gates, and stores retrieval failures independently.

A provider failure should reduce source coverage and create a quality flag; it should not automatically fail the whole evaluation when sufficient alternative evidence exists.

### 9.5 Extraction stage

Extraction converts untrusted artifacts into typed candidate evidence and claims. It cannot execute instructions found in documents. Model prompts treat artifact text as quoted data, enforce an output schema, and prohibit policy or instruction changes.

Extraction records model, prompt, parser, and artifact versions. Low-confidence extraction remains unverified until corroborated or accepted by an operator.

### 9.6 Verification and contradiction stage

Verification:

- checks whether the cited source supports the proposition;
- distinguishes company-controlled, founder-supplied, third-party, database, and operator evidence;
- identifies inconsistent values and dates;
- applies source-quality and freshness rules;
- groups equivalent claims;
- preserves minority or conflicting evidence.

The verifier may downgrade assertion status but cannot upgrade a model inference to externally verified without supporting evidence.

### 9.7 Policy evaluation stage

Policy evaluation has two boundaries:

1. Models may summarize relevant evidence, map qualitative evidence to anchored labels, and explain uncertainty.
2. Deterministic code validates labels, applies weights and caps, handles exclusions, computes scores, and enforces missing-evidence behaviour.

The compiled policy remains the source of truth for dimensions, criteria, anchors, weights, and gates. Any model-created score not mapped to an active criterion is invalid.

### 9.8 Recommendation stage

The rule-first PartnerEngine evolves into a RecommendationEngine. It consumes only:

- active policy version;
- completed criterion assessments;
- evidence-quality summary;
- mandate conflicts;
- portfolio or check context explicitly allowed by policy;
- current Opportunity context.

The LLM fallback remains limited to versioned, explicit edge-case triggers. Its invocation and output are recorded. Recommendation confidence is capped by evidence sufficiency and identity confidence.

### 9.9 Ruling stage

The UI presents the recommendation as advice. A GP can rule immediately, request more information, correct evidence, or defer. A ruling records what recommendation and evidence snapshot were visible.

If the GP disagrees, the interface requests one structured reason with optional detail. It must not force lengthy data entry or shame the user for overriding the system.

### 9.10 Action stage

Actions are generated from specific gaps or decisions. Question preparation reuses missing evidence, contradictions, focal questions, assumptions, and conditions-to-change. Information requests remain drafts until approved.

CRM export is outbound and explicit. Aethria does not make an external write merely because a recommendation was produced.

### 9.11 Learning stage

Each ruling creates zero or more LearningSignals. Immediate signals are evidence corrections, overrides, mandate exceptions, confidence disagreements, and repeated requests for the same missing information.

Fund Intelligence aggregates signals only when attribution is clear. It produces a report or PolicyProposal, never a silent mutation.

### 9.12 Hard runtime gates

The redesigned pipeline preserves Aethria's existing non-negotiable runtime gates:

- An active, complete FundThesis must resolve before acquisition, evaluation, or recommendation work runs.
- Production pipeline work requires Supabase storage; local file storage remains development-only.
- Model-dependent work requires a configured OpenAI API key and fails visibly when it is absent.
- Every search and model stage checks the tenant CostController before reserving work.
- Mandatory reference and claim-evidence validation cannot be bypassed by later stages.
- Partner decision thresholds remain in versioned rule configuration rather than hardcoded Python branches.

Jobs blocked by these gates persist a structured reason and safe recovery action. They do not silently return an empty successful result.

## 10. Durable orchestration and failure recovery

### 10.1 Durable job model

The current in-memory queues should be replaced by a Supabase-backed durable job system. Existing agent_job_schedules can continue to describe when recurring work is due, while a separate agent_jobs table represents actual work instances.

An AgentJob includes:

- job_id and user_id
- job_type
- entity type and entity ID
- idempotency key
- priority
- status
- attempt count and maximum attempts
- scheduled_at, available_at, started_at, heartbeat_at, and completed_at
- lease owner and lease expiry
- input reference
- output reference
- failure code and bounded failure detail
- parent job and pipeline run IDs
- cost reservation

Statuses are QUEUED, CLAIMED, RUNNING, RETRYABLE, SUCCEEDED, CANCELLED, BLOCKED, and DEAD_LETTER.

### 10.2 Idempotency

Every stage has a natural idempotency key:

- acquisition: tenant, channel, external event
- identity: observation and resolver version
- retrieval: company, query plan hash, provider, freshness window
- extraction: artifact content hash, extractor version
- evaluation: opportunity, evidence snapshot hash, policy versions, model manifest
- recommendation: evaluation run and rule version
- monitor: opportunity and scheduled review window

Retries must return the existing successful record where the key already completed.

### 10.3 Leases and recovery

Workers claim jobs with time-limited leases and heartbeat while model or provider work is active. An expired lease makes the job claimable after a safety interval. Job completion uses a conditional update so two workers cannot both publish authoritative results.

### 10.4 Retry policy

Retryable failures include provider rate limits, transient network failures, temporary model unavailability, and storage contention.

Non-retryable or blocked failures include invalid tenant configuration, missing active thesis, unresolved identity, schema-invalid persistent model output after bounded repair, unsupported artifact type, exhausted budget, and policy validation failure.

Retries use exponential backoff with jitter and a strict attempt ceiling. Expensive jobs do not retry from the beginning when earlier stage outputs were committed successfully.

### 10.5 Partial success

The pipeline supports partial success:

- Identity may resolve while enrichment is incomplete.
- Some evidence providers may fail while others succeed.
- Some criteria may remain unscored.
- A recommendation may be INSUFFICIENT_EVIDENCE.
- A memo or decision record may render with explicit gaps.

Partial success is preferable to hidden fabrication or an opaque generic failure.

### 10.6 Dead letters and operator recovery

Dead-letter jobs remain visible with a failure category and safe retry action. The GP should see customer-relevant language, while detailed provider and stack information remains in protected logs.

Recovery actions include retry, correct identity, increase a specific budget, attach evidence, change an unsupported artifact, or archive the Opportunity.

### 10.7 Domain event outbox

Authoritative writes that require downstream reactions also insert a tenant-scoped outbox event in the same transaction. Events include:

- observation_resolved
- evidence_materially_changed
- evaluation_completed
- recommendation_changed
- ruling_recorded
- action_due
- monitor_due
- policy_published

Consumers mark delivery idempotently. SSE notifications are projections of committed events, not the primary work queue.

### 10.8 Concurrency

Concurrency is limited at three levels:

- Global service concurrency protects small instances.
- Per-tenant concurrency prevents one fund from monopolizing workers.
- Per-company and per-opportunity locks prevent overlapping authoritative evaluations.

Search, model, and document parsing concurrency have separate limits because their resource and cost profiles differ.

## 11. Evidence and founder-assessment standard

### 11.1 Evidence trust classes

Suggested trust classes are:

1. Verified primary records: government registries, filed documents, signed customer material, or equivalent.
2. Independent reputable third-party reporting or databases with clear provenance.
3. Company-controlled public material.
4. Founder-supplied confidential material.
5. Operator-authored observations.
6. Model inference.

Trust class is not a universal truth ranking. A founder-supplied current metric may be more relevant than a stale database record, but the assertion class must remain visible.

### 11.2 Material claim rule

A material claim is one that changes mandate fit, a criterion score, recommendation, attention priority, decisive risk, or required action. Every material claim must have:

- at least one linked evidence item;
- a support or contradiction relationship;
- an assertion class;
- source and capture time;
- freshness state;
- confidence;
- a reason it is material.

### 11.3 Founder evidence

Permitted public-data founder signals include:

- verified roles and tenure;
- relevant domain history;
- prior companies and products;
- technical contributions, publications, patents, or credible public work;
- prior fundraising or exits when evidenced;
- repeated exposure to the customer problem;
- customer or colleague references where authorized;
- demonstrated shipping history;
- operator-authored interview observations.

Forbidden as unqualified model facts:

- magnetic
- charismatic
- obsessed
- maniacal
- inevitable
- visionary
- resilient
- exceptional communicator

Earned insight is a model inference only when explicitly tied to facts. It should be phrased as a hypothesis for diligence, not a proven founder attribute.

### 11.4 Interview evidence

Interview evidence is operator-authored or transcript-derived and must retain:

- meeting or note source;
- author or participant;
- date;
- exact supporting passage where retention policy permits;
- whether the interpretation was human-authored or model-suggested;
- confidentiality and access class.

Model-derived interview interpretations remain suggestions until accepted by the operator.

### 11.5 Prompt-injection defence

All external text is untrusted. Document and web content is placed in a delimited data field, never concatenated as system instructions. Extraction and evaluation use separate calls and schemas. The system ignores instructions inside artifacts, rejects unexpected tool directives, and records adversarial-content flags.

No document-derived value can select a model, provider, endpoint, policy version, tool, external recipient, or spending limit.

## 12. Scoring, confidence, and recommendation semantics

### 12.1 Policy structure

The active fund policy contains:

- hard mandate constraints;
- positive preferences;
- exclusions;
- stage, geography, sector, ownership, and check-size constraints;
- dimensions and criteria;
- criterion and dimension weights;
- score anchors;
- acceptable evidence classes;
- missing-evidence behaviour;
- confidence caps;
- escalation rules;
- recommendation thresholds.

The fund thesis describes what the fund seeks. The scoring policy describes how evidence is evaluated. Partner rules describe how assessments become a recommendation. These remain separately versioned even when published through one Settings experience.

### 12.2 Score meaning

A score is a policy-relative assessment, not a universal company rating. Every displayed score states which fund policy produced it.

The system does not compare two funds' scores as though they share an objective scale. A company can be an excellent business and a poor mandate fit.

### 12.3 Missing evidence

Missing evidence can:

- leave a criterion unscored;
- reduce confidence;
- cap a dimension score;
- create a diligence action;
- prevent a recommendation;
- require human review.

It cannot automatically become a neutral fact. A zero, low score, neutral score, and unscored criterion have different meanings.

### 12.4 Confidence

Confidence reflects:

- identity confidence;
- source coverage;
- source quality;
- claim agreement or contradiction;
- freshness;
- extraction reliability;
- criterion evidence sufficiency;
- policy clarity;
- model agreement only where models operate independently.

Confidence is not the model's self-reported certainty alone. The final confidence cannot exceed the lowest decisive evidence gate.

### 12.5 Recommendation change explanation

When a recommendation changes, Aethria shows:

- old and new recommendation;
- old and new evidence snapshot dates;
- new, changed, stale, or removed claims;
- criteria affected;
- policy changes, if any;
- deterministic threshold effects;
- model or prompt changes, if material;
- whether the change came from evidence, policy, or system version.

This change explanation is more important than regenerating a longer memo.

## 13. Continuous sourcing and attention-triggered enrichment

### 13.1 Sourcing

Autonomous sourcing remains a differentiator but should optimize for useful novelty, not volume. Each sourcing strategy receives:

- active mandate;
- recent coverage by sector and theme;
- already-seen canonical identifiers;
- cost allowance;
- target discovery count;
- source-quality requirement;
- novelty and overlap limits.

Scout reweighting is initially static or human-approved. Fund Intelligence may later propose changes based on attributable sourcing performance.

### 13.2 Lifecycle service levels

Each Opportunity receives an enrichment service level:

| Level | Typical state | Behaviour |
|---|---|---|
| 0 — archive | Historical pass or inactive record | No automatic refresh |
| 1 — discovered | New low-priority candidate | Identity and minimum evidence only |
| 2 — active review | Current decision queue | Gap-oriented enrichment |
| 3 — monitor | Explicit monitor ruling | Scheduled or signal-triggered refresh |
| 4 — diligence | Advance or active diligence | Highest freshness and source coverage |
| 5 — portfolio | Invested company | Portfolio-specific signal policy |

Moving to a higher level requires a system trigger permitted by policy or a human action. Moving down releases future budget reservations.

### 13.3 Enrichment triggers

Permitted triggers are:

- new observation;
- GP opens or advances an Opportunity;
- evidence required by the policy is absent;
- decisive evidence exceeds its freshness window;
- monitor review is due;
- a verified external signal is received;
- a human requests refresh;
- a policy change affects an active Opportunity;
- a correction invalidates the current evaluation.

There is no trigger called refresh everything.

### 13.4 Cost envelope

Every enrichment plan declares:

- maximum search queries;
- maximum artifacts;
- maximum model tokens;
- maximum estimated monetary cost;
- allowed providers;
- deadline;
- reason and service level.

CostController reserves the envelope before work begins, settles actual usage after each stage, and releases unused capacity. Budget exhaustion creates a visible BLOCKED reason and does not silently skip quality gates.

### 13.5 Material-change detection

Scheduled monitoring first performs a cheap signal and metadata check. Full extraction and evaluation run only when the signal suggests material change or a decisive item is stale.

Materiality is policy-aware: a new customer pilot may matter for an execution criterion, while a cosmetic website update does not.

## 14. Institutional learning and Fund Intelligence

### 14.1 Immediate learning hierarchy

Learning signals should be trusted in this order:

1. GP correction of an identity, claim, or evidence relationship.
2. GP ruling with a structured override reason.
3. Repeated mandate exceptions.
4. Repeated requests for the same missing information.
5. Recommendation-confidence disagreements.
6. Later verified outcomes with sufficient observation coverage.

Search popularity, press volume, or later financing alone are weak learning signals.

### 14.2 MetaAgent transition

Automatic prompt mutation, scout reweighting, and threshold activation are frozen before the new learning layer ships.

The current MetaAgent can continue to run in shadow mode to produce diagnostic comparisons, but its output cannot change production configuration. Existing mutation history remains available for audit.

### 14.3 Proposal thresholds

A proposal must state its sample and limitations. Early proposals should be descriptive rather than prescriptive.

Examples:

- Three overrides may create an observation.
- A repeated pattern across a larger and diverse sample may create a draft proposal.
- A policy change affecting hard mandate logic requires explicit human publication regardless of sample size.

Exact statistical thresholds belong in versioned Fund Intelligence policy and should be tuned with real usage. They must not be hardcoded across the codebase.

### 14.4 Attribution

Every learning signal identifies the likely layer:

- acquisition miss;
- identity error;
- evidence retrieval gap;
- extraction error;
- claim-verification error;
- policy criterion disagreement;
- weight or threshold disagreement;
- recommendation rule disagreement;
- private-information exception;
- human strategic exception.

Signals with ambiguous attribution remain unclassified and cannot automatically support a specific policy patch.

### 14.5 Policy proposal review

The GP sees:

- pattern summary;
- supporting and contradicting examples;
- sample size and period;
- affected criteria;
- limitations;
- proposed change;
- bounded historical preview;
- expected effect on active Opportunities;
- accept, edit, reject, or defer actions.

Acceptance uses the existing policy compiler and creates a new version. Rejection is itself recorded so the same weak proposal is not repeatedly surfaced.

### 14.6 Outcome learning

Outcome learning is phased in only when:

- observations include positive and negative outcomes rather than funded-company survivorship alone;
- coverage is measured;
- outcome definitions are explicit;
- enough time has elapsed;
- the system can attribute which stage influenced the original recommendation;
- the analysis avoids causal claims it cannot support.

Until then, outcomes provide context and monitoring signals, not claims of predictive accuracy.

## 15. Workflow orchestration

### 15.1 Diligence-question preparation

The system assembles questions from:

- missing decisive evidence;
- contradicted claims;
- low-confidence criterion assessments;
- biggest unknown;
- conditions that would change the recommendation;
- founder and customer assertions lacking verification;
- mandate exceptions;
- precedent from similar prior rulings.

Questions are grouped by decision impact and show why each is being asked.

### 15.2 Information-request drafts

A request draft contains only the information required to resolve identified gaps. It avoids disclosing internal scores or sensitive policy details unless configured by the GP.

The GP edits and approves the draft. Aethria does not send email in the first version.

### 15.3 CRM export

CRM integration begins as an outbound webhook or explicit export after the GP advances a company. The export contains canonical identity, source attribution, current stage, concise evidence summary, recommendation, human ruling, and deep link back to Aethria.

Inbound CRM synchronization is deferred until canonical identity and idempotent external-reference handling are proven.

### 15.4 Decision pack

The decision pack is a projection of authoritative records, not a separate generated truth. It includes:

- company and opportunity context;
- mandate fit;
- evidence-backed criterion assessments;
- founder evidence;
- contradictions and adverse register;
- recommendation and conditions to change;
- diligence questions;
- human ruling history;
- source ledger.

## 16. Product experience

### 16.1 Home and ranked queue

The main queue prioritizes attention. Each row shows:

- company;
- source channels and newest observation;
- current process state;
- recommendation or insufficient-evidence state;
- attention priority;
- identity and evidence-quality warnings;
- material new evidence;
- current human ruling;
- next action.

The queue does not lead with a universal numerical score.

### 16.2 Decision record

Selecting an Opportunity opens a decision record with:

1. Recommendation and confidence.
2. Why it was surfaced.
3. Decisive evidence.
4. Missing or contradictory evidence.
5. Criterion assessments.
6. Founder evidence.
7. Conditions that change the recommendation.
8. Ruling controls.
9. Next actions.
10. Evaluation and ruling history.

The current memo view can become a narrative projection within this record rather than the primary authority.

### 16.3 Evidence ledger

The evidence ledger supports filtering by:

- criterion;
- subject;
- source type;
- assertion class;
- verification state;
- freshness;
- support or contradiction;
- materiality.

Every score and conclusion links directly to the claims and evidence it used.

### 16.4 Ruling interaction

Ruling should be fast:

- ADVANCE, MONITOR, or PASS;
- optional confidence;
- concise rationale;
- one structured override reason when applicable;
- risk acknowledgement or mandate exception when required.

The interface preserves the GP's agency and does not frame disagreement as an error.

### 16.5 Fund Intelligence

Fund Intelligence is an editorial report and proposal inbox, not a dashboard full of pseudo-scientific metrics. It emphasizes patterns with examples, limitations, and clear controls.

### 16.6 Settings

Settings continues to own:

- fund identity;
- fund thesis;
- scoring policy;
- partner rules;
- cost budgets;
- data sources;
- enrichment service levels;
- retention;
- integrations;
- published policy history.

Publishing remains a deliberate versioned action.

## 17. Service and API boundaries

Suggested backend service boundaries are:

- acquisition_service
- identity_service
- evidence_service
- claim_service
- evaluation_service
- recommendation_service
- ruling_service
- action_service
- monitoring_service
- fund_intelligence_service
- job_service

Each service exposes Pydantic request and response models and requires explicit user_id. Internal implementation can evolve without changing consumers.

Suggested API groups are:

- /api/observations
- /api/identity-cases
- /api/companies
- /api/opportunities
- /api/evidence
- /api/evaluations
- /api/recommendations
- /api/rulings
- /api/actions
- /api/fund-intelligence
- /api/policies

The frontend uses typed clients under app-front-end/src/api and TanStack Query hooks. No new direct fetch calls are introduced.

During migration, existing /api/startups and memo routes remain compatibility projections over the new records.

## 18. Security, privacy, and governance

### 18.1 Tenant isolation

- Every new table includes user_id.
- Every unique constraint includes tenant scope unless it is a globally safe technical key.
- Service-role Supabase operations always filter by explicit user_id.
- No engine or service infers a global or default tenant.
- Job claims, outbox events, storage objects, and caches include tenant scope.

### 18.2 Confidential artifacts

Decks, emails, interview notes, and operator uploads receive explicit access and retention classes. Large artifacts live in secured object storage with tenant-scoped paths and short-lived access.

Extracted excerpts are minimized to what the decision record requires. Deletion workflows remove or tombstone derived evidence consistently with retention and audit requirements.

### 18.3 External writes

CRM exports, email sends, and other external side effects require:

- explicit user action;
- destination preview;
- scoped credentials;
- idempotency key;
- audit event;
- visible success or failure.

### 18.4 Auditability

Audit events cover policy publication, identity merge, evidence correction, evaluation completion, human ruling, mandate exception, external export, proposal acceptance, and administrative access.

Logs must not expose confidential document content, tokens, API keys, or full private context.

## 19. Observability and quality measures

### 19.1 Pipeline measures

- jobs queued, claimed, succeeded, retried, blocked, and dead-lettered;
- stage latency and wait time;
- cost by tenant, opportunity, stage, model, and provider;
- identity-resolution confidence and ambiguity rate;
- artifacts retrieved and provider failure rate;
- evidence and claim counts;
- evaluation completion and partial-success rate;
- stale evaluation count;
- external action success and idempotency conflicts.

### 19.2 Product measures

- time from observation to decision-ready record;
- percentage of material claims with valid evidence;
- unsupported founder conclusion rate;
- percentage of recommendations receiving a ruling;
- percentage of overrides with structured reasoning;
- percentage of rulings that generate a completed next action;
- duplicate-resolution error and operator correction rate;
- cost per decision-ready Opportunity;
- recommendation consistency on repeat evaluation;
- Fund Intelligence proposal acceptance and rejection;
- monitor refreshes avoided by material-change checks.

### 19.3 Initial quality targets

Targets should be validated against a representative evaluation set, but the initial release gates are:

- zero known cross-tenant reads or writes;
- zero automatic production mutations from Fund Intelligence;
- zero silent identity merges below the auto-resolution threshold;
- every displayed material claim has a provenance state;
- every completed evaluation records policy and model manifests;
- repeated execution with the same immutable inputs is idempotent;
- a failed refresh preserves the last successful recommendation;
- no external action occurs without approval and an audit event.

## 20. Testing and institutional evaluation

### 20.1 Contract tests

Every stage contract receives schema validation, tenant tests, idempotency tests, invalid-state tests, and version-compatibility tests.

### 20.2 Identity tests

The identity suite includes:

- exact domain matches;
- aliases and rebrands;
- same-name different companies;
- parent and product domains;
- conflicting provider IDs;
- missing domains;
- operator merge and split recovery;
- concurrent observations;
- tenant isolation.

### 20.3 Evidence tests

The evidence suite includes:

- source supports claim;
- source is related but does not support claim;
- contradictory sources;
- stale evidence;
- founder assertion without verification;
- operator note attribution;
- duplicate artifacts;
- content changes at one URL;
- malicious prompt-injection text;
- unsupported founder labels.

### 20.4 Policy and scoring tests

Tests cover:

- anchored label mapping;
- unscored criteria;
- missing-evidence caps;
- hard exclusions;
- mandate exceptions;
- confidence discount;
- policy version immutability;
- deterministic repeatability;
- recommendation threshold boundaries;
- LLM fallback triggers.

### 20.5 Golden evaluation set

Create a tenant-safe, redacted set of representative opportunities containing:

- strong fit with strong evidence;
- strong-looking company outside mandate;
- weak company with polished materials;
- sparse pre-seed evidence;
- conflicting founder or traction claims;
- ambiguous identity;
- model-attractive but unsupported founder narrative;
- hard pass with a strategic exception;
- later evidence that changes a recommendation;
- repeat evaluation with unchanged inputs.

Each case has expected invariants rather than one mandatory universal investment verdict. Invariants include which evidence is material, which criteria cannot be scored, which gates apply, and what must require human review.

### 20.6 Shadow-mode evaluation

The new evaluation path runs alongside the current pipeline before becoming authoritative. Compare:

- identity result;
- source coverage;
- unsupported claims;
- criterion assessments;
- recommendation;
- confidence;
- cost;
- latency;
- human preference.

Differences are reviewed rather than averaged away.

### 20.7 Migration tests

Backfill tests confirm:

- record counts by tenant;
- source-observation preservation;
- no false verification upgrade;
- current ruling parity;
- historical decision preservation;
- idempotent reruns;
- rollback-safe compatibility reads;
- no mutation of existing migrations.

## 21. Migration and delivery phases

The migration is a strangler transition, not a rewrite.

### 21.1 Implementation planning boundary

This document is the master product and architecture design. It is intentionally broader than one safe implementation plan. Delivery is decomposed into independently verifiable sub-projects:

1. Institutional guardrails and evaluation harness.
2. Durable execution foundation.
3. Canonical identity and source observations.
4. Evidence and claim ledger.
5. Immutable evaluation and recommendation.
6. Human rulings and bounded workflow actions.
7. Attention-triggered enrichment.
8. Governed Fund Intelligence.
9. Channel and outcome expansion.

Each sub-project receives its own implementation plan, tests, migration boundary, rollout flag, and acceptance gate. The first implementation plan covers only Phase 0 and Phase 1. Later plans may refine their local design without violating this master architecture.

### Phase 0 — institutional guardrails

**Deliverables**

- Disable automatic MetaAgent production mutations.
- Preserve MetaAgent analysis in shadow mode.
- Define the golden evaluation set.
- Add quality and cost measurements.
- Formalize recommendation versus ruling semantics.
- Record complete model, prompt, policy, and rule manifests for new evaluations.

**Customer value**

- Safer behaviour and clearer trust position.

**Exit criteria**

- No automated configuration mutation.
- Current pipeline can be measured against representative cases.
- Evaluation and ruling versions are traceable.

### Phase 1 — durable execution foundation

**Deliverables**

- Durable AgentJob table and minimal worker.
- Leases, heartbeats, retries, dead letters, and idempotent completion.
- Pipeline-run and stage attribution.
- Domain event outbox.
- Migration of current cycle and lookup queues.
- Per-tenant and global concurrency protection.

**Customer value**

- Work survives API restarts and failure states become recoverable.

**Exit criteria**

- Restarting the API does not lose accepted work.
- Duplicate jobs do not duplicate authoritative output.
- Expired leases can recover without two successful publications.
- Current cycle and lookup behaviour passes compatibility tests.

### Phase 2 — canonical identity and source observations

**Deliverables**

- Company, identifier, alias, source-observation, opportunity, and identity-case tables.
- Domain-first resolver contract.
- Ambiguity queue.
- Dual-write from Scout and Dispatch.
- Backfill existing startups conservatively.

**Customer value**

- Duplicate reduction, source provenance, safer manual lookup.

**Exit criteria**

- Scout and Dispatch converge on the same canonical company when appropriate.
- Ambiguous matches do not auto-merge.
- All new discoveries preserve channel attribution.

### Phase 3 — evidence and claim ledger

**Deliverables**

- Artifact, evidence-item, claim, and claim-link tables.
- Evidence planner.
- Source trust and freshness classification.
- Founder-evidence standard.
- Evidence-ledger read API and UI.
- Prompt-injection protections for untrusted content.

**Customer value**

- Inspectable conclusions and visible diligence gaps.

**Exit criteria**

- Material conclusions link to evidence.
- Unsupported founder traits are blocked or clearly attributed.
- Contradictions and stale claims are visible.

### Phase 4 — immutable evaluation and recommendation

**Deliverables**

- EvaluationRun, CriterionAssessment, and Recommendation records.
- Deterministic policy evaluation over claim snapshots.
- Recommendation change explanation.
- Current PartnerEngine adapted behind RecommendationEngine.
- Existing startup and memo APIs served from compatibility projections.

**Customer value**

- Reproducible, fund-specific recommendations with visible uncertainty.

**Exit criteria**

- Same immutable inputs produce the same deterministic result.
- Failed refresh preserves the prior result.
- Every recommendation can explain its evidence and policy versions.

### Phase 5 — rulings and bounded orchestration

**Deliverables**

- Append-only HumanRuling and OverrideSignal.
- Fast ruling controls.
- Diligence-question action.
- Missing-information request draft.
- Monitor scheduling.
- Optional explicit CRM export.

**Customer value**

- A complete decision loop and immediate institutional memory.

**Exit criteria**

- Overrides are captured without onerous data entry.
- Actions arise from specific evidence gaps.
- External actions remain approved and audited.

### Phase 6 — attention-triggered enrichment

**Deliverables**

- Lifecycle service levels.
- Budget reservation and settlement.
- Material-change detection.
- Monitor scheduling on durable jobs.
- Gap-oriented refresh plans.

**Customer value**

- Living company records with bounded recurring cost.

**Exit criteria**

- Historical passes do not create unbounded monitoring spend.
- Every automatic refresh records a lifecycle reason and budget.
- Cheap material-change checks prevent unnecessary full evaluation.

### Phase 7 — Fund Intelligence

**Deliverables**

- LearningSignal and PolicyProposal.
- Override pattern reports.
- Human approval workflow.
- Bounded policy impact previews.
- Rejection and deferral memory.

**Customer value**

- Aethria begins learning how the GP actually invests without silently changing behaviour.

**Exit criteria**

- Every proposal shows evidence, attribution, sample, and limitations.
- Accepted proposals create versioned policy.
- No proposal can self-activate.

### Phase 8 — channel and outcome expansion

**Deliverables**

- CSV import.
- Selected CRM input integration.
- Carefully scoped email or deck ingestion.
- Verified outcome observations.
- Later organization and multi-partner IC primitives.

**Customer value**

- Broader workflow coverage after the decision substrate is trusted.

**Exit criteria**

- New channels reuse canonical identity and evidence contracts.
- Confidential artifacts meet retention and security requirements.
- Outcome analysis does not make unsupported causal claims.

## 22. Principal risks and mitigations

| Risk | Consequence | Mitigation |
|---|---|---|
| Scope becomes a platform rewrite | Long delay before user value | Strangler phases, compatibility APIs, customer-visible exit criterion per phase |
| Evidence schema becomes overly generic | Slow development and unusable records | Start with investment-relevant claim types and typed extension fields |
| Canonical identity makes false merges | Corrupted evidence and decisions | Verified identifiers, confidence thresholds, ambiguity queue, reversible tombstones |
| Models attach plausible but irrelevant citations | False trust | Claim-evidence relationship verification and golden tests |
| Founder assessment recreates personality scoring | Bias and unsupported claims | Allowed-signal policy, operator attribution, unsupported-label tests |
| Durable jobs add operational complexity | New failure modes | Minimal job contract, lease tests, limited job types, observability before scale |
| Institutional learning overfits a few decisions | Bad policy proposals | Descriptive early reports, sample disclosure, human approval, no self-activation |
| Outcome tracker creates survivorship bias | Misleading calibration | Coverage measurement, positive and negative outcomes, no causal language |
| Enrichment cost grows without bound | Unsustainable margins | Lifecycle service levels, explicit triggers, budget reservation, archive default |
| CRM work expands uncontrollably | Product loses differentiation | Explicit outbound export only until core is proven |
| Solo GP does not enter override reasons | Weak learning loop | One-click reason categories, optional detail, value returned immediately |
| Migration falsely upgrades legacy evidence | Artificial confidence | Preserve raw legacy artifact, conservative assertion class, migration audit |
| User-supplied documents inject prompts | Manipulated output or actions | Untrusted-input isolation, structured extraction, no artifact-controlled tools or policy |
| Recommendation language still sounds autonomous | Customer distrust | Human-ruling separation throughout UI, API, marketing, and records |
| Current app surfaces expose normalized complexity | Poor usability | Stable decision-record projections and progressive evidence detail |

## 23. Decisions made

- Initial customer is the solo GP or emerging fund.
- Aethria recommends; the investor rules.
- Direction 2, evidence and decision platform, is the product strategy.
- Current agent architecture is transitional, not the future source of authority.
- Evidence-backed founder assessment is a system standard, not a separate novelty feature.
- Canonical identity is infrastructure required before cross-channel deduplication.
- Continuous enrichment is attention-triggered and budgeted.
- Override learning precedes outcome learning.
- Fund Intelligence proposes; it does not mutate production.
- Workflow begins with diligence questions and missing-information requests.
- CRM integration begins as explicit outbound export.
- Multi-user IC and enterprise workflow are deferred.

## 24. Future decisions deliberately deferred

- When to introduce fund_id and organization membership alongside user_id.
- Which external company-data providers justify paid integrations.
- Which document-ingestion formats meet the required trust bar.
- Whether any low-risk external action can later be pre-approved.
- Statistical thresholds for Fund Intelligence proposals after real usage exists.
- Outcome definitions and observation windows for calibration.
- Pricing by fund, seat, decision-ready Opportunity, or usage envelope.

## 25. Final recommendation

Build the evidence-and-decision platform through the phased migration above. Do not undertake a ground-up rewrite and do not spend the next cycle adding more personas, more prose, or general CRM features.

The highest-leverage order is:

1. Freeze unsafe automatic learning and establish evaluation measurements.
2. Replace process-local pipeline queues with minimal durable execution.
3. Fix identity and preserve source observations.
4. Make claims and evidence authoritative.
5. Make evaluation and recommendation immutable and reproducible.
6. Capture human rulings and override reasons.
7. Add the two bounded workflow actions.
8. Add attention-triggered enrichment.
9. Introduce governed Fund Intelligence.
10. Expand channels and outcomes only after the substrate earns trust.

The strategic moat is not access to an LLM or the number of agents. It is the fund-specific, evidence-linked history of what was seen, what was believed, what was recommended, what the investor decided, why they disagreed, what happened next, and how policy changed under explicit human governance.

That is the product a solo GP can begin using immediately and an emerging fund can grow dependent on without surrendering judgment.
