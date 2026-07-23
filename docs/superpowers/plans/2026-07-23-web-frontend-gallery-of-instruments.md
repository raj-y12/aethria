# Web Front-End — Gallery of Instruments — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the `web-front-end` marketing site as a "gallery of instruments" — a cool-grey, film-grained, Obys/Izanami-grade page where every section is a bracket-framed plate whose "photograph" is a mark the Aethria pipeline draws — and ship it as prerendered static HTML.

**Architecture:** Reconceive `HomePage` as a central spine of framed *plates* in wide margins with fixed marginal furniture (wordmark, nav, live dual-bureau clocks, edition number). Reuse the existing `DottedMarketMap`, `product-chrome` lookup, and `AccessForm`, plus all real app-grounded copy. Prerender `/` and `/home` to static HTML at build via `vite-react-ssg`, self-host fonts, and add JSON-LD.

**Tech Stack:** Vite 7, React 18, TypeScript, Tailwind 3, framer-motion, GSAP, d3-geo canvas, `@fontsource`, `vite-react-ssg` (new), Vercel static hosting.

**Design source of truth:** `_design-explore/J-gallery-instruments.html` — the approved mockup. Match its styling (tokens, spacing, bracket frames, grain, plate rhythm) exactly; this plan governs structure, content, and integration, the mockup governs pixels.

**Spec:** `docs/superpowers/specs/2026-07-23-web-frontend-living-broadsheet-design.md`.

## Global Constraints

Every task implicitly includes these (exact values from the spec):
- **Stock color:** `#D9D7D4` (cool grey). Ink `#111820`. Accent verdigris `#3d6b5e` = whisper only. NO warm cream `#f4f1ea` / `#E9E0D1` anywhere in the marketing site. NO dark theme.
- **Playfair Display stays** (display/statements/plate numerals). Marginalia = `Instrument Sans`. Data/clocks/plate-numbers = `Space Mono`. All self-hosted via `@fontsource`; NO `fonts.googleapis.com`.
- **NO italic-for-emphasis** anywhere. Statements are roman. **NO "Scroll" cue and NO animated hero line.**
- **Preserve real copy** (spec §5) — do not invent or exaggerate claims. Sample records use the **Specimen Edition** framing; nothing may imply a real closed deal.
- All motion `prefers-reduced-motion` safe (settles to static state).
- Scope: `web-front-end/` only. Do not touch `app-front-end/` or backend.

**Verification approach (read once):** `web-front-end` has no test runner; frontend work here is gated by **`npm run build`** (runs `tsc && vite build`) and **`npm run lint`** both passing, plus **`node scripts/check-marketing.mjs`** (added in Task 14) asserting the content/SEO invariants against the built HTML. Where a task adds a pure function, a tiny inline Node assertion (`node --check` / a one-off `node -e`) is the test. Raj runs the site locally to eyeball visuals — do not start preview servers.

**Commit after every task.** Branch off `main` first: `git checkout -b web-frontend-gallery-of-instruments`.

---

## Phase 0 — Foundation

### Task 1: Grey stock tokens + grain + gallery CSS primitives

**Files:**
- Modify: `web-front-end/src/index.css` (`:root` tokens ~L10-69; body/base)
- Modify: `web-front-end/tailwind.config.js` (colors)
- Modify: `web-front-end/src/components/AnimatedRoutes.tsx:8` (`PAPER` constant)
- Modify: `web-front-end/index.html:7` (`theme-color`)

**Interfaces:**
- Produces: CSS custom props `--stock`, `--stock-2`, `--ink`, `--ink-2/3/4`, `--line`, `--line-2`, `--accent`; utility classes `.grain`, `.plate`, `.framed`, `.plate-head`, `.plate-title`, `.plate-num`, `.plate-cap-l/-r`, `.reveal`/`.reveal.d1-d3`, `.lbl`, `.frame` (+ `.tl/.tr/.bl/.br`), `.wordmark`. Copy their definitions verbatim from `_design-explore/J-gallery-instruments.html` `<style>`.

