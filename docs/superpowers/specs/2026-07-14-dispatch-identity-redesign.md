# Dispatch company identity redesign

## Purpose

Redesign the ambiguous-company selection step in Dispatch so an investor can distinguish similarly named companies quickly and understand why Aethria considers each candidate plausible. Fix the background activity dots so they remain ambient and spatially stable instead of appearing to fly or zoom across the screen.

## Product principles

- The screen answers one question: “Which real company did you mean?”
- Identity evidence is more important than investment data at this stage.
- Aethria may recommend a likely match, but the analyst makes the selection.
- Only verified resolver data is shown. Sector, funding, founders, stage, and geography remain out of this chooser unless the resolver later provides them explicitly.
- Motion communicates activity without competing with the decision.

## Information hierarchy

Each candidate becomes a compact identity brief with four layers:

1. **Identity:** candidate number, company name, and registrable domain.
2. **Company description:** the resolver’s best evidence-backed snippet, limited to two or three readable lines.
3. **Match quality:** a plain-language label derived from confidence—“Strong identity match,” “Likely identity match,” or “Possible identity match”—with the numeric percentage secondary.
4. **Evidence:** a “Verified by” row that translates resolver badges into readable sources such as Official site, LinkedIn, Crunchbase, or Press.

The highest-confidence candidate receives a restrained “Best match” marker only when it clears the strong-match threshold. Other candidates remain visually neutral. Confidence never auto-selects a company.

## Layout and visual treatment

The candidate chooser expands beyond the current narrow card stack to a responsive editorial dossier:

- The section uses a wider reading measure inside the Dispatch progress view while preserving the centered takeover composition.
- A section header explains why confirmation is required and shows the number of plausible identities.
- Candidates render as asymmetric horizontal rows on desktop: candidate number and confidence sit in a narrow evidence rail; identity, description, and sources occupy the main column; the selection affordance sits at the row edge.
- Mobile collapses each row into a single column without hiding evidence or requiring horizontal scrolling.
- Rows use subtle surface tint and dividers rather than generic floating cards and heavy shadows.
- Hover changes border/surface color only on fine pointers. Press feedback uses a small, fast scale. Keyboard focus remains visibly outlined.
- The selected action reads “Use this company” and includes the candidate domain in its accessible label.
- The website-refinement path becomes a composed secondary panel labeled “None of these?” with a short explanation and an explicit website field.

## Candidate data and boundaries

The first implementation uses the existing `LookupCandidate` contract:

- `name`
- `website`
- `description`
- `confidence`
- `source_badges`

Presentation helpers normalize domains, confidence labels, source names, and best-match eligibility. They live alongside the picker or in a focused identity-presentation module and are covered directly by unit tests. The backend resolver contract does not expand in this change because it does not currently verify richer company-profile fields per candidate.

Unknown or empty values degrade cleanly:

- Missing description shows a direct identity-only explanation rather than an empty gap.
- Missing badges display “Official domain candidate” when a valid company-owned domain exists.
- Confidence is clamped to the 0–100% display range.
- A candidate without a usable website remains selectable only if the existing API allows it; the UI does not manufacture a link.

## Background activity dots

Dispatch activity dots become spatially stable:

- Dot positions are generated once when an active lookup begins and are recomputed only when the overlay’s measured grid dimensions change.
- Dots do not relocate on animation iterations.
- Each dot only animates opacity and a restrained scale range near `1`—never from a visibly small size that reads as depth travel.
- Predetermined breathing uses CSS animation so it remains smooth under pipeline/network load.
- Dot count, opacity, and stagger remain varied enough to avoid a mechanical pattern.
- `prefers-reduced-motion` removes scale movement and leaves either a static low-opacity field or no activity overlay.
- Resize handling uses `ResizeObserver` on the actual overlay rather than relying only on the window resize event.

## Component changes

### `CandidatePicker`

Owns the identity-brief composition, confidence/evidence presentation, selection actions, and website-refinement panel. It remains controlled by the existing `onPick`, `onRefine`, and `busy` contract.

### `DispatchCommandBar`

Provides a wider candidate container in the Identify stage and avoids applying a second competing entrance animation around the picker. Other Dispatch stages and result views keep their existing layout.

### `DispatchDotPulse`

Measures available grid space, creates stable dot coordinates for the active session, and renders decorative spans without per-cycle React state updates.

### Global motion styles

The dot keyframes change from a zoom-like `0.6 → 1 → 0.6` loop to a restrained opacity/scale breath. Reduced-motion behavior is explicit.

## Interaction and accessibility

- Candidate rows remain native buttons or contain one unambiguous native selection button, avoiding nested interactive elements.
- Domain text is readable without a protocol while accessible labels retain enough identity detail.
- The section announces its purpose and candidate count.
- Busy state disables candidate selection and website refinement consistently.
- Focus order follows candidate ranking, then the “None of these?” refinement path.
- Evidence badges are text, not icon-only signals.
- Motion is decorative and hidden from assistive technology.

## Testing and verification

Automated coverage will verify:

- confidence-label thresholds and clamping;
- best-match designation rules;
- evidence-label normalization and fallback behavior;
- candidate name, domain, description, confidence, and sources render together;
- candidate selection and website refinement preserve their existing callbacks;
- the dot overlay has no animation-iteration relocation path;
- reduced-motion CSS disables positional/scale movement;
- existing Dispatch lookup tests remain green.

Final verification includes frontend unit tests, lint, production build, and a browser check at desktop and mobile widths. The browser check covers long names, missing descriptions, multiple evidence sources, keyboard focus, busy state, and an active lookup lasting several animation cycles.

## Out of scope

- Adding unverified sector, funding, founder, stage, or geography data to resolver candidates.
- Changing resolver ranking or automatic resolution thresholds.
- Redesigning Dispatch compose, review, decision, or result screens.
- Replacing the project’s typography, color tokens, animation library, or overall navigation.
