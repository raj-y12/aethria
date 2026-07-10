# Investment Memo Redesign — Implementation Plan

**Date:** 2026-07-10
**Scope:** `InvestmentMemoContent` (+ modal wrapper, FlowPage embed), sector tags, unified Add context / IC Pack (PDF) actions, PDF alignment.
**Design language:** paper editorial (paper `#F4F1EA`, oxford `#001433`, burgundy escalation-only, heritage gold decorative). No new palette, no new libraries.

---

## Coordination with the 2026-07-10 product-UI recalibration plan

That plan's **Task 4** (DecisionBrief) and **Task 5** (StickyRulingControls) touch the same files. This plan **owns the memo surface**:

- If Task 4 lands first, the redesigned cover consumes `buildDecisionBrief()` instead of the ad-hoc derivations in `InvestmentMemoContent`.
- Task 5's `StickyRulingControls` is absorbed here as **Task 4 (Ruling)** — do it once, in whichever plan executes first.
- Everything else here is disjoint from that plan.

---

## Design direction

**Concept: the dossier masthead.** The memo reads as a printed IC pack. Today its identity is split: on desktop the actions (Add context, IC pack) are injected into `DecisionStage`'s `action` slot by `FlowPage`; on mobile they render inside `memoHeaderActions`; sector/category is a flat uppercase text line. The redesign gives the document one owner for its header:

```
┌──────────────────────────────────────────────────────────────┐
│ INVESTMENT MEMO                     [Add context] [IC pack ↓]│  ← masthead band
│                                                              │
│ Acme Robotics                                                │  ← display-scale name
│ Berlin, DE                                                   │
│ [ ROBOTICS ] [ INDUSTRIAL AUTOMATION ] [ SEED ] [ LOOKUP ]   │  ← sector tags
├──────────────────────────────────────────────────────────────┤
│ Recommendation · standfirst · conviction · focal question    │  ← verdict block
│ Snapshot (vitals grid)                                       │
│ Why Now  /  What Limits Conviction  /  Assessment  /  Risks  │
├──────────────────────────────────────────────────────────────┤
│ YOUR RULING  [Invest] [Monitor] [Pass]  notes…    (sticky)   │
├──────────────────────────────────────────────────────────────┤
│ Appendix: rationale · ledger · context · sources · run log   │
└──────────────────────────────────────────────────────────────┘
```

- **Signature element:** the masthead — classification-stamp sector tags under the company name, with the two document actions always in the same place on every viewport.
- **Everything below stays quiet:** single editorial column, existing type scale (`type-label`, mono numbers), disclosure appendix. Boldness is spent on the masthead only.
- **Motion:** keep the opacity umbrella on `memoBody`; drop the per-section staggered reveal (also required by recalibration Task 5). Reduced motion already respected via `transitionOrReduced`.

**Explicit non-goals (v2 candidates, do not build now):**
- Clickable sector tags that filter the queue.
- Masthead condensing/sticking on scroll.
- Section table-of-contents rail.

---

## Task 1: Sector tags

**Files:**
- Modify: `src/components/memo/memoContentHelpers.tsx` (add `buildMemoTags`)
- Create: `src/components/memo/MemoTags.tsx`
- Create: `src/components/memo/__tests__/memoTags.test.tsx`

**Steps:**

1. **Model.** `buildMemoTags(startup): MemoTag[]` where `MemoTag = { label: string; kind: 'sector' | 'category' | 'stage' | 'origin' }`.
   Order: sector → category → funding stage → `LOOKUP` (only when `isLookupStartup`). Trim, uppercase, drop empties and duplicates. Reuses the fields already read by `formatSectorAndCategory` (which becomes PDF-only after Task 5).
2. **Component.** `MemoTags` renders a `<ul>` of quiet chips: mono 11px, `tracking-[0.08em]`, `border-oxford/12`, paper background, oxford/70 ink. `origin` kind gets the existing lookup-badge treatment (see `verdictBadgeTokens.ts` for the compact-chip precedent — reuse its metrics, not new ones). No color-coding by sector; the word carries the meaning (house rule).
3. **Test.** Fixture startup → tag order, dedupe, LOOKUP presence/absence, empty-sector renders nothing.

**Verify:** `cd app-front-end && npm test -- --run src/components/memo/__tests__/memoTags.test.tsx`

```bash
git commit -m "feat(front): add sector tags to memo model"
```

## Task 2: Masthead — one owner for title + actions

**Files:**
- Create: `src/components/memo/MemoMasthead.tsx`
- Create: `src/components/memo/__tests__/MemoMasthead.test.tsx`
- Modify: `src/components/InvestmentMemoContent.tsx`
- Modify: `src/components/InvestmentMemo.tsx`
- Modify: `src/pages/FlowPage.tsx`
- Modify: `src/components/DecisionStage.tsx` (drop the `action` slot once unused)

**Steps:**

