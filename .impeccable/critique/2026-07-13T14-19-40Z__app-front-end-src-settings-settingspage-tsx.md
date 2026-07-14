---
target: new Settings page
total_score: 20
p0_count: 0
p1_count: 4
timestamp: 2026-07-13T14-19-40Z
slug: app-front-end-src-settings-settingspage-tsx
---
Method: dual-agent (A: settings_design_assessment · B: settings_detector_assessment)

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---:|---|
| 1 | Visibility of system status | 2 | Deploy feedback can appear offscreen; pending state is hidden on small screens. |
| 2 | Match system / real world | 3 | VC language is good, but save-model labels are misleading. |
| 3 | User control and freedom | 2 | No undo, dirty-navigation guard, or safe reset flow. |
| 4 | Consistency and standards | 2 | Rail/page order diverges; Administration is not actually all live. |
| 5 | Error prevention | 2 | Validation exists, but Reset is unconfirmed and errors are spatially detached. |
| 6 | Recognition rather than recall | 2 | Desktop rail helps; mobile loses the section map. |
| 7 | Flexibility and efficiency | 2 | Scroll jumps and keyboard sliders help, but precise numeric threshold editing was removed. |
| 8 | Aesthetic and minimalist design | 2 | Calm and restrained, but repetitive labels and rules create a long visual rhythm. |
| 9 | Error recovery | 2 | Runtime rollback is good; deploy recovery and reset recovery are weak. |
| 10 | Help and documentation | 1 | Consequential threshold and confidence concepts remain under-explained. |
| **Total** |  | **20/40** | **Acceptable; significant trust and clarity work remains.** |

## Anti-Patterns Verdict

The page avoids generic rounded-card SaaS and the deterministic detector returned zero banned-pattern findings. It still falls into a recognizable prestige-finance editorial lane: paper, Oxford ink, display serif headings, tiny uppercase mono labels, and repeated hairline rules. It feels authored, but not yet uniquely Aethria.

No reliable visual overlay or screenshot was available. The Vite route returned HTTP 200, but browser discovery found no controllable browser. The screenshot harness also lacks the Clerk context now required by `AppFrame`.

## Overall Impression

This is directionally stronger than a conventional settings dashboard. The focused takeover, persistent deploy action, desktop scroll-spy, and single reading column create a coherent configuration room. The biggest weakness is trust: the page visually explains one save model while the code implements another.

## What's Working

1. The focused mode creates a deliberate workspace with a clear exit, draft state, and persistent deployment action.
2. Runtime switches are behaviorally strong: optimistic updates, per-control saving state, rollback, concurrency preservation, and correct switch semantics.
3. Accessibility foundations are better than average: keyboard-operable sliders, `aria-checked`, focus rings, and reduced-motion handling.

## Priority Issues

### P1 — The information architecture misstates the save model

The rail calls Administration `Live`, and the page calls it `Saves immediately`, but memo and risk settings still enter the deployable pending-change set. Organize by actual persistence: **Deployable fund policy** for thesis, thresholds, weights, sensitivity, memo output, and ruling workflow; **Live runtime** for pipeline switches, budget enablement, and system state.

### P1 — Reset is unsafe and can make defaults appear live

`handleReset` replaces the draft and also overwrites `savedSnapshot`, allowing pending changes to disappear without deployment. Rename the action **Restore defaults**, confirm it, preserve the real live snapshot, keep restored defaults pending, and offer Undo.

### P1 — Mobile loses the only section navigation

The rail disappears below `lg`, while the mobile replacement contains only pipeline controls. Add a sticky mobile section picker with grouped Configuration and Runtime destinations plus active-section feedback.

### P1 — Deployment feedback is detached from the fixed action

Deploy can be triggered from anywhere, but outcome messages render near the top of the scrolling document. Show outcome beside the fixed deploy control; on validation failure, scroll/focus the first invalid section and mark its rail destination.

### P2 — Functional text is too small and faint

Several functional labels are 9–10px at 42–55% Oxford. Raise functional text to at least 12px with verified 4.5:1 contrast. Keep tiny mono labels only for nonessential metadata.

## Persona Red Flags

- **Alex, power user:** weight edits silently rebalance other dimensions; Reset is fast but unsafe; precise numeric threshold boundary fields were removed.
- **Sam, low-vision/keyboard user:** slider semantics are strong, but low-contrast 9–10px labels are fragile and validation is not connected to fields with `aria-invalid` or focus movement.
- **Casey, distracted mobile user:** no section map, pending count hidden, no unsaved-exit guard, and pipeline controls consume the first screen before the requested setting.

## Minor Observations

- Rail order and page order disagree around Weights and Sensitivity.
- Version is visible as a section but absent from the scroll-spy model.
- The unavailable state lacks Retry and a way back.
- Extreme threshold bands may collide despite having non-color labels.
- The screenshot harness is not currently a functioning visual-regression path.

## Questions to Consider

- If Administration contains deployable policy, what does Administration mean to the user?
- Should Reset discard a draft, restore defaults as a draft, or roll production back? Those are different actions.
- Would three jobs—define the fund, tune decisions, operate the pipeline—be clearer than one continuous document?
- What should make this specifically Aethria: vocabulary, downstream-impact previews, or decision simulation?
