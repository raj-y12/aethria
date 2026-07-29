# App Front-End — Cool-Grey / Blue-Ink Token Migration (Phase 1)

**Date:** 2026-07-24
**Scope:** `app-front-end/` tokens + docs only. No layout, spacing, font, or component-structure changes.
**Context:** The marketing site shipped the "Gallery of Instruments" (cool grey `#D9D7D4`, ink now experimenting at `#0a1629` on branch `web-blue-ink-and-co-domain`). User decisions: bring the same color foundation to the product app — **tokens first, then judge** deeper language elements later; **strip decorative warmth** (gold removed; escalation + lookup keep recolored semantic roles).

## Token map (exact)

| Token | Old | New |
|---|---|---|
| `--color-paper` / `paper` / `ivory` / `canvas` | `#f4f1ea` | `#D9D7D4` |
| `--color-paper-rgb` | `244, 241, 234` | `217, 215, 212` |
| `--color-paper-bright` / `paper-bright` | `#f8f5ee` | `#E1DFDC` |
| `--color-paper-deep` | `#e7e0d4` | `#CDCBC7` |
| `--color-oxford` / `oxford` / `graphite` | `#001433` | `#0a1629` |
| `--color-oxford-rgb` | `0, 20, 51` | `10, 22, 41` |
| text-inverse family | `rgba(244,241,234,…)` | `rgba(217,215,212,…)` |
| `--color-charcoal` / `charcoal` (body prose) | `#26313f` | `#1c2836` |
| `--color-accent` / `escalation` | `#7d2b3a` | `#6E2A3C` |
| `--color-accent-soft` | `rgba(125,43,58,0.24)` | `rgba(110,42,60,0.24)` |
| `escalation-bright` | `#C97B6A` | `#BF7583` |
| `lookup.DEFAULT` | `#B5893E` | `#8C7A4E` |
| `lookup.surface` | `#E8D7B4` | `#D6D0BE` |
| `lookup.ink` | `#3D2A12` | `#2C2514` |
| `mist` | `#f2f4f8` | `#E1DFDC` (alias raised) |
| heritage-gold / gold / gold-soft / brass / brass-line | — | **DELETED** (zero component usage confirmed; any CSS straggler → hairline/ink equivalent) |

Unchanged: verdigris `brand-mark` `#3d6b5e` / `-inverse` `#7aab9a`; all fonts; all spacing; hairline/tint alphas (they follow `--color-oxford-rgb`); Clerk vars (follow `var()` refs); motion tokens.

## Also
- Sweep literal `#f4f1ea`/`244, 241, 234`/`rgba(0,20,51`/`rgba(0, 20, 51`/`#001433` occurrences in `app-front-end/src` + `index.html` (theme-color) to the new values.
- Update `DESIGN_SYSTEM.md` color table + `src/index.css` header comment to match reality (gold rows removed, new hexes documented).
- Accent hexes (`#6E2A3C`, lookup bronze family) are proposals — tunable after visual review.

## Success criteria
- `grep -rniE '#f4f1ea|#f8f5ee|#e7e0d4|244, ?241, ?234|#001433|0, ?20, ?51|a88a5e|8a704d|B5893E' app-front-end/src app-front-end/index.html app-front-end/tailwind.config.js` → 0 matches (excluding DESIGN_SYSTEM history notes if any).
- `npm run build` (tsc+vite) and `npm run lint` pass; `vitest` suite passes if present (per user: verify with tsc + vitest, no preview servers).
- No layout/font/structure diffs — token and doc files only, plus literal-value sweeps in components.
