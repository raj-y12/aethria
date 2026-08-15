# Reviewer section audit — `/make-plan` handoff

```text
/make-plan Redesign Aethria's reviewer system and investment-memo reviewer section. Current design failed audit at 7/30 with critical gaps in principles #2 Useful, #4 Understandable, #6 Honest, #8 Thorough, #9 Environmentally friendly, and #10 As little design as possible.

Verdict paragraph (quoted from 03-verdict.md):
> REDESIGN — The reviewer section is a polished confidence machine that obscures rather than explains its method: it cannot show what each reviewer knows, makes incompatible numbers look comparable, and presents deliberately biased same-evidence AI lenses as an honest consensus panel.

Why redesign and not refine: Load-bearing usefulness, understandability, and honesty each scored 0; changing styling or copy around the existing rows would preserve the false reviewer metaphor, incompatible scoring contracts, and absent evidence path.

Primary user: a venture investor or IC operator reviewing one startup.
Primary task: understand what each reviewer or lens actually knows, how conclusions differ, which claims and sources support those conclusions, and whether disagreement warrants diligence or a human ruling.
Constraints: preserve Aethria's paper/Oxford/burgundy visual language and React/FastAPI stack; preserve explicit tenancy, versioned policy, fail-closed behavior, evidence provenance, canonical human authority, and CostController gates; thresholds must remain versioned data; frontend backend calls remain in src/api; behavior changes require tests and decision-policy changes require partner-rules contract coverage.

Preserve from current design:
- The paper/Oxford/burgundy editorial token system and quiet memo typography in `app-front-end/src/components/InvestmentMemoContent.css:8-34`.
- The deterministic structured-scoring and evidence-provenance direction in `backend/evaluation_v2/governed_scoring.py:270-379` and `app-front-end/src/components/institutional/ClaimEvidenceLedger.tsx:6-108`.
- Canonical human rulings remain authoritative; AI output is advisory and must never masquerade as the final decision.

Discard:
- The three anonymous scalar rows masquerading as an independent reviewer panel. Evidence: `backend/reviewer/engine.py:342-349`, `app-front-end/src/components/scoring/AssessmentScorecard.tsx:276-305`. Caused failure on principles #2, #4, and #6.
- The disconnected legacy Assessment and canonical “Reviewer state — Unknown” truth systems. Evidence: `app-front-end/src/lib/memoDecisionBrief.ts:281-305`, `app-front-end/src/components/InvestmentMemoContent.tsx:437-454`. Caused failure on principles #4 and #10.
- The duplicated fallback and structured reviewer renderers with different content and evidence behavior. Evidence: `app-front-end/src/components/InvestmentMemoContent.tsx:715-741`, `app-front-end/src/components/scoring/AssessmentScorecard.tsx:276-307`. Caused failure on principles #8 and #10.

Top 3–5 moves from the audit (verbatim):
1. Principle #6 — Honest: Rename the three “reviewers” as disclosed AI lenses, state that they share one evidence packet and model family, name each prompt posture, and reserve “reviewer state” for actual human or independently sourced review. Evidence: `backend/reviewer/engine.py:342-349`, `backend/reviewer/skeptical.py:11-19`, `backend/reviewer/opportunist.py:11-18`.
2. Principle #2 — Useful: Replace scalar persona rows with a decision-critical disagreement matrix keyed by dimension and claim, exposing each lens's score, missingness, rationale, and linked provenance with a direct drill-down. Evidence: `app-front-end/src/components/InvestmentMemoContent.tsx:419-435`, `app-front-end/src/components/scoring/AssessmentScorecard.tsx:295-305`.
3. Principle #4 — Understandable: Establish one score and agreement contract: use the same scored dimensions, denominator, policy weights, tie state, and missing-data rules everywhere, then feed that canonical result into both the Decision brief and Assessment. Evidence: `app-front-end/src/components/memo/memoContentHelpers.tsx:338-350`, `app-front-end/src/lib/memoDecisionBrief.ts:281-305`, `backend/reviewer/engine.py:351-379`.
4. Principle #8 — Thorough: Design and test reviewer-specific empty, loading, error, partial, success, focus, and disabled states; add accessible disclosure relationships, visible focus, passing metadata contrast, and behavioral regression tests for ties, disagreement, coverage, and score comparability. Evidence: `app-front-end/src/components/InvestmentMemoContent.tsx:683-699`, `app-front-end/src/components/scoring/AssessmentScorecard.tsx:147-188`, `app-front-end/src/components/memo/__tests__/InvestmentMemoSections.test.ts:26-105`.
5. Principles #9 and #10 — Efficient and minimal: Eliminate the duplicate reviewer renderers and challenge the need for three LLM calls; prefer one provenance-preserving analysis with deterministic risk/upside comparisons where rules suffice, or explicitly justify and surface the incremental information from each retained call. Evidence: `app-front-end/src/components/InvestmentMemoContent.tsx:715-741`, `app-front-end/src/components/scoring/AssessmentScorecard.tsx:276-307`, `backend/reviewer/engine.py:342-349`.

Redesign principles in priority order:
1. Principle #6 — Honest — every label must disclose whether it describes a human reviewer, an AI lens, a rule-derived result, model-derived analysis, or verified evidence; ties and missingness remain explicit.
2. Principle #2 — Useful — the primary view must let an IC operator identify the exact decision-critical disagreement and inspect its supporting/contradicting claims without hunting through another screen.
3. Principle #4 — Understandable — one canonical score/agreement contract must produce every visible score, verdict, split state, denominator, and explanatory label.

Deliverables for the plan:
- New information architecture, not derived from the old three-row panel.
- New primary flow, low-fi and labeled, compared side-by-side to the current reviewer panel.
- A backend-to-frontend contract map for persona/lens identity, score dimensions and weights, ties, missingness, agreement, provenance, and human authority.
- A migration strategy from legacy review snapshots to the canonical decision/evidence path without renaming or removing existing public fields silently.
- A test-first sequence covering backend tie/disagreement/scoring behavior and frontend score comparability, evidence drill-down, accessibility, and all states.
- States checklist: empty, loading, error, partial, success, focus, and disabled.
- Cost analysis comparing one structured analysis plus deterministic lenses against the current three-call approach, with CostController enforcement.
- Cutover criteria: the old panel retires only when the canonical path renders a single truthful reviewer state, every displayed score shares the documented contract, every disagreement is traceable to a dimension/claim, and the full verification gate passes.

Out of scope: the general startup Snapshot, portfolio workflow, marketing site, and memo styling unrelated to reviewer interpretation.

Anti-patterns to guard against:
- Porting the old three-row structure under new styling.
- Renaming AI personas without fixing score, tie, evidence, and authority contracts.
- Treating model agreement as independent corroboration.
- Adding another summary layer or fallback renderer instead of deleting duplication.
- Hardcoding thresholds or score weights in Python/TypeScript.
- Keeping both legacy and canonical reviewer truth systems behind a flag indefinitely.
- Redesigning to follow an AI-agent trend rather than the principles above.
- Treating the Preserve list as optional.
```
