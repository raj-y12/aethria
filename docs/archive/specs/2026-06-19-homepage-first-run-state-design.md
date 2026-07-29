# First-Run State on HomePage

**Date:** 2026-06-19  
**Scope:** Frontend only — `app-front-end/src/pages/HomePage.tsx`

---

## Problem

New users land on `HomePage` and see "The desk is clear" with an empty pipeline and no explanation. The fund mandate is the hard gate for all pipeline activity, but there is no prompt to set one up. `useFundReadiness` exists but is wired to nothing.

## Design

When `mandatePublished === false` (and the readiness check is not loading), `HomePage` renders a first-run variant instead of the normal four-door layout.

### First-run variant

Same editorial shell as the normal home screen:
- **Wordmark** — "Aethria." (unchanged)  
- **Eyebrow** — live date/time (unchanged)  
- **Headline** — "Define your mandate." (replaces the pipeline-status headline)  
- **Subline** — "Aethria won't scout or evaluate until a fund mandate is published." (replaces the pipeline counters)  
- **CTA** — a single `<Link to="/v1/settings">` styled like the existing footer meta-links ("Set mandate"), with the same `btn-interaction` pattern  
- **No nav doors** — the four workspace doors are hidden; they all lead to empty state anyway

### Loading / error behaviour

While the readiness check is in-flight (`loading === true`) or errored (`unknown === true`), the hook already defaults `mandatePublished: true`, so the normal home screen renders. No flicker, no false positive lockout.

### What doesn't change

- Backend: no changes required
- Settings/FundPage: no changes
- `useFundReadiness` hook: no changes (consumed as-is)
- Routing: no redirect, no hard gate

## Files changed

- `app-front-end/src/pages/HomePage.tsx` — import `useFundReadiness`, add conditional first-run branch
