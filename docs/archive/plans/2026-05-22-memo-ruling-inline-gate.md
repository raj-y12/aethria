# Memo Ruling Inline Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the memo ruling section and make risk acknowledgement a clear inline gate before the final commit action.

**Architecture:** Keep the existing ruling logic in `src/components/InvestmentMemoContent.tsx`, but restructure the JSX to group acknowledgement and submission into a clearer flow. Update `src/components/InvestmentMemoContent.css` to introduce a gated action block, stronger ruling panel styling, and a more explicit acknowledgement control.

**Tech Stack:** React 18, TypeScript, CSS, Vite

---

### Task 1: Restructure the Ruling Markup

**Files:**
- Modify: `src/components/InvestmentMemoContent.tsx`

- [ ] Move the acknowledgement UI into an inline gate inside the ruling panel.
- [ ] Replace `Mark reviewed` copy with explicit risk-review confirmation language.
- [ ] Keep the existing gating and submit logic unchanged.

### Task 2: Restyle the Section

**Files:**
- Modify: `src/components/InvestmentMemoContent.css`

- [ ] Add a stronger ruling panel treatment with clearer spacing and background hierarchy.
- [ ] Style the acknowledgement block as a checkpoint card.
- [ ] Visually mute the final action row while locked and promote it when unlocked.

### Task 3: Verify the Change

**Files:**
- Verify: `src/components/InvestmentMemoContent.tsx`
- Verify: `src/components/InvestmentMemoContent.css`

- [ ] Run `npm run lint`.
- [ ] Run `npm run build`.
