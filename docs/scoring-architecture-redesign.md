# Scoring architecture redesign

## Current state — verified September 2026

Aethria previously had two active decision paths and five score producers. The
legacy paths below are retained as an audit record because their historical
snapshots remain readable; they no longer authorize a new Partner decision.

| Path | Score used by Partner | What produces it | Current result |
|---|---|---|---|
| On-demand lookup | Canonical `evaluation_v2` criterion scores | Evidence extraction classifies policy bands; evaluator applies eligibility and fixed anchors | Partner blocks if no evaluation is available. |
| Periodic pipeline | Canonical `evaluation_v2` criterion scores | Identity admission → canonical claims → one immutable evaluation per opportunity | Partner blocks if no evaluation is available. |
| Memo | Canonical criteria only for current assessments | Immutable evaluation plus source ledger | Legacy reviewer numbers are not presented as canonical. |

Historical and internal producers that were previously decision-capable are:

1. Raw reviewer persona scores.
2. The deterministic structured scorer.
3. Reviewer consensus/resolution blending.
4. Canonical evidence-extraction claim scores.
5. Partner fallback averaging when canonical evaluation is absent.

None of these can now create a Partner decision or a public scorecard. Legacy
rows remain readable for audit; list projections, queue conviction, portfolio
score enrichment, lookup snapshots, the memo scorecard, and the live review
feed do not turn their numbers into a current score. Queue priority metadata is
also rebuilt at the API boundary, so stored pre-redesign numeric priorities are
not replayed as current conviction.

### Residual compatibility surfaces

The old Reviewer personas, deterministic scorer, numeric blend, and legacy
Partner ladder have been removed. Historical rows remain readable through
one-way projections; the API/UI do not promote their numeric fields to current
assessment authority. Published policy data and its compiler remain because
the live analysis still consumes versioned fund policy.

One presentation fallback remains: `semantics.ts` contains the same four-band
rubric mirror used when a legacy structured presentation has no policy payload.
Canonical presentations carry their own bands when available, and the parity
test prevents drift; making every historical evaluation carry its original band
definition would require persisting a rubric snapshot rather than consulting
the active policy. That is the remaining runtime-derived-band workstream.

### Live example: Rippling

The historical lookup had allowed the reviewer path to turn a passage containing
`$570M` annualized revenue and `99.5%` retention into unexplained model-selected
scores, including `6.0`. That is not an analyst-grade basis for a number.

On 4 September 2026, the same verified runtime evidence was re-evaluated through
the canonical path. Deterministic extraction persisted two typed claims:
`570000000 USD → Execution high anchor 8.0` and `99.5 percentage points → Product
high anchor 8.0`. The source-quality safeguard then produced `7.99` for each
criterion because the corroborated source quality was `0.6`; the resulting
canonical recommendation was `monitor`. The ledger stores the concise fact,
full source link, policy band, raw value, and adjustment, so the number can be
reconstructed without trusting a model-selected decimal.

### Other verified operational defect — fixed

The live Dispatch retry control reports “Retry accepted” before the API response
has confirmed that the job was requeued. In the Rippling test the persisted job
remained `dead_letter`, so the screen continued to imply progress that never
started. Retry confirmation now follows the server acknowledgement; telemetry
after a durable Partner outcome can no longer turn that outcome into a failed
lookup.

## Target architecture

```
retrieved evidence
  → atomic, cited claims
  → rubric-band classification (low | mid | high | unscored)
  → policy-owned numeric anchor
  → deterministic criterion aggregation + evidence gate
  → canonical recommendation
  → Partner decision
  → memo ledger using that same evaluation
```

The model may extract facts and classify a claim against published criteria. It never selects an exact score, an overall score, a verdict, or a decision threshold.

### Invariants

- One completed evaluation is the only score source Partner and the memo may use.
- A numeric score has a policy version, rubric band, supporting claim IDs, source links, confidence, and exact formula.
- Missing evidence is `unscored`; it is never neutral, averaged, or silently replaced.
- A claim score is an anchor from versioned policy, never a model-selected decimal.
- Reviewer personas supply adversarial evidence and qualitative observations only. They do not publish competing scorecards.
- Partner consumes only the canonical recommendation plus named risk gates. It never falls back to a reviewer average.
- Historical records retain their original policy and snapshot; migration changes only new evaluations.

