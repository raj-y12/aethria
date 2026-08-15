# Dieter Rams scorecard — Corgi Insurance memo

1. **Good design is innovative — Score: 1/3**
   Evidence: The surface applies a polished editorial dossier treatment to a familiar investment memo, but no observed interaction materially advances the form (`01-evidence.md#per-principle-evidence-map`).
   Justification: This is a competent stylistic variation on existing memo and document patterns, not a clear functional innovation.

2. **Good design makes a product useful — Score: 1/3**
   Evidence: The first screen contains the decision summary, but the human action is buried after duplicated analysis and the recommendation state contradicts itself (`01-evidence.md#copy-decision-integrity-and-honesty-evidence`).
   Justification: The primary task is possible, but the user must resolve unnecessary semantic and navigational detours first.

3. **Good design is aesthetic — Score: 1/3**
   Evidence: The palette and typography are coherent, but S6 visibly overprints Assessment text, S5 shows justification artifacts, faint microcopy fails contrast, and spacing escapes the canonical scale (`01-evidence.md#visual-evidence`).
   Justification: One jarring layout failure plus several systemic inconsistencies keeps this below a minor-refinement score.

4. **Good design makes a product understandable — Score: 0/3**
   Evidence: `Pass`, `Human ruling required`, `Required next move: Pass`, split reviewers, 80% partner confidence, and 25% thesis confidence coexist without a shared model (`01-evidence.md#copy-decision-integrity-and-honesty-evidence`).
   Justification: A first-time user cannot identify the actual decision state or required action without reconstructing the implementation's semantics.

5. **Good design is unobtrusive — Score: 2/3**
   Evidence: Paper, typography, and hairline rules keep chrome quiet, while large vertical gaps, repeated content, and section reveals remain perceptible (`01-evidence.md#visual-evidence`).
   Justification: The interface mostly recedes, but its document theatre and scroll cost do not disappear behind the task.

6. **Good design is honest — Score: 1/3**
   Evidence: Rule integers are presented as confidence percentages, generated labels as evidence, a reported valuation as categorical, and expansion risk as present impossibility (`01-evidence.md#copy-decision-integrity-and-honesty-evidence`).
   Justification: Multiple material claim-to-method mismatches inflate authority even without a conventional dark pattern.

7. **Good design is long-lasting — Score: 2/3**
   Evidence: The flat editorial palette and square geometry are durable, but faux-broadsheet justification and dense tracked mono microcopy are conspicuously stylistic (`01-evidence.md#visual-evidence`).
   Justification: The core visual language should age well, with one clear cluster of dated editorial markers.

8. **Good design is thorough down to the last detail — Score: 2/3**
   Evidence: Empty, loading, error, success, focus, disabled, print, and reduced-motion states exist; the success view still has a severe responsive collision, hidden focus targets, and failing microcopy contrast (`01-evidence.md#state-and-accessibility-evidence`).
   Justification: State coverage is unusually complete, but the shipped success state is rough enough to block a top score.

9. **Good design is environmentally friendly — Score: 1/3**
   Evidence: Initial JS is 547,122 raw bytes, Framer Motion is eagerly preloaded, and the memo can run roughly nine entrance animations; PDF libraries are lazy and there is no idle loop (`01-evidence.md#product-weight-and-friction`).
   Justification: The payload falls in the 500 KB–2 MB band despite some responsible loading and motion decisions.

10. **Good design is as little design as possible — Score: 0/3**
    Evidence: The same regulatory concern and positioning recur across the cover, The Read, Snapshot, Why Now, conviction limits, Assessment, and Risks; nine captures do not reach the appendix or ruling (`01-evidence.md#repetition-and-category-errors`).
    Justification: Duplication dominates the document and materially obscures the decision task.

**Total: 11/30**
