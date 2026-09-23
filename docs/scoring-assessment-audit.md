# Scoring Assessment Audit — Investment Memos

Historical audit. The Reviewer/scorer executors discussed below were retired
in September 2026; the paths and findings describe the code as it existed
when this audit was written.

**Scope:** How startup scores are *produced* (the "who/how") and *presented* in
investment memos, plus whether scores are *comparable across companies*.
**Status:** Audit + remediation plan. No code changed by this document.
**Source of truth at time of writing:** `evaluation_rubric/v1.json` (v1.1),
`partner_rules/v1.json`, `backend/services/scoring/*`, `backend/reviewer/*`,
`app-front-end/src/components/scoring/*`, `app-front-end/src/lib/reviewScoring.ts`,
`app-front-end/src/design-system/semantics.ts`.

---

## TL;DR

A score in Aethria is **reproducible arithmetic on top of a subjective, isolated
LLM judgment, then re-labelled and re-aggregated inconsistently on the way to the
memo.** Three independent problem clusters:

1. **Meaning / comparability** — a "5 on Market" means "the same formula ran," not
   "the same investment reality." ~21 of 25 scoring components are an LLM-chosen
   adjective mapped to a number through a lookup table; "unknown" and "off-vocabulary"
   both silently become `5.0`.
2. **Provenance / aggregation** — there are 3 competing score producers and up to 3
   different ways the "overall" is computed; defensibility is counted 3 contradictory
   ways; several computed signals are dead.
3. **Presentation / formatting** — the backend and frontend disagree on what a score
   *means* (a `7` is "Promising" in the rubric, "Strong" in the memo), label
   vocabularies collide across axes, and two different conviction scales are shown.

The bar this document is written against: **a VC analyst should be able to
interrogate any score fact-by-fact and never be confused about how it was produced.**
Today the platform fails that bar on all three clusters.

---

## 1. How scoring works today (the pipeline of producers)

```
Scout (LLM)  ─▶  Reviewer ×3 personas (LLM)  ─▶  Structured scoring engine  ─▶  Partner (rules)  ─▶  Memo
              Default / Skeptical / Opportunist     extract → normalize →            INVEST /
                                                     aggregate (deterministic)        MONITOR / PASS
```

A published dimension score can originate from **any of three producers**, and the
memo never says which:

- **LLM integers** from each reviewer — explicitly demoted to *"non-authoritative
  hints for coherence checks only"* (`backend/reviewer/base.py:165`).
- **Deterministic structured engine** — recomputes scores from extracted signals
  using fixed weights when `USE_STRUCTURED_SCORING` is on (**default true**,
  `base.py:161`; `backend/services/scoring/scoring_engine.py`,
  `backend/config/scoring_config.py`).
- **Resolution blend** — when personas diverge ≥2 points on a dimension, overrides
  again with `resolved = round(0.55*mean + 0.45*min)`
  (`backend/services/reviewer_resolution.py`).

---

## 2. Part A — Provenance issues (the "who")

| ID | Issue | Evidence |
|----|-------|----------|
| **A1** | Three competing score producers, silently layered. No single source of truth for a number. | `base.py:161,165`; `scoring_engine.py`; `reviewer_resolution.py` |
| **A2** | The "reviewer panel" is **not** three independent votes. Personas are prompt-language only; their integers can be discarded by the deterministic engine. | `reviewer/skeptical.py:10-20`, `reviewer/opportunist.py:10-19` |
| **A3** | **Defensibility is counted three contradictory ways at once:** excluded from the 4-dim mean that drives the partner decision (`utils/scoring.py`); included at equal 0.20 weight in the structured 5-dim engine (`scoring_config.py`); and a 1.5×-skeptical `weighted_defensibility_score` is computed then displayed nowhere (`reviewer/engine.py:256-272`). | as cited |
| **A4** | The "overall" is computed **up to three ways** depending on payload shape: structured 5-dim, `review.overall_score` (4-dim mean), `aggregate_score`, or simple mean of 5 flat scores. The displayed overall is not reproducible from the displayed dimensions. | `app-front-end/src/lib/reviewScoring.ts:155-160` |
| **A5** | Dead computed signals: `confidence_adjusted_score` (penalizes reviewer disagreement, `engine.py:298-302`) and `weighted_defensibility_score` are never rendered. | as cited |
| **A6** | Verdict thresholds drift silently over time (meta calibrator, ±0.3 on weak/strong, `meta/calibrator.py`); no policy version shown — and `sanitizeReasoning` strips any text mentioning `policy_version`/`policy_hash`/`Component weights`. | `reviewScoring.ts:180-212` |

