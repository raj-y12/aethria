# Web Front-End — The Gallery of Instruments

**Date:** 2026-07-23 (direction revised same day after mockup review)
**Scope:** `web-front-end/` (public marketing site only). No changes to `app-front-end/` or backend.
**Supersedes the composition of:** `2026-06-22-marketing-editorial-rebuild`, `2026-06-30-marketing-observatory`.
**Approved mockup:** `_design-explore/J-gallery-instruments.html` (the visual source of truth; `I-living-broadsheet.html` was the rejected first swing — kept for reference only).

---

## 1. Why

The current site is an *airy editorial brand site* dressed as a newspaper. It's competent but reads as AI-made and — with its warm cream stock, Playfair, and one-idea-per-section rhythm — indistinguishable from a template. The goal: a gallery-grade site that signals Aethria's level so a VC inquires on sight, grounded entirely in what the app really does.

## 2. The idea — "a gallery of instruments"

A photography gallery where **every "photograph" is a mark the machine draws.** Cool architectural stock, huge negative space, a central spine of framed *plates*, marginal editorial furniture. The reference DNA:
- **Izanami** → atmosphere: a quiet statement floating in space, film grain, live dual-bureau clocks, calm.
- **Obys** → structure: a central vertical spine of plates in wide empty margins, the centered plate framed in `[ ]` brackets, index/caption rails pinned to the margins.
- **Dieter Rams** → restraint: near-monochrome, honest labels, grid discipline, "as little design as possible."

The mechanic that makes a VC inquire: the front page *is* the product — instruments the system produces, given the room of gallery plates.

## 3. Design language