1. **Component.** Props: `startup`, `tags`, `onAddContext?`, `onDownloadPDF`, `onClose?`, `readOnly?`. Renders kicker (`INVESTMENT MEMO`), action cluster (Add context = primary oxford button; `IC pack (PDF)` = quiet `memoAction`; Close only when `onClose` given), company name (`memoCoverCompany`, keeps `id="memo-title"`), location line, `MemoTags` row. `readOnly` hides Add context and ruling affordances, keeps PDF.
2. **Wire into `InvestmentMemoContent`.** Masthead renders in **both** embedded and modal modes, above `coverOverride`/cover. Delete the `memoHeaderActions` block and the cover's title row (`memoCoverTitleRow`, `headerMeta` line) — the masthead replaces them. `handleDownloadPDF` and the `downloadPDF` imperative handle stay as-is.
3. **FlowPage.** Stop injecting the `action` span into `DecisionStage`; pass `onAddContext={() => openRerun(memoStartup)}` to the embedded `InvestmentMemoContent` instead. `DecisionStage` keeps only decision content.
4. **Modal (`InvestmentMemo.tsx`).** No prop changes needed — `onAddContext`/`onClose` already flow through; verify Escape/focus-trap still work with the new header order.
5. **Tests.** Masthead: actions render per props; `readOnly` hides Add context; `aria-label`s preserved (`Add context and re-review <name>`, `Download IC pack as PDF`).

**Verify:** `cd app-front-end && npm test -- --run src/components/memo/__tests__/MemoMasthead.test.tsx && npx tsc --noEmit`

```bash
git commit -m "feat(front): unify memo masthead with actions and tags"
```

## Task 3: Document body restructure

**Files:**
- Modify: `src/components/InvestmentMemoContent.tsx`
- Modify: `src/components/InvestmentMemoContent.css`

**Steps:**

1. **Section order (unchanged content, tightened frame):** verdict block → Snapshot → Why Now → What Limits Conviction → Assessment → Risks → Ruling → Appendix. The verdict block keeps recommendation word, standfirst, conviction line, reviewers-split flag, focal question ("What decides it"), Blocker/Next move brief.
2. **Snapshot becomes a two-column definition grid** on ≥sm (label column fixed, value column fluid; single column on mobile) instead of the current wrap-flex + stacked lines. Vitals and snapshot rows merge into one grid — one visual system instead of two.
3. **Appendix.** Wrap the existing `memoDiscGroup` disclosures under a labeled rule: `APPENDIX` eyebrow. Disclosure components (`MemoDisclosureSection`) are unchanged.
4. **Motion.** Remove `memoSectionReveal` staggering from CSS; keep the single opacity fade.
5. **CSS.** Add masthead/tag/grid classes; delete classes orphaned by Tasks 2–3 (`memoHeaderActions`, `memoCoverTitleRow`, old vitals stack). The file is 4,381 lines — remove only what these tasks orphan, no general cleanup.

**Verify:** existing memo-related tests still pass; then live check (Task 6).

```bash
git commit -m "feat(front): restructure memo document body"
```

## Task 4: Sticky ruling controls

**Files:** (identical to recalibration Task 5 — skip if that shipped)
- Create: `src/components/memo/StickyRulingControls.tsx` (extract from `MemoRulingSection`)
- Modify: `src/components/InvestmentMemoContent.tsx`, `.css`

**Steps:**

1. Move ruling behavior behind `StickyRulingControls`; retain `shouldGateRisk`, `buildOptimisticResolution`, `resolveEscalation`, optimistic-rollback flow exactly as-is.
2. Desktop: `position: sticky; bottom: 0` within the memo scroll region, paper-bright surface, top hairline. Mobile: safe-area bottom padding. Hidden when `readOnly` or already decided (current logic).

**Verify:** `npm test -- --run src/components/memo/__tests__/StickyRulingControls.test.tsx`

```bash
git commit -m "feat(front): sticky memo ruling controls"
```

## Task 5: IC pack (PDF) alignment

**Files:**
- Modify: `src/lib/memoIcPack.ts`

**Steps:**

1. **Header:** add the tag line (same `buildMemoTags` labels joined with ` · `) under the company name; keep `formatSectorAndCategory` usage removed in favor of tags so screen and PDF say the same thing.
2. **Section order mirrors the new document:** verdict → snapshot/vitals → why now → limits → assessment scores (`drawScoreBars`) → risks → appendix (sources, run log). Reuse existing `drawHeading`/`drawBodyLine`/`ensureSpace` primitives; no new PDF machinery.
3. Filename (`icPackSafeBaseName`) and jspdf dependency unchanged.

**Verify:** download a PDF from the preview for one decided and one in-pipeline startup; confirm section order and tag line.

```bash
git commit -m "feat(front): align IC pack PDF with redesigned memo"
```

## Task 6: End-to-end verification

1. `cd app-front-end && npm test -- --run && npx tsc --noEmit`
2. Preview (`npm run dev`) — check both entry points:
   - Desktop workspace (embedded, DecisionStage cover): masthead actions present, no duplicate buttons, sticky ruling.
   - Mobile modal (resize to 375px): masthead wraps, Close works, Escape works, focus trap intact.
   - Read-only share view: Add context and ruling hidden, PDF available.
   - `prefers-reduced-motion`: no transforms.
3. States: pipeline `generating` (pending pulse), `failed` (gate strip), decided (recorded ruling), lookup startup (LOOKUP tag).
4. Screenshot desktop + mobile for the record.

```bash
git commit -m "feat(front): memo redesign polish and verification"
```

---

## Open decisions (product, not blocking)

1. **Clickable tags** — should a sector tag filter the deal-flow queue to that sector? Deferred to v2; the tag component takes an optional `onSelect` later without rework.
2. **Masthead on scroll** — condense to a slim sticky strip on long memos? Deferred; measure whether users actually lose the actions first.