---

## 3. Part B — Presentation / formatting issues (the "how")

### B1 🔴 Backend and frontend disagree on what a score means

`app-front-end/src/design-system/semantics.ts:3,9` claims to be *"Aligned with
canonical bands"* / aligned to `evaluation_rubric/v1.json (v1.1)`. **It is not.**

| Score | Backend rubric (`evaluation_rubric/v1.json:13-18`) — what the model scored against | Frontend memo (`semantics.ts:10-24`) — what the analyst reads |
|------:|---|---|
| 4 | **Concerning** | Below Threshold |
| 5 | **Concerning** | **Promising** |
| 7 | **Promising** | **Strong** |
| 9–10 | **Strong** | Exceptional |

A reviewer scoring a `7` means *"Promising, requires validation"*; the memo stamps
it **"Strong — venture-scale, supported by evidence."** This is a **verdict
inversion at the exact boundary where INVEST decisions are made**, and it is a pure
config/UI misalignment — independent of any LLM behaviour. **Highest-severity
finding in this audit.**

### B2 — Label collisions across axes

"Promising" is both a *dimension band* (5–6) and the *reviewer verdict* MEDIUM
(`QUALITY_LABELS`, `semantics.ts:28-32`). "Strong" is both a *dimension band* (7–8)
and the *reviewer verdict* STRONG. When the memo says "Strong," the analyst cannot
tell which axis it refers to.

### B3 — Two conviction scales for one concept

Deal-flow grid shows `INVEST 78` (0–100 integer that reads like a percentage,
`QueueVerdictLine`); the memo cover shows `7.8/10 conviction`
(`InvestmentMemoContent.tsx:911`). The cover's `${overall_score}/10` interpolation
renders a 0–100 value as a nonsensical `78/10` if that field is ever the percentage.

### B4 — The five visible numbers don't reconcile to the overall

Because of A3/A4, averaging the five displayed dimensions does not reproduce the
displayed overall, and no formula/caption is shown.

### B5 — Confidence shown three incompatible ways

Per-dimension `low/medium/high` → 0.3/0.6/0.9 (`reviewScoring.ts:21-25`); a 0–1
fraction bar; and evidence labels bucketed at 0.25/0.5/0.75
(`ConfidenceIndicator.tsx`). Worse, low confidence **silently reformats the number**:
`AssessmentDimensionStrip.tsx:20-24` renders `7.5` as **"7"** when confidence < 0.4 —
reading as a *lower score*, not as *less certain*.

### B6 — Methodology is invisible by construction

No scale legend, no aggregation formula, no persona explanation — and
`sanitizeReasoning` (`reviewScoring.ts:180-212`) deletes the engine's own
explanations of weights and policy before they reach the analyst.

---

## 4. Comparability analysis — "why is Company A a 5 on Market and Company B also a 5 if they're totally different?"

### What exists (and is genuinely good)

Scoring is **not** raw LLM vibes. A deterministic normalization layer applies
**absolute, stage-agnostic, sector-agnostic anchors**
(`backend/services/scoring/normalization_layer.py`, thresholds in
`config/scoring_config.py`):

