# Informed urgency — UI design spec

**Date:** 2026-05-02  
**Status:** Approved for implementation planning  
**Scope:** `app-front-end/` primary; optional API naming/alias for analyst resolution (backend already supports writes for all deals).

---

## 1. Goal

Refactor the overview experience from passive “PDF read” to **action-oriented informed urgency**: analysts absorb **risks and blockers first**, sense **time pressure** on open items, and complete **`YOUR RULING`** as the natural end state for **every deal** (not only escalations), reflecting that analysts may agree or disagree with the partner recommendation on any row.

**Constraints (non-negotiable):**

- Aethria **navy / parchment / action-red (register)** palette.
- **Swiss / typography-heavy** layout; **professional tool**, not consumer UI (no rounded pill CTAs, no bright gradients).
- **Brutalist** cues: hairlines, square controls, mono labels, system-like copy.

---

## 2. Strategic approach

| Track | Choice |
|--------|--------|
| **UI strategy** | **B — Hierarchy + mechanics:** new risk fold, gate-age signals, ruling rail, motion/border tension. |
| **Data strategy** | **C-lite:** Derive gate age and stall counts from **existing** fields (`timestamps.*`, `last_updated`, list payloads) until a dedicated `analyst_due_at` (or similar) exists. |
| **Ruling scope** | **Every deal:** Any startup visible in the user’s queue may receive `human_resolution` once the analyst submits **YOUR RULING**. |

---

## 3. Analyst ruling — product and API

**Product rule:** Submitting **YOUR RULING** records the analyst’s **YES / NO / MAYBE** (`human_resolution.decision`) plus **notes**, independent of whether `partner.human_review_required` is true. Partner recommendation remains **read-only context** (e.g. `PARTNER: INVEST · YOUR RULING:`).

**Backend (verified):** `POST /api/escalations/{startup_id}/resolve` accepts `{ decision, notes }`, writes `human_resolution` via `update_startup_partial`, and appends meta mutation telemetry. The handler does **not** require the row to appear on `GET /api/escalations`; it only requires the startup to exist for the tenant.

**Frontend contract:**

- v1: Continue calling this endpoint for all deals; add a **semantically named** client (`submitAnalystResolution` or `postHumanResolution`) wrapping the same URL to avoid implying “escalation-only.”
- Optional follow-up: Add `POST /api/startups/{id}/human-resolution` as an **alias** to the same handler for REST clarity (out of scope unless desired in implementation plan).

**Re-ruling / edits:** Spec assumes **one resolution per row** until product defines “amend ruling.” If `human_resolution.resolved_at` exists, UI shows **read-only** ruling summary + optional “Request change” flow later (YAGNI for v1).

---

## 4. Gate age (“time in gate”)

**Definition v1 — `gate_opened_at`:** Best available timestamp among:

1. `timestamps.reviewed_at`
2. `timestamps.partnered_at`
3. Else fallback: earliest useful signal from row (`last_updated` or equivalent from API)

**Stall hours:** `now - gate_opened_at` for rows **without** `human_resolution.resolved_at`.

**Stall tiers (default thresholds):**

| Tier | Condition | UI |
|------|-----------|-----|
| **Fresh** | &lt; 24h | Neutral 2px left rail (oxford hairline). |
| **Stale** | ≥ 24h | Register-tint rail; include in sidebar **M** count. |
| **Critical** | ≥ 48h **or** `human_review_required` | Stronger register rail; optional **slow** opacity pulse on **rail only** (not full row). |

**Reduced motion:** Pulse becomes **static** high-contrast rail; no infinite animation.

**Sidebar / SystemBar:** One mono line, e.g. `QUEUE · N undecided · M >24h`, with hairline + register tint when `M > 0`. Numbers derived client-side from `startups` + gate-age rules + “undecided” = no `human_resolution.resolved_at` (exact “in queue” filter must match `WorkGrid` filter for undecided rows — implementation must share one helper).

---

## 5. Risk-first architecture (detail panel)

**New block — `ADVERSE REGISTER` (working title):** Placed **above** executive summary / bullish narrative in the memo detail (`InvestmentMemoContent` or extracted subsection).

**Tier 1 — Deal killers / policy / escalation signal**

- `review.diligence_red_flags`
- `partner.risks`
- Thesis misalignment: `thesis_matches_fund === false`, `thesis_deviation_points`
- `partner.human_review_required`
- Reviewer contest: `review.reviewer_disagreement === true` (or equivalent flag in types)

