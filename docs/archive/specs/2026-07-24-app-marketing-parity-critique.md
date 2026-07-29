# App ↔ Marketing Design Parity — Critique Findings & Decisions

**Date:** 2026-07-24. **Method:** impeccable:critique skill — deterministic scan (clean, 0/25 — this is a brand-consistency problem, not generic AI-slop) + two independent fresh-context LLM reviews (no session history, read both codebases + live marketing site cold).

## Resolved decisions (user)

1. **Scope:** fix everything found (P0–P3).
2. **Memo section heads:** stay Playfair. The memo is a document/dossier, not a marketing plate — intentional broadsheet character, NOT full marketing parity here. Do not touch `.memoDocSectionHead` or similar recurring memo labels.
3. **Verdict/annotation colors:** one accent only, full marketing parity. Verdict is read by label text, not fill color. Escalation (burgundy) stays reserved for genuine human-attention alerts only — never a decision-verdict color.

## Two findings overridden (conflicted with earlier explicit user corrections this session — not visible to the fresh reviewers)

- **Do NOT add `.focus-frame` to the Flow memo panel.** User explicitly said "remove that bracket" about this exact surface earlier today. Leave it bracket-free.
- **Do NOT rebuild the memo scorecard as a bordered/gridded `.dims` box.** User explicitly rejected boxed number cells on Fund/Portfolio ("what's the use of that") — same pattern, stays rejected. Increase the scorecard's typographic weight instead (bigger Playfair numerals, per decision #2 above), never a border/grid.

## The verdict-badge color feature (a nuance the critique didn't surface)

Verdict badge colors are currently **user-configurable** (`VerdictBadgeConfig[]` from Settings → `DecisionThresholdsPanel.tsx`, stored via `fundConfiguration.ts`), threaded into `DecisionBadge.tsx` as an inline `backgroundColor` override. Full marketing parity would mean deleting this feature. Decision: **do not delete it** — repurpose it. The chip becomes transparent-background/mono/outline (matching marketing's `.record-verdict`); the configured color becomes the **border** tint instead of a fill. This keeps the existing Settings feature meaningful (still a form of at-a-glance customization) while eliminating the filled-pastel-block problem, which was the actual complaint.

## Full punch list (grouped into plan tasks below)

| # | Issue | Severity |
|---|---|---|
| 1 | Body font is Figtree Variable, not Instrument Sans | P0 |
| 2 | Verdict badges filled pastel, not mono outline chip | P0 |
| 3 | Brackets + redundant borders stacked (Home docket, Fund Thesis modal) | P1 |
| 4 | `--color-accent` means burgundy in app, verdigris in marketing — same name, opposite meaning | P1 |
| 5 | Verdigris eyebrow dot missing from RoomHeader everywhere | P2 |
| 6 | Memo scorecard too quiet vs. marketing's numeral weight (no box, per override above) | P2 |
| 7 | Six warm hues beyond the one accent (queue annotations gold/green + badge pastels) | P2 |
| 8 | Login furniture only has bottom two corners; Spine bureau line gets CSS-truncated | P2 |
| 9 | `.impeccable.md` design doc has false claims (Figtree "matches web-front-end", JetBrains Mono mentioned but never loaded) | P3 |
| 10 | Hairline opacity has no single value (`0.10/0.12/0.08/0.06/0.05` vs marketing's `0.16/0.26`) | P3 |
| 11 | Dead `.doc-rule-with-diamond::before { content: none; }` — marketing motif ported then disabled | P3 |
| 12 | Home door numerals are Roman ("III"/"IV"), marketing plate numerals are arabic ranges ("01 — 08") | P3 |
| 13 | `SettingsTopBar.tsx` chrome label set in Playfair — marketing reserves it for names/statements, mono for chrome | P3 |
| 14 | Paper-dot-grid values drift slightly (`#d6d4d0`/0.08 dots vs marketing `#D9D7D4`/0.055) | P3 |