```
TAM    ≥ $10B → 10 · ≥ $3B → 8.5 · ≥ $1B → 7.0 · ≥ $300M → 5.5 · else 4.0
Growth ≥ 40% → 10 · ≥ 25% → 8.5 · ≥ 12% → 7.0 · ≥ 5% → 5.5 · else 4.0
```

By design, a "5 on Market" is pinned to the same definition for a seed fintech and a
Series-A biotech. Funds can reweight dimensions but **cannot move the anchors**
(`policy_compiler.py`). This is meaningfully better than most AI scoring tools.

### Why it is not bulletproof

The determinism is real **only from the extracted signal forward.** Every gap is
*upstream* of the anchor:

| ID | Issue | Evidence |
|----|-------|----------|
| **C1** | The anchor sits on a **subjective, isolated LLM extraction.** The hard judgment ("is TAM $3B?", "is traction 'scaling'?") is parsed from LLM narrative. Determinism on a subjective input gives the *appearance* of objectivity. | `extraction_layer.py:29-55` |
| **C2** | **Missing → `DEFAULT_SCORE = 5.0`**, and a *verified small* TAM returns `4.0`. "We have no idea" (5.0) outscores "we know it's small" (4.0). Same number, opposite epistemics. | `normalization_layer.py:33-37`; `scoring_config.py:8` |
| **C3** | **Stage/persona leniency happens at extraction.** Opportunist: *"early-stage → give benefit of doubt"*; Skeptical: *"assume the worst."* Same evidence → different label → different 5. | `opportunist.py:14`, `skeptical.py` |
| **C4** | **Stage-agnostic anchors hide a stage bias.** Traction/growth anchors presume revenue maturity (`pre-product → 2`, `mvp → 4`, `growth < 5% → 4.0`), structurally capping pre-revenue companies on execution regardless of quality. | `normalization_layer.py:173-200` |
| **C5** | **Sector blindness.** A $1B TAM → 7.0 for biotech and dev-tools alike; "deeptech" complexity → 10 for both. A 5 in a winner-take-all market ≠ a 5 in a fragmented one. | `normalization_layer.py:244` |
| **C6** | **No cross-company / outcome calibration.** Every company scored in isolation; the calibrator tunes global thresholds, never inter-company coherence. Comparability is asserted by construction, never measured against reality. | `scoring_engine.py`; `meta/calibrator.py` |

**Verdict:** bulletproof on *arithmetic* (same signals → same score), not on
*meaning* (the inputs are stage-, sector-, and evidence-dependent, and "unknown"
is rendered as a neutral 5).

---

## 5. Per-dimension normalization — the problem applies to all five dimensions

Every component runs through either a numeric threshold (`$`/`%`) or `_map_label`
(an LLM adjective → number lookup, `normalization_layer.py:111-122`). **Only 4 of
25 components have any objective numeric anchor.** Severity *inverts*: the dimensions
with the least grounding are Technical and Defensibility.

| Dimension | Components | Objective (`$`/`%`) | Subjective (adjective → number) |
|---|---|---|---|
| **Market** | tam, growth, urgency, timing, competition | tam, growth | urgency, timing, competition |
| **Execution** | traction, growth_velocity, gtm, team, operational | growth_velocity\* | traction, gtm, team, operational |
| **Product** | value_prop, pain, differentiation, ux, retention | retention\* | value_prop, pain, differentiation, ux |
| **Technical** | complexity, engineering, scalability, data_adv, architecture | **none** | **all 5** |
| **Defensibility** | network, switching, proprietary_data, barriers, brand | **none** | **all 5** |

\* falls back to an adjective label when no number is present (i.e. almost always,
pre-revenue).

Two failure modes are therefore **universal across all 25 components**:

