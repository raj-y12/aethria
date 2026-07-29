# App Cool-Grey Token Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Migrate `app-front-end` color tokens to the gallery foundation (grey `#D9D7D4` stock, blue ink `#0a1629`), recolor escalation/lookup, delete gold — per the spec's exact token map.

**Spec:** `docs/superpowers/specs/2026-07-24-app-cool-grey-token-migration-design.md` (the token map there is the single source of truth — apply it verbatim).

**Branch:** `web-blue-ink-and-co-domain` (continues the blue-ink experiment so both properties match).

## Global Constraints
- Tokens/docs/literal-sweeps ONLY. No layout, font, spacing, or component-structure changes. No `app-front-end` behavior changes.
- Verification: `npm run build` + `npm run lint` from `app-front-end/`; run the vitest suite if `package.json` has a test script (user rule: tsc + vitest, never preview servers).
- Commit after each task.

### Task 1: Apply the token map
- [ ] Apply the spec's token map to `app-front-end/src/index.css` (`:root` + header comment) and `app-front-end/tailwind.config.js`.
- [ ] Delete gold/brass/heritage tokens; first `grep -rn 'gold\|brass\|heritage\|a88a5e\|8a704d' app-front-end/src` — replace any CSS straggler usage with the hairline/ink equivalent, then delete the tokens.
- [ ] Sweep literals in `app-front-end/src` + `app-front-end/index.html`: `#f4f1ea`→`#D9D7D4`, `#f8f5ee`→`#E1DFDC`, `#e7e0d4`→`#CDCBC7`, `#001433`→`#0a1629`, `0, 20, 51`/`0,20,51`→`10, 22, 41`, `244, 241, 234`→`217, 215, 212` (case-insensitive on hexes; include theme-color in index.html).
- [ ] `npm run build && npm run lint` → PASS. Commit: `feat(app): cool-grey stock + blue ink token migration (phase 1)`.

### Task 2: Tests + docs
- [ ] Run the vitest suite if present (`npm test` / `npx vitest run`); fix any color-literal assertions broken by the sweep (update expected values to the new tokens — do not weaken assertions). Check `e2e/`/`screenshot/`/`tests/` for hardcoded old hexes and update.
- [ ] Update `app-front-end/DESIGN_SYSTEM.md`: color table rows per the spec map, gold rows removed, philosophy line about palette updated if it names old hexes.
- [ ] Commit: `docs(app): design-system palette updated to grey/blue foundation`.

### Task 3: Acceptance
- [ ] Run the spec's success-criteria grep → 0 matches. Full `npm run build && npm run lint` (+ vitest if present) → PASS.
- [ ] Commit (allow-empty if clean): `chore(app): token-migration acceptance pass`.