## Design and delivery sequence

### 1. Fixed rubric anchors — implemented

`evaluation_rubric/v3.json` defines conservative anchors: low = 3, mid = 5, high = 8. The extractor requests a band, and the backend persists the configured anchor. A model-supplied decimal is ignored. v1/v2 records remain readable with legacy behavior.

Criterion aggregation uses the lowest eligible policy anchor rather than
confidence-weighting claims. Confidence controls evidence eligibility and is
shown as uncertainty; it cannot manufacture an in-between decimal. Where a
dimension has a published typed-fact rule, an eligible typed fact takes scoring
precedence over historical generic scores for that dimension. A cited `$570M`
annualized-revenue fact is `570000000 USD` and selects Execution's high `8`
anchor; a cited `99.5%` retention fact selects Product's high `8` anchor.
Generic contradiction evidence remains visible as a safety signal. Missing
required criteria still keep the decision gate closed.

### 2. Canonical-only decision path — implemented

Periodic Scout discoveries now pass through identity admission, canonical Scout
claim persistence, and one `EvaluationRepository.evaluate()` call per resolved
opportunity before Reviewer/Partner. Every `PartnerEngine.run_cycle()` loads
that current evaluation by the startup's canonical projection; if it is absent,
it blocks the decision rather than falling back to a reviewer average. The
single-startup Partner method applies the same requirement. The old manual
"decide anyway" endpoint now returns a named conflict directing the operator to
run a canonical evidence evaluation instead of creating a reviewer-score decision.

Inside Partner, canonical state now takes an early, separate path. It maps
`advance | monitor | pass | insufficient_evidence` to the Partner vocabulary,
adds only named critical-risk, contradiction, evidence-coverage, and mandate
gates, and does not average criteria, invoke grey-zone score logic, or run an
LLM score ladder. `company_quality` is deliberately empty for that path.

Existing legacy reviewed rows are deliberately not bulk-rewritten or silently
re-admitted: they retain their historical snapshots and cannot receive new
automatic Partner decisions until an explicit re-evaluation. The existing
tenant-scoped `POST /api/opportunities/{id}/evaluate` path records such a run
with `trigger_type=operator_refresh`; it appends an immutable snapshot and
refuses to reopen invested or completed-workflow opportunities.

Expected result for newly discovered opportunities: manual and periodic
processing reach the same recommendation from the same immutable snapshot.

### 3. Reviewer role reduction — implemented

Reviewer runs no longer construct the deterministic scoring engine. Prompts do
not request numeric score fields or the former 25-component structured-signal
matrix, and every parser, preview, persona-snapshot, and persistence path
redacts dimension scores, derived overall scores, structured score traces,
score variance, and derived verdicts before persistence.
The three perspectives retain their evidence challenges, contradictions,
diligence gaps, and qualitative observations. Their disagreement is retained as
an evidence-quality signal, not a numerical blend.

The operator scorecard and AethriaView headline also no longer fall back to
reviewer verdict labels; reviewer output is qualitative context only.

API projections null historical reviewer scores and scrub nested persona score
traces, so a legacy record cannot regain score authority in an operator
surface. The Markdown memo and IC/PDF export likewise omit reviewer scores,
bands, verdict labels, and score bars.

Expected result: no reviewer can overwrite, average, or contradict a canonical score.

### 4. Fact-first criterion rules — implemented for the initial commercial facts

The active v3 rubric registers typed, policy-owned commercial rules: annualized revenue (USD) under Execution and customer retention (percentage points) under Product. The model must extract the cited numeric value in that base unit; the extractor derives the fixed anchor from the published threshold and persists the raw value, unit, policy origin, and band. It drops an unparseable value rather than falling back to a model score.

