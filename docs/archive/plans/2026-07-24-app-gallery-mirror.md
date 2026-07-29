# App Gallery Mirror — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Checkbox steps.

**Goal:** Apply the finishing moves from `docs/superpowers/specs/2026-07-24-app-gallery-mirror-audit.md` to `app-front-end`, per-page as specified there. The audit doc is the design source of truth; this plan sequences it.

**Branch:** `web-blue-ink-and-co-domain`.

## Global Constraints — "don't overdo it" (user mandate)
- **Quieter than marketing, always:** grain opacity **0.3** (marketing is 0.5); plate numerals use the SMALL mono `.plate-num` voice (`01 — 04`, ~11px) — NOT the giant ghost folio numerals; brackets are hairline `var(--line-2)`-weight, fade in ≤0.3s; rule draw-ins 0.6–0.9s, once, reduced-motion safe.
- When a move competes with density or legibility, the move loses. No new decoration beyond the audit's listed moves. No copy changes except where the audit names them.
- Locked: memo structure/fonts (rule draw-ins only), no in-app blocking loader, warm-start instant paint, docket rows stay bare (2px ink left-edge on selected only), fonts/spacing untouched.
- Verification per task: `npm run build` + `npm run lint` + `npm test` (vitest) from `app-front-end/`. Never start preview servers. Commit per task.
- Reuse marketing CSS constructions (`.grain`, `.framed` brackets, plate-num, draw keyframes) by porting into `app-front-end/src/index.css` — translate token names; do not import across packages.

### Task 1: System layer — grain + RoomHeader plate-head + rule draws (audit M1/M2/M5)
- [ ] Port `.grain` (opacity 0.3, z-index above content below modals — pick a sane z; `pointer-events:none`) mounted once in `AppFrame`.
- [ ] `RoomHeader`: optional `plateIndex?: string` prop → renders small mono numeral right-aligned in the eyebrow row (`.plate-num` voice). Wire the four rooms: Home `01 — 04`, Flow `02 — 04`, Portfolio `03 — 04`, Fund `04 — 04`.
- [ ] Add `rule-draw` CSS (scaleX origin-left, 0.7s house ease, reduced-motion: none) + apply to RoomHeader's under-hairline and Portfolio/Settings/SystemIntelligence section top-rules where a rule already exists (class swap only — no new rules).
- [ ] build+lint+test → PASS. Commit: `feat(app): grain, plate-head numerals, rule draw-ins (gallery mirror 1/4)`.

### Task 2: Login mirror + spine furniture (audit §2-Login, M4)
- [ ] LoginPage: corner marginal furniture at `lg+` (wordmark TL exists via layout — add clocks BL + `No. {editionNo}` BR using ported `bureauTimes`/`editionNo` utils copied to `app-front-end/src/lib/clocks.ts`); settle-in stagger on the form card (kicker→title→fields, ≤0.9s, no blocking); `AuthInstitutionalFooter` gains the colophon line (typefaces · bureaus) — keep existing legal/links.
- [ ] `AppSpine` foot: live clocks (two lines, mono, inverse-muted, ticking) + `No. {editionNo}` near the existing build line. Interval cleaned up; reduced-motion renders once.
- [ ] build+lint+test → PASS. Commit: `feat(app): login mirror + spine bureau furniture (gallery mirror 2/4)`.

### Task 3: Bracket focus-framing + Fund dims (audit M3, §2-Flow/Fund/Settings)
- [ ] Port `.framed`-style bracket CSS as `.focus-frame` (hairline, fade-in 0.3s). Apply to: Flow's active DecisionStage/memo panel (only when a deal is open), `FundThesisConfirmationModal` card, Settings active section container. NOT on lists/rows.
- [ ] Flow selected `DocketCaseRow`: 2px ink left-edge on the selected row (replace/augment current tint per audit).
- [ ] FundPage `HeaderReadout` row → bordered dims cells (1px `var(--line)` grid like marketing `.dims`, transparent bg) with existing count-up preserved.
- [ ] build+lint+test → PASS. Commit: `feat(app): focus brackets + fund dims cells (gallery mirror 3/4)`.

### Task 4: Home/Portfolio/Dispatch refinements (audit §2-Home/Portfolio/Dispatch, M6)
- [ ] Home: bracket-frame the digest block; `HomeDoor` numerals → `.plate-num` mono voice; statement line to hero-statement weight/air (Playfair 400, slightly larger, same copy).
- [ ] Portfolio: group headers adopt draw-in top rule + mono kicker + count as small ghost numeral; right-column stats as bordered dims cells with count-up.
- [ ] Dispatch idle placeholder: `› look up …` + blinking block caret (CSS only; caret hidden under reduced motion); running state untouched.
- [ ] build+lint+test → PASS. Commit: `feat(app): home, portfolio, dispatch voice (gallery mirror 4/4)`.