1. **Missing → 5.0** (the C2 problem on every dimension).
2. **Off-vocabulary → 5.0, silently.** A label the LLM invents that isn't in the
   dictionary (e.g. `"promising"` for differentiation, whose valid set is
   `none/slight/clear/strong`) falls through to `5.0`. A differentiated company, a
   no-data company, and a genuinely average company collapse to one number.

Also note a quiet coupling: the synonym table hard-maps stage words into Execution —
`"seed" → "early_adoption"`, `"pre_revenue" → "early_adoption"`, `"growth" → "scaling"`
(`normalization_layer.py:104-107`) — so a company's *stage label* can directly set
its *traction score*.

---

## 6. The fix for the "LLM meaning" problem (Layers 1–6)

Root cause: **the LLM is asked for a *judgment* (a label) when it should be asked
for *evidence*, with rules turning evidence into the label.** Each layer below is
stress-tested against the obvious objection.

### Layer 1 — Replace adjectives with behaviorally-anchored criteria (core fix)
Define each label by checkable, evidence-bound conditions instead of a vibe, e.g.
team execution:
```
elite    = ≥1 founder with prior venture-backed exit OR senior leadership at a category leader
credible = ≥5y domain experience at a directly relevant company
decent   = relevant background, first-time in this domain
weak     = no demonstrable relevant background
unscored = no team evidence in source
```
*Objection:* conditions still contain fuzzy words. *Survives because:* it collapses
an open-ended 1–10 feeling into near-binary evidence checks (this is how human
inter-rater variance is controlled), and every score becomes defensible
("7 because founder was VP Eng at X"). Highest-leverage change; fits the existing
`scoring_config.py` rubric structure.

### Layer 2 — LLM emits facts + citations; rules derive the label
Split extraction: (A) LLM extracts atomic, cited facts; (B) deterministic rules map
facts → label → score. Separates the subjective step (reading) from the scoring step
(rules). The architecture already aspires to this; today extraction outputs the
*label* (the judgment) directly.
*Objection:* rules can't cover everything (esp. Defensibility). *Survives because:*
cover the ~70% that is fact-derivable; mark the rest qualitative (Layer 5). Honest
partial determinism beats uniform fake determinism.

### Layer 3 — Abstain instead of defaulting to 5.0
No evidence / off-vocabulary → `unscored`, not `5.0`. Aggregation handles nulls
explicitly (down-weight or cap confidence); the memo shows the gap.
*Objection:* more nulls, thinner scorecards. *Survives because:* that thinness is the
truth, and it stops "unknown" impersonating "average." Cheapest fix; removes two of
three universal failure modes immediately.

### Layer 4 — Calibrate with shared reference exemplars
Put fixed worked examples (one per label) in the scoring prompt so every company is
judged against the same yardstick.
*Objection:* exemplars bias toward themselves; token cost. *Survives because:* prompt
caching makes cost negligible and anchored examples are an established way to cut LLM
rating drift. Complement, never the sole fix.

### Layer 5 — Measure label stability; treat instability as low confidence
Score judgment-heavy components (Technical, Defensibility) N times or across the
existing personas; disagreement → low-confidence/flagged, not false-precise. Mark
no-objective-anchor dimensions as qualitative so an analyst never reads a
Defensibility 8 as a TAM-backed Market 8.
*Objection:* N× cost. *Survives because:* only needed near thresholds and on the two
pure-judgment dimensions; you already run 3 personas.

### Layer 6 — Outcome calibration (the only real validity test)
Map scores → outcomes (advanced round / died / marked up) and re-fit anchors to be
predictive. Until then you can claim consistency, not correctness. Cost today is just
*storing* the structured evidence trail Layers 1–3 already produce.

---

## 7. Does the LLM-meaning fix solve everything? (Coverage map)

**No.** Layers 1–6 fix the *meaning/comparability* cluster and leave *provenance* and
*presentation* largely open.

