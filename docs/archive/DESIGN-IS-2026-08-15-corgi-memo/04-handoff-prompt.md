# /make-plan handoff

```text
/make-plan Redesign the Aethria investment memo. Current design failed audit at 11/30 with critical gaps in principles #2 Useful, #4 Understandable, #6 Honest, and #10 As little design as possible.

Verdict paragraph (quoted from 03-verdict.md):
> REDESIGN: the visual shell has assets worth preserving, but at 11/30 the memo fails the load-bearing requirements of understandable, honest, useful decision support and cannot be repaired by copy polish alone.

Why redesign and not refine: the total is below 20 and the load-bearing Understandable principle scored 0 because the current surface cannot express recommendation, evidence state, and human decision without contradiction.

Preserve from current design:
- The paper/Oxford/burgundy palette and Playfair Display/Instrument Sans/Space Mono role system in app-front-end/src/components/InvestmentMemoContent.css:8-24.
- The cover's company → recommendation → reason hierarchy in app-front-end/src/components/memo/MemoDossierOpening.tsx:27-63.
- Focus trapping, Escape handling, reduced-motion, print, empty, and error foundations in app-front-end/src/components/InvestmentMemo.tsx:26-95 and app-front-end/src/components/InvestmentMemoContent.tsx:626-682.

Discard:
- The linear opening → The Read → seven duplicative sections → appendix → buried ruling structure. Evidence: app-front-end/src/components/InvestmentMemoContent.tsx:684-1442. Caused failure on principles #2 and #10.
- Probability-like `partner confidence`, generic `evidence-backed`, and categorical Pass on incomplete or contradictory evidence. Evidence: app-front-end/src/components/InvestmentMemoContent.tsx:518-535,1051-1085 and backend/partner/decision.py:924-951,1620-1658. Caused failure on principles #4 and #6.
- Separate What Limits Conviction and Risks renderings of the same adverse register, plus process diagnostics treated as company risks. Evidence: app-front-end/src/components/InvestmentMemoContent.tsx:891-903,1051-1085. Caused failure on principles #2, #6, and #10.
- The current Assessment responsive grid. Evidence: app-front-end/src/components/InvestmentMemoContent.css:1462-1485,2098-2101 and screenshot 6. Caused failure on principles #3 and #8.

Top 3–5 moves from the audit (verbatim):
1. Principle #6 — Honest: Replace authority theatre with explicit evidence states—verified, rule-derived, model-derived, reported, and missing—and attach every material claim to an inline source; incomplete or contradictory evidence must produce `Blocked`, not a categorical `Pass`. Evidence: 01-evidence.md#copy-decision-integrity-and-honesty-evidence.
2. Principle #4 — Understandable: Establish one decision-state model and one confidence vocabulary that separately names recommendation, mandate match, evidence coverage, reviewer disagreement, and human ruling; never present rule integers as probabilities. Evidence: 01-evidence.md#copy-decision-integrity-and-honesty-evidence.
3. Principle #2 — Useful: Rebuild the primary view around a one-screen decision brief: current status, recommendation, three independent decision drivers, top evidence gaps, and the human action; move detailed scoring, pipeline history, and supporting analysis behind secondary disclosure. Evidence: 01-evidence.md#structural-evidence.
4. Principle #10 — Minimal: Semantically deduplicate the memo before rendering; keep one timing section and one risk register, exclude internal scoring diagnostics from company risks, and remove restatements disguised as reframes or capability slopes. Evidence: 01-evidence.md#repetition-and-category-errors.
5. Principles #3/#8 — Aesthetic and thorough: Replace the failing Assessment layout, remove on-screen justification, raise microcopy contrast/size to AA, and make closed disclosures truly inert; verify the captured width range and keyboard flow. Evidence: 01-evidence.md#visual-evidence and 01-evidence.md#state-and-accessibility-evidence.

Redesign principles in priority order:
1. Principle #6 — Honest — every visible claim exposes provenance and certainty without pretending model or rule output is sourced fact.
2. Principle #4 — Understandable — a first-time partner can state the recommendation, evidence state, open question, and required human action in under 15 seconds.
3. Principle #2 — Useful — the primary decision and ruling fit in one working view; deep analysis remains reachable without blocking the task.
4. Principle #10 — As little design as possible — each fact, risk, and action appears once in the primary narrative.

Deliverables for the plan:
- New information architecture not derived from the old section order.
- New primary flow, low-fi and labeled, compared side-by-side with the current memo.
- A typed decision/evidence-state contract covering recommendation, Blocked, mandate match, evidence coverage, reviewer disagreement, and human ruling.
- Claim-level provenance and semantic-deduplication strategy across backend payload and frontend rendering.
- States checklist: empty, loading, blocked, error, success, focus, disabled, read-only, and print.
- Responsive and accessibility verification at 520, 666, 680, 729, 760, and desktop widths.
- Migration path for persisted legacy memos and a cutover criterion for retiring the old rendering.

Anti-patterns to guard against:
- Porting the old section order under new styling.
- Keeping both designs behind a flag indefinitely.
- Replacing one invented confidence percentage with another.
- Treating retrieval failure as negative company evidence.
- Allowing policy labels, reviewer persona names, or scoring diagnostics to masquerade as company facts.
- Treating the Preserve list as optional.
```
