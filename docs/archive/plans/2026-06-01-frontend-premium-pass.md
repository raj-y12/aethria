# Frontend Premium Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Aethria cockpit feel premium by enforcing a consistent visual hierarchy ("one volume per element") and removing competing text — without changing fonts or splitting into pages.

**Architecture:** Pure frontend. Each of three surfaces (deal queue, left rail, memo) gets three tiers — focal / support / recede — via size, weight, opacity, spacing, and removing/relocating text. No logic, data, or handler changes; reorder and restyle only.

**Tech Stack:** React + TypeScript, Tailwind (custom `oxford`/`paper`/`phi`/`type-*` tokens), Framer Motion, Vite.

**Verification model (every task):** `npx tsc --noEmit` clean → `npm run build` green → screenshot the running surface for visual review → commit. Working dir for FE commands: `app-front-end/`.

---

### Task 0: Rail telemetry compaction — DONE

Already restored on this branch (compact status strip in `MainLayout.tsx`): escalations hero + status dot on one row, `N total · N rec · N ruled` on one mono line. No further action.

---

### Task 1: Deal queue row hierarchy

**Files:**
- Read first: `src/components/WorkGrid.tsx`, `src/components/queue/queueRowShared.ts`, and any `src/components/queue/*Row*.tsx` to locate the row + filter markup.
- Modify: the queue row component and the filter-bar markup found above.

- [ ] **Step 1: Locate the row + filter markup.** Grep `src/components/WorkGrid.tsx` and `src/components/queue/` for the deal-row JSX (company name, sector/age meta, one-line description, verdict/conviction) and the filter bar (`ALL / PRIORITY / NEW / STALE / ESCALATED`).