**Tier 2 — Structural / void blockers**

- Entries from **void registry** (Section 6), rendered as first-class rows, not footnotes.

**Presentation**

- Dense **monospace** list; severity via **left tick / bar** or `P1` / `P2` labels — **no** playful multi-color chips.
- Optional single-line **policy clash** when fund thesis summary is available from existing settings/summary fetch (if absent, omit).

---

## 6. Information scarcity (void as blocker)

**Void registry (client-side v1):** Map missing critical fields to `BLOCKER` rows in **ADVERSE REGISTER**, e.g.:

- Founder / team signal missing (heuristic from empty `team_analysis` or explicit missing flags if present in payload)
- References empty or below product threshold
- Partner / review incomplete for “decision-ready” read

**Styling:** Sharp rectangle, **register-tint** background, thin border, mono `BLOCKER · <CODE> · <short reason>`.

**Non-goals:** No fake data; absence stays honest but **visually blocking**.

---

## 7. Mechanical tension (brutalist activity)

- **Grid rows:** Optional **full-width 1px register hairline** under key metadata when `human_review_required` or contested; **shimmer** only on that line (opacity), &lt;300ms perceived rhythm or CSS-only slow pulse; **reduced motion → static**.
- **Ruling controls:** Square, outlined; **armed** state after user scrolls **past ADVERSE REGISTER** (Intersection Observer): full-opacity border + **1px inner register “charge”** (not glow).
- Optional mono caption when partner output exists but no human resolution yet: e.g. `SYSTEM AWAITING ANALYST` (copy review in implementation).

---

## 8. YOUR RULING rail (detail)

**Placement:** **Sticky bottom** inside embedded memo column, full width of memo content column, above safe area.

**Contents**

- Label: **`YOUR RULING`** (mono, small caps).
- Read-only: **Partner recommendation** line for contrast with analyst choice.
- Actions: **YES / NO / MAYBE** (map to API; labels may mirror `DECISION_LABELS` / INVEST–PASS–MONITOR where product copy requires).
- **Notes:** Required minimum length TBD in implementation (recommend non-empty for audit); enforce client + server.

**States**

- **Default:** Disabled or low-emphasis until **armed** (scroll past adverse register) — product choice: either block submit until armed **or** allow with confirmation; **recommend** block until armed for urgency narrative.
- **Resolved:** Show summary + `resolved_at`; hide destructive actions or show read-only strip.

---

## 9. Touch surfaces (file-level hints)

| Surface | Changes |
|---------|---------|
| **Sidebar / SystemBar** | Queue strip with undecided + stale counts; register accent when stale &gt; 0. |
| **WorkGrid** | Left rail by gate age tier; escalation/contested line treatment; shared gate-age helper. |
| **Detail / memo** | ADVERSE REGISTER + void blockers; reorder sections; sticky YOUR RULING rail; armed state. |
| **API client** | Wrapper for human resolution POST; invalidate startup list/detail on success. |

---

## 10. Accessibility

- All new motion: respect `prefers-reduced-motion`.
- Ruling rail: clear focus order, `aria-disabled` until armed if applicable, live region on submit success/failure.
- Color never sole signal: pair register with **weight / label / position**.

---

## 11. Testing / acceptance (high level)

- Undecided count in sidebar matches grid filter for “needs ruling.”
- Stall tier updates when clocks cross 24h/48h (unit-test pure date helper with frozen `now`).
- Submit ruling on **non-escalation** row persists and appears in feed/history if applicable.
- ADVERSE REGISTER renders empty state gracefully (section omitted or single “No adverse signals flagged” mono line — product pick in plan).

---

## 12. Out of scope (v1)

- New backend fields (`analyst_due_at`, normalized risk enums) unless added in a small parallel task.
- Re-opening or editing a past ruling.
- Email / Slack nudges for stall.

---

## 13. Spec self-review checklist

- [x] No unresolved TBD in requirements above; threshold numbers are defaults and may be tuned in implementation.
- [x] Ruling-for-all-deals consistent with API behavior.
- [x] Scope bounded to urgency UX + ruling rail + risk fold; no unrelated redesign.
- [x] Ambiguity: “Undecided” = no `human_resolution.resolved_at`; implementation must align sidebar and grid filters explicitly.

---

**Next step:** Implementation plan (`writing-plans`) then phased PRs: shared `gateAge` + `adverseRegister` helpers → WorkGrid + SystemBar → memo layout + ruling rail + API client rename.