- [ ] **Step 1: Replace the palette tokens in `index.css` `:root`.** Set `--color-paper`→`#D9D7D4` is NOT enough (many refs). Add the new token set from the mockup and repoint existing semantic tokens:
  - `--stock:#D9D7D4; --stock-2:#d1cfcb; --ink:#111820;` and set `--color-paper:#D9D7D4`, `--color-oxford:#111820` (keep names so existing utility classes still resolve), `--surface-base:var(--stock)`, `--text-primary:var(--ink)` etc. Keep `--color-accent:#3d6b5e`.
  - Add `--line:rgba(17,24,32,.16); --line-2:rgba(17,24,32,.26);` and set `--section-divider:var(--line)`.
- [ ] **Step 2: Port the mockup's gallery classes** (`.grain`, `.frame*`, `.wordmark`, `.plate`, `.framed`, `.plate-head`, `.plate-title`, `.plate-num`, `.plate-cap-l/-r`, `.reveal*`, `.lbl`) verbatim into `index.css` (translate the mockup's `var(--disp/--sans/--mono)` to the existing `var(--font-display/--font-sans/--font-mono)`).
- [ ] **Step 3: Repaint the hardcoded cream.** In `AnimatedRoutes.tsx` set `const PAPER = '#D9D7D4';`. In `index.html` set `<meta name="theme-color" content="#D9D7D4" />`.
- [ ] **Step 4: Build + lint.** Run `npm run build && npm run lint`. Expected: PASS (tsc clean, no eslint errors).
- [ ] **Step 5: Grep guard.** Run `grep -rniE '#f4f1ea|#e9e0d1|f4f1ea' web-front-end/src web-front-end/index.html`. Expected: no matches (any remaining are follow-on tasks; note them). Commit: `git add -A && git commit -m "feat(web): cool-grey stock tokens + gallery CSS primitives"`.

### Task 2: Self-host fonts, drop the CDN, retire unused faces

**Files:**
- Modify: `web-front-end/index.html` (remove Google Fonts `<link>` ~L22-24; keep preconnect only if still needed → remove)
- Modify: `web-front-end/src/main.tsx:5-15` (font imports)
- Modify: `web-front-end/src/index.css:28-33` (font-family vars)

**Interfaces:**
- Produces: `--font-sans:'Instrument Sans'…`, `--font-mono:'Space Mono'…`, `--font-display:'Playfair Display'…`, `--font-wordmark:'Playfair Display'…`. Removes `Figtree` and `Source Serif 4` (they came only from the CDN).

- [ ] **Step 1: Remove the CDN link.** Delete the `fonts.googleapis.com` `<link rel="stylesheet">` and the two `preconnect` lines in `index.html`.
- [ ] **Step 2: Repoint CDN-only faces.** In `index.css`, change `--font-sans` to `'Instrument Sans', system-ui, sans-serif` and `--font-serif-text` to `'Playfair Display', Georgia, serif` (Source Serif 4 is gone; running copy is minimal in the new design and uses sans/display). Grep `Figtree|Source Serif` in `src/` and replace any remaining refs.
- [ ] **Step 3: Keep `@fontsource` imports in `main.tsx`** (instrument-sans 400/500/600, playfair-display 400/500/600, space-mono 400/700). Drop the two `playfair-display/*-italic.css` imports (no italic-for-emphasis; re-add later only if a legit italic use appears).
- [ ] **Step 4: Build + lint + grep.** `npm run build && npm run lint`; then `grep -rn 'googleapis' web-front-end/index.html` → no matches. Commit: `feat(web): self-host all fonts, drop Google CDN + unused faces`.

### Task 3: `clocks.ts` — pure dual-bureau time formatter

**Files:**
- Create: `web-front-end/src/lib/clocks.ts`

