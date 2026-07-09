# App Home — Briefing, Not Doors

**Date:** 2026-07-09
**Scope:** `app-front-end/src/pages/HomePage.tsx` (plus a small ordering helper)
**Status:** Approved direction; pending spec review

## Problem

The app home (`/v1`, bare chrome) is a full-screen launcher: a situational
headline plus four "doors" (Flow / Portfolio / Fund / Dispatch). Every one of
those destinations is already reachable from the persistent spine on all other
pages and from global shortcuts (1–4, ⌘K — bound at document level in
`AppFrame.tsx`, so they work on the bare-chrome home too). The page therefore
duplicates navigation without offering anything of its own, and at real scale
("79 matters await your ruling") it names a backlog it does nothing about.

Two complaints, verified against a rendered screenshot at n=79:
1. The landing doesn't earn itself — nothing here that the nav can't give.
2. It should feel fresher — while **staying calm, not becoming a dashboard**.

## Design

Keep the calm, centered, bare-chrome editorial canvas. Replace the four-door
band with a small amount of synthesis only this page can offer. Content doubles
as navigation ("blocks as doors").

### Page composition (top to bottom)

1. **Wordmark + date/time eyebrow** — unchanged.
2. **Situational headline** — unchanged priority cascade
   (escalations → new → open → "The desk is clear.").
3. **Digest line** *(new)* — one quiet line under the headline's existing
   subline, from `useSinceAwaySummary()` (which already returns the
   `ActivitySummary`; the page currently discards it). E.g.
   `Since you left: 12 scouted · 4 reviewed · 2 escalated`.
   Renders only when the hook returns a non-null summary.
4. **Attention block** *(new — the only dense element on the page)*
   - Kicker `ON THE DESK`, trailing `FLOW →`.
   - **At most 3 rows**: company name + one short clause explaining why it
     needs attention. Mono, small, no badges/scores/images.
   - Ordering: escalations first, then `is_new_to_user`, then oldest
     unresolved (via existing `isDealUnresolved`).
   - One muted trailing line: `+ N more` when more exist.
   - The whole block is a single door: click/tap navigates to `/v1/flow`.
     Rows are scent, not actions — no inline accept/pass (ruling is Flow's job).
   - Collapses away entirely when nothing is unresolved.
5. **Two quiet doors — Portfolio and Fund** — same visual weight as today's
   doors, slightly richer copy (e.g. Portfolio: conviction/watch counts; Fund:
   mandate version + published date). Same hover language.
6. **Footer bar** — identity · fund thesis · settings · log out. Unchanged.

### What is deliberately out (calmness rules)

- No pipeline funnel/sparkline/heartbeat line — the existing subline
  (`142 in pipeline · 83 open`) suffices.
- No fourth "Dispatch" door — ⌘K, plus a `DISPATCH ⌘K` entry added to the
  existing footer bar (calls `openDispatch`).
- No per-row actions, scores, or thumbnails in the attention block.
- No new sections beyond the above. Net change vs. today: one new region,
  one new line.

### Navigation

- **Blocks as doors:** attention block → Flow; Portfolio/Fund blocks → their
  workspaces. Existing oxford-tint lift + hairline draw-in hover language marks
  clickability.
- **Keyboard:** 1–4 workspace shortcuts and ⌘K Dispatch already global
  (`AppFrame.tsx` document listener) — no changes.
- **Footer:** settings / logout / fund link unchanged.

### States

| State | Behaviour |
|---|---|
| First-run (no mandate) | Unchanged from today ("Define your mandate."). |
| Desk clear | Headline "The desk is clear."; attention block absent; doors + footer remain. |
| Backlog | Full composition as above. |
| No away activity | Digest line absent. |

### Implementation shape

- Rewrite `pages/HomePage.tsx` (~150 net-new lines). Reuse `Reveal`, design
  tokens, `usePrefersReducedMotion`, `isDealUnresolved`, existing selectors.
- Use the return value of `useSinceAwaySummary()` (no hook changes needed).
- Attention ordering: small pure helper (exported for a unit test) that sorts
  unresolved startups: escalation → new → oldest.
- No new dependencies, API changes, or routes. Framer Motion stays the only
  animation library.

### Verification

- Unit test for the ordering helper (the one branchy piece of logic).
- Browser check + screenshots of all four states (first-run, desk-clear,
  backlog, no-digest), desktop and mobile widths.