The conservative initial thresholds are explicit: annualized revenue of `$100M+` maps to the Execution high anchor (`8`), `$10M+` to mid (`5`), and lower verified revenue to low (`3`); retention of `95%+` maps to the Product high anchor (`8`), `80%+` to mid (`5`), and lower verified retention to low (`3`). A source-quality or freshness cap can still lower an otherwise high anchor, and missing required criteria still block the decision.

The next expansion is to publish similarly typed rules for growth, market size, customer concentration, and repeatability. Qualitative criteria remain explicitly qualitative and require analyst review.

Expected result: the ledger can say "Execution is high because `$570M` annualized
revenue cleared the published threshold; evidence coverage is still incomplete",
rather than presenting one undifferentiated company score.

### 5. Canonical memo ledger — implemented

The canonical evaluation API already returns criterion claim IDs and deterministic
adjustments; the evidence ledger supplies the source locators. The memo now
joins these at render time: expanding a canonical score shows the aggregation
formula, eligible anchors, cited supporting/contradicting claims, and source
links inline. “How scored” names the persisted rubric version and fixed
low/mid/high anchors. No ledger is rendered for legacy Reviewer scores, because it
would imply provenance they do not have.

When canonical recommendation state is `insufficient_evidence`, the scorecard
suppresses its headline average and states that the decision is blocked by
evidence. Individual cited observations remain inspectable, but cannot be
misread as a decision-ready score.

Expected result: an analyst can reconstruct every number without navigating to a separate provenance section.

### 6. Policy and outcome validation — implemented

Contract tests cover fixed anchors, no confidence-weighted interpolation,
canonical Partner gating, and periodic/manual canonical handoff. Historical
tests that formerly asserted a raw reviewer score could yield an
`INVEST`/`PASS` outcome now use canonical-decision fixtures; no compatibility
fallback preserves the retired score path.
Immutable snapshot replay remains covered by the existing evaluator suite. A
score-to-outcome calibration dataset is a future operating-data requirement,
not a missing scoring-path implementation or a substitute for score-consistency
tests.

Expected result: Aethria can demonstrate consistency now and predictive validity when outcome coverage is sufficient.

## Resulting behavior matrix

| Input state | Before | Now |
|---|---|---|
| Reviewer says `6`, no canonical evidence | Could pass a decision threshold, appear as queue conviction, and be rendered in the memo | Partner blocks; UI shows no score and directs work to canonical evaluation. |
| Extractor emits `6.5` | Persisted as model-selected decimal | Ignored: qualitative claims map to policy anchors, and typed facts map to their published threshold band. |
| Extractor finds `$570M` annualized revenue | Model could call the surrounding evidence “mid” | Extracts `570000000 USD`; v3 assigns Execution’s high `8` anchor before evidence-quality caps. |
| Two eligible qualitative claims disagree | Confidence weighting could create an in-between decimal | Criterion uses the lowest eligible policy anchor and shows every contributing claim. |
| Typed fact and legacy generic score disagree | A model-selected generic score could dilute the factual threshold | The typed fact's published anchor scores that dimension; the generic claim remains only for provenance and contradiction checks. |
| Canonical evaluation says `advance` | Partner could re-average and rerun its own thresholds | Partner maps `advance` directly to `INVEST`; only named safety/mandate gates can change it. |
| Canonical evaluation is incomplete | A reviewer fallback could still look decision-ready | `MONITOR`, human review, explicit missing criteria, and no headline score. |

## Acceptance checks

1. The same evidence snapshot produces the same criterion scores and recommendation in manual and periodic paths.
2. No model output field can set a decimal score, overall, or decision directly.
3. Partner fails closed if canonical evaluation is unavailable.
4. The memo renders only canonical criterion values and their source ledger.
5. Live canonical re-review completed against the existing Rippling evidence:
   typed claims and `7.99` quality-capped criterion results are persisted. The
   authenticated Chrome queue opens the Rippling memo and shows the canonical
   decision workspace. The rendered score basis and both typed-claim rows show
   the policy-derived high anchor and the explicit `8.00 → 7.99`
   source-quality cap; the memo reports `Ready for ruling`. The local backend
   health endpoint is also responding successfully after the database service
   recovery.