### Color — new
- **Stock:** `#D9D7D4` (cool architectural grey) — replaces warm cream `#f4f1ea`. This is the defining shift; reads gallery/concrete, not cozy paper.
- **Ink:** near-oxford `#111820` (softened for the grey stock).
- **Accent:** verdigris `#3d6b5e` demoted to a **whisper** — a single bracket, the map hits, the verdict outline, the wordmark dot. Never a coloured label.
- **Grain:** a fixed film-grain overlay (SVG `feTurbulence`, low opacity, `multiply`) — the anti-flat texture. Kills the "flat AI gradient" read.
- No dark OS theme. No warm cream. (Reverses the prior marketing specs' palette.)

### Typography — **Playfair stays** (reverses the earlier "off-Playfair" call; user overrode it)
- **Display / statements / plate numerals:** `Playfair Display` — used the Izanami way: quiet, large, roman, with air. NOT busy headline blocks.
- **Marginalia / UI:** `Instrument Sans` (grotesque).
- **Data / clocks / plate numbers / captions-mono:** `Space Mono`.
- Self-hosted via `@fontsource` (SEO/LCP) — drop the Google-CDN `<link>`.

### Hard "no-slop" rules (user-specified)
- **No gratuitous italics.** Statements are roman. Italic is allowed only for a true editorial convention (e.g. a cited publication name), never for emphasis colour.
- **No "Scroll" cue and no animated scroll line.** Removed from the hero entirely.
- No decorative fade-up-on-everything (see motion).

### Motion — diegetic, Izanami/Obys-grade, all `prefers-reduced-motion` safe
Ambitious but purposeful — "go crazy" within restraint:
- Film grain sits static (or barely breathes).
- Plates reveal as they enter: bracket marks draw in, caption text sets, the instrument animates.
- **Instruments animate diegetically:** dot map assembles + scout arcs fire + verdigris spreads (existing `DottedMarketMap`); record figures **set** (count-up); the wire **typesets**; the query line types.
- Live dual-bureau clocks tick (London / San Francisco).
- Edition number advances by day-of-year; dateline is today.
- Optional custom cursor / kinetic statement settle — additive, reduced-motion safe.
- **Explicitly NOT:** a scroll cue, an animated hero line, or random italic emphasis.

## 4. Composition — the plate spine

- **Fixed marginal furniture:** wordmark (top-left), nav/index (top-right), live clocks + edition (bottom corners), plus per-plate vertical caption rails and plate numbers (`01 — N`). This *replaces* the big dark centered masthead.
- **Hero:** Izanami-calm — a faint dot-map echo field under a single quiet Playfair statement + mono kicker. No scroll cue.
- **Gallery:** a central spine of plates (max-width ~860px) in wide margins; each plate is bracket-framed when centered, has a plate head (title + number), the instrument, and a caption. Massive vertical rhythm.
- **Colophon:** Rams furniture — typefaces set, bureaus, edition, © .

Each plate is a distinct instrument (fixes the repeated-template tell structurally).

## 5. Content — preserve the real copy (hard rule)

**Carry over the app-grounded content already written in `src/HomePage.tsx` and the section components** — change the vessel, not the claims. Nothing invented or exaggerated.

Real content that must survive the redesign:
- **Lede:** "Private-market judgment, on the record." + "Aethria reads the open web for companies, scores each one against your fund's thesis, keeps the record where its reviewers disagree, and files an investment-ready brief for every name it surfaces."
- **The four scouts:** market-driven, builder/technical, pain-point, contrarian — working the live web, never a static list.
- **Three reviewer modes** built to disagree (Default / Skeptical / Opportunist); the partner engine rules INVEST / PASS / MONITOR; splits stay on the record, never averaged.
- **Reviewer dimensions (real):** Market, Product, Technical, Execution, Defensibility (1–10). Specimen record scores 9/8/9/8/7.
- **Mandate:** the thesis as a hard constraint ("It only looks for what you tell it to.").
- **On-demand lookup**, **portfolio** (post-INVEST watch), **meta-agent** (revises its own prompts/weights).
- **Closing:** "For funds that need judgment with memory." / evidence trail, "not another beautiful spreadsheet."

**Specimen Edition framing** keeps sample records honest: everything on the page is transparently representative (real vocabulary, no implied real closed deal). The marketing site is public/static/unauthenticated — it cannot pull a live tenant; the "live" feel is motion + self-advancing furniture, not real user data.

Plate ↔ real feature map (each a distinct instrument):

| Plate | Real feature |
|---|---|
| Hero statement + map echo | what Aethria is |
| The Market (dot map — centerpiece) | field scanned, few that fit |
| The Record (typographic score plate) | verdict + 5 real reviewer dims |
| The Review (two quiet columns) | reviewer disagreement, preserved |
| The Newsroom (index plate) | 4 scouts + 3 reviewers + partner |
| Corrections (revisions box) | the meta-agent |
| Place a Query (typed line) | on-demand lookup (`product-chrome`) |
| Holdings (table) | portfolio after INVEST |
| Access + Colophon | request access (`AccessForm`) + furniture |

## 6. SEO / tech architecture (per "prerender" decision — unchanged)

- **Prerender the marketing route to static HTML** at build time (lightest option that works — e.g. `vite-react-ssg` or a `react-snap`-style post-build prerender). Content ships in the HTML.
- **Self-host fonts** via `@fontsource`; drop the Google-CDN `<link>`.
- **JSON-LD**: `Organization` + `SoftwareApplication`. Semantic `<article>/<section>`, exactly one `<h1>`.
- **Real OG image** (the grey hero) for link shares.
- Canvas instruments stay `aria-hidden`; crawlable content is the surrounding real HTML.

## 7. Reuse vs. rebuild

- **Reuse:** `DottedMarketMap` (the hero plate — feature it, don't rewrite; real world silhouette replaces the mockup's field); `product-chrome` lookup components; `AccessForm`; `CountUp`; `motionTokens`; reduced-motion discipline; **the real copy** (§5).
- **Rebuild:** `HomePage` → plate-spine composition; the color tokens (grey stock); marginal furniture; add grain overlay; retire the dark masthead + `EditionLoader`; each section → a framed plate; `index.html` head; add prerender + self-hosted fonts.
- **Remove:** blocking `EditionLoader`, the scroll cue/line, the `ScrollReveal` uniform fade-up pattern (replaced by plate reveals).

## 8. Out of scope

- `app-front-end/` and backend — untouched.
- Real per-tenant live data on the marketing page (§5).
- A new brand palette beyond the cream→grey stock shift, or a dark theme.

## 9. Success criteria

- Stock is `#D9D7D4`; no warm cream anywhere in the marketing site.
- No scroll cue, no animated hero line, no italic-for-emphasis anywhere.
- Every plate is a distinct instrument; no two consecutive plates share a shape.
- All copy in §5 survives; every displayed record/event maps to a real backend concept; nothing implies a real closed deal.
- `curl` of the built marketing route returns the lede, plate titles, and JSON-LD in the HTML (prerender proof).
- Fonts served same-origin (no `fonts.googleapis.com` request).
- `prefers-reduced-motion` settles every animation to a static state.
- `npm run build` (tsc + vite) and `npm run lint` pass; `check:bundle` within budget.
