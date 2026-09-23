# Aethria Design System

Institutional, editorial UI. Modelled after a private equity firm's internal deal-flow terminal — flat, typographic, zero decoration.

---

## Philosophy

- **No rounded corners by default.** Every product surface is rectilinear. Any radius exception must be explicitly documented in this file.
- **No shadows.** Depth is created via hairline borders and background tints, never box-shadow.
- **No colour for colour's sake.** The palette has four roles: surface, text, structure (hairlines), and attention (escalation only).
- **Typography carries hierarchy.** Four type roles are locked to purpose. Font size follows the golden ratio (phi = 1.618034).
- **Spacing is a Fibonacci sequence.** Every spacing decision maps to a named step — no arbitrary px values.
- **Information density is intentional.** The UI is compact and tabular. Whitespace is earned, not decorative.

---

## Colour

### Semantic names — use these in code, never raw hex

| Token | Hex / Value | Role |
|---|---|---|
| `oxford` | `#0a1629` | Primary text, borders at full opacity |
| `paper` | `#D9D7D4` | Page & panel background |
| `paper-bright` | `#E1DFDC` | Raised surface, sheet overlay |
| `paper-deep` | `#CDCBC7` | Recessed surface — selected rows |
| `ivory` | `#D9D7D4` | Document surface |
| `charcoal` | `#1c2836` (`--color-charcoal`) | Primary body prose on paper |
| `escalation` | `#6E2A3C` | **Human-attention alerts only** — escalation dots, counts, critical intervention states |
| `brand-mark` | `#3d6b5e` | **Wordmark punctuation dot only** — shared with marketing; never for status |
| `brand-mark-inverse` | `#7aab9a` | Wordmark dot on oxford/dark chrome |
| `hairline` | `rgba(10,22,41,0.06)` | Default 1px borders (structural frames) |
| `hairline-strong` | `rgba(10,22,41,0.12)` | Emphasized dividers |
| `field-border` | `rgba(10,22,41,0.15)` | Input / select borders |
| `field-border-strong` | `rgba(10,22,41,0.20)` | Focused input border |
| `registerTint` | `rgba(10,22,41,0.03)` | WorkGrid row hover / column header fill |
| `lookup.DEFAULT` | `#8C7A4E` | On-demand lookup origin chip |
| `lookup.surface` | `#D6D0BE` | Lookup chip background |
| `lookup.ink` | `#2C2514` | Lookup chip text |

### Text opacity ladder (oxford as base)

Use Tailwind's opacity modifier: `text-oxford/100`, `text-oxford/80`, etc.

| Opacity | Usage |
|---|---|
| `100` | Primary headings, key numbers |
| `80` | Body text, primary labels |
| `60` | Secondary labels, descriptions |
| `40` | Tertiary metadata, hints |
| `25` | Placeholder, disabled |
| `10` | Faint rules, ghost text |

### Cross-app semantic contract (mandatory)

- `escalation` is always `#6E2A3C` and is never used as a decorative accent.
- `brand-mark` (verdigris) is for the wordmark dot only — never for alerts, badges, or links.
- In code, avoid introducing new raw hex values in class strings when a semantic token exists.

---

## Typography

### Typeface roles

| Family | Variable | Role | When to use |
|---|---|---|---|
| **Geist Sans** | `font-sans` / `font-body` | UI text, body, most headings | Everything by default in app product UI |
| **Playfair Display** | `font-display` | Editorial display headings | Hero/editorial headings in both fronts |
| **Playfair Display** | `font-wordmark` | Wordmark only | Logo lockups, brand mark word treatment |
| **Space Mono** | `font-mono` | Metadata, labels, tabular microtext | Section labels, timestamps, badge text, telemetry labels |

### Type scale (golden ratio, φ = 1.618034)

| Class | Family | Size | Line-height | Tracking | Weight |
|---|---|---|---|---|---|
| `.type-hero` | Playfair Display | `37px` (14×φ²) | `1.2` | `-0.02em` | `400` |
| `.type-title` | Geist Sans | `23px` (14×φ) | `1.382` (2−1/φ) | `-0.02em` | `500` |
| `.type-body` | Geist Sans | `14px` | `1.618` (φ) | `0` | `400` |
| `.type-body-sm` | Geist Sans | `13px` | `1.618` | `0` | `400` |
| `.type-label-section` | Space Mono | `11px` | `1.5` | `0.12em` | `400` |
| `.type-label-tab` | Space Mono | `10px` | `1.5` | `0.14em` | `400` |
| `.type-meta` | Space Mono | `10px` | `1.5` | `0.12em` | `400` |

