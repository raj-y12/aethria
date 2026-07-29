# App ↔ Marketing Mirror — Page-by-Page Audit (Phase 2 proposal)

**Date:** 2026-07-24 · **Status:** proposal, awaiting user green-light per move
**Premise (user):** make every app page mirror the marketing "Gallery of Instruments" language *without changing the idea of the pages*.
**Foundation already shipped:** grey `#D9D7D4` stock + blue `#0a1629` ink on both properties (branch `web-blue-ink-and-co-domain`).

## 0. The good news — shared DNA already in place

| Marketing move | App equivalent that already exists |
|---|---|
| Plate head (title + numeral) | `RoomHeader` — mono eyebrow → Playfair title + verdigris period → mono readouts |
| Record plate dims (bordered cells, count-up) | `FundPage` `HeaderReadout` row + existing `CountUp` |
| Holdings table | `PortfolioPage` decision ledger |
| Hairline discipline, no radius/shadow | app-wide already |
| Mono data voice (Space Mono) | app-wide `type-label-section` / `type-data` |

So the gap is the **finishing layer**: grain, bracket framing, plate numerals, marginal furniture, diegetic reveals, and one arrival moment. Below, per page — *idea kept* stated first, then the moves.

## 1. Shared moves (one implementation, every page benefits)

- **M1 · Grain** — port the marketing `.grain` overlay app-wide via `AppFrame`, at *lower* opacity (~0.35 vs 0.5; this is an 8-hour work surface, not a poster). Fixed, pointer-events none.
- **M2 · Plate-head upgrade of `RoomHeader`** — add an optional oversized ghost plate-numeral (`01 — 04` for the four rooms: Home 01, Flow 02, Portfolio 03, Fund 04) rendered like the marketing `.plate-num`; hairline under the header **draws in** (scaleX) instead of appearing. One component change, all four rooms inherit.
- **M3 · Bracket focus-framing** — the gallery frames the *centered plate* with `[ ]`; the app's translation: brackets frame **the surface holding the user's attention** — the active `DecisionStage`/memo panel in Flow, the confirm modal, the active settings section. Reuse the marketing `.framed::before/::after` construction; brackets fade in when the panel becomes active. NOT on dense list rows (noise).
- **M4 · Spine furniture** — `AppSpine` (the dark rail — keep it; it's the app's identity, the "dark plate" the marketing site doesn't have) gains the marketing's furniture at its foot: live dual-bureau clocks (`bureauTimes` — copy the small util) + `Specimen-style edition line` → here it becomes `No. {day-of-year}` under the wordmark where a build-date already sits. Quiet, mono, inverse-muted.
- **M5 · Rule draw-ins** — replace static section hairlines with the marketing scaleX draw (respecting reduced-motion) in: RoomHeader underline, Portfolio group rules, Settings section rules, SystemIntelligence panel rules. The app's `Reveal` (y-fade) stays for content; rules get the draw.

## 2. Per page

### Login (`LoginPage`) — the most marketing-like surface; mirror fully
*Idea kept:* sign in, warm-start fast.
- Full corner marginal furniture (wordmark TL, clocks BL, `No.` BR) — exactly the marketing `.frame` classes.
- Hero-settle arrival on the form card (kicker → title → fields stagger, ~0.9s) — **no blocking loader** (login warm-start decision stays law).
- `AuthInstitutionalFooter` → colophon voice ("Set in Playfair Display, Figtree & Space Mono · London · San Francisco").

### Home (`HomePage` briefing) — closest to a gallery already
*Idea kept:* desk teaser + digest + two doors; no launcher creep (locked decision).
- The digest block gets the **bracket frame** (it's "today's plate").
- The two `HomeDoor`s get ghost plate-numerals (`01`/`02`) in the marketing `.plate-num` voice instead of their current small numerals.
- Statement line adopts marketing hero-statement scale/weight (Playfair 400, more air) — same copy.
- Dispatch footer hint stays; idle state may borrow the marketing typing caret (M6 below).

### Flow (`FlowPage`) — the workroom; restraint
*Idea kept:* dense docket left | decision stage right. Density is the point — no plates around list rows.
- RoomHeader → M2 plate-head (`02 — 04`).
- **Bracket-frame the active memo/DecisionStage panel** (M3) — the "selected plate" reading is genuinely meaningful here: the docket is the contact sheet, the stage is the framed print.
- Selected `DocketCaseRow` keeps its current tint; add only a 2px ink left-edge (spine mark), no brackets.
- Panel-open transition: rule draws + content settles (M5), replacing plain fades.

### Portfolio (`PortfolioPage`) — already the Holdings plate
*Idea kept:* the book of decided deals, grouped by ruling.
- RoomHeader → `03 — 04`.
- Group headers (`INVEST` etc.) get the marketing table voice: hairline-strong top rule that draws in + mono kicker; counts as ghost numerals.
- The right column (stats) formatted as a Record-plate dims strip (bordered cells, count-up on first view — `CountUp` exists).

### Fund (`FundPage`) — the instrument room; nearly there
*Idea kept:* mandate header + SystemIntelligence panels.
- RoomHeader → `04 — 04`; readouts already mirror the dims — upgrade to bordered `.dims` cells (marketing Record plate) with the existing count-up.
- SystemIntelligence sections each get a small plate-head (title + `.plate-num`-voice index) — content untouched.

### Settings — the control room
*Idea kept:* two-mode control room, trust language (locked decisions).
- Section heads adopt plate-head voice; active section gets the bracket (M3).
- `FundThesisConfirmationModal` (already on dot-grid) gets the full framed-plate treatment — it is literally "a document being signed."

### Memo (`InvestmentMemoContent`) — **do not touch structure**
Broadsheet structure + house fonts are locked (prior decision; serif reverted once already). Foundation colors already applied. Only permitted touch: rule draw-ins on section rules (M5), nothing else.

### Dispatch (`DispatchCommandBar`) — M6 · the typing voice
*Idea kept:* ⌘K lookup with context textarea.
- Idle placeholder borrows the marketing query voice: `› look up …` with the blinking block caret (CSS only). When a lookup runs, the existing dot-pulse stays.

## 3. Explicitly NOT proposed (would change the idea / break locked decisions)
- No arrival loader inside the app (warm-start is law); login gets a settle, not a gate.
- No vertical caption rails on work pages (marginalia noise in a tool).
- No memo restructure; no font changes anywhere; no spacing-system changes.
- No plates/brackets around dense rows (docket, tables) — density is the app's voice.

## 4. Suggested order (each independently shippable)
1. M1 grain + M2 plate-head RoomHeader + M5 rule draws (the "one system" feel, ~a day)
2. Login mirror + AppSpine furniture (M4)
3. Flow/Settings bracket framing (M3) + Fund dims cells
4. Home refinements + Portfolio group voice + Dispatch caret (M6)
