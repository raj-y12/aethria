---
target: Aethria frontend UI/UX
total_score: 23
p0_count: 0
p1_count: 5
timestamp: 2026-07-10T09-09-44Z
slug: app-front-end-src
---
# Aethria UI/UX audit

Method: dual-agent (A: /root/design_review · B: /root/detector_browser), supplemented by authenticated mock-data renders of Today, Flow, Portfolio, Fund, Settings, and mobile Flow.

## Design health score

| # | Heuristic | Score | Key issue |
|---|---|---:|---|
| 1 | Visibility of system status | 3 | Strong pipeline/loading states; some technical errors leak into UI. |
| 2 | Match system / real world | 2 | VC language is relevant, but private vocabulary obscures ordinary tasks. |
| 3 | User control and freedom | 3 | Escape/reset/filter controls exist; reversal and undo are unclear. |
| 4 | Consistency and standards | 3 | Cohesive system, but standard affordances are often reinvented. |
| 5 | Error prevention | 3 | Validation exists; Save/Publish/version semantics are risky. |
| 6 | Recognition rather than recall | 2 | Interactive readouts and branded destinations require learning. |
| 7 | Flexibility and efficiency | 2 | Useful shortcuts, but little bulk/comparison workflow. |
| 8 | Aesthetic and minimalist design | 2 | Restrained appearance, yet ceremonial metadata creates noise. |
| 9 | Error recovery | 2 | Recovery exists but can be generic or developer-facing. |
| 10 | Help and documentation | 1 | No visible task-focused contextual help. |
| **Total** | | **23/40** | **Acceptable — significant improvement required** |

## Technical audit score

| Dimension | Score | Key finding |
|---|---:|---|
| Accessibility | 2/4 | Systemic low-contrast 9–11px text, small targets, Settings visual/DOM order mismatch. |
| Performance | 2/4 | Orchestrated delays and layout-property animation create perceived latency. |
| Responsive | 3/4 | No sampled horizontal overflow; mobile structure works but loses decision context. |
| Theming | 3/4 | Strong tokens; opacity ladder institutionalizes failed contrast. |
| Anti-patterns | 2/4 | Distinctive but over-authored institutional theater; hero metric and repeated mono eyebrows. |
| **Total** | **12/20** | **Acceptable — systemic work, not polish** |

## Anti-pattern verdict

Aethria does not look like generic rounded-card SaaS. It has a more sophisticated failure: institutional theater. Paper texture, Playfair, Space Mono, Roman numerals, tiny uppercase labels, hairlines, and terms such as “ruling,” “instrument,” and “docket” are repeated until the product performs an old-world investment institution instead of disappearing into the task.

The source detector returned zero CLI findings. The runtime detector flagged the cream palette and two width transitions in LoginPage. The cream signal is contextual, not a mandatory defect; the layout-property animation is a valid minor issue. The detector missed the dominant problems because they are systemic product decisions, not isolated syntactic anti-patterns.

## Overall impression

The product is not ugly. It is coherent, memorable, and over-authored. Its strongest moment is Today: it calmly says what needs attention and when nothing does. Its weakest moment is Flow: a huge machine score visually outranks evidence, uncertainty, and the human decision. The biggest opportunity is to turn the existing identity into a quiet operational instrument rather than a ceremonial interface.

## What works

1. The Oxford/paper palette, square geometry, and restrained semantic colors create genuine identity.
2. Accessibility intent is visible in focus rings, reduced-motion handling, semantic controls, live regions, and keyboard queue navigation.
3. Today expresses the autonomous-agent value proposition clearly and respects the user's time.

## Priority issues

### [P1] Low-contrast microtype is a system-level accessibility failure

The code contains roughly 290 muted Oxford/white opacity uses at 55% or lower. Oxford at 40% on paper is about 2.55:1; 45% is about 2.94:1. Normal text requires 4.5:1 and reaches it only around 60%. Many affected labels are only 9–11px. Raise operational text to 12–14px, set a 60% opacity floor for meaningful text, and reserve lighter values for decorative marks only.

### [P1] Flow creates automation bias

The 0–100 conviction score grows to 148px and precedes decisive evidence. Replace the hero metric with a compact decision brief: recommendation, confidence range, decisive evidence, decisive uncertainty, what changed, and what would change the call. Keep the score secondary.

### [P1] Data placement is simultaneously cramped and wasteful

Flow overloads the right stage while Portfolio compresses almost all useful content into the top third of a wide canvas. Fund leaves a large dead region while presenting the mandate as a document. Use the wide screen for comparison, trends, evidence provenance, and active exceptions—not bigger scores or empty paper. Reduce the desktop spine and establish per-room density targets.

### [P1] Navigation speaks Aethria's dialect before the user's language

Flow, Fund, Dispatch, ruling, docket, conviction book, and Evolution are coherent brand language but weak predictors. Use explicit primary labels or persistent subtitles: Deals, Portfolio, Fund Strategy, Search. Let brand voice support navigation rather than replace it.

### [P1] Settings exposes three overlapping persistence models

Save changes, Publish fund thesis version, and Publish policy version have different runtime effects. Separate Draft and Live states, show a sticky change summary and affected pipeline stages, and consolidate publication into one explicit deployment transaction where possible. Fix the CSS `order-*` visual/DOM mismatch so keyboard and screen-reader order matches the page.

### [P2] Motion is engineered into latency

Flow delays auto-selection by about 460ms and row settling by about 900ms; recurring pages use staggered reveals. Render task content immediately and keep state transitions within roughly 150–200ms. Avoid animating width.

### [P2] Affordances are too subtle

Hairlines at 6–8%, clickable readouts, footer links, and several 36px controls disappear into the composition. Increase structural contrast, make interactive states visible at rest, and use 44px targets on touch surfaces.

### [P2] Error and help UX is incomplete

The app can expose `VITE_API_URL`, CORS, and `ALLOWED_ORIGINS` to users, while contextual help is almost absent. Replace developer diagnostics with user recovery actions and add concise in-context explanations for scoring, publication, and pipeline states.

## Persona red flags

**Alex, power user:** cannot bulk compare or dispose of deals, waits through deliberate motion, and must traverse long memos without an obvious compact evidence mode.

**Jordan, first-timer:** cannot predict Flow/Fund/Evolution contents, may not recognize readouts as controls, and must decode multiple score scales plus Save/Publish semantics without contextual help.

**Sam, accessibility-dependent:** benefits from semantic controls and keyboard support, but systemic low-contrast microtype, sub-44px controls, subtle color-only states, and Settings order mismatch remain major barriers.

## Minor observations

- Repeated uppercase mono labels have lost their hierarchical meaning.
- Home's desk band is useful but does not read strongly enough as the primary path into Flow.
- Mobile Flow is structurally sound but hides the actual decision context until a row is opened.
- The cream/paper aesthetic is increasingly common; Aethria's differentiation must come from superior decision mechanics, not texture alone.
- The global API error is written for developers, not operators.

## Questions to consider

- If the 0–100 score disappeared, would the decision become more trustworthy?
- Which three facts must a partner understand before ruling, and why are they not the first three objects in Flow?
- What is the single source of truth: saved configuration, published thesis, or published policy?
- Would an actual investment team prefer “quiet and immediate” over “cinematic and institutional”?

## Verdict

Do not discard the brand. Do not treat this as border-and-spacing polish. Preserve the Oxford/paper identity, square geometry, and editorial restraint, but redesign the typography floor, navigation language, Flow hierarchy, Settings state model, content density, and motion behavior. Approximately 60–70% of component styling can survive; the primary decision experience and information architecture need structural work.
