# App ↔ Marketing Design Parity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Checkbox steps.

**Goal:** Close the 14 findings from `docs/superpowers/specs/2026-07-24-app-marketing-parity-critique.md` — the app should read as the same design system as `web-front-end`, at the app's own (denser, functional) register.

**Branch:** create `app-marketing-parity` off current `main`.

## Global Constraints — read the spec's "Resolved decisions" and "Two findings overridden" sections FIRST; they bind every task
- **Font:** Instrument Sans replaces Figtree Variable as `--font-sans` everywhere.
- **Verdict/annotation colors:** transparent-background, mono, uppercase, 1px border outline chips — NEVER a filled color block on a product-facing decision badge or queue annotation. Verdict is read by LABEL TEXT, not fill color. Configured badge colors (from Settings) become the border tint, not a fill. Escalation (burgundy `#6E2A3C`) is the ONE exception — it stays a strong/filled "fire alarm" treatment, reserved for genuine human-attention alerts, never a decision-verdict color.
- **Do NOT** add `.focus-frame` (bracket) to the Flow memo panel — explicitly rejected by the user earlier.
- **Do NOT** wrap the memo scorecard (or any number) in a bordered/gridded box — explicitly rejected by the user earlier (Fund/Portfolio precedent). "More presence" = bigger/bolder typography only, never a border.
- **Do NOT** touch `.memoDocSectionHead` or other recurring memo section-head labels — Playfair stays there intentionally (broadsheet character).
- A Settings color-picker SWATCH (a small preview chip whose entire job is showing a raw color, e.g. `DecisionThresholdsPanel.tsx`'s `bandColors`) is not the same thing as a product-facing verdict badge — filled swatches there are fine and out of scope; only the actual `DecisionBadge`/`QUEUE_ANNOTATION_CLASS` chips need to become outline-mono.
- Verification per task: `npm run build && npm run lint && npm test` from `app-front-end/`. Never start preview/dev servers — the owner runs the app locally. Commit per task.

### Task 1: Font foundation — Instrument Sans

**Files:**
- Modify: `app-front-end/src/main.tsx:6` — replace `import '@fontsource-variable/figtree';` with the Instrument Sans imports (`@fontsource/instrument-sans/400.css`, `/500.css`, `/600.css` — match the weights marketing loads).
- Modify: `app-front-end/package.json` — add `@fontsource/instrument-sans`, remove `@fontsource-variable/figtree` if nothing else in the app uses it (grep first).
- Modify: `app-front-end/src/index.css:5,34,37,64,219,226,238,297` — every `'Figtree Variable'`/`"Figtree Variable"` occurrence → `'Instrument Sans'`/`"Instrument Sans"`. Fix the two comments claiming parity with web-front-end (they were false before, must be true now).
- Modify: `app-front-end/.impeccable.md:13` — "Figtree Variable for body/UI prose (warm geometric sans, matches web-front-end)" → correct to Instrument Sans. Also fix line 17's "JetBrains Mono" (nowhere loaded) → "Space Mono" (what's actually loaded, per line 13's own claim).

- [ ] Step 1: `npm install @fontsource/instrument-sans` in `app-front-end/`.
- [ ] Step 2: Make all edits above. Grep `grep -rn "Figtree" src .impeccable.md` → must return zero hits when done (except possibly a historical changelog/comment explicitly noting the migration, which is fine).
- [ ] Step 3: `npm run build && npm run lint && npm test` → PASS.
- [ ] Step 4: Commit: `feat(app): swap Figtree Variable for Instrument Sans (matches marketing body font)`

### Task 2: Verdict & annotation colors — mono outline chips

**Files:**
- Modify: `app-front-end/src/design-system/verdictBadgeTokens.ts` — full rewrite of `DECISION_BADGE_CLASS`, `REVIEWER_BADGE_CLASS`, `QUEUE_ANNOTATION_CLASS`.
- Modify: `app-front-end/src/components/DecisionBadge.tsx` — `badgeBackground()` currently returns `{ backgroundColor }`; change to return `{ borderColor: backgroundColor }` (or similar — the configured color becomes a border tint, chip background stays transparent/paper).
- Modify: `app-front-end/src/lib/fundConfiguration.ts:333-338` (`DEFAULT_VERDICT_BADGES`) — values can stay as reference colors (now used as border tints) OR be cooled to the same values used earlier this session (`#c3d3c9`/`#cfccbb`/`#d6c4c0`) — implementer's call; either is consistent with "border tint, not fill," but prefer the cooled values since raw `#bfe3cc` etc. as a BORDER is still a fairly saturated mint/rose — cool them.
- Check (do not necessarily change): `app-front-end/src/settings/DecisionThresholdsPanel.tsx` `bandColors` — this is a picker-preview swatch, out of scope per Global Constraints; leave its filled-swatch rendering as-is unless it visually breaks.
- Check: `app-front-end/src/components/queue/QueueVerdictLine.tsx` and any other `DecisionBadge`/`QUEUE_ANNOTATION_CLASS` consumers (grep `DECISION_BADGE_CLASS\|QUEUE_ANNOTATION_CLASS\|DecisionBadge` across `src/`) — confirm nothing else hardcodes an assumption of a filled background (e.g. computing text-contrast against a fill color) that would break when the fill goes transparent.

**New token shape (apply this exact pattern):**
```ts
export const VERDICT_CHIP_CLASS =
  'type-status inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none leading-none min-w-[4.25rem] px-2 py-1 border bg-transparent';

export const DECISION_BADGE_CLASS: Record<DecisionBadgeVariant, string> = {
  INVEST: 'border-oxford/40 text-oxford',
  PASS: 'border-oxford/40 text-oxford',
  MONITOR: 'border-oxford/40 text-oxford',
  awaiting: 'border-oxford/25 text-oxford/70',
  undecided: 'border-oxford/25 text-oxford/70',
  escalation: 'bg-escalation !text-white border-escalation', // the one exception — stays filled
};

export const REVIEWER_BADGE_CLASS: Record<ReviewerQualityBand, string> = {
  STRONG: 'border-oxford/40 text-oxford',
  MEDIUM: 'border-oxford/40 text-oxford',
  WEAK: 'border-oxford/40 text-oxford',
};

export type QueueAnnotationVariant = 'burgundy' | 'gold' | 'positive';
export const QUEUE_ANNOTATION_CLASS: Record<QueueAnnotationVariant, string> = {
  burgundy: 'bg-escalation !text-white border-escalation', // genuine human-attention alert — stays filled
  gold: 'border bg-transparent border-oxford/40 text-oxford',
  positive: 'border bg-transparent border-oxford/40 text-oxford',
};
```
(INVEST/PASS/MONITOR/STRONG/MEDIUM/WEAK/gold/positive all render IDENTICALLY — ink outline, ink text — because the label text is the signal, not the color. `DecisionBadge.tsx`'s `badgeBackground()` then layers the CONFIGURED color as `borderColor` on top of this base, so a fund that has customized "Invest" to a specific color still sees that color, just as a border tint on an otherwise-neutral chip, not a fill.)

- [ ] Step 1: Rewrite `verdictBadgeTokens.ts` per the pattern above.
- [ ] Step 2: Update `DecisionBadge.tsx`'s `badgeBackground()` to return a border-color style object instead of background-color.
- [ ] Step 3: Cool `DEFAULT_VERDICT_BADGES` hex values in `fundConfiguration.ts` to `#c3d3c9`/`#cfccbb`/`#d6c4c0` (INVEST/MONITOR/PASS) and matching for STRONG/MEDIUM/WEAK.
- [ ] Step 4: Grep every consumer, confirm nothing assumes a filled background. Fix any that do.
- [ ] Step 5: `npm run build && npm run lint && npm test` → PASS.
- [ ] Step 6: Commit: `feat(app): verdict badges become mono outline chips (marketing parity — label reads the verdict, not fill color)`

### Task 3: Bracket/border de-stacking (two opposite fixes)

**Files:**
- Modify: `app-front-end/src/pages/HomePage.tsx:257` — remove `focus-frame` from the "On the desk" block's className. It's a docket/list (per `.focus-frame`'s own CSS comment: "Not for list rows/docket — density stays bare"). Keep the existing `border-y border-oxford/[0.12]` — that's the correct bare treatment, and it now matches its sibling "Two quiet doors" block below, which never had the bracket.
- Modify: `app-front-end/src/settings/FundThesisConfirmationModal.tsx:101` — remove `border border-oxford/10` from the className (keep `focus-frame` and `bg-paper`). The brackets ARE the frame around this single-document confirmation card; a box on top of them is the redundant-framing bug.

- [ ] Step 1: Make both edits (opposite directions — read the reasoning above carefully, don't apply the same fix to both).
- [ ] Step 2: `npm run build && npm run lint && npm test` → PASS.
- [ ] Step 3: Commit: `fix(app): de-stack redundant bracket+border framing (Home docket loses the bracket, Fund Thesis modal loses the box)`

### Task 4: `--color-accent` rename (fixes the token-collision landmine)

**Files:**
- Modify: `app-front-end/src/index.css` (the `--color-accent: #6E2A3C;` definition, ~line 25) — rename the custom property to `--color-escalation`. Keep the value (`#6E2A3C`) unchanged. Do NOT touch the separate Tailwind `escalation` utility class in `tailwind.config.js` — that's already correctly named and independent.
- Modify: `app-front-end/src/components/ActivityStatsRow.tsx` and `app-front-end/src/components/InvestmentMemoContent.css` — every `var(--color-accent)` reference → `var(--color-escalation)`.

- [ ] Step 1: `grep -rn '\-\-color-accent' app-front-end/src` → confirm exactly these 3 files, rename in all.
- [ ] Step 2: `npm run build && npm run lint && npm test` → PASS.
- [ ] Step 3: Commit: `fix(app): rename --color-accent to --color-escalation (matches marketing's --color-accent = verdigris, not burgundy)`

### Task 5: Eyebrow dot + memo scorecard weight (no box)

**Files:**
- Modify: `app-front-end/src/index.css` — find `.type-label-section` (grep it; note this class is used for MANY things beyond room-header eyebrows — check every call site before adding a `::before` dot globally, since it may also label form fields, table headers, etc. where a dot would be wrong). If `.type-label-section` is too broad, instead add the dot via a NEW modifier class (e.g. `.type-label-section--eyebrow`) applied only where `RoomHeader.tsx` renders the eyebrow, matching marketing's `.accent-eyebrow::before` (6px circle, `background: var(--color-brand-mark)` — the existing verdigris wordmark-dot token, already defined in the app).
- Modify: `app-front-end/src/components/RoomHeader.tsx:33` — apply the eyebrow-dot class to the eyebrow `<p>`.
- Modify: `app-front-end/src/components/InvestmentMemoContent.css` (the score-value rules around `.memoScoreVal`/`.memoDocComponentTrack`/`.memoDocComponentFill`, ~lines 1237-1452) — increase the score numeral's typographic presence (larger `font-size`, consider Playfair per the "keep broadsheet character" decision, or a larger/bolder mono treatment — implementer's call for exact values, staying consistent with the memo's existing scale). Do NOT add any border, background box, or grid container around these values — this is a font-weight/size-only change.

- [ ] Step 1: Investigate `.type-label-section` usage breadth (grep call sites) before deciding global vs. scoped dot.
- [ ] Step 2: Add the dot (scoped correctly), wire into `RoomHeader.tsx`.
- [ ] Step 3: Increase memo scorecard numeral presence — typography only, no box. Compare visually against the current tiny-mono treatment for a clear, deliberate size/weight jump.
- [ ] Step 4: `npm run build && npm run lint && npm test` → PASS.
- [ ] Step 5: Commit: `feat(app): verdigris eyebrow dot on room headers; heavier memo score numerals (no box, per house rule)`

### Task 6: Remaining polish (P2/P3 sweep)

**Files:**
- `app-front-end/src/components/LoginPage.tsx` — the corner furniture currently has only bottom-left/bottom-right (`~575-594`). Check whether a top-left wordmark treatment already exists elsewhere on this page (it likely does, as the page's own logo/header) — if a `.frame.tl`-equivalent doesn't exist, add one matching marketing's corner style; do NOT invent a top-right nav with links to nowhere (login has no obvious nav target) — leave top-right empty if there's nothing meaningful to put there, that's fine, marketing's four-corner symmetry isn't a hard requirement here.
- `app-front-end/src/components/AppSpine.tsx:159-161` and wherever `bureauLine` renders with `truncate` — stop truncating with an ellipsis (reads as broken). Prefer a shorter format (drop `:SS`, show `HH:MM LON · HH:MM SF`) or, if the ~248px rail still can't fit it, stack the two cities on separate lines instead of clipping one string.
- `app-front-end/src/index.css:517-523` (`.doc-rule-with-diamond`) — the diamond is disabled (`content: none`). Check `git log -p --follow -- app-front-end/src/index.css | grep -B5 -A5 "doc-rule-with-diamond"` for why it was killed. If no clear reason surfaces, restore the diamond (match marketing) using marketing's `web-front-end/src/index.css` `.doc-rule-with-diamond::before` rule as reference. If it's genuinely unused anywhere, delete the whole class instead of leaving dead CSS.
- `app-front-end/src/pages/HomePage.tsx:316,323` — door numerals "III"/"IV" → match marketing's plate-numeral language, e.g. `"03 — 04"` / `"04 — 04"` (Home is conceptually plate 01 of 4 rooms: Home/Flow/Portfolio/Fund — confirm against whatever numbering the earlier gallery-mirror pass already established for Flow/Portfolio/Fund's `plateIndex` prop and stay consistent with it).
- `app-front-end/src/settings/SettingsTopBar.tsx:59` — the "Settings." chrome label is `type-display` (Playfair). Demote to the mono chrome voice used elsewhere in the app shell (check `AppSpine.tsx` for the established mono-chrome pattern and match it).
- `app-front-end/src/index.css:203-204` (`.paper-dot-grid`) — nudge `#d6d4d0`/`0.08` toward marketing's `#D9D7D4`/`0.055` (exact values: background-color `#D9D7D4`, dot opacity `0.055`) unless there's a clear reason the app intentionally runs slightly darker (note: this surface sits under dark chrome in places marketing's doesn't — use judgment, but default to matching marketing's exact values since no prior reasoning for the drift was found in the critique).
- `app-front-end/src/index.css` — `--section-divider` currently `rgba(var(--color-oxford-rgb), 0.10)` (~line 32). Change to `0.16` to match marketing's `--line`. This is a global hairline-weight change — after editing, skim 2-3 pages' worth of screenshots or source for any hairline that was clearly tuned to the old lighter value and would now look too heavy; adjust case-by-case rather than assuming uniform 0.10→0.16 is always right. Settings' hand-rolled `oxford/[0.12]`, `/[0.08]`, `/[0.06]`, `/[0.05]` instances are lower priority — sweep to `/[0.16]` where they're clearly meant to be a standard divider, but leave any that are deliberately a lighter sub-divider (e.g. a divider between rows within an already-divided group) — use judgment, don't flatten meaningful hierarchy.

- [ ] Step 1: Login furniture check + fix.
- [ ] Step 2: AppSpine truncation fix.
- [ ] Step 3: Diamond rule — investigate, then restore or delete.
- [ ] Step 4: Home door numerals → plate-numeral language.
- [ ] Step 5: SettingsTopBar Playfair → mono.
- [ ] Step 6: Paper-dot-grid value alignment.
- [ ] Step 7: Hairline value reconciliation (`--section-divider` 0.10→0.16 + judgment sweep of Settings literals).
- [ ] Step 8: `npm run build && npm run lint && npm test` → PASS.
- [ ] Step 9: Commit: `fix(app): remaining marketing-parity polish (furniture, hairlines, dead CSS, numeral language)`
