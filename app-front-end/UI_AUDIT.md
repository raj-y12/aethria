# Aethria UI Audit

Compared against `/app-front-end/DESIGN_SYSTEM.md`. Every issue below is a concrete, actionable deviation.

---

## Component Issues

### `WorkGrid.tsx`

**Layout**
- Column split is coded as `60/40` — design system mandates `61.8% / 38.2%` (golden ratio). Off by ~2% but semantically wrong.

**Spacing**
- Row padding uses `p-4` (16px) and `p-2` (8px) — should be `p-phi-4` (13px) / `p-phi-3` (8px).
- `gap-2`, `gap-3`, `gap-4` throughout — should be `gap-phi-2`, `gap-phi-3`, `gap-phi-4`.

**Typography**
- Decision badges use arbitrary `text-[11px]` — should use `type-label-section` (11px + correct tracking + mono).
- Company name row uses `text-sm` (14px Tailwind default = OK) but with no explicit `font-sans` or `type-body` class — relies on body inheritance, fragile.
- Filter tabs lack `type-label-tab` class; use raw `text-[10px] tracking-widest` instead of canonical `type-label-tab`.

**Colour / Opacity**
- Various opacities not on the canonical ladder: `text-oxford/70`, `text-oxford/50`, `text-oxford/55` — ladder is `100 / 80 / 60 / 40 / 25`.
- Hover state uses `hover:bg-oxford/5` in some rows, `hover:bg-registerTint` in others — should be `bg-registerTint` everywhere.

**Animation**
- Staggered row entrance animation (Framer Motion `staggerChildren`) — not in the design system motion spec. Adds visual noise on a data terminal. Should be reduced or removed.

---

### `SystemIntelligence.tsx`

**Typography**
- `text-[15px]` on escalation startup name — off-scale. Closest canonical is `type-body` (14px). Use `type-body font-medium`.
- `font-body text-[13px] leading-[1.6]` — should be `type-body-sm` class (handles family, size, line-height together).
- Inline `style={{ fontFamily: '"Space Mono", ui-monospace, monospace' }}` on badge `<p>` — should be `font-mono`.
- `type-meta` class used correctly in some places but inconsistently with raw `font-mono text-[10px]` elsewhere in same file.

**Spacing**
- Content area padding: `p-4 sm:p-5` — `p-4` = 16px (off-scale), `sm:p-5` = 20px (close to `phi-5` = 21px but wrong). Should be `p-phi-4 sm:p-phi-5`.
- `mt-0.5`, `mt-1`, `mt-2` throughout — arbitrary Tailwind steps. Should be `mt-phi-1`, `mt-phi-2`, `mt-phi-3`.
- `mx-0.5` on separator — should be `mx-phi-1` (3px) or `mx-phi-2` (5px).

**Colour / Opacity**
- `text-oxford/65` — off-ladder (nearest: 60).
- `text-oxford/50` — off-ladder (nearest: 40 or 60).
- `text-oxford/90` — off-ladder (nearest: 80 or 100).
- `text-oxford/35` — off-ladder (nearest: 40 or 25).
- Button border: `border-oxford/15` — the `field-border` token (`rgba(0,33,71,0.15)`) exists precisely for this. Use `border-field-border`.

**Buttons**
- Button: `px-2.5 py-1` — not phi scale. Should be `px-phi-3 py-phi-2` (8px / 5px).
- `tracking-[0.1em]` on button label — should be `tracking-label` (0.12em) or `tracking-tab` (0.14em).
- `border-solid` is redundant (Tailwind default). Remove.
- Badge: `px-2 py-0.5` — `px-2` = 8px (phi-3 ✓), `py-0.5` = 2px (off-scale, use `py-phi-1` = 3px).
- `tracking-[0.08em]` on badge — should be `tracking-badge` (0.08em, which is correct value but use the token name now it exists).

---

### `SettingsPage.tsx`

**Inline styles — pervasive violation**
- `style={{ fontFamily: FONT_GEIST }}` appears on ~20+ elements: `DescText`, `SettingRow` labels, hints, `<p>` tags. Since `font-sans` is Geist Sans globally, this is redundant AND violates the no-inline-styles rule. All instances should be deleted — body inherits it.
- `FONT_GEIST` constant is defined at top of file as a workaround for a non-issue.

**Typography**
- `text-[12px] text-oxford/55` — double violation: 12px is off the type scale (nearest: 13px = `type-body-sm`), and `/55` is off the opacity ladder (nearest: `/60`).
- `text-[13px] text-oxford/[0.35]` — 13px is `type-body-sm` ✓ but opacity `[0.35]` should be `/40` (ladder step).
- `text-[12px] text-oxford/70` — off-scale size, off-ladder opacity.
- `leading-relaxed` used — should be `leading-phi` or `leading-label`.
- `italic` text — not in the design system. Use opacity decrease instead to signal secondary status.
- `text-base` used inconsistently — should be explicit `type-body`.

