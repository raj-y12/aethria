# IC Dossier Sunday Review Redesign

Date: 2026-07-10

## Objective

Restyle the complete investment memo as a modern Sunday-review-style IC dossier. Preserve Aethria's existing typefaces—Playfair Display, Figtree Variable, and Space Mono—while making typography and whitespace, rather than prominent ruling, the primary source of hierarchy.

The page must feel considered and editorial without becoming ornamental. It remains an investment decision instrument: the recommendation, evidence, risks, and final ruling must stay fast to scan.

## Approved Direction

The chosen direction is **Sunday Review with soft rules**.

Its character comes from:

- a generous, asymmetrical editorial opening;
- restrained Playfair Display headlines and verdict typography;
- Figtree for all explanatory prose and controls;
- Space Mono only for document metadata, labels, numbers, and compact status text;
- larger vertical intervals between major ideas;
- short, low-contrast strokes beneath section titles instead of dominant full-width borders;
- one signature pull-question—“What decides it”—placed between the cover recommendation and the body;
- nearly flat surfaces, with background tint used only when a control area needs separation.

The design must not introduce new fonts or an unrelated color system.

## Visual Tokens

### Type

- **Display:** existing `--font-display` / Playfair Display. Company title, recommendation, major section headings, pull-question, and high-level score only.
- **Body and interface:** existing `--font-sans` / Figtree Variable. Prose, descriptions, buttons, form controls, and detailed assessment content.
- **Utility:** existing `--font-mono` / Space Mono. Eyebrows, folio data, section numbers, metric labels, evidence metadata, and compact numeric values.

Display type should be lighter and more spacious than the current memo. Body prose must retain a readable editorial measure and never be reduced to metadata scale.

### Colour

- **Paper:** existing paper token, used as the continuous document field.
- **Oxford ink:** existing Oxford blue for primary text and decisive actions.
- **Muted ink:** Oxford blue at approximately 42–72% opacity for secondary information.
- **Soft structure:** Oxford blue at approximately 8–14% opacity for the few necessary separators.
- **Risk accent:** existing accent colour, used sparingly for high-risk severity and escalation states.
- **Control wash:** Oxford blue at approximately 3–4% opacity, reserved for the final ruling area and exceptional system notices.

Decision states continue to use the existing semantic verdict tokens where those states need colour. Colour must not become decorative.

### Spacing and Measure

- Embedded memo content uses the available panel width with a comfortable inner gutter; full-screen/mobile uses a narrower reading measure.
- Major sections receive visibly larger top spacing than internal rows.
- The opening recommendation uses a wide editorial column plus a narrower decision-record column when the container is wide enough.
- Long narrative content may use two balanced columns only at generous container widths. It collapses to one column before either column becomes narrow.
- Detail lists, definitions, score rows, and risk entries use compact internal rhythm so the overall document remains scannable.

## Layout and Component Treatment

### 1. Memo Masthead

`MemoMasthead` becomes a quiet folio rather than a toolbar framed by rules.

- Aethria / IC identity sits at the upper left.
- Dossier number, issue date, and privacy state sit at the upper right in Space Mono.
- Company name is the page's largest identity headline, followed by an italic descriptor and lightweight tags.
- Add context, PDF, and close remain available but visually subordinate. On narrow screens they wrap into a compact action row without competing with the company name.
- Full-width dark lines are removed from the masthead.

### 2. Dossier Opening

`MemoDossierOpening` owns the decision-cover hierarchy.

- The partner recommendation and standfirst occupy the primary column.
- Conviction, reviewer state, mandate fit, and status form a sparse decision record in the secondary column.
- Metrics are separated by breathing room and very light hairlines only where needed.
- The highest-priority blocker appears below the record with a subtle risk-colour rule.
- The focal question becomes the signature editorial pull-question below the opening grid.
- The required next move follows the question or the record as a concise action note, never as a competing card.

### 3. Context Modules

`MemoPrecedentStrip` and `MemoPortfolioContext` must read as adjacent editorial evidence, not dashboard widgets.

- Collapsed states use a label, concise summary, and quiet disclosure marker.
- Expanded precedent entries use flat rows with restrained verdict chips, rationale, match reasons, and date.
- Portfolio signals use a compact chronological list with type and date aligned as metadata.
- Containers avoid rounded cards and heavy outlines.

### 4. Numbered Dossier Sections

`MemoSectionTitle` establishes a shared section grammar for Snapshot, Why Now, What Limits Conviction, Assessment, and Risks.

- A small Space Mono section number occupies a narrow left rail.
- The Playfair section title sits in the content column.
- A short 24–32px, low-contrast stroke appears beneath the title.
- Major sections use whitespace, not repeated full-width horizontal rules, to separate from one another.
- Numbering remains because these sections form the intended IC reading order.

### 5. Snapshot

- Definition rows form a two-column editorial record at wide container sizes and a single column when narrow.
- Labels remain compact and aligned; values receive enough width and line height for real company data.
- Rows have no boxes. Only spacing and alignment separate facts.
- Missing values remain omitted under existing data rules.

### 6. Investment Case and Conviction Limits

- Investment-case prose is set as a readable editorial narrative. Two text columns are allowed only where the content and width support them.
- Ranked conviction limits use a two-column risk/editorial grid at wide widths and a single column when narrow.
- Rank and severity are metadata; the risk statement is the visual lead.
- Risk descriptions use muted body text. High severity may use the existing accent on the severity label, not a filled card.

