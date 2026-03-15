# Critical audit: app-front-end

Unsparing audit of the entire app-front-end. Goal: identify what is working against the product and what is missing that would make it significantly stronger. Not a catalogue — actionable problems and gaps.

---

## 1. What is working against the product

### Typography and brand consistency

- **Hero font + bold:** `type-hero` (Libre Baskerville) is used with `font-bold` on the dashboard (MainLayout), Settings, and Login. Libre Baskerville is a serif; the font stack may not include a bold weight (only 400/700 are loaded in index.css). Either the bold has no effect or the browser is faking it. **Recommendation:** Use `type-hero text-oxford` without `font-bold`, or load a real bold weight and use it explicitly.
- **Mobile wordmark is not the hero font:** MobileHeader uses `type-title font-bold text-ivory` for "Aethria", so on mobile the product name is Inter (24px), not Libre Baskerville. Desktop uses the hero wordmark; mobile does not. **Recommendation:** Use `type-hero text-ivory` (or equivalent) in MobileHeader so the wordmark is consistent.
- **Inline style overrides token:** InvestmentMemoContent uses `style={{ fontSize: '14px' }}` on the judgment paragraph even though `type-body` is already 14px in the design system. Redundant and bypasses the single source of truth. **Recommendation:** Remove the inline style and rely on `type-body`.

### Layout and structure

- **SystemBar bottom gap is magic number:** `bottom-4` (1rem) leaves a strip of paper visible below the spine. There is no documented reason for this; it can look like a mistake. **Recommendation:** Either remove the gap and make the bar full-height, or document it (e.g. "footer clearance") and align with a token.
- **Nested flex/grid in MainLayout:** The main content area uses three nested flex/grid wrappers (`flex-1 flex flex-col`, then `lg:grid lg:grid-cols-[3fr_2fr]`, then two flex columns). Hard to reason about min-height and overflow. **Recommendation:** Consider flattening to a single grid for desktop or documenting the overflow contract (which div scrolls, which is flex-none) in a comment.
- **Right panel “empty” state is easy to miss:** When no panel is selected, the aside shows “Click a deal to open the memo here” in very low contrast (`text-oxford/25`). On a wide desktop the right column is large and that line is visually weak. **Recommendation:** Stronger visual hierarchy (e.g. a light rule, slightly larger or bolder copy, or a minimal illustration) so the CTA is obvious.

### Data and loading

- **No error surface for pipeline data:** `useSystemData` and `usePoll` swallow errors (`.catch(() => {})`). If startups, escalations, or settings fail, the UI shows empty arrays / null and the user gets no explanation. **Recommendation:** Expose at least a global or per-resource error (e.g. “Couldn’t load pipeline”) and show a non-blocking banner or inline message with retry.
- **Settings fetches settings + system-health in parallel:** `fetchSettings()` in the API merges `/api/settings` and `/api/analytics/system-health`. If one fails, the whole promise rejects. Health could be optional so the settings form still loads. **Recommendation:** Catch system-health failure and merge a default so Settings always renders when `/api/settings` succeeds.
- **Poll intervals are fixed:** 12s startups, 30s escalations, 60s signals/meta/settings, 300s analytics. There is no refetch-on-focus or faster poll when the tab is active. **Recommendation:** Consider refetch on window focus and/or shorter interval when tab is visible for key resources (e.g. startups, escalations).

### Accessibility and interaction

- **WorkGrid rows are focusable but not keyboard-navigable as a list:** Each row is `role="button"` and has Tab/Enter/Space, but there is no arrow-key navigation between rows. For long lists, keyboard users must tab through every row. **Recommendation:** Add arrow-up/arrow-down (and optionally Home/End) to move focus between rows and treat Enter/Space as click.
- **Escalation resolve has no loading or error feedback:** EscalationCard calls `resolveEscalation` and then animates out. If the request fails, the catch is silent and the card stays in “Confirm” state with no message. **Recommendation:** Show a brief “Failed to resolve” (and optionally retry) or at least set local error state and display it.
- **Modal memo: clicking backdrop closes without confirmation:** InvestmentMemo (full-screen modal) uses `onClick={onClose}` on the backdrop. Accidental click loses context with no undo. **Recommendation:** Either add a “Discard?” confirm for dirty state or keep current behavior but ensure the panel memo is the primary path so modal is only for small screens.

### Copy and semantics

