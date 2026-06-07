# Aethria P0 Implementation Plan

Three highest-leverage moves. Sequenced so each ships independently and de-risks the next.
No engine/pipeline logic changes required — these are surfacing, IA, and onboarding moves.

---

## P0.1 — Promote on-demand lookup to a hero action + first-run demo

**Why:** Mandate-aware company → IC memo in ~60s (`run_on_demand_lookup`, pipeline_runner.py:417)
is the conversion moment. Today it's a cramped sidebar "Dispatch" field (MainLayout.tsx:813).

**Changes**
- Reframe `AgentDispatch` into a first-class **command bar**: full-width, centered, persistent
  affordance ("Analyze any company →"), keyboard shortcut (⌘K) to focus. Keep the existing
  `handleLookupSubmit` / `queueOnDemandLookup` / polling state machine in MainLayout.tsx —
  only the placement + visual weight change.
- Rename user-facing "Dispatch" → "Analyze a company" (keep internal lookup plumbing).
- Surface the lookup phase ladder (Scouting → Reviewing → Deciding, already computed as
  `lookupPhaseLabel`) as a visible progress trace, not a one-line message.
- First-run: when queue is empty, the lookup bar IS the empty state (replaces
  `EmptyState` "Scouts are filling the workspace" in WorkGrid.tsx:265).

**Files:** `components/AgentDispatch.tsx`, `components/MainLayout.tsx`, `components/WorkGrid.tsx` (empty state)
**Risk:** Low. Pure UI re-placement over existing working flow.

---

## P0.2 — Multi-page IA (give Intelligence + Portfolio real homes)

**Why:** Memo, Judgements, System Intelligence all fight one split-pane via `rightPanel`
toggling (MainLayout.tsx:1063). The differentiated intelligence is hidden behind a tab.

**Target routes** (under existing `/v1` root, App.tsx:19)
- `/v1` — Deal queue (WorkGrid) + lookup hero
- `/v1/deal/:id` — Memo as a route (deep-linkable, shareable), not modal/panel state
- `/v1/portfolio` — Portfolio + concentration/yield (promote SystemIntelligence's portfolio data)
- `/v1/intelligence` — Meta/calibration/scout-weights/rejection analytics (out of the toggle)
- `/v1/settings` — unchanged

**Changes**
- Add routes in `App.tsx` AppShell; convert `selectedStartup` panel state to URL param so memos
  are linkable (enables the existing `readOnly` co-GP share to be a real URL).
- Split `SystemIntelligence.tsx` consumers: portfolio-flavored panels → Portfolio page;
  meta/calibration → Intelligence page. Component already receives all props (MainLayout.tsx:1024).
- `SystemBar` nav becomes route links instead of `setRightPanel`.
- Keep desktop split-pane for queue↔memo; everything else gets a full page.

**Files:** `App.tsx`, `components/MainLayout.tsx`, `components/SystemBar.tsx`, new
`pages/PortfolioPage.tsx` + `pages/IntelligencePage.tsx`, route wiring in `main.tsx`.
**Risk:** Medium. Touches navigation + memo open/close state. Ship behind the deep-link memo first.

---

## P0.3 — Surface trust at the point of decision

**Why:** Strip the chrome and a verdict is `mean(4 scores) ≥ threshold` (decision.py:269).
Calibration (`meta/calibrator`) and outcomes exist but never appear where the GP decides.
This is the institutional-credibility blocker.

**Two surfaces**

1. **Track record badge** (memo cover + Intelligence page)
   - "Aethria's INVEST calls: N tracked · X% still active · calibration vN"
   - Source: meta calibration state + portfolio health already loaded in `useSystemData`
     (MainLayout.tsx:255 `calibrationState`, `systemHealth`). New typed API in `api/meta.ts`
     if not already exposed; otherwise derive client-side.

2. **Per-dimension provenance** (memo Scoring section, InvestmentMemoContent.tsx:1217)
   - Each of the 5 scores links to the evidence/sources that drove it. The data exists:
     `scout.source_evidence` (memoSourceRows, line 84) + `evidenceLedger` (line 719).
   - Render: hover/expand on each `DimensionCard` → the supporting reference rows.
   - Add a confidence chip per dimension from `thesis_alignment_confidence` and reviewer spread
     (`reviewerConsensus.spread`, already computed line 891).

**Files:** `components/InvestmentMemoContent.tsx`, `components/scoring/DimensionCard.tsx`,
`components/scoring/ScoreOverview.tsx`, `api/meta.ts`, `lib/evidenceLedger.ts` (wire dim→evidence).
**Risk:** Low–medium. Read-only surfacing of existing data. No scoring math changes (honors
CLAUDE.md: partner rules stay in v1.json, no hardcoded thresholds).

---

## Suggested sequence
1. **P0.1** (1–2 days, low risk, immediate demo value)
2. **P0.3 surface #2** (provenance — pure additive memo win)
3. **P0.2** (deep-link memo first, then Portfolio/Intelligence pages)
4. **P0.3 surface #1** (track record — best once Intelligence page exists)

## Guardrails (from CLAUDE.md)
- No `fetch` outside `api/`; new calls go through typed clients + Clerk auth.
- TanStack Query hooks for any new data (extend `useSystemData` / `hooks/`).
- Framer Motion only for animation. Decision logic stays in `partner_rules/v1.json`.