### 7. Assessment Scorecard

`AssessmentScorecard` and its scoring children are restyled as an editorial evidence instrument.

- The overall score is a restrained Playfair display value with Figtree/Space Mono support text.
- Dimension summaries become a balanced grid on wide containers and stacked rows on narrow ones.
- Score tracks remain because they encode magnitude, but they use two-pixel, low-contrast tracks and Oxford fills.
- Expanded reasoning, evidence, gaps, reviewer consensus, moat dimensions, and method disclosures share the same label/prose rhythm.
- The interface must preserve all existing disclosure behavior, keyboard access, and reduced-motion behavior.

### 8. Risk Register

- Adverse-register entries use flat editorial rows, not bordered cards.
- Severity, rank, basis, source, and missing-data states are clearly distinguished through label scale and alignment.
- Missing evidence, other risks, and mitigation use the same list grammar as the rest of the dossier.
- The risk-acknowledgement gate remains unmistakable and accessible without dominating the document before interaction is required.

### 9. Final Ruling

`MemoRulingSection` is the one intentional control surface.

- It receives a very light Oxford wash to distinguish an action area from read-only analysis.
- Invest, Monitor, and Pass form a flat segmented choice with semantic selected state.
- The rationale field uses a clean editorial underline and a clear focus state.
- Commit ruling remains the decisive Oxford action.
- Disabled, saving, risk-gated, error, and success states retain explicit text—not colour alone.
- Read-only mode continues to omit ruling controls.

### 10. Appendix and Disclosures

- Partner rationale, reviewer detail, company resolution, analyst context, sources, and run log become a quiet appendix index.
- Closed rows use thin, low-contrast separators because they encode interactive boundaries.
- Open content follows the same typography and list grammar as the main dossier.
- The appendix label is present only when at least one disclosure renders.

### 11. System States

- Loading/generating, pipeline failure, read-only, and empty states use the same editorial system.
- Failure and escalation may use the risk accent, but remain flat and text-led.
- Empty state preserves the Aethria identity and gives a clear next instruction.
- No state may cause major layout shift when the memo partial payload becomes ready.

## CSS and Component Architecture

The current `InvestmentMemoContent.css` has accumulated multiple overlapping memo generations and exceeds 5,000 lines. The implementation should consolidate rather than append another override layer.

- Keep the existing component boundaries where they already express clear responsibilities: masthead, dossier opening, section title, precedent, portfolio context, scorecard, and ruling.
- Replace superseded memo selectors and container-query overrides with one ordered stylesheet organized by tokens, document shell, opening, shared section primitives, component sections, interaction states, and responsive rules.
- Remove dead selectors only after confirming they are unused across the frontend.
- Prefer shared primitives for labels, prose, section titles, flat rows, disclosures, and focus states so every memo component visibly belongs to one system.
- Keep the existing data flow, derived memo content, polling, ruling submission, PDF generation, and tenant/auth behavior unchanged.
- Do not modify backend models or API contracts for this redesign.

## Responsive Behaviour

The memo responds to its own container width because it appears both embedded in the workspace and full-screen on smaller devices.

- Wide: two-column dossier opening, paired snapshot/risk layouts, and optional two-column narrative.
- Medium: opening remains two columns only while the decision record has sufficient width; score dimensions may wrap.
- Narrow: all content becomes single-column; section-number rail tightens; display sizes reduce; masthead actions wrap; ruling controls remain at least 44px high.
- No horizontal scrolling is permitted in memo content, score details, or disclosures.
- Focus outlines remain visible against paper and the ruling wash.
- Reduced-motion preferences continue to disable nonessential transitions.

## Data Flow and Behaviour

This is a presentation redesign only.

1. `InvestmentMemoContent` continues to merge partial memo payloads and derive all display data.
2. Child components continue to receive presentation-ready props.
3. Disclosures and expandable lists retain local open/closed state.
4. Ruling actions continue to use the existing optimistic update and API error rollback.
5. PDF export remains functionally unchanged; the on-screen visual redesign does not silently change IC pack content.

## Verification

### Automated

- Run the existing memo component and helper tests.
- Update assertions only where class names or intentionally changed markup require it.
- Add or extend tests for the approved opening hierarchy, responsive-safe structural wrappers, disclosure accessibility, and ruling states.
- Run frontend type checking and the production build.

### Visual

Verify representative memos in both embedded and modal/full-screen contexts at wide, medium, and mobile widths.

Review at least:

- a complete INVEST memo with scores, risks, precedents, portfolio signals, and ruling controls;
- a MONITOR or PASS memo;
- a memo with sparse data;
- a generating/partial memo;
- a pipeline failure;
- a read-only memo;
- expanded assessment and appendix disclosures;
- keyboard focus, long company names, long evidence text, and reduced motion.

Success means the complete dossier reads as one editorial system, the recommendation and critical question are immediately legible, dense evidence remains scannable, and no component falls back to the previous card-heavy or rule-heavy styling.

## Out of Scope

- Changing memo data, recommendation logic, reviewer scoring, or partner rules.
- Changing the three existing font families.
- Redesigning the deal-flow queue or global application shell.
- Redesigning the generated PDF in this pass.
- Adding new animation libraries or significant motion.