**Rules:**
- No font sizes outside this scale.
- Titles use `letter-spacing: -0.02em` (tighter, editorial).
- Labels use `text-transform: uppercase` + wide tracking.
- Base `font-size` on `<body>` is `14px`.
- `type-display` and `type-display-xl` are editorial utility variants built from `font-display`.

### Transitional typography allowances (current code reality)

- Existing `11px/12px/15px` utility text appears in both fronts and is temporarily allowed during cleanup.
- Existing clamp-based hero sizes are temporarily allowed for responsive editorial sections.
- New component work should map to the canonical scale unless there is a documented accessibility or responsive reason.

---

## Spacing

Golden ratio Fibonacci sequence. Every layout value maps to a named step.

| Token | Value | Use case |
|---|---|---|
| `phi-1` | `3px` | Icon padding, divider gap |
| `phi-2` | `5px` | Tight inline gap |
| `phi-3` | `8px` | Compact component padding |
| `phi-4` | `13px` | Element gap, row padding |
| `phi-5` | `21px` | Card padding, page padding-x (mobile) |
| `phi-6` | `34px` | Section padding, page padding-y |
| `phi-7` | `55px` | Panel gap |
| `phi-8` | `89px` | Page bottom padding |
| `phi-9` | `144px` | Major layout gap |

**CSS vars:** `--space-1` … `--space-9` are also set in `:root` for non-Tailwind contexts.

---

## Layout

### Breakpoints

| Name | Width |
|---|---|
| `xs` | 480px |
| `sm` | 640px |
| `md` | 768px |
| `lg` | 1024px |
| `xl` | 1280px |
| `2xl` | 1440px |

### Page margins
- Desktop (`lg+`): `64px` horizontal
- Mobile: `24px` horizontal

### Column split (golden ratio)
- Sidebar: `38.2%` (`1/φ²`)
- Content: `61.8%` (`1/φ`)
- CSS vars: `--col-sidebar: 38.2%`, `--col-content: 61.8%`

### Max widths
- Reading column: `38rem` (`max-w-reading`)

### Grid philosophy
- Tables and lists are the primary layout primitives — this is a data terminal, not a marketing page.
- Use `border-collapse`-style hairline grids for tabular data.
- Panels divide via `border-r` / `border-b` hairlines, not gaps or padding.

---

## Borders & Surfaces

- **All borders**: `1px solid` — no `2px`, no `dashed`, no `dotted` (except dev only).
- **Default border colour**: `hairline` = `rgba(10,22,41,0.06)`.
- **Component frames**: `border border-hairline` → `.app-chrome-frame`.
- **Raised surfaces**: `border border-hairline bg-paper-bright` → `.app-chrome-frame-raised`.
- **No `border-radius` on product chrome.** Tailwind's `rounded-*` should resolve to `0` for all app shell/UI surfaces.
- **No `box-shadow` anywhere.** Tailwind's `shadow-*` resolves to `none`.

### Radius exceptions (explicitly allowed)

- Animated loader dots and cursor primitives may use circular geometry when required for motion language.
- Tiny mechanical toggles may use `2px` radius where square edges materially harm legibility/touch affordance.
- No other radius usage is allowed without updating this section first.

### Utility classes
```
.app-chrome-frame         border border-hairline bg-paper
.app-chrome-frame-raised  border border-hairline bg-paper-bright
```

### Section decoration (web-front-end pattern, use in editorial contexts)
- `.doc-rule-with-diamond` — full-width 1px rule + centered 4×4 oxford diamond
- `.paper-dot-grid` — `#D9D7D4` bg with `rgba(10,22,41,0.08)` 1px dots at 28px
- `.section-numeral` — `Space Mono 9px`, tracking `0.12em`, `oxford/20`

---

## Components

### Button

```tsx
// Primary / ghost (same base, only border/bg changes)
className="
  inline-flex items-center min-h-7
  border border-field-border bg-transparent
  px-phi-3 py-phi-2
  font-mono text-[10px] uppercase tracking-[0.1em] leading-none
  text-oxford/65
  transition-[background-color,border-color,color,transform] duration-150 ease-out
  hover:bg-oxford/[0.04] hover:border-oxford/35 hover:text-oxford
  active:translate-y-px
  focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40
  rounded-none
"
```

**Rules:**
- Buttons are `rounded-none` always.
- `→ LABEL` arrow-prefix pattern for directional actions.
- Disabled: no pointer, `opacity-40`.
- Never use colour fills for primary actions — use border weight instead.