**Interfaces:**
- Produces: `export function bureauTimes(now?: Date): { label: string; time: string }[]` returning `[{label:'London', time:'HH:MM:SS'}, {label:'San Francisco', time:'HH:MM:SS'}]` using `Intl.DateTimeFormat` with `timeZone: 'Europe/London'` / `'America/Los_Angeles'`, `hour12:false`.
- Produces: `export function editionNo(now?: Date): number` = day-of-year (`Math.floor((Date.now() - Date.UTC(y,0,0)) / 86_400_000)`).

- [ ] **Step 1: Write `clocks.ts`** with both functions (SSR-safe: no `window`/`document`).

```ts
const ZONES = [
  { label: 'London', tz: 'Europe/London' },
  { label: 'San Francisco', tz: 'America/Los_Angeles' },
] as const;

export function bureauTimes(now: Date = new Date()) {
  return ZONES.map(({ label, tz }) => ({
    label,
    time: new Intl.DateTimeFormat('en-GB', {
      timeZone: tz, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    }).format(now),
  }));
}

export function editionNo(now: Date = new Date()) {
  return Math.floor((now.getTime() - Date.UTC(now.getUTCFullYear(), 0, 0)) / 86_400_000);
}
```

- [ ] **Step 2: Assert it.** Run:
`node -e "import('./web-front-end/src/lib/clocks.ts')" ` is not valid for TS; instead assert via a throwaway: `npx tsx -e "import {bureauTimes,editionNo} from './web-front-end/src/lib/clocks'; const t=bureauTimes(new Date('2026-07-23T12:00:00Z')); if(t.length!==2||!/^\d\d:\d\d:\d\d$/.test(t[0].time)) throw new Error('bad'); if(editionNo(new Date('2026-01-02T00:00:00Z'))!==2) throw new Error('edition'); console.log('ok')"`. Expected: `ok`. (If `tsx` unavailable, `npm i -D tsx` or skip and rely on the Task 5 build.)
- [ ] **Step 3: Commit.** `feat(web): dual-bureau clock + edition-number utils`.

### Task 4: `GalleryFrame` — fixed marginal furniture + grain

**Files:**
- Create: `web-front-end/src/components/GalleryFrame.tsx`

**Interfaces:**
- Consumes: `bureauTimes`, `editionNo` from `src/lib/clocks`.
- Produces: `export default function GalleryFrame(): JSX.Element` — renders `<div class="grain">`, and four fixed `.frame` corners: `tl` wordmark (`Aethria` + `.` accent, links `/home`), `tr` nav (`Index`→`#market`, `Access`→`#access`), `bl` live clocks, `br` `Specimen Edition · No. {editionNo}`. Clocks update via `setInterval(1000)` inside `useEffect`, cleared on unmount; under `useReducedMotion()` render once, no interval. All `window`/timer use inside `useEffect` (SSR-safe).

- [ ] **Step 1: Implement `GalleryFrame.tsx`.** Structure/classes per mockup `.frame.tl/.tr/.bl/.br`, `.wordmark`, `.grain`. State `const [times,setTimes]=useState(bureauTimes())`; effect sets interval unless reduced. Use `<Link to="/home">` for the wordmark, `<a href="#market">`/`<a href="#access">` for nav (Lenis handles smooth scroll via existing `__lenis`; reuse the `scrollToAnchor` helper pattern from `HomePage.tsx:58` — extract it in Task 6).
- [ ] **Step 2: Contrast fix (spec caveat).** Clocks/edition use `color: var(--ink-3)` — on grey verify legible; if faint, use `--ink-2`.
- [ ] **Step 3: Build + lint.** `npm run build && npm run lint` → PASS. Commit: `feat(web): GalleryFrame marginal furniture + film grain`.

### Task 5: `Plate` — bracket-framed plate wrapper with reveal

**Files:**
- Create: `web-front-end/src/components/Plate.tsx`