- [ ] **Step 2: Apply row hierarchy.** In the row component:
  - Name = focal (keep current family; ensure it's the largest/heaviest element in the row).
  - Verdict + conviction → right-anchored; render conviction as a single bold integer (`55`) with the `%` dropped or faint.
  - Sector + age → one faint mono micro-line (`text-oxford/40`, `text-[10.5px]`, uppercase, tracking `0.1em`); stale segment in `text-escalation`.
  - Remove the one-line description from the default row entirely.
  - Increase vertical padding for breathing room; keep the priority accent rule.

- [ ] **Step 3: Description on selected row only.** When a row is the selected/active one (the existing selection state used to drive the memo), render the one-line description beneath the micro-line at `text-oxford/55`, `text-[13px]`. Default (unselected) rows show no description.

- [ ] **Step 4: Quiet the filter bar.** Active filter at `text-oxford` semibold; inactive filters at `text-oxford/40`; reduce size to `text-[11px]` mono uppercase. Keep the `+` (dispatch trigger) and sort affordances but de-emphasize.

- [ ] **Step 5: Verify.** `cd app-front-end && npx tsc --noEmit` (expect exit 0) → `npm run build` (expect success).

- [ ] **Step 6: Screenshot + visual review.** Run the app, screenshot the queue, confirm: eye lands on name → verdict; meta recedes; no description noise; filter bar quiet.

- [ ] **Step 7: Commit.** `git add -A && git commit -m "Queue: enforce three-tier row hierarchy; description on selected row only"`

---

### Task 2: Rail — mandate pill + ⌘K dispatch

**Files:**
- Modify: `src/components/MainLayout.tsx` (mandate block ~lines with `railEditorial.label` "Mandate"; dispatch block "Dispatch" + `<AgentDispatch>`).
- Modify: `src/components/AgentDispatch.tsx` (add command-bar invocation).

- [ ] **Step 1: Mandate → status pill.** Replace the titled multi-line Mandate block with a single inline pill: thesis name when active, else "No active thesis" — small, `border border-oxford/[0.12]`, clickable to open Fund Policy/Settings. Remove the "MANDATE" section header.

- [ ] **Step 2: ⌘K command bar.** In `AgentDispatch.tsx`, add a global `keydown` listener (⌘K / Ctrl+K) that opens the lookup as a centered command bar (modal overlay, paper bg, single input, Enter = run). Reuse the existing lookup submit handler — no new API.

- [ ] **Step 3: Wire the `+` trigger.** The queue header `+` (and a rail affordance if desired) opens the same command bar. Remove the always-on Dispatch input block from the rail.

- [ ] **Step 4: Verify.** `npx tsc --noEmit` (exit 0) → `npm run build` (success).

- [ ] **Step 5: Screenshot + review.** Confirm ⌘K opens the bar, Enter runs a lookup, result appears in queue; rail no longer shows the input; mandate is a single pill.

- [ ] **Step 6: Commit.** `git add -A && git commit -m "Rail: mandate pill + ⌘K command-bar dispatch; remove always-on input"`

---

### Task 3: Memo hierarchy + investor-question IA

**Files:**
- Modify: `src/components/InvestmentMemoContent.tsx`, `src/components/InvestmentMemoContent.css`.
- Reference (prior, off-branch) IA: Decision → Why Now → What Must Be True → bear case → analytics → Next Actions → Ruling, with **evidence/sources at the bottom**.

- [ ] **Step 1: Section-heading hierarchy.** Ensure `.memoDocSectionHead` clearly outranks body (size/weight/spacing) and that the recommendation + conviction on the cover is the unmistakable focal point. Reduce duplicated copy (e.g. one-liner repeated in cover + snapshot).

- [ ] **Step 2: Reorder body to investor-question flow.** Snapshot → Why Now → What Must Be True → What Limits Conviction → Risks → Scoring → Reviewer Consensus → Next Actions → Your Ruling → Evidence/sources (bottom) → collapsed run-log/rationale. (Port the prior structure; sections are guarded by their own conditions so moves are behavior-preserving.)

- [ ] **Step 3: Recede supporting detail.** Scoring tables, reviewer detail, run log, and source citations drop to lower visual weight / collapsed disclosures so evidence-of-decision leads over generated prose.

- [ ] **Step 4: Verify.** `npx tsc --noEmit` (exit 0) → `npm run build` (success).

- [ ] **Step 5: Screenshot + review.** Open a deal with a partner decision; confirm the read flows top-to-bottom as an IC memo and the recommendation is the focal point.

- [ ] **Step 6: Commit.** `git add -A && git commit -m "Memo: three-tier hierarchy + investor-question IA; sources to bottom"`

---

### Task 4: Cross-surface polish pass

- [ ] **Step 1: Spacing + density rhythm.** Walk all three surfaces; normalize vertical rhythm (consistent `phi` spacing between tiers), ensure faint elements use a consistent opacity scale (focal `text-oxford`, support `/55`, recede `/40`).
- [ ] **Step 2: Motion restraint.** Keep Framer Motion transitions subtle (existing easings only); no new animation deps.
- [ ] **Step 3: Verify.** `npx tsc --noEmit` → `npm run build`.
- [ ] **Step 4: Final screenshots** of queue + rail + memo for owner review.
- [ ] **Step 5: Commit.** `git add -A && git commit -m "Premium pass: cross-surface spacing + opacity rhythm"`

---

## Self-Review

- **Spec coverage:** Queue hierarchy (Task 1) ✓ · rail telemetry (Task 0 done) + mandate pill + ⌘K dispatch (Task 2) ✓ · memo hierarchy + IA (Task 3) ✓ · cross-surface polish (Task 4) ✓ · no multi-page routing ✓ · fonts unchanged ✓.
- **Placeholders:** Steps that need current markup begin with an explicit "locate/read" step rather than guessing selectors — intentional for files not yet read on this branch; all transformations are concrete (classes, opacities, sizes named).
- **Consistency:** Opacity scale (focal=`text-oxford`, support=`/55`, recede=`/40`) and "single bold conviction integer" are used consistently across queue and memo.
