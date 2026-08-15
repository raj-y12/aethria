# Reviewer section audit — evidence

Evidence was gathered from the supplied Corgi screenshot, the current Calderwell screenshot harness, and the checked-out frontend/backend implementation. The implementation is authoritative where the older screenshot differs. All load-bearing graph findings were verified against source.

## P1 — Innovative

- The apparent panel is three LLM calls over the same evidence packet, dispatched together as Default, Skeptical, and Opportunist. It is not three independently informed reviewers. [`backend/reviewer/engine.py:342-349`](../../../backend/reviewer/engine.py)
- The variation comes primarily from prompt posture: Skeptical is told to assume the worst and default lower; Opportunist is told to grant benefit of doubt and score more generously. [`backend/reviewer/skeptical.py:11-19`](../../../backend/reviewer/skeptical.py) · [`backend/reviewer/opportunist.py:11-18`](../../../backend/reviewer/opportunist.py)
- The baseline is itself conservative and skeptical of missing data, so “Default” is not a neutral control. [`backend/reviewer/base.py:411-453`](../../../backend/reviewer/base.py)

## P2 — Useful

- The primary task is to learn what each reviewer knows, how their conclusions differ, and which evidence supports the difference. Each visible row is reduced to name, one derived scalar, verdict, and a lead sentence; risks, assumptions, per-dimension reasoning, claim IDs, source links, confidence, and prompt version do not enter the row model. [`app-front-end/src/components/InvestmentMemoContent.tsx:419-435`](../../../app-front-end/src/components/InvestmentMemoContent.tsx)
- Reviewer rows provide no drill-down or source-inspection action. The source comment says the full read lives in “Reviewer detail,” but no such production component or route exists. [`app-front-end/src/components/InvestmentMemoContent.tsx:427-429`](../../../app-front-end/src/components/InvestmentMemoContent.tsx) · [`app-front-end/src/components/scoring/AssessmentScorecard.tsx:295-305`](../../../app-front-end/src/components/scoring/AssessmentScorecard.tsx)
- The backend retains persona traces in the governed artifact, but frontend normalization discards `input_traces`. [`backend/evaluation_v2/governed_scoring.py:270-324`](../../../backend/evaluation_v2/governed_scoring.py) · [`app-front-end/src/lib/reviewScoring.ts:176-218`](../../../app-front-end/src/lib/reviewScoring.ts)
- `coverage` is built for every row but omitted by the normal structured-scorecard renderer; it appears only in the mutually exclusive fallback. [`app-front-end/src/components/InvestmentMemoContent.tsx:419-435`](../../../app-front-end/src/components/InvestmentMemoContent.tsx) · [`app-front-end/src/components/scoring/AssessmentScorecard.tsx:23-29`](../../../app-front-end/src/components/scoring/AssessmentScorecard.tsx)
- The whole Assessment sits inside a closed `Supporting analysis` disclosure below the canonical brief. [`app-front-end/src/components/InvestmentMemoContent.tsx:524-533`](../../../app-front-end/src/components/InvestmentMemoContent.tsx)

## P3 — Aesthetic

- The panel preserves a coherent paper/Oxford/burgundy editorial language, with five rendered color variants and a restrained type scale of 11, 12, 13.60, 14, and 23.79 px. [`app-front-end/src/components/InvestmentMemoContent.css:8-34`](../../../app-front-end/src/components/InvestmentMemoContent.css)
- The fallback places the reviewer list inside a flex consensus header. The list receives only 229 px at a 520 px viewport and 411 px at 1512 px, while `Split · MEDIUM` is stranded in a separate left column.
- The intended three-column reviewer layout is unreachable on the actual Flow surface: the room cap and 38/62 split keep the memo near 685–689 px, below the 760 px container breakpoint, even at a 2200 px viewport. [`app-front-end/src/components/InvestmentMemoContent.css:2326-2357`](../../../app-front-end/src/components/InvestmentMemoContent.css) · [`app-front-end/src/design-system/workspaceLayout.ts:1-5`](../../../app-front-end/src/design-system/workspaceLayout.ts)
- The faint 11 px consensus metadata renders at approximately 3.16:1 against paper, failing WCAG contrast for normal text. [`app-front-end/src/components/InvestmentMemoContent.css:1508-1525`](../../../app-front-end/src/components/InvestmentMemoContent.css)

## P4 — Understandable

