# Aethria Design System

Institutional, editorial UI. Modelled after a private equity firm's internal deal-flow terminal — flat, typographic, zero decoration.

---

## Philosophy

- **No rounded corners.** Every surface is rectilinear. No `border-radius` anywhere.
- **No shadows.** Depth is created via hairline borders and background tints, never box-shadow.
- **No colour for colour's sake.** The palette has four roles: surface, text, structure (hairlines), and attention (escalation only).
- **Typography carries hierarchy.** Three typefaces, each locked to a role. Font size follows the golden ratio (φ = 1.618034).
- **Spacing is a Fibonacci sequence.** Every spacing decision maps to a named step — no arbitrary px values.
- **Information density is intentional.** The UI is compact and tabular. Whitespace is earned, not decorative.

---

## Colour

### Semantic names — use these in code, never raw hex

| Token | Hex / Value | Role |
|---|---|---|
| `oxford` | `#002147` | Primary text, borders at full opacity |
| `paper` | `#F2F0EA` | Page & panel background |
| `paper-bright` | `#faf8f4` | Raised surface, sheet overlay |
| `ivory` | `#fcfcfc` | Memo/document surface (white-adjacent) |
| `charcoal` | `#2f333b` | Secondary prose text |
| `gold` | `#b8976a` | Heritage decorative accent — section rules, diamonds |
| `gold-soft` | `rgba(184,151,106,0.35)` | Gold tint surfaces |
| `escalation` | `#7D2B3A` | **Human-attention alerts only** — escalation dots, counts |
| `hairline` | `rgba(0,33,71,0.06)` | Default 1px borders (structural frames) |
| `hairline-strong` | `rgba(0,33,71,0.12)` | Emphasized dividers |
| `field-border` | `rgba(0,33,71,0.15)` | Input / select borders |
| `field-border-strong` | `rgba(0,33,71,0.20)` | Focused input border |
| `registerTint` | `rgba(0,33,71,0.03)` | WorkGrid row hover / column header fill |
| `lookup.DEFAULT` | `#B5893E` | On-demand lookup origin chip |
| `lookup.surface` | `#E8D7B4` | Lookup chip background |
| `lookup.ink` | `#3D2A12` | Lookup chip text |

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

---

## Typography

### Typeface roles

| Family | Variable | Role | When to use |
|---|---|---|---|
| **Geist Sans** | `font-sans` / `font-body` | UI text, body, headings | Everything by default |
| **Libre Baskerville** | `font-display` | Display / hero | Large hero text only (`type-hero`) |
| **Cormorant Garamond** | `font-cormorant` | Wordmark | Logo / wordmark lockup only |
| **Space Mono** | `font-mono` | Metadata, labels | Section labels, timestamps, badge text |

### Type scale (golden ratio, φ = 1.618034)

| Class | Family | Size | Line-height | Tracking | Weight |
|---|---|---|---|---|---|
| `.type-hero` | Libre Baskerville | `37px` (14×φ²) | `1.2` | `-0.02em` | `400` |
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
- **Default border colour**: `hairline` = `rgba(0,33,71,0.06)`.
- **Component frames**: `border border-hairline` → `.app-chrome-frame`.
- **Raised surfaces**: `border border-hairline bg-paper-bright` → `.app-chrome-frame-raised`.
- **No `border-radius` anywhere.** Tailwind's `rounded-*` resolves to `0`.
- **No `box-shadow` anywhere.** Tailwind's `shadow-*` resolves to `none`.

### Utility classes
```
.app-chrome-frame         border border-hairline bg-paper
.app-chrome-frame-raised  border border-hairline bg-paper-bright
```

### Section decoration (web-front-end pattern, use in editorial contexts)
- `.doc-rule-with-diamond` — full-width 1px rule + centered 4×4 oxford diamond
- `.paper-dot-grid` — `#F2F0EA` bg with `rgba(0,33,71,0.055)` 1px dots at 28px
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

### Market tape (web-front-end, editorial contexts)
```css
animation: market-tape-marquee 96s linear infinite;
```

---

## What makes the UI feel premium

1. **Zero decoration.** No gradients, no shadows, no border-radius. Every element earns its place through structure.
2. **Typographic hierarchy is everything.** Three distinct typefaces, each locked to a single role. Size follows the golden ratio — relationships feel inevitable, not arbitrary.
3. **Spacing is a mathematical system.** The Fibonacci sequence means every gap is proportionally related to every other gap.
4. **Colour restraint.** Entire UI runs on one colour (oxford blue) at different opacities over one warm neutral (paper). Nothing else. Escalation red appears ≤1% of the time.
5. **Institutional references.** The aesthetic draws from Lazard/Goldman research documents: section diamonds, document rules, paper-dot grids, uppercase mono labels.
6. **Density signals competence.** The interface is compact and data-forward. Information is not padded for comfort — it respects the user's expertise.
7. **The golden ratio is structural.** Column split (38.2/61.8), spacing steps, type scale — φ is the hidden grid.
