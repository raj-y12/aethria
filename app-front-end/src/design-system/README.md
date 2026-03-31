# Design system

Aethria design constitution: palette, typography, layout, system elements.

**Full doc:** [docs/DESIGN_SYSTEM.md](../../../docs/DESIGN_SYSTEM.md) (from repo root: `docs/DESIGN_SYSTEM.md`).

## Implementation map (app-front-end)

### Semantic colours (Tailwind)

Defined in `tailwind.config.js` — use these instead of ad-hoc rgba / hex where possible:

| Token | Role |
|--------|------|
| `hairline` | Default 1px frame / dividers (`border-hairline`) |
| `hairline-strong` | Underline selects, stronger separators |
| `field-border` / `field-border-strong` | Inputs, focus rings |
| `lookup` / `lookup-surface` / `lookup-ink` | On-demand lookup origin chip |
| `escalation` | Human-attention only (matches `tokens.color.accent`) |

Chrome helpers in `chrome.ts` use `border-hairline`.

### Typography bundles

Repeated dense mono / toolbar strings live in `ui-text.ts` (e.g. `UI_FILTER_TOOLBAR_LABEL`, `UI_PANEL_CHROME_LABEL`). Prefer `index.css` utilities (`type-label-tab`, `type-meta`, …) when a single class is enough.

### Motion

- Timing: `design-system/tokens.ts` (`motion.duration`, `motion.ease`).
- **`prefers-reduced-motion`:** `usePrefersReducedMotion()` from `src/hooks`; pair Framer transitions with `transitionOrReduced()` from `design-system/motion.ts`.

### Interaction vocabulary

| Pattern | Use for |
|---------|---------|
| `border-b` tab/segment (`PanelShell`, `SystemIntelligence`, `WorkGrid` Source + “More filters” / “Reset”) | Mode switching and filter toolbar; active tint, inactive `border-transparent` + hover |
| `opacity` hovers on oxford rail | Tertiary / dense spine only |
| `btn-interaction` + `focus-visible:ring-oxford/40` | All buttons / `role="button"` rows |

Filled status = `DecisionBadge` / `VerdictBandBadge`; transparent queue chips use a hairline border only when the fill is transparent.