- Reviewer row means average five available dimensions, including defensibility, and can silently be based on only one scored dimension. [`app-front-end/src/components/memo/memoContentHelpers.tsx:338-350`](../../../app-front-end/src/components/memo/memoContentHelpers.tsx)
- The scorecard explains that Overall is based on four driver dimensions and that defensibility is not averaged. The displayed headline may also use tenant policy weights. The visually comparable `/10` values therefore do not share a calculation contract. [`app-front-end/src/components/scoring/AssessmentScorecard.tsx:49-53`](../../../app-front-end/src/components/scoring/AssessmentScorecard.tsx) · [`backend/services/scoring/scoring_engine.py:365-387`](../../../backend/services/scoring/scoring_engine.py)
- `buildMemoDecisionBrief` hardcodes reviewer agreement to `unknown`, while the legacy Assessment separately emits `Split` or `Aligned`. One memo can therefore show “Reviewer state — Unknown” above “Reviewers split.” [`app-front-end/src/lib/memoDecisionBrief.ts:281-305`](../../../app-front-end/src/lib/memoDecisionBrief.ts) · [`app-front-end/src/components/InvestmentMemoContent.tsx:437-454`](../../../app-front-end/src/components/InvestmentMemoContent.tsx)
- Backend disagreement detects different verdict strings; frontend disagreement additionally detects a two-point gap between derived row means. Neither exposes the per-dimension variance already computed by the backend, so offsetting disagreements can be labelled aligned. [`backend/reviewer/engine.py:351-379`](../../../backend/reviewer/engine.py) · [`app-front-end/src/components/InvestmentMemoContent.tsx:437-445`](../../../app-front-end/src/components/InvestmentMemoContent.tsx)
- “Evidence” names three different constructs: rubric criteria without missing-data fallback, extraction confidence/completeness, and canonical claim support. The interface does not distinguish them.

## P5 — Unobtrusive

- The paper-like typography, low-chrome rules, and absence of animation inside the reviewer panel keep the visual treatment quiet. [`app-front-end/src/components/InvestmentMemoContent.css:1485-1728`](../../../app-front-end/src/components/InvestmentMemoContent.css)
- The panel itself has zero badges, notifications, dialogs, alerts, or running animations in the rendered success state.
- The consensus label, three repeated scalar rows, and repeated summary prose consume space without providing inspectable evidence or dimension-level disagreement.

## P6 — Honest

- The UI calls three same-model, same-packet prompt lenses a “Reviewer panel” without disclosing their shared evidence or deliberately manufactured postures. [`backend/reviewer/engine.py:342-349`](../../../backend/reviewer/engine.py) · [`app-front-end/src/components/scoring/AssessmentScorecard.tsx:276-303`](../../../app-front-end/src/components/scoring/AssessmentScorecard.tsx)
- A 1–1–1 verdict tie is resolved by `Counter.most_common(1)` in execution order, so “consensus” becomes Default rather than a tie. [`backend/reviewer/engine.py:351-359`](../../../backend/reviewer/engine.py)
- `N% evidenced` means the percentage of rubric criteria without `missing_data_applied`; it does not mean verified claims or source coverage. [`backend/reviewer/engine.py:50-71`](../../../backend/reviewer/engine.py)
- Missing reviewer confidence is silently persisted as `medium` rather than unknown. [`backend/reviewer/schema.py:156-164`](../../../backend/reviewer/schema.py)
- The active rubric describes numeric output as “risk-adjusted investment quality,” calls 8+ “fundable,” and says the verdict must be explainable by numbers alone, overstating the certainty available from model-extracted evidence. [`resources/config/evaluation_rubric/v1.json:3-18`](../../../resources/config/evaluation_rubric/v1.json) · [`resources/config/evaluation_rubric/v1.json:70-88`](../../../resources/config/evaluation_rubric/v1.json)
- The visible band labels and the disclosed band method use different boundaries, so scores 3, 5, or 7 can receive a label that contradicts “How this was scored.” [`backend/services/scoring/presentation_layer.py:32-38`](../../../backend/services/scoring/presentation_layer.py) · [`app-front-end/src/components/scoring/AssessmentScorecard.tsx:49-52`](../../../app-front-end/src/components/scoring/AssessmentScorecard.tsx)
- The top-level narrative comes from Default while numeric dimensions are blended across successful personas; that split authorship is not disclosed. [`backend/reviewer/engine.py:1149-1169`](../../../backend/reviewer/engine.py)

## P7 — Long-lasting