**Spacing**
- `grid-cols-[minmax(0,200px)_1fr] gap-x-6 gap-y-1` — `gap-x-6` = 24px (not phi), `gap-y-1` = 4px (not phi). Should be `gap-x-phi-6` (34px) / `gap-y-phi-1` (3px) or `gap-phi-4` column gap.
- `gap-2 max-w-md` — arbitrary. Should be `gap-phi-2` / named max-width.
- `p-3` on thesis JSON viewer — 12px, should be `p-phi-3` (8px) or `p-phi-4` (13px).
- `min-h-[8rem] max-h-[min(20rem,40vh)]` — arbitrary height constraints. Use `min-h-phi-8` / `max-h-[40vh]` with a phi-based min.
- `flex flex-col gap-6` section wrapper — `gap-6` = 24px, should be `gap-phi-6` (34px) for section rhythm.

**Toggle button**
- `TOGGLE_TRACK` constant inlines background-color states via raw Tailwind arbitrary classes rather than referencing colour tokens.
- Toggle uses `rounded-full` — **direct design system violation** (all border-radius must be 0). Toggle pill shape breaks the flat institutional aesthetic.

**Inputs/Selects**
- `selectCls` / `inputCls` constants defined locally with mixed arbitrary sizes and spacing. No canonical input class pattern reused from design system.
- Focus state on selects: relies on browser default ring, not `focus:border-field-border-strong` from design system.

---

### `PanelShell.tsx`

**Generally compliant** but:
- Tab active state uses a bottom-border highlight — correct pattern — but the border colour is `border-oxford` (full opacity) rather than `border-oxford/80` (slightly subdued, per hierarchy).
- Header padding uses `px-phi-5 py-phi-4` ✓ — correct.
- Content slot has no padding applied by default; callers must add their own, leading to inconsistency across uses.

---

### `InvestmentMemoContent.tsx`

**Inline CSS-in-JS block (~400 lines)**
- The entire component uses a `<style>` tag injected into the memo frame. This is partially intentional (document renderer with print styles) but creates a parallel style system that diverges from the design tokens:
  - `font-size: 12px` used extensively — off the canonical scale (nearest: 13px).
  - `margin-bottom: 18px` — arbitrary (phi-4 = 13px, phi-5 = 21px).
  - `color: rgba(0,33,71,0.58)` — off-ladder (nearest: 0.60).
  - `letter-spacing: 0.11em` — should be `0.12em` (label token).
  - `gap: clamp(12px, 2.5vw, 20px)` — arbitrary clamp not on phi scale.
- The hardcoded hex `#002147` and `#F2F0EA` inside `<style>` should reference CSS variables (`var(--color-oxford)`, `var(--color-paper)`).

---

### `MainLayout.tsx`

*(Modified file — current state)*

**Navigation / sidebar**
- Navigation item active state uses a left-border accent (`border-l-2 border-oxford`) — `border-l-2` is 2px, design system mandates 1px borders.
- Sidebar width is hardcoded as `w-64` (256px) — should be expressed as `--col-sidebar` (38.2%) or a named layout variable.
- Top navigation bar height not aligned to phi scale — uses `h-14` (56px) which is between phi-7 (55px) ✓ and phi-8 (89px). Actually phi-7 = 55px is close, should use `h-[55px]` / `h-phi-7`.
- `gap-1` on nav items — should be `gap-phi-1` or `gap-phi-2`.
- `px-4 py-2` on nav links — `px-4` = 16px (off phi), `py-2` = 8px = phi-3 ✓. Should be `px-phi-5 py-phi-3`.

**Typography**
- Nav item labels: `text-sm font-medium` — should be `type-label-section` (mono, uppercase, tracked) for a terminal app or `type-body` for word-label links — not ambiguous `text-sm`.
- Page title in header: `text-lg font-semibold` — `text-lg` = 18px is off-scale. Should be `type-title` (23px) or `type-body` (14px) depending on context.

---

## Page / Layout Issues

### `HomePage.tsx` / `DashboardPreview`

**Typography**
- `text-[12px]` on "DIMENSION SCORES" label — off-scale (should be `type-label-section` = 11px).
- `tracking-[0.11em]` — should be `tracking-label` (0.12em).
- `text-[rgba(0,33,71,0.58)]` — not a token, not on opacity ladder (nearest: 0.60).
- `text-[rgba(0,33,71,0.55)]` — same issue.
- `font-mono text-base font-bold` — `text-base` = 16px off-scale. Should be explicit size class.
- `tracking-[0.03em]` — not a token. Design system has `tight` (-0.02), `label` (0.12), `tab` (0.14), `badge` (0.08). Remove or use nearest (`0` default).

