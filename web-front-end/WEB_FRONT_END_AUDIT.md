# Web-front-end audit (marketing site)

Full scan of the marketing site against the app-front-end work we did. Goal: identify what should be updated for consistency, accuracy, and a single brand experience.

---

## What’s already aligned

- **Palette:** Oxford `#002147`, paper `#F2F0EA`, ivory `#fcfcfc`, charcoal `#2f333b` — matches app tokens.
- **Fonts:** Libre Baskerville (display), Inter (sans), Space Mono (mono) — same as app.
- **Border radius:** Tailwind `borderRadius: 0` — no rounded corners, matches app.
- **Scrollbars:** Thin, oxford thumb, transparent track — matches app index.css.
- **Motion:** Easing `cubic-bezier(0.16, 1, 0.3, 1)` used in animations — matches app tokens.
- **GrainOverlay:** Same pattern as app (noise texture); used on Home, Request Access, SystemAccess.
- **High-level copy:** Pipeline (Scout / Reviewer / Partner / Portfolio) and signal strip are still accurate; no product renames needed.

---

## Recommended updates

### 1. Input focus (match app behaviour)

**App change:** We removed the focus ring and “border change on focus” for all inputs (index.css + Settings + SystemIntelligence).

**Web today:**  
`index.css` has:

```css
.form-input-aethria:focus {
  border-bottom-color: rgba(0, 33, 71, 0.55);
}
```

So the border still gets darker on focus. There is no explicit focus ring (box-shadow), but the border change is the same kind of “border on click” we removed in the app.

**Recommendation:**  
- Keep the underline; remove the focus border change so it matches the app:  
  `.form-input-aethria:focus { border-bottom-color: rgba(0, 33, 71, 0.15); }` (same as default).  
- Optionally add explicit `outline: none; box-shadow: none` on `input:focus` / `textarea:focus` in the web base layer so no browser or global style adds a ring later.

**Files:** `web-front-end/src/index.css` (`.form-input-aethria`, and base `input`/`textarea` focus if desired).

---

### 2. Section divider opacity (optional)

**App:** Section dividers use a single frame opacity: `border-oxford/[0.06]` (and `frameBorder` in tokens).

**Web:** Uses mixed opacities: `rgba(0,33,71,0.08)` (pipeline border-t, hero strip), `0.1` (base `*` border-color), `0.12` (pipeline column line), `0.15` (form input border).

**Recommendation:**  
For a single “frame” language across app and marketing, use `rgba(0, 33, 71, 0.06)` for section dividers (e.g. pipeline strip `border-t`, pipeline column verticals, and the small horizontal line under pipeline labels). Leave form input at 0.15 if you prefer slightly more visible underlines there.

**Files:** `web-front-end/src/index.css`, `web-front-end/src/HomePage.tsx` (inline `borderTopColor`, `borderColor`, `backgroundColor` for dividers).

---

### 3. “Proceed to sign in” link target

**Web:** RequestAccessPage success links to:

```ts
href={APP_URL.replace(/\/$/, '') + '/dashboard'}
```

**App:** The app’s main route is `/v1` (and sign-in redirects to `/v1`). There is no `/dashboard` route; the dashboard is effectively the root of the app at `/v1`.

**Recommendation:**  
Point “Proceed to sign in” to the app’s real entry:  
`APP_URL.replace(/\/$/, '') + '/v1'` (or `/sign-in` if you want the sign-in page).  
Otherwise users may hit a 404 or an unexpected redirect.

**File:** `web-front-end/src/RequestAccessPage.tsx` (success block).

---

### 4. CustomCursor is unused

**Web:** `CustomCursor.tsx` exists but is not imported in `App.tsx`, `main.tsx`, or any page component. So the custom cursor is never rendered.

**Recommendation:**  
Either wire it into the root layout (e.g. in `App.tsx` or a layout used by Home and Request Access) or remove the component to avoid dead code. If you keep it, ensure it only enables for `(pointer: fine)` so touch devices don’t get a hidden default cursor.

**Files:** `web-front-end/src/components/CustomCursor.tsx`; `App.tsx` or layout if you add it.

---

### 5. SystemAccessPage status copy

**Web:** Status line is fixed: `INFRASTRUCTURE IN PREPARATION`.

If the product is now live or the message has changed (e.g. “Loading…”, “Redirecting…”), this can feel outdated.

**Recommendation:**  
Update the copy to match current product state, or make it configurable (e.g. env or props) so you can change it without code edits.

**File:** `web-front-end/src/components/SystemAccessPage.tsx` (and optionally `AnimatedRoutes` or env if you drive it from config).

---

## Not required (nice-to-have)

- **Typography scale:** Web uses ad-hoc font sizes and opacities; app uses a strict ladder (type-label-section, type-body, oxford 100/80/60/40/25). The marketing site can keep its editorial hierarchy; no change needed unless you want a shared design token file or doc.
- **Tailwind colours:** Web has `graphite`; app has `charcoal` in tokens. Same hex; naming difference only. Optional to align names if you ever share config.
- **Paper in Tailwind:** Web uses CSS var `--color-paper` in components; Tailwind doesn’t define `paper`. Fine as-is; add a `paper` colour in Tailwind only if you want to use it in utility classes.

---

## Summary

| Priority | Item | Action |
|----------|------|--------|
| High | Input focus | No border change on focus; optional no focus ring (match app). |
| High | “Proceed to sign in” | Link to `/v1` (or `/sign-in`), not `/dashboard`. |
| Medium | Section dividers | Use 0.06 for frame borders to match app. |
| Low | CustomCursor | Use in layout or remove. |
| Low | SystemAccess status | Update or make configurable. |

The marketing site is already close to the app in palette, type, and motion. The updates above bring focus behaviour and link targets in line with the app and tidy consistency and dead code.