- The editorial visual system is restrained and likely to age better than a dashboard full of cards or gradients. [`app-front-end/src/components/InvestmentMemoContent.css:8-34`](../../../app-front-end/src/components/InvestmentMemoContent.css)
- The product model—anthropomorphized “Default / Skeptical / Opportunist” AI agents presented as a council—is a current AI-product convention rather than a durable explanation of method.
- Core semantics are duplicated across a legacy Assessment and canonical Decision brief, making the surface likely to drift as either data path evolves. [`app-front-end/src/components/InvestmentMemoContent.tsx:524-533`](../../../app-front-end/src/components/InvestmentMemoContent.tsx) · [`app-front-end/src/lib/memoDecisionBrief.ts:238-306`](../../../app-front-end/src/lib/memoDecisionBrief.ts)

## P8 — Thorough down to the last detail

- Reviewer-specific empty, loading, and error states are missing. When scorecard, panel, and readouts are absent, Assessment returns `null`. [`app-front-end/src/components/InvestmentMemoContent.tsx:683-699`](../../../app-front-end/src/components/InvestmentMemoContent.tsx)
- The rendered fallback has no focusable reviewer control. The outer native `Supporting analysis` summary has no authored focus-visible treatment; computed keyboard focus had no outline or shadow. [`app-front-end/src/components/InvestmentMemoContent.css:2236-2246`](../../../app-front-end/src/components/InvestmentMemoContent.css)
- Structured dimension buttons expose `aria-expanded` without an `aria-controls` relationship; disabled rows change only their cursor. [`app-front-end/src/components/scoring/AssessmentScorecard.tsx:147-188`](../../../app-front-end/src/components/scoring/AssessmentScorecard.tsx)
- There is no skip link. Reviewer metadata at `--memo-ink-faint` fails normal-text contrast.
- Assessment tests assert source/CSS structure, not disagreement semantics, score comparability, coverage rendering, keyboard behavior, or tie handling. [`app-front-end/src/components/memo/__tests__/InvestmentMemoSections.test.ts:26-105`](../../../app-front-end/src/components/memo/__tests__/InvestmentMemoSections.test.ts)

## P9 — Environmentally friendly

- The production demo initial JS bundle is 736,482 raw bytes (224,157 transferred bytes in local Chromium), which falls in the audit rubric's 500 KB–2 MB band.
- Reviewer-ready navigation in the local unthrottled harness made six requests, transferred 299,795 bytes, and reached the visible reviewer state in 2,178.7 ms including scripted action-stability waits.
- Reviewer evaluation itself fans the same evidence packet out to three LLM calls; token usage is summed across all three. [`backend/reviewer/engine.py:342-349`](../../../backend/reviewer/engine.py) · [`backend/reviewer/engine.py:1186-1195`](../../../backend/reviewer/engine.py)
- The interface discards much of the resulting persona-specific provenance, so the extra inference cost does not buy equivalent user-visible inspectability.

## P10 — As little design as possible

- The reviewer panel is implemented twice: once in `AssessmentScorecard` and once as an inline fallback, with different content and evidence behavior. [`app-front-end/src/components/scoring/AssessmentScorecard.tsx:276-307`](../../../app-front-end/src/components/scoring/AssessmentScorecard.tsx) · [`app-front-end/src/components/InvestmentMemoContent.tsx:715-741`](../../../app-front-end/src/components/InvestmentMemoContent.tsx)
- Three scalar persona rows, an aggregate consensus label, a separate governed score, and a canonical reviewer state repeat the idea of reviewer judgment without agreeing on one contract.
- Three persisted resolution fields—`score_variance`, `resolution_notes`, and `disagreement_summary`—have no frontend consumer beyond type declarations. [`app-front-end/src/types/startup.ts:383-385`](../../../app-front-end/src/types/startup.ts) · [`app-front-end/src/types/startup.ts:439-445`](../../../app-front-end/src/types/startup.ts)
- The quiet visual treatment is restrained, but the underlying information architecture is not: complexity is hidden rather than removed.

## Known gaps

- No authenticated production or persisted Corgi reviewer payload was available; the supplied Corgi screenshot and current Calderwell fixture were used.
- The current fixture omits structured scoring and reviewer evidence coverage, so structured controls and focus order were source-inspected.
- Runtime tenant-specific prompt promotion and fund scoring weights were unavailable.
- No screen-reader session or automated axe scan was run; keyboard and computed-style checks used Chromium.