**Interfaces:**
- Produces:
```ts
export interface PlateProps {
  id?: string;
  index: string;        // e.g. "01 — 07"
  title: string;        // plate head title (Playfair)
  capLeft: string;      // vertical caption rail (left)
  capRight: string;     // vertical caption rail (right)
  children: React.ReactNode;
  headingLevel?: 2 | 3; // default 2; the plate title renders as this heading
}
export default function Plate(props: PlateProps): JSX.Element
```
- Behavior: `<section class="plate" id>` with `.plate-cap-l/-r`, a `.framed` inner containing `.plate-head` (title as `<h2|h3 class="plate-title">` + `.plate-num`), then `children`. Adds class `in` when it scrolls into view (IntersectionObserver, `threshold:.28`, once); under reduced motion add `in` immediately. This drives `.reveal`/bracket animations via CSS.

- [ ] **Step 1: Implement `Plate.tsx`** with an `useEffect` IntersectionObserver on a `ref`, guarded for SSR (`if (typeof IntersectionObserver === 'undefined') { setIn(true); return; }`) and reduced motion. Title heading element chosen by `headingLevel`.
- [ ] **Step 2: Build + lint** → PASS. Commit: `feat(web): Plate wrapper (bracket frame + scroll reveal)`.

---

## Phase 1 — Hero + skeleton

### Task 6: Extract `scrollToAnchor`; add `HeroPlate`

**Files:**
- Create: `web-front-end/src/lib/scrollToAnchor.ts` (move the helper from `HomePage.tsx:57-65`)
- Create: `web-front-end/src/components/HeroPlate.tsx`
- Modify: `web-front-end/src/components/DottedMarketMap.tsx` (already supports `echo` prop — reuse as the faint hero field; no change expected)

**Interfaces:**
- Consumes: `DottedMarketMap` with `echo` prop; `scrollToAnchor(e, href)`.
- Produces: `export default function HeroPlate(): JSX.Element` — full-viewport hero: `<DottedMarketMap echo className="hero-echo" />` behind a `.hero-veil`, centered `.hero-kicker` ("Private-market intelligence") + one roman Playfair `<h1 class="hero-statement">`. **NO scroll cue, NO animated line.** Statement copy (roman, no italics): `Private-market judgment, on the record.`

- [ ] **Step 1: Create `scrollToAnchor.ts`** with the exact helper body currently in `HomePage.tsx:57-65`; export it. (Task 12 removes the inline copy.)
- [ ] **Step 2: Implement `HeroPlate.tsx`** per mockup `.hero/.hero-center/.hero-kicker/.hero-statement` minus `.scrollcue`. `<h1>` is the single page `<h1>`. Use `DottedMarketMap` with `echo`.
- [ ] **Step 3: Build + lint** → PASS. Commit: `feat(web): HeroPlate (Izanami calm, no scroll cue/italics)`.

### Task 7: Recompose `HomePage` skeleton (frame + hero + plate slots)

**Files:**
- Modify: `web-front-end/src/HomePage.tsx` (replace composition)

**Interfaces:**
- Consumes: `GalleryFrame`, `HeroPlate`, `Plate`, and the plate components from Phase 2 (stub/import as created). Renders `<GalleryFrame/>`, `<HeroPlate/>`, then the plate spine `<div class="gallery">` containing the Phase-2 plates in order, then Access + Colophon (Task 11).
- Removes: `SiteHeader`, `EditionLoader`, `MarketSection`/`MethodSection`/`MetaAgentSection`/`DashboardPreview`/`ReviewDisagreement`/`PortfolioSection` imports (superseded by plates), `ScrollReveal`, `SectionRule` usage.

- [ ] **Step 1: Rewrite `HomePage.tsx`** to render `GalleryFrame` + `HeroPlate` + a `.gallery` wrapper. For this task, include only Hero + a single placeholder `Plate` so it compiles; Phase 2 fills the rest. Keep the `#access` hash-scroll effect (`HomePage.tsx:80-86`).
- [ ] **Step 2: Delete the now-unused `EditionLoader` mount and `SiteHeader`.** (Files deleted in Task 13 after all refs gone.)
- [ ] **Step 3: Build + lint** → PASS. Commit: `feat(web): HomePage recomposed as gallery spine (hero + frame)`.