### Badge / Chip

```tsx
className="
  inline-flex items-center min-h-6
  border border-hairline bg-transparent
  px-phi-2 py-0.5
  font-mono text-[10px] uppercase tracking-[0.08em] leading-[1.5]
  text-oxford/50
  rounded-none
"
```

### Input / Select

```tsx
className="
  border border-field-border bg-paper
  px-phi-3 py-phi-2
  font-sans text-[13px] text-oxford/80
  placeholder:text-oxford/40
  focus:outline-none focus:border-field-border-strong
  rounded-none
"
```

### Card / Panel

```tsx
className="app-chrome-frame p-phi-5"
// or raised:
className="app-chrome-frame-raised p-phi-5"
```

### Table / WorkGrid row

- Header row: `bg-registerTint` + `border-b border-hairline`
- Data row: `border-b border-hairline` + `hover:bg-registerTint`
- Columns separated by `border-r border-hairline`

---

## Effects & Motion

### Transitions

All interactive elements use:
```css
transition-[background-color,border-color,color,transform] duration-150 ease-out
```

Only these properties are animated. No `opacity` fade-ins on content.

### Active state
```css
active:translate-y-px  /* 1px downward press */
```

### Hover (buttons)
```css
hover:bg-oxford/[0.04]    /* barely-there fill */
hover:border-oxford/35    /* border darkens */
hover:text-oxford         /* text goes to full opacity */
```

### Escalation pulse (attention alerts only)
```css
@keyframes pulse — used only for escalation indicator dots
```

### Scrollbar
```css
scrollbar-width: thin;
scrollbar-color: oxford transparent;
/* webkit: 4px width, oxford thumb, no border-radius */
```

### Reduced motion

- Any continuous marquee, pulse, breathe, or reveal animation must provide a `prefers-reduced-motion: reduce` fallback.

### Market tape (web-front-end, editorial contexts)
```css
animation: market-tape-marquee 96s linear infinite;
```

---

## What makes the UI feel premium

1. **Zero decoration.** No gradients, no shadows, no border-radius. Every element earns its place through structure.
2. **Typographic hierarchy is everything.** Typeface roles are strict and non-overlapping. Size follows the golden ratio — relationships feel inevitable, not arbitrary.
3. **Spacing is a mathematical system.** The Fibonacci sequence means every gap is proportionally related to every other gap.
4. **Colour restraint.** Entire UI runs on one colour (oxford blue) at different opacities over one warm neutral (paper). Nothing else. Escalation red appears ≤1% of the time.
5. **Institutional references.** The aesthetic draws from Lazard/Goldman research documents: section diamonds, document rules, paper-dot grids, uppercase mono labels.
6. **Density signals competence.** The interface is compact and data-forward. Information is not padded for comfort — it respects the user's expertise.
7. **The golden ratio is structural.** Column split (38.2/61.8), spacing steps, type scale — phi is the hidden grid.

---

## Canonical vs Transitional

### Canonical (new code must follow)

- Use semantic tokens first (`oxford`, `paper`, `escalation`, `hairline`).
- Keep product UI surfaces square and shadowless.
- Use typography roles exactly as defined in this document.
- Prefer token utilities and design-system primitives over ad-hoc per-component styling.

### Transitional (legacy code tolerated short-term)

- Existing arbitrary color classes and raw rgba/hex in older marketing sections.
- Existing non-canonical type utility sizes (`11px`, `12px`, `15px`, custom clamp ranges).
- Existing isolated radius usage in loaders/toggles.

These are migration debt, not precedent for new code.

---

## Enforcement Checklist

- No new raw hex color in TSX class strings when token alternatives exist.
- No new `rounded-*` classes outside documented exceptions.
- No new `shadow-*` classes.
- New typography utilities should map to canonical scale or include a comment explaining exception intent.
- `escalation` red stays reserved for human-attention states only.


## Investment memo reading surface

The memo uses an editorial, line-free layout: Playfair Display titles, regular
sans-serif analysis, and compact company facts. Recommendation reasons remain
visible. At wider memo container widths, the investment case, assessments, and
risk/diligence sections use reading columns; narrow containers return to one
column. Sources, detailed company records, and review history share one appendix
entry. The ruling remains the final section. Decorative rules and framed panels
are omitted; form boundaries and keyboard focus indicators remain functional.
Scores, recommendation provenance, and ruling permissions are unchanged by this
presentation.
