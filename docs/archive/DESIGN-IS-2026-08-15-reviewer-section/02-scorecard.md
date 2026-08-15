# Reviewer section audit — scorecard

1. **Good design is innovative — Score: 1/3**
   Evidence: Three same-model, same-packet calls are differentiated mainly by instructed posture, then presented as a reviewer panel ([evidence](01-evidence.md#p1--innovative)).
   Justification: This is a familiar multi-agent pattern with renamed prompt roles, not a materially new or better review method.

2. **Good design makes a product useful — Score: 0/3**
   Evidence: Rows omit reviewer-specific reasoning and provenance and provide no path to inspect the “full read” ([evidence](01-evidence.md#p2--useful)).
   Justification: The audited screen does not directly support its primary task—understanding what each reviewer knows and why they disagree.

3. **Good design is aesthetic — Score: 1/3**
   Evidence: The coherent editorial palette is undermined by an unreachable intended layout, width-starved rows, a stranded consensus column, and failing small-text contrast ([evidence](01-evidence.md#p3--aesthetic)).
   Justification: One jarring responsive-layout failure and multiple visible inconsistencies place it below an otherwise polished surface.

4. **Good design makes a product understandable — Score: 0/3**
   Evidence: Same-looking `/10` values use incompatible dimension sets and weights, while one memo can say both “Reviewer state — Unknown” and “Reviewers split” ([evidence](01-evidence.md#p4--understandable)).
   Justification: A user cannot identify which judgment is authoritative or interpret the numbers correctly without reading source code.

5. **Good design is unobtrusive — Score: 2/3**
   Evidence: The paper treatment is quiet and animation-free, though repeated summaries and consensus metadata consume space without adding inspectability ([evidence](01-evidence.md#p5--unobtrusive)).
   Justification: Chrome is visible but restrained; the problem is information value, not visual shouting.

6. **Good design is honest — Score: 0/3**
   Evidence: Prompt lenses are labelled reviewers, order-dependent ties are called consensus, and “evidenced” does not mean verified evidence ([evidence](01-evidence.md#p6--honest)).
   Justification: These are deceptive mappings between labels and behavior on a decision-critical surface, not minor copy inflation.

7. **Good design is long-lasting — Score: 1/3**
   Evidence: Durable editorial styling wraps a fashionable AI-council metaphor and two drifting truth systems ([evidence](01-evidence.md#p7--long-lasting)).
   Justification: The visual shell may age well, but the anthropomorphized agent-panel model reads as a product convention of this AI cycle.

8. **Good design is thorough down to the last detail — Score: 0/3**
   Evidence: Reviewer-specific empty, loading, error, focus, and disabled treatments are missing or rough, with no behavioral tests for core semantics ([evidence](01-evidence.md#p8--thorough-down-to-the-last-detail)).
   Justification: At least four required states are missing, meeting the rubric's zero-score threshold.

9. **Good design is environmentally friendly — Score: 1/3**
   Evidence: Initial JS is 736,482 raw bytes and every startup review makes three same-packet LLM calls while discarding much persona provenance ([evidence](01-evidence.md#p9--environmentally-friendly)).
   Justification: The surface falls in the 500 KB–2 MB band and spends dominant inference cost on output the user cannot properly inspect.

10. **Good design is as little design as possible — Score: 1/3**
    Evidence: Two reviewer renderers, three persona rows, aggregate consensus, governed scoring, and canonical reviewer state duplicate judgment without one shared contract ([evidence](01-evidence.md#p10--as-little-design-as-possible)).
    Justification: Several removable or consolidatable layers remain; complexity has been concealed, not reduced.

## Total

**7/30**

The verdict follows mechanically: the total is below 20 and the load-bearing principles Useful, Understandable, and Honest each score 0.
