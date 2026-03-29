<!--
  Audit artifact: documents pre-fix inconsistencies in app-front-end (2026-03-29).
  Fixes applied in-repo; keep this file as the historical checklist.
-->

# Aethria — Full app design audit (app-front-end)

This document records inconsistencies found against the enforced system:

- **Fonts:** Geist (company names, verdicts, prominent UI labels); IBM Plex Sans (body, reasoning, descriptions); Space Mono (metadata, scores, section labels, badges, stats, actions); Libre Baskerville (Aethria wordmark only).
- **Colours:** `#002147`, `#F2F0EA`, `#FFFFFF` (memo surfaces only), `#7D2B3A` (escalations only), plus opacity variants of oxford.
- **Radius:** zero everywhere.
- **Line height:** 1.5 for UI labels; 1.6 for body/reasoning; 1.4 permitted where needed for tight display lines.
- **Space Mono letter-spacing:** 0.08em–0.14em only.

## 1. Typography — font families

| Location | Issue |
|----------|--------|
| `index.css` | Body and headings use **Inter**; canonical spec uses **IBM Plex Sans** for body. |
| `index.css` | **Geist** not loaded while components (e.g. `WorkGrid`, `SystemIntelligence`) reference it inline. |
| `design-system/tokens.ts` | `font.body` set to Inter. |
| `InvestmentMemoContent.tsx` (inline `<style>`) | **IBM Plex Serif** used for `.memoCompany`, `.memoVerdict`, `.memoEmptyWordmark` — disallowed; company/verdict → **Geist**; empty-state wordmark → **Libre Baskerville** only. |
| Stack fallbacks | Long stacks include `Roboto`, `Georgia`, etc. as system fallbacks only (acceptable); primary faces corrected above. |

## 2. Typography — line heights (not 1.4 / 1.5 / 1.6)

| Location | Issue |
|----------|--------|
| `index.css` `.type-hero` | `line-height: 1` |
| `index.css` `.type-title` | `line-height: 1.2` |
| `index.css` `.type-label-section`, `.type-label-tab`, `.type-meta` | `line-height: 1.2` (UI labels → target **1.5**) |
| `index.css` `.type-body-sm` | `line-height: 1.5` (body tier → **1.6** per spec) |
| `InvestmentMemoContent.tsx` | Multiple rules: 1.12, 1.18, 1.05, 1.65, 1, 1.2, 1.4, etc. |
| `SignalEventRow`, `EmptyState`, `SystemIntelligence`, `SettingsPage` | `leading-relaxed` (≈1.625) or `leading-snug` / `leading-tight` / `leading-none` on UI/body |
| `WorkGrid.tsx` | `leading-tight`, `leading-none` on names, meta, badges |
| `DecisionBadge.tsx` | `leading-none` on badges |
| `MainLayout.tsx` | Wordmark `leading-none` |
| `SystemBar.tsx` | `leading-none` on clock |

## 3. Space Mono — letter-spacing

| Location | Issue |
|----------|--------|
| `index.css` `.type-label-section` | `0.16em` (above **0.14em** max) |
| `index.css` `.type-label-tab` | `0.18em` |
| `index.css` `.type-meta` | `0.22em` |
| `index.css` Clerk `.cl-formButtonPrimary` | `0.16em` |
| `design-system/tokens.ts` | Documents 0.16em / 0.18em / 0.22em — misaligned with 0.08–0.14em rule |
| `WorkGrid.tsx` `GRID_BADGE_SHELL` | `tracking-normal` (0) for uppercase mono labels |
| `EmptyState.tsx` | `tracking-wider` on label (additive to utility tracking) |
| `InvestmentMemoContent.tsx` | `.memoScoreBandLabel` `0.04em` (below **0.08em** floor) |
| `InvestmentMemoContent.tsx` | `.memoVerdict` `0.04em` on serif (verdict → Geist; spacing adjusted) |

## 4. Colours outside approved set

| Location | Issue |
|----------|--------|
| Tailwind theme | `ivory`, `charcoal`, `bone`, `warning` (`#F5F0E8`), etc. — **ivory** (`#fcfcfc`) and **warning** not in the reduced whitelist. |
| `MainLayout.tsx`, `SystemBar.tsx`, `SettingsPage.tsx`, `MobileHeader.tsx`, `verdictTint.ts` | `text-ivory/*` on oxford chrome → align with **`text-white`** (`#FFFFFF`) per memo/chrome contrast rule. |
| `MainLayout.tsx`, `SettingsPage.tsx` | `bg-warning` / `border-oxford/25` strip → **`bg-paper`** to drop non-whitelist fill (`#F5F0E8`). |
| `InvestmentMemoContent.tsx` | Memo shell backgrounds **`#F2F0EA`** → spec reserves **`#FFFFFF`** for memo panel. |
| `InvestmentMemo.tsx` | Modal backdrop / container used paper; **memo modal → white** surfaces. |
| `DecisionBadge.tsx` (escalation) | `text-[#F2F0EA]` on burgundy → **`text-white`** for allowed light text. |

## 5. Border radius ≠ 0

| Location | Issue |
|----------|--------|
| `WorkGrid.tsx` | Escalation dot `rounded-full` |
| `MainLayout.tsx` | Status strip dot `rounded-full` |
| `LoadingAnimation.tsx` | Orbit points `rounded-full` |
| `SettingsPage.tsx` | Toggle track and knob `rounded-full`; knob `shadow-sm` |

## 6. Font sizes — one-offs / drift

| Location | Note |
|----------|------|
| `MainLayout.tsx` | Wordmark `text-[20px]` vs `.type-hero` / `.type-title` scale — kept deliberate for nav; uses display font. |
| `SystemIntelligence.tsx` | Ad hoc `13px` sector line vs `type-body-sm` 13px — aligned via line-height only. |
| `InvestmentMemoContent.tsx` | Rich memo scale (22px company, 28px verdict, etc.) — font families fixed; line-heights normalized. |

## 7. Padding / spacing (relative inconsistencies)

| Location | Note |
|----------|------|
| `SignalEventRow` | `py-2.5` (10px) vs grid `py-3` (12px) — minor; left as-is to avoid layout shift unless paired rows look off. |
| Memo inline CSS | Mix of 8px, 16px, 18px, 20px gaps — documented only; no global spacing token change requested. |

## 8. Clerk / third-party (`index.css`)

| Issue | Fix direction |
|--------|----------------|
| Inter on `.cl-*` and profile | **IBM Plex Sans** to match app body. |
| Primary button letter-spacing 0.16em | **0.14em** cap. |

## 9. Resolution summary

All items above were addressed in **app-front-end** via targeted updates to:

- `src/index.css` (fonts, type utilities, Clerk, `:root` warning bg)
- `tailwind.config.js` (`fontFamily.sans` / `body` → IBM Plex Sans)
- `src/design-system/tokens.ts` (font + type metadata; `warningBg` aligned to paper `#F2F0EA`)
- Components listed in the tables (className / inline style / `<style>` blocks only)

**Out of scope:** `backend/`, API modules, routing, auth, hooks logic, and non-visual code paths.