---

## Phase 2 — The plates (each reuses real copy from spec §5)

> Each plate is a `<Plate>` with the real content below. Match mockup plate styling. Plate numbers use a running `NN — 08` count. Every plate is a distinct instrument.

### Task 8: MarketPlate (centerpiece) + RecordPlate

**Files:**
- Create: `web-front-end/src/components/plates/MarketPlate.tsx`
- Create: `web-front-end/src/components/plates/RecordPlate.tsx`
- Reference for real data: `web-front-end/src/components/MarketSection.tsx:9-31` (`HITS`, `SCANNED_TOTAL`, real vocabulary)

**Interfaces:**
- MarketPlate: `Plate` id `market`, index `01 — 08`, title `The Market`, caps `The Market — Plate 01` / `Every company scanned · the few that fit`. Body = `<Suspense>`-wrapped `DottedMarketMap hits={HITS}` (copy the real `HITS` array from `MarketSection`) in a `.market-stage`, plus the real caption + the "scanned / in-thesis" legend. Keep the real count-up of `SCANNED_TOTAL` (reuse `MarketSection`'s IntersectionObserver+GSAP pattern) and the "N companies scanned · N inside your thesis" line.
- RecordPlate: `Plate` id `record`, index `02 — 08`, title `The Record`. Body = record name `Meridian Compute`, verdict `Invest` (verdigris outline), the **5 real reviewer dims** `Market 9 / Product 8 / Technical 9 / Execution 8 / Defensibility 7` as the `.dims` typographic plate with count-up (reuse `CountUp` from `HomePage.tsx:27-43` — extract to `src/lib/CountUp.tsx` in this task). Caption (Specimen framing): `B2B Infrastructure · Series A · London. A specimen record…`.

- [ ] **Step 1: Extract `CountUp`** from `HomePage.tsx` to `web-front-end/src/lib/CountUp.tsx` (same code) and export.
- [ ] **Step 2: Implement `MarketPlate.tsx`** — copy `HITS`/`SCANNED_TOTAL`/real strings from `MarketSection`; `DottedMarketMap` in `.market-stage`; count-up on reveal.
- [ ] **Step 3: Implement `RecordPlate.tsx`** — `.dims` grid, `CountUp` per dim, verdict chip, Specimen caption.
- [ ] **Step 4: Wire both into `HomePage` gallery.** Build + lint → PASS. Commit: `feat(web): Market + Record plates (real map, real reviewer dims)`.

### Task 9: ReviewPlate + NewsroomPlate

**Files:**
- Create: `web-front-end/src/components/plates/ReviewPlate.tsx`
- Create: `web-front-end/src/components/plates/NewsroomPlate.tsx`
- Reference: `web-front-end/src/components/ReviewDisagreement.tsx` (real disagreement copy), spec §5 (scouts/reviewers)

**Interfaces:**
- ReviewPlate: id `review`, index `03 — 08`, title `The Review`. Body = two quiet columns (`.review`): **Opportunist — for (9)** vs **Skeptical — against (7)**, using the real disagreement framing ("built to disagree"; the partner engine logs the split rather than averaging — "a nine and a seven remain a nine and a seven"). Pull exact argument copy from `ReviewDisagreement.tsx` if present; else the spec §5 wording. No italics for emphasis.
- NewsroomPlate: id `method`, index `04 — 08`, title `The Newsroom`. Body = a staff/index plate: **Scouts** (Market-Driven, Builder/Technical, Pain-Point, Contrarian) and **Reviewers** (Default, Skeptical, Opportunist) + **Partner Engine** (rules v1 · invest/pass/monitor), set as two ruled index columns.

- [ ] **Step 1: Implement `ReviewPlate.tsx`** (`.review` two-column, real copy).
- [ ] **Step 2: Implement `NewsroomPlate.tsx`** (two ruled columns, real persona names from spec §5 / `backend` vocabulary — do not invent personas).
- [ ] **Step 3: Wire into gallery. Build + lint → PASS.** Commit: `feat(web): Review + Newsroom plates (disagreement + agent masthead)`.

### Task 10: CorrectionsPlate + QueryPlate + HoldingsPlate

**Files:**
- Create: `web-front-end/src/components/plates/CorrectionsPlate.tsx`
- Create: `web-front-end/src/components/plates/QueryPlate.tsx`
- Create: `web-front-end/src/components/plates/HoldingsPlate.tsx`

**Interfaces:**
- CorrectionsPlate: id `corrections`, index `05 — 08`, title `Corrections & Revisions`. Body = a ruled box of the meta-agent's real behavior: scout **weighting** reweighted, reviewer **thresholds** recalibrated, mutated scout **prompts re-hashed / versioned** (spec §5; real modules: mutator/reweighter/calibrator). No fabricated numbers beyond "representative".
- QueryPlate: id `query`, index `06 — 08`, title `Place a Query`. Body = the on-demand lookup, reusing `@aethria/product-chrome` `LookupCommandBar` + `LookupResultSnapshot` with `DEMO_LOOKUP_QUERY`/`DEMO_LOOKUP_RESULT` (as `HomePage.tsx:44-49,348-356` does today), framed as a plate. Real caption: benchmarked against your active thesis the moment results arrive.
- HoldingsPlate: id `holdings`, index `07 — 08`, title `Holdings`. Body = a small portfolio table (Company / Stage / Signal / Health) — Specimen holdings; caption cites the portfolio engine tracking execution, signals, health.

- [ ] **Step 1: Implement the three plate files** with the real copy above; QueryPlate reuses the existing `product-chrome` imports.
- [ ] **Step 2: Wire into gallery. Build + lint → PASS.** Commit: `feat(web): Corrections + Query + Holdings plates`.

### Task 11: AccessPlate + Colophon (reuse `AccessForm`)

**Files:**
- Create: `web-front-end/src/components/plates/AccessPlate.tsx`
- Reference/reuse: `web-front-end/src/components/AccessForm.tsx` (unchanged)

**Interfaces:**
- AccessPlate: id `access`, index `08 — 08`, title `Request Access`. Body = kicker `Request access`, roman Playfair statement `For funds that need judgment with memory.` (NO italics), the real `<AccessForm/>`, and the Colophon furniture (wordmark + "Private-market intelligence for funds that need the evidence trail." + typefaces set + `London · San Francisco` + `Specimen Edition · © {year}`). Keep the `#access` id so header/nav anchor scroll works.

- [ ] **Step 1: Implement `AccessPlate.tsx`** reusing `AccessForm`; colophon per mockup `.colophon`.
- [ ] **Step 2: Wire into gallery (last). Build + lint → PASS.** Commit: `feat(web): Access plate + colophon (reuses AccessForm)`.

---

## Phase 3 — Motion pass + cleanup

### Task 12: Diegetic motion pass + no-slop audit

**Files:**
- Modify: the plate components (reveal timing), `HomePage.tsx` (remove inline `scrollToAnchor`, import from `src/lib`)

- [ ] **Step 1: Confirm plate reveals** use `.reveal`/`.reveal.d1-d3` staggering (bracket draw + caption set + instrument animate) via the `Plate` `in` class. Ensure the Market map assembles, Record dims count up, Query line types — all on reveal, all reduced-motion safe.
- [ ] **Step 2: No-slop audit.** Grep the marketing `src/` for banned patterns: `grep -rniE '\bscroll\b.*cue|scrollcue' src` (none); `grep -rn 'italic' src` → each hit must be a legit editorial use, not emphasis (remove emphasis italics); confirm no leftover `ScrollReveal` import. Fix inline.
- [ ] **Step 3: Build + lint → PASS.** Commit: `refactor(web): diegetic reveal pass + no-slop audit`.

### Task 13: Delete superseded components

**Files:**
- Delete (after confirming zero imports): `src/components/EditionLoader.tsx`, `SiteHeader.tsx`, `MarketSection.tsx`, `MethodSection.tsx`, `MetaAgentSection.tsx`, `DashboardPreview.tsx`, `ReviewDisagreement.tsx`, `PortfolioSection.tsx`, `IntelligenceSection.tsx`, `IntelligenceMap.tsx`, `PipelineSection.tsx`, `ScrollReveal.tsx`, `SectionRule.tsx`, `SectionKicker.tsx`, `LiveIndicatorsPanel.tsx`, `RotatingSeal.tsx`, `DeskClock.tsx`, `ReviewDisagreement.tsx` — **only those with no remaining importer.**

- [ ] **Step 1: For each candidate, `grep -rn "<ComponentName" src && grep -rn "import.*ComponentName" src`.** Delete only if zero hits outside its own file.
- [ ] **Step 2: Build + lint → PASS** (proves nothing dangling). Commit: `chore(web): remove superseded section components`.

---

## Phase 4 — SEO: prerender, JSON-LD, OG

### Task 14: `check-marketing.mjs` content/SEO guard (write first, wire in Task 15-17)

**Files:**
- Create: `web-front-end/scripts/check-marketing.mjs` (mirrors `scripts/check-bundle.mjs`)
- Modify: `web-front-end/package.json` (add `"check:marketing"` script)

**Interfaces:**
- Produces a script that reads the built home HTML (Task 16 emits `dist/home.html` and `dist/index.html`) and asserts: contains `Private-market judgment, on the record`; contains all of `Market`,`Product`,`Technical`,`Execution`,`Defensibility`; contains `application/ld+json`; does NOT contain `fonts.googleapis.com`; contains `#D9D7D4` OR the grey is in linked CSS (assert `theme-color" content="#D9D7D4`); does NOT contain a scroll-cue marker. Exit 1 with a clear message on any failure.

- [ ] **Step 1: Write `check-marketing.mjs`** reading `../dist/home.html` (fallback `../dist/index.html`), running the assertions above, `process.exit(1)` on failure with the failing assertion named.
- [ ] **Step 2: Add script** `"check:marketing": "node scripts/check-marketing.mjs"` to `package.json`.
- [ ] **Step 3:** Do not run yet (needs prerender). Commit: `test(web): marketing content/SEO guard script`.

### Task 15: JSON-LD + OG meta in `index.html`

**Files:**
- Modify: `web-front-end/index.html`
- Create: `web-front-end/public/og.png` (1200×630)

**Interfaces:**
- Produces: an `application/ld+json` `<script>` with `@type` `Organization` and `SoftwareApplication` (name Aethria, description from meta, url, applicationCategory `BusinessApplication`). Updated `og:title/description/image`, `twitter:image`, `og:url`, `og:image:width/height`. `og.png` = a 1200×630 render of the grey hero.

- [ ] **Step 1: Add JSON-LD `<script type="application/ld+json">`** to `index.html` `<head>` with the two entities (real copy; no invented metrics).
- [ ] **Step 2: Update OG/Twitter meta** to reference `/og.png`, add `og:url` (production domain), `og:image:width/height`.
- [ ] **Step 3: Create `public/og.png`.** Produce a 1200×630 PNG of the hero (grey stock, wordmark, statement). (Execution note: screenshot the built hero at 1200×630, or export from the mockup; must be raster PNG for Twitter.)
- [ ] **Step 4: Build + lint → PASS.** Commit: `feat(web): JSON-LD + OG image for share/crawl`.

### Task 16: Prerender `/` and `/home` to static HTML via `vite-react-ssg`

**Files:**
- Add dep: `vite-react-ssg`
- Modify: `web-front-end/src/main.tsx` (SSG entry), `src/App.tsx`/routing as needed, `vite.config.ts`, `package.json` (build script), `vercel.json` (serve prerendered routes)

**Interfaces:**
- Produces: `dist/index.html` and `dist/home.html` (or `dist/home/index.html`) containing fully-rendered marketing HTML. Client hydrates as today; private routes/gate remain client-side.

- [ ] **Step 1: Install** `npm i -D vite-react-ssg` (pin the version compatible with Vite 7 / React 18; check its README).
- [ ] **Step 2: Convert the entry.** Replace `createRoot(...)` in `main.tsx` with `ViteReactSSG`'s entry, exporting `createRoot` per its React Router recipe. Move the **Lenis init into a client-only `useEffect`** (in a top-level `App` effect) so it never runs during SSG (`window` is undefined there). Set `includedRoutes` to `['/', '/home']` only.
- [ ] **Step 3: Guard all browser APIs at render time.** Confirm every `window`/`document`/`canvas`/`IntersectionObserver`/`matchMedia` use in the new components sits inside `useEffect` or a `typeof window !== 'undefined'` guard (Plate, GalleryFrame, HeroPlate, DottedMarketMap, count-ups). DottedMarketMap already fetches world data in an effect — SSG renders the empty canvas, fine.
- [ ] **Step 4: Update build script** in `package.json`: `"build": "vite-react-ssg build"` (keep `tsc` as a separate `"typecheck"` step run in CI/lint; or `"build": "tsc && vite-react-ssg build"`). Update `vercel.json` so `/home` serves the prerendered file and the SPA rewrite still covers gate/private routes (exclude the prerendered paths from the catch-all rewrite).
- [ ] **Step 5: Build.** `npm run build`. Expected: `dist/home.html`/`dist/index.html` exist and contain the lede text: `grep -c "Private-market judgment" dist/home.html` ≥ 1.
- [ ] **Step 6: Run the guard.** `npm run check:marketing`. Expected: PASS. `npm run lint` → PASS. Commit: `feat(web): prerender / and /home to static HTML (vite-react-ssg)`.

> **Risk note:** if `vite-react-ssg` fights the custom `AnimatedRoutes`/`import.meta.glob` private-route setup, fall back to a build-time headless snapshot: add `scripts/prerender.mjs` using `puppeteer` to load the built `/` and `/home` from a local static server and write the serialized DOM back into `dist/`. Same acceptance gate (Step 5-6). Choose this only if Step 2-4 can't be made to hydrate cleanly.

### Task 17: Full acceptance pass

- [ ] **Step 1: Clean build.** `rm -rf dist && npm run build && npm run lint && npm run check:bundle && npm run check:marketing`. All PASS.
- [ ] **Step 2: Grep the built HTML** for regressions: no `f4f1ea`, no `googleapis`, contains `application/ld+json`, contains the 5 reviewer dims. 
- [ ] **Step 3: Spec success-criteria checklist** (spec §9) — tick each. Commit: `chore(web): gallery-of-instruments acceptance pass`.

---

## Self-Review (author)

- **Spec coverage:** §3 tokens→T1/T2; Playfair kept→T2 (italic import dropped); no-italics/no-scroll→T6/T12; §4 composition→T4/T5/T7; §5 content→T8-T11 (real copy) + Specimen framing; §6 SEO→T14-T16; reuse (map/lookup/AccessForm/CountUp)→T6/T8/T10/T11; removals→T13. Covered.
- **Placeholder scan:** exact files/copy/commands given; the only deferred artifact is `og.png` (raster, produced by screenshot/export — noted, not a code placeholder).
- **Type consistency:** `PlateProps`, `bureauTimes`/`editionNo`, `CountUp` signatures are defined once (T5/T3/T8) and consumed by name thereafter.