- **“Judgements” vs “Judgments”:** The product uses British “Judgements” in the UI. If the audience is mixed, consider “Judgments” for US or make the spelling consistent and intentional everywhere.
- **SystemBar nav says “Settings” but Settings page nav says “Home”:** SystemBar’s nav link goes to `/settings` with label “Settings”. From Settings, the link is “Home” to `/`. That’s correct but the dashboard doesn’t show a “Home” or “Overview” in the bar; only Settings. **Recommendation:** Minor; document or add “Overview” in the spine if you want symmetry.
- **Empty state in Escalations tab is not the shared EmptyState:** EscalationsTab shows “No pending escalations” as a plain `<p>`, not the shared EmptyState component. Inconsistent with Signals, Analytics, Meta. **Recommendation:** Use EmptyState with a short line (e.g. “No deals need your decision right now.”) for consistency.

### Code and maintainability

- **PanelSkeleton is unused:** PanelSkeleton (and its variants) are never imported after reverting panel-level skeletons. Dead code. **Recommendation:** Remove the file or reintroduce skeletons for a specific loading scenario.
- **verdictTint is unused:** `verdictTextClass` in verdictTint.ts is not imported anywhere. Dead code. **Recommendation:** Remove or use (e.g. for a verdict strip or feed).
- **Duplicate API_BASE and env handling:** Each API file (settings, agents, etc.) defines `API_BASE` from `import.meta.env.VITE_API_URL`. Centralize in one place (e.g. `api/config.ts`) and import. **Recommendation:** Single source for base URL and any env-derived config.
- **LoginPage uses inline styles and a scoped `<style>` tag:** Placeholder and layout use inline styles and a string template for `[data-login-page] input::placeholder`. Harder to keep in sync with design tokens. **Recommendation:** Move to Tailwind/classes and token-based values where possible.
- **MainLayout passes `startupsError` in props but it is never set by the parent:** App.tsx renders `<MainLayout data={systemData} />` with no `startupsError`. The error banner exists but is never triggered from the current data flow. **Recommendation:** Either wire a real error from useSystemData (or a wrapper) or remove the prop and banner until you have a source.

### Visual and motion

- **Confidence bar in WorkGrid is not a progress bar:** The “confidence” strip uses a `<span>` with inline `width` for the fill, but the parent is `w-10 h-0.5` and the inner span has `block h-full` and no explicit height. May not render as intended in all browsers. **Recommendation:** Use a proper two-element bar (track + fill) with explicit heights and widths (e.g. like BarFill in SystemIntelligence).
- **GhostTransition is not used with AnimatePresence:** WorkGrid wraps children in GhostTransition (single motion.div). List additions/removals don’t get exit animations because there’s no AnimatePresence. **Recommendation:** If you want list exit/enter, wrap in AnimatePresence and give items stable keys; otherwise remove GhostTransition or document that it’s entrance-only.
- **LoadingAnimation uses a different ease than tokens:** LoadingAnimation uses `EASE = [0.33, 0, 0.67, 1]`; tokens use `[0.16, 1, 0.3, 1]`. Motion feels inconsistent with the rest of the app. **Recommendation:** Use `tokens.motion.ease` (or the same cubic-bezier) for the loader.

---

## 2. What is missing that would make the product significantly stronger

### Orientation and trust

- **No explicit “last updated” for the pipeline:** The status strip shows counts but not when data was last fetched. Users can’t tell if the numbers are stale. **Recommendation:** A “Updated Xs ago” or “Refreshed at HH:MM” (from the last successful poll) in the status strip or as a tooltip.
- **No way to manually refresh:** If polling is slow or failed, there is no “Refresh” control. **Recommendation:** A refresh button (or pull-to-refresh on mobile) that triggers an immediate fetch for startups (and optionally escalations).
- **Agent trigger is invisible:** App.tsx calls `triggerAgents()` once on mount. The user never sees that the pipeline was triggered or that it’s queued. **Recommendation:** A one-time toast or status line (“Pipeline run queued”) or surface agent status (e.g. from `/api/agents/status`) in the dashboard or Settings.

### Escalations and decisions

- **Escalations are only visible in System:** The status strip shows the count, but there is no direct link “X escalations” → open System and select Escalations tab. **Recommendation:** Make the escalation count (or a small “Review” link) open the System panel with the Escalations tab active.
- **No notification or badge when a new deal is escalated:** New escalations appear only when the user looks at the strip or opens System. **Recommendation:** Optional browser notification or a brief in-app cue when `pending_escalations` increases (e.g. after a poll).

### Memo and PDF

