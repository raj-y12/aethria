# Aethria UI Audit

Audited against `.impeccable.md` (design brief) and the implemented design system
(`src/design-system/`, `tailwind.config.js`, `src/index.css`, `DESIGN_SYSTEM.md`).

**Source of truth:** the *implemented* system. The brief was reconciled to it —
Playfair Display (display/wordmark), Figtree Variable (body/UI), Space Mono
(labels/data); oxford `#0a1629`, paper `#D9D7D4`,
escalation burgundy `#6E2A3C`. (An earlier draft of this doc and the brief named
Geist/Instrument/EB Garamond/JetBrains Mono and `#002147`/`#F2F0EA`/`#b8976a`;
those describe a prior era and no longer reflect the code.)

---

## Result: strongly compliant

The codebase enforces its design principles consistently. Verified clean across
the whole of `src/`:

- **No rounded corners** — `borderRadius` is pinned to `0`/`none` in
  `tailwind.config.js`; the only `border-radius: 9999px` usages are circular
  signal/loader dots (which must be round). The previously-flagged `rounded-full`
  toggle in `SettingsPage.tsx` is now `rounded-none`.
- **No shadows** — `boxShadow` pinned to `none`; no `shadow-*` / `drop-shadow`
  utilities anywhere.
- **No gradients / glassmorphism** — no `bg-gradient`, `backdrop-blur`, or
  `blur()`. The single `radial-gradient` is the intentional editorial paper
  dot-grid texture (`.paper-dot-grid`).
- **Palette discipline** — no off-palette Tailwind colors (no `*-red-500`,
  `*-slate-*`, etc.). Verdict-chip pastels are centralized as sanctioned tokens
  in `design-system/verdictBadgeTokens.ts`, not scattered hex.
- **1px hairlines** — global `border-color` defaults to the oxford 6% hairline;
  semantic `hairline` / `field-border` tokens used for structure.
- **Tabular numerals** — financial figures use `font-mono` + `tabular-nums` /
  the `.type-data` utility.
- **Mono labels** — section labels/tabs are Space Mono, ALL CAPS, tracked.

---

## Fixes applied in this pass

- `components/SystemIntelligence.tsx` — "Why no further action" callout used a
  2px left accent (`border-l-2`); the system mandates 1px hairlines. → `border-l`.
- `components/DecisionStage.tsx` — "What decides it" callout used `border-l-2`. → `border-l`.

---

## Accepted conventions (intentional, not violations)

These read as deviations against a literal reading of the brief but are the
established, deliberate house style — left as-is:

- **Arbitrary `text-[Npx]` sizes** (`9/10/11/12/13/15/16px`) appear directly in
  components *and* in the design-system constant modules (`ui-text.ts`,
  `railEditorial.ts`, `productSystem.tsx`, `verdictBadgeTokens.ts`). The team
  treats explicit px in shared class-constants as the canonical pattern rather
  than routing everything through `.type-*` utilities.
- **Off-ladder oxford opacities** (`/35`, `/45`, `/55`, `/58`, …) are used for
  fine hierarchy steps beyond the 100/80/60/40/25 ladder. Pervasive and
  deliberate for dense-data legibility.
- **`text-white/NN` on oxford chrome** (spine, system bar, sidebar) rather than
  `text-paper/NN`. Consistent across all dark-surface chrome.
- **`font-style: italic` in `InvestmentMemoContent.css`** — rendered markdown
  `<em>` emphasis in memo prose (editorial document body), not UI chrome. Correct.

---

## Watch-list (no action needed now)

- A few literal verdict-pastel hexes (`#bfe3cc` / `#eabfb7` / `#e5d39f`) appear
  as *fallbacks* in `EscalationQueueMarker.tsx` and `DecisionThresholdsPanel.tsx`.
  They mirror the centralized `verdictBadgeTokens.ts` values and the configurable
  `verdictBadges`, so they're consistent — but if those tokens ever change,
  update the fallbacks too.