**Spacing**
- `mb-[18px]` — arbitrary. Nearest phi steps: `phi-4` (13px) or `phi-5` (21px).
- `gap-x-0.5 gap-y-1` on dimension grid — arbitrary, not phi. Should be `gap-phi-1` / `gap-phi-2`.
- `sm:gap-x-2 sm:gap-y-2 md:gap-x-3` — escalating arbitrary breakpoint gaps, not phi.

---

### `RequestAccessPage.tsx`

*(Based on file size 15KB — substantial)*
- Likely contains form inputs without consistent input styling pattern.
- Marketing/landing page aesthetic may diverge from institutional app style if not carefully bounded.
- Needs direct audit once components are standardised.

---

### `App.tsx` / `LoadingAnimation`

- `LoadingAnimation` component: unknown — if it uses a spinner with `rounded-full`, this violates the design system. Loading state should be a skeleton shimmer (`skeleton-shimmer` class exists in CSS) not a circular spinner.

---

## Global Issues

### `index.css`

1. **Scrollbar thumb near-invisible**: `scrollbar-color: rgba(0, 33, 71, 0.06) transparent` — `0.06` is the hairline frame opacity, making the scrollbar invisible. Should be `rgba(0, 33, 71, 0.18)` (as defined in the canonical `:root` and used in later declarations in the same file — there is a **duplicate conflicting declaration**).

2. **Hardcoded `color: #002147`** on `body` and `h1–h6` — should be `color: var(--color-oxford)` or `text-oxford` to maintain single source of truth.

3. **`font-family` hardcoded** on `body` and `h1–h6` as `"Geist Sans", system-ui, ...` instead of `var(--font-sans)` — CSS variable exists for this.

4. **`scrollbar-color` conflicts**: two separate declarations in the file with different opacity values (0.06 vs 0.18). The first silently overrides correct behaviour.

### `tailwind.config.js`

5. **`font-sans` was `"Instrument Sans"`** (web marketing font) — now corrected to `"Geist Sans"`. However, any component that relied on `font-sans` class for Instrument Sans (unlikely in app context) needs verification.

6. **No `opacity` scale defined** for the canonical text hierarchy (100/80/60/40/25). Tailwind's built-in opacity modifier works but there's no enforcement. Custom `safeList` or documented constraint would prevent off-ladder values like `/55`, `/65`, `/70` proliferating.

### Cross-component

7. **Off-ladder opacities widespread**: `text-oxford/55`, `/65`, `/70`, `/90`, `/35`, `/50` appear across `SettingsPage`, `SystemIntelligence`, `WorkGrid`, `DashboardPreview`. The canonical ladder is `100 / 80 / 60 / 40 / 25` — everything else is a violation.

8. **Arbitrary `text-[Npx]` sizes**: `text-[15px]`, `text-[12px]`, `text-[13px]` (partially), `text-[11px]` used directly instead of `.type-*` utility classes. Off-scale sizes (12, 15) have no canonical equivalent.

9. **`style={{ fontFamily: ... }}` inline overrides** in SettingsPage (20+ instances). This is the single biggest maintenance debt in the codebase.

10. **`gap-*` / `p-*` not on phi scale**: Tailwind's default spacing scale (`gap-2` = 8px, `gap-4` = 16px, `gap-6` = 24px) is used throughout instead of the phi-scale tokens (`gap-phi-3` = 8px, `gap-phi-4` = 13px, `gap-phi-5` = 21px, `gap-phi-6` = 34px). The values are close enough to look acceptable but break the proportional system.

11. **`rounded-full` on toggle** in SettingsPage — the only known `border-radius ≠ 0` in the app. Violates the institutional flat rule.

12. **Missing `btn-interaction` class** on most buttons outside `SystemIntelligence`. The CSS class `.btn-interaction` exists and provides the canonical 150ms transition. Most buttons inline the transition properties instead, leading to inconsistent easing.

13. **`leading-relaxed` / `leading-loose`** used instead of `leading-phi`, `leading-label`, or `leading-title`.

14. **Framer Motion `staggerChildren`** on list items (WorkGrid) — not in the design system motion spec. All animations should be `opacity 0→1` only, `duration.short`, `motion.ease`. No translate, no stagger on data rows.

15. **`italic`** used in SettingsPage for secondary text — not part of the type system. Use opacity reduction to signal secondary status, not font style.