| Issue | Fixed by L1–6? | Still needs |
|---|---|---|
| C1 subjective extraction | ✅ | L1, L2 |
| C2 missing → 5.0 | ✅ | L3 |
| Off-vocabulary → 5.0 | ✅ | L3 |
| Technical/Defensibility pure-adjective | ◑ | L1 + L5 (flag qualitative) |
| C6 stability / outcome validity | ◑ | L5 / L6 (long-horizon) |
| **C4 stage bias** | ❌ | stage-cohort design (Workstream A) |
| **C5 sector blindness** | ❌ | sector benchmarks (Workstream A) |
| A1 three producers | ❌ | canonical-score decision (Workstream B) |
| A3 defensibility counted 3 ways | ❌ | Workstream B |
| A4 overall computed 3 ways | ❌ | Workstream B |
| A5 dead signals | ❌ | Workstream B |
| A6 threshold drift / policy hidden | ❌ | Workstream B + C |
| **B1 band mismatch** | ❌ | Workstream C (highest severity) |
| B2 label collisions | ❌ | Workstream C |
| B3 two conviction scales | ❌ | Workstream C |
| B4 dims don't reconcile to overall | ◑ | L3 helps; root is Workstream B |
| B5 confidence shown 3 ways / silent truncation | ◑ | L5 helps; rest is Workstream C |
| B6 methodology invisible / censored | ◑ | L1/L2 produce the trail; Workstream C must display it |

---

## 8. The three remaining workstreams

### Workstream A — Comparability completeness (beyond L1–6)
- **Stage cohorts:** score against a stated stage cohort and print it on the memo
  ("Execution 7 — strong *for Seed*"). Preserve within-cohort comparability; make the
  cross-stage caveat visible instead of hidden (fixes C4).
- **Sector benchmarks:** anchor TAM/complexity/competition to sector-relative
  references so a 5 carries sector meaning (fixes C5).

### Workstream B — One canonical score, one formula
- Decide *once* whether defensibility is a scored driver or a risk modifier (fixes
  A3). Make the partner decision and the memo read the **same** `overall_score`
  (fixes A4). The memo caption must reproduce exactly from the displayed dimensions
  (fixes B4). Surface or delete the dead signals (fixes A5).

### Workstream C — One presentation vocabulary, methodology exposed
- **Single banded scale** derived from the versioned rubric — delete the frontend
  duplicate in `semantics.ts`; import/derive bands from the policy payload and stamp
  the rubric version on the memo (fixes B1).
- **Distinct words per axis** (dimension band vs panel verdict vs decision) so no word
  means two things (fixes B2).
- **One conviction scale** end-to-end (fixes B3); **one confidence treatment**, and
  stop truncating the digit on low confidence (fixes B5).
- **Expose the methodology** — render the evidence trail Layers 1–2 produce and the
  rubric version, instead of `sanitizeReasoning` deleting it (fixes B6/A6).

---

## 9. Recommended sequencing

1. **B1 band-mismatch fix** — highest severity, smallest change, pure config/UI.
2. **L3 (abstain, not 5.0)** — removes the two worst silent failures.
3. **Workstream B canonical-score decision** — unblocks B4 and the memo reconciliation.
4. **L1 (behaviorally-anchored criteria)** — the structural meaning fix.
5. **L2 (facts → rules)** — biggest engineering lift; also produces the content for B6.
6. **Workstream C presentation cleanup** + **L4/L5** calibration hardening.
7. **Workstream A** (stage cohorts, sector benchmarks) and **L6** (outcome
   calibration) — longer horizon; begin storing the evidence trail now.

**Endgame:** a score must (a) never secretly mean "unknown," (b) declare the stage
cohort it was judged against, (c) show whether its inputs were verified, (d) read on
one banded scale shared by backend and frontend, (e) reconcile arithmetically to the
dimensions shown, and (f) expose its evidence. The deterministic skeleton for all of
this already exists in `backend/services/scoring/` — most of it simply isn't wired
through to the memo, and the frontend contradicts the backend where it is.
