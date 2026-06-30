# Marketing site — "The Observatory" art direction

**Date:** 2026-06-30
**Surface:** `web-front-end` (public marketing site + `/request-access`)
**Status:** design locked, pending spec review → implementation plan
**Supersedes:** the home-page direction in `2026-06-22-marketing-editorial-rebuild-design.md` (that rebuild shipped; this is the next art-direction layer over it). Tokens, fonts, and "no rounded corners" rule carry forward unchanged.

## Why

The current site is a competent continuous-paper editorial scroll, but the user finds it understated and not memorable, and the two genuinely under-built surfaces — the nav and the `/request-access` page — read as weak. Goal: make the marketing site feel like an elite studio built it (Awwwards-tier), while staying informative — a cold visitor must grasp the level Aethria operates at, what it does, how, and who it's for, within seconds.

## The organizing concept (locked)

**The Observatory / Instrument.** Aethria is a precision instrument trained on the private markets; the market is a live plotted field, and the site is its readout. This is the one concept the whole site hangs on (cf. Tresmares' "Pico Tres"). It is also the legitimate, premium form of the "dark map-grid" aesthetic the user was originally drawn to — the grid plots *real evaluations* (companies scored against the fund thesis), so it reads as intelligence, not decoration.

Concepts considered and rejected: **The Record/Dossier** (the output, slightly passive) and **The Tribunal** (strong but narrower — folds in as a *section*, the reviewer-disagreement beat, rather than the whole-site frame).

## Treatment (locked)

- **Warm paper is the dominant ground**, cohesive with the product app. Palette unchanged: paper `#F4F1EA`, oxford `#001433`, accent green `#3d6b5e` (brightened to `#5b9b8a`/`#7bbfac` on dark).
- **Exactly one full-bleed dark "Observatory field" movement** inside the scroll — the dramatic instrument beat. Not zebra-striping; a single deliberate inversion. The visitor arrives on paper → drops into the dark instrument → resolves back to paper.
- Fonts unchanged: Playfair Display (display/serif), Space Mono (labels/telemetry/numerals), Figtree (body, weight 300–500). No new fonts. No rounded corners.

## Validated prototypes (visual source of truth)

Built and screenshot-verified at 1440×900:
- `_design-explore/D-observatory-light.html` — the paper hero (dominant ground).
- `_design-explore/D-observatory-dark.html` — the dark field movement treatment.

The hero composition, type scale, radar/instrument graphic, telemetry, eyebrow, and CTA in those files are the reference the build matches. Implementation ports them into the existing React/Tailwind `web-front-end` using existing components where possible.

## Craft rules (from `high-end-visual-design`, filtered to Aethria)

Adopt: macro-whitespace (section padding `clamp(4rem,12vh,9rem)`+), custom cubic-bezier motion (`cubic-bezier(0.32,0.72,0,1)`), staggered scroll-reveal entries (`IntersectionObserver`/Framer `whileInView`, never scroll listeners), magnetic CTA physics, film-grain on a fixed `pointer-events:none` layer, GPU-safe animation (`transform`/`opacity` only).
Reject (fights the brand): glassmorphism, squircle/`rounded-full` pills, drop shadows, edge-to-edge generic navbars. The eyebrow is a hairline+mono label, not a pill.

## Reference techniques baked in

- **Tresmares Capital** — single-accent discipline (green used sparingly, large when it lands); a map/field as the signature graphic; institutional restraint.
- **Sui** — one signature animated graphic carrying the page; punchy declarative tagline.
- **Sakazuki** — invitation-only luxury tone; one dark dramatic movement; custom art direction (no stock photography).
- **Invoko** — custom data-art, scroll-sequenced reveals.

## Page architecture (light, with one dark movement)

Mostly an art-direction + clarity reframe over existing sections. New work is marked **[NEW]**; reuse is marked **[REUSE]**.

1. **Hero — the instrument [NEW]** *(prototype: D-observatory-light)*. Mono eyebrow (`— THE INSTRUMENT · PRIVATE MARKETS`), serif H1 `A precision instrument for private markets.` (accent-green italic climax word), one concrete subline, a `See what falls inside your thesis →` underline-CTA, and a quiet telemetry block (`12,408 scanned / 03 in thesis`). The radar/field sits subtle on paper behind the lead. Replaces the current `01 — The thesis engine` hero.

2. **What / How / Who [NEW]**. A hairline-divided editorial triad answering the three cold-visitor questions in one glance (what it does / how it works / who it's for). Concrete, not vague.

3. **The Observatory field — THE DARK MOVEMENT [NEW]** *(prototype: D-observatory-dark)*. Full-bleed oxford section. The `IntelligenceMap` is reframed here as the instrument: a plotted field of companies, most faint ("out of thesis"), a few green ("in thesis"), one locked under the reticle, the pipeline (scouts → review → partner → record) shown as the instrument's mechanism. Scroll-scrubbed draw-on + rotating sweep + lock-ping. This is the single inversion and the signature wow. Folds in the *meta-agent* as the dashed feedback edge.

4. **The mandate [REUSE]**. Existing `#mandate` `MandateCard` (paper) + "It only looks for what you tell it to." Reframed copy to tie to the instrument ("calibration": the thesis is what the instrument is tuned to).

5. **How the judgment is formed [REUSE/reframe]**. Existing `PipelineSection`, reframed as the instrument's method: "Four scouts source it. Three reviewers argue it. One partner rules." Preserves the reviewer-disagreement idea (the Tribunal beat folded in).

6. **The record it produces [REUSE]**. `DashboardPreview` — the full-bleed product slice, unchanged structurally, copy tightened to "what one reading produces."

7. **Reviewer disagreement [REUSE]**. `ReviewDisagreement` (paper) — the preserved dissent.

8. **On-demand lookup [REUSE]**. Existing `#lookup` section + `LookupCommandBar`/`LookupResultSnapshot` — "point the instrument at any company."

9. **Closing CTA + `NewsletterBand` + footer [REUSE]**. Copy tightened.

## Nav rebuild — `SiteHeader.tsx` [NEW]

The current header is a wordmark + three plain mono text links with no CTA. Rebuild:
- Keep the wordmark (`Aethria.` with green dot).
- Section links in mono caps (`Instrument / Field / Record`, or keep `Mandate / Pipeline / Product` — decide in plan).
- Add a real **`Request access`** CTA: bordered rectangle (no pill), oxford-fill-on-hover, **magnetic hover** micro-interaction.
- **Cut** any "system active" live indicator — it reads as gimmick.
- Backdrop: paper gradient fade + blur (already present). Adopt this same header on `/request-access` (see below).

## Request-access rebuild — `RequestAccessPage.tsx` [NEW]

Today it's a lonely centered form on blank paper with its own bespoke header (and a `DeskClock`). Rebuild:
- **Adopt the shared `SiteHeader`** (with a `backTo` link); delete the bespoke header.
- **Two-column** layout: the form on the left; on the right a quiet **instrument-calibration panel** — a compact static Observatory readout + one serif pull-quote ("Every decision arrives with the evidence already attached.") framed as "what you're calibrating access to."
- **No ticking counters / dashboard gimmicks.** The right panel is art direction + one or two static, true facts, not a fake live dashboard.
- Keep all existing form logic, validation, success/processing states, and the `/api/waitlist` POST exactly as-is — this is a presentation rebuild only.

## Warmth levers (locked: color + texture + micro-interactions; NOT voice)

- **Color** — extend accent green beyond headline italics to: the eyebrow tick, telemetry numerals, the in-thesis nodes + reticle, the `accent-link` underline draw-in. Single-accent discipline; no second hue. (Optional ochre "stamp" tone is **dropped** — keep the two-color discipline of the references.)
- **Texture** — `GrainOverlay` (have it), `RotatingSeal` (have it; the seal can live in the footer or a quiet hero corner), mono ledger/telemetry stamps, hairline rules. `DeskClock` retired from the access page (it read as filler).
- **Micro-interactions** — magnetic `Request access` CTA; cursor-reactive reticle/nodes on the dark field; the radar sweep + lock-ping; `accent-link` underline draw-in; subtle hover-lift on cards/rows; staggered fade-up-from-blur scroll entries. All `transform`/`opacity` only.

## Motion spec

- Smooth scroll: existing **Lenis** (`window.__lenis`) stays; honor `SITE_HEADER_SCROLL_OFFSET`.
- Scroll reveals: existing `ScrollReveal` / Framer `whileInView`, never `addEventListener('scroll')`.
- Dark-field draw-on: existing GSAP + `ScrollTrigger` in `IntelligenceMap` (already used) — extend for the scrub + sweep + reticle.
- `prefers-reduced-motion`: all motion gates off (existing `useReducedMotion` pattern); the radar renders static, no sweep/ping/drift.

## Explicitly cut

- The blinking `System active` / live indicator.
- Ticking "live counters" on the access page (read as fake dashboard).
- Micro-interactions that only wiggle. Motion must serve the instrument metaphor or be cut.

## Out of scope

- No new fonts, no rounded corners, no palette/token changes (accent green + paper + oxford only).
- No backend, auth, routing, or `/api/waitlist` changes.
- Not rebuilding the `@aethria/product-chrome` demo components (`MandateCard`, `LookupCommandBar`, `DashboardPreview` internals, `LookupResultSnapshot`) — reuse as-is, reframe surrounding copy/layout only.
- App (`app-front-end`) is untouched; it stays paper. The dark movement is a marketing-only beat.

## Verification

- Build each surface and screenshot-verify at 1440×900 and mobile (`375`) via the local-server + Playwright loop already used for the prototypes (serve `web-front-end` dev server; navigate; screenshot; compare to `_design-explore/D-observatory-*.html`).
- `npm run build` + typecheck clean (no TS/import regressions).
- `prefers-reduced-motion` renders static and legible.
- Manual scroll review by the user against the prototypes.

## Open decisions for the plan

1. Nav link labels: `Instrument / Field / Record` (concept-true) vs. keep `Mandate / Pipeline / Product` (literal). Lean concept-true.
2. Whether the dark field movement *absorbs* the existing `PipelineSection` (one combined dark beat) or sits adjacent to a paper pipeline section. Lean absorb, to keep exactly one dark movement.
