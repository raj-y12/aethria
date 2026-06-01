# Frontend Premium Pass — Design

**Date:** 2026-06-01
**Branch base:** `main`
**Track:** A (Frontend). Backend bulletproofing is a separate spec.

## Problem

The cockpit reads as a wall of text. Titles, descriptions, the filter row, and meta all
carry similar visual weight, so nothing guides the eye — it feels cluttered, not premium.
The information is right; the *hierarchy* is flat.

## Principle: "One volume per element"

Premium comes from **hierarchy + restraint**, not new styling. Every surface gets three tiers:

- **Focal** — the one thing the eye should land on first (full weight/size).
- **Support** — the single number/verdict that matters (clear, secondary).
- **Recede** — everything else: faint mono, smaller, or removed entirely.

**Constraints:**
- **No multi-page routing.** This is the ONE hard exclusion. The single-surface cockpit is the product's identity and stays.
- **Keep existing font families** (per the owner's stated preference). Hierarchy is achieved via size, weight, color/opacity, spacing, and removing competing text — not typeface swaps. Revisit only if the owner asks.
- **Everything else is in scope.** Palette/spacing tokens, component structure, dependencies, and backend glue may all change where it makes the product feel more premium. (Deep backend bulletproofing remains its own separate spec, but small backend changes that serve the frontend — e.g. a list-projection field — are fine here.)

## Surface 1 — Deal Queue

- **Name** leads (focal), existing type family, slightly tightened.
- **Verdict + a single bold conviction number** anchors the right (support). `MONITOR · 55` not `MONITOR · 55%`.
- **Meta** collapses to one faint mono micro-line (`Climate · Stale 6d`); stale renders in accent.
- **One-line description removed from default rows.** It reappears **only on the selected/expanded row** (progressive disclosure) — not 108× down the list.
- **Filter row goes quiet** — active filter at full weight, the rest faint. Smaller overall.
- More vertical breathing room per row; a thin accent rule only on priority rows.

## Surface 2 — Left Rail

- **Telemetry → compact status strip.** Remove the "Pipeline Overview" header and the 3-cell
  grid. One row: escalations hero number + live/off status dot. One mono line below:
  `108 total · 97 rec · 1 ruled`. All numbers retained; ~half the height; reads like a terminal readout.
- **Dispatch → ⌘K command bar + the queue header's `+` trigger.** Remove the always-on rail input.
  ⌘K is the power path; `+` keeps it discoverable. Lookups still land in the queue.
- **Mandate → a single status pill** (e.g. "No active thesis" / thesis name), not a titled multi-line block.
- **Nav modes** (Workspace / Judgements / System) and identity footer unchanged.
- Result: nav + one status block + dispatch trigger + identity. Calm.

## Surface 3 — Memo (right pane)

- Same three-tier treatment: section headings clearly outrank body; recommendation + conviction
  is the unmistakable focal point; duplicated/repeated copy removed; supporting detail collapses.
- **Port the stronger memo information architecture** already designed (not yet on `main`):
  investor-question order (Decision → Why Now → What Must Be True → bear case → analytics →
  Next Actions → Ruling) with **evidence/sources as reference material at the bottom**.

## Components likely touched

- `components/MainLayout.tsx` (rail telemetry, mandate, dispatch trigger)
- `components/WorkGrid.tsx` + `components/queue/*` (row hierarchy, selected-row description, filters)
- `components/AgentDispatch.tsx` (⌘K command bar)
- `components/InvestmentMemoContent.tsx` (memo hierarchy + IA port)
- `components/InvestmentMemoContent.css` and the relevant Tailwind token usages

## Out of scope (YAGNI)

- **Multi-page routing** — the one hard exclusion; the cockpit stays single-surface.
- **Font-family swaps** — keep existing typefaces (owner preference; revisit on request).
- Deep backend bulletproofing, org/fund collaboration, durable queues, and MetaAgent governance
  remain *separate* specs — not because they're forbidden, but to keep this pass focused.

## Verification

- `tsc --noEmit` clean and `npm run build` green after each surface.
- Screenshot the running app per surface so the real UI (not just mockups) is reviewed.
- No behavior/logic regressions: reorder and restyle only; data and handlers unchanged.

## Success criteria

Opening the cockpit, the eye lands on: (queue) the company name then its verdict; (rail) the
escalations number; (memo) the recommendation. Nothing else competes. It reads calm and
deliberate — premium — with zero information actually lost.