- **Memo has no “last updated” or version:** The memo shows prompt_version at the bottom but no “Generated at” or “Data as of” that would help with auditability. **Recommendation:** Add a timestamp (e.g. “Pipeline data as of …”) and ensure it’s in the PDF export.
- **PDF export has no fund identity:** The generated PDF doesn’t include fund name / stage / geography. For an investor memo, that’s a missed branding and context. **Recommendation:** If fund_identity is set, add a one-line header or footer in the PDF (and optionally in the on-screen memo).

### Settings and configuration

- **Fund identity has no preview on Settings:** You edit fund name, stage, geographic focus but don’t see how the dashboard line will look until you go back. **Recommendation:** A live preview line (e.g. “Hermes Capital · Seed–Series A · Europe”) in the Fund identity section.
- **No validation feedback before Save:** Settings can be invalid (e.g. confidence outside 0–1). Validation runs on PATCH; the user only sees errors after clicking Save. **Recommendation:** Inline validation on blur or on change for numeric/required fields so errors appear before submit.
- **Meta-agent tab appears/disappears based on backend:** If `meta_agent` is null, the tab is hidden and `activeTab` is switched to budget. The tab order and default tab change dynamically, which can be disorienting. **Recommendation:** Keep a stable tab order (e.g. always show Meta-agent but show an “Not configured” empty state when null), or clearly document that the tab is environment-dependent.

### Mobile and responsiveness

- **Mobile menu doesn’t show pipeline summary:** On desktop the status strip shows companies, decided, unreviewed, etc. On mobile, the dropdown only has Judgements / System / Settings and no pipeline summary. **Recommendation:** Add a compact one-line summary (e.g. “X companies · Y escalations”) in the mobile menu or in the header so mobile users get the same signal.
- **No tablet-optimized layout:** The breakpoint is lg (1024px). Between ~768 and 1024 the layout is the same as small mobile (single column, overlay panels). **Recommendation:** Consider a layout that uses the right panel as a side sheet (e.g. 40% width) on md/lg instead of full overlay.

### Performance and resilience

- **No request deduplication:** If multiple components trigger the same fetch (e.g. settings used by MainLayout and SettingsPage), each can fire its own request. useSystemData is the single consumer for dashboard; Settings has its own fetch. **Recommendation:** Shared cache or SWR-style hook for settings so dashboard and Settings share one source of truth and avoid duplicate calls when navigating.
- **Fonts block render:** index.css loads Google Fonts via `@import`. That can block first paint. **Recommendation:** Preload critical fonts in index.html and/or use font-display: swap and local fallbacks so text is visible immediately.

### Security and auth

- **No session expiry or idle handling:** useIdleTimeout exists but is not used in App or MainLayout. Long-open tabs never log out. **Recommendation:** Use idle timeout to show a “Session expiring” modal or to sign out after a configured period of inactivity, especially for shared machines.
- **Clerk token readiness has a 5s fallback:** If getToken() never resolves, tokenReady is set true after 5 seconds so the app doesn’t hang. The user might then hit 401s on API calls. **Recommendation:** After the fallback, show a non-blocking message (“Having trouble connecting. Retry or sign out.”) or trigger a retry for the token.

---

## 3. Summary

| Category | Working against | Missing |
|----------|------------------|--------|
| **Typography / brand** | Hero+bold inconsistency; mobile wordmark not hero; inline style override | — |
| **Layout** | Magic-number bar gap; nested overflow; weak empty right-panel CTA | — |
| **Data / loading** | Silent poll errors; settings merge fails all if health fails; fixed polls | Refetch on focus; error + retry UI; optional health |
| **A11y / interaction** | No list keyboard nav in WorkGrid; silent escalation resolve failure; modal close on backdrop | — |
| **Copy / semantics** | Judgements spelling; Escalations empty state not shared component | — |
| **Code** | Dead PanelSkeleton, verdictTint; scattered API_BASE; unused startupsError | Central config; wire or remove error |
| **Visual / motion** | Confidence bar markup; GhostTransition without exit; loader ease ≠ tokens | — |
| **Trust / orientation** | — | Last updated; manual refresh; agent trigger feedback |
| **Escalations** | — | Link from count to Escalations tab; new-escalation cue |
| **Memo / PDF** | — | Timestamp/version; fund identity in PDF |
| **Settings** | — | Fund identity preview; inline validation; stable meta tab |
| **Mobile** | — | Pipeline summary in menu; optional tablet layout |
| **Performance** | — | Shared settings cache; font loading strategy |
| **Auth** | — | Idle timeout; post-fallback token message |

This audit should be used to prioritise fixes and product improvements, not implemented in one pass.
