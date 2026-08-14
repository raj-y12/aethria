# Aethria web frontend premium refresh

## Status

Approved direction; implementation pending review of this design.

## Intent

Aethria should feel like a high-quality technology and intelligence company: forward-looking, precise, institutional, and visually confident. The current “Gallery of Instruments” direction has strong materiality and pacing, but its repeated plate structure makes the whole site read as a slide deck. This refresh keeps the best parts of that language while giving the web frontend a more varied, product-led composition.

The site’s primary job remains converting serious fund teams into qualified access requests. It should also establish enough company credibility for investors, partners, press, and future hires without becoming a generic corporate site.

## Preserve

- Grey stock and oxford navy as the dominant material palette.
- Verdigris as the single primary accent; heritage gold remains a restrained secondary detail where it already carries meaning.
- Space Mono for labels, evidence metadata, timestamps, and product/system language.
- Instrument Sans as the default interface and body face.
- Playfair Display only for rare thesis statements, editorial pull quotes, or one high-impact page title at a time.
- The existing evidence-first product story: thesis, source, evaluation, decision, memory.
- Framer Motion, Lenis, Vite, React, and the existing SSG/build pipeline.
- Existing routes, access modal/form behavior, links, reduced-motion support, and marketing verification gates.

## Change

### Shared shell

The frame remains a recognizable Aethria signature, but it becomes quieter and more functional:

- Keep the wordmark and primary navigation.
- Reduce the feeling of four permanent slide-deck corners by allowing the frame to recede on content-heavy sections.
- Use active route state and one primary access action consistently.
- Introduce a compact scroll-state treatment for long pages rather than repeating identical marginal furniture everywhere.

### Home page

Replace the sequence of visually similar plates with a chapter rhythm that alternates between product evidence and editorial space:

1. Thesis hero: a crisp technical headline and an immediately legible decision artifact.
2. Product proof: an actual interface-like composition showing the relationship between thesis, evidence, review, and decision.
3. Market intelligence: retain the geographic/data story, but give it a stronger visual stage and less card-like framing.
4. Institutional memory: use the record/review material as a deep oxford chapter with a single focused interaction.
5. Research/news: make it feel like an active intelligence desk rather than another plate.
6. Access: a quiet, high-trust close with one clear action.

No new backend data or API is required for this pass. Existing static data and UI primitives should be composed into stronger scenes.

### Team page

Keep the approved content flow, but elevate the visual hierarchy:

- Use the founder image as a deliberate editorial portrait, not a small profile card.
- Lead with company thesis and founder credibility rather than a generic team heading.
- Keep the decision-record artifact, but make it feel like a real product specimen.
- Use a more varied rhythm between biography, philosophy, evidence, and invitation.
- End with one high-trust conversation CTA.

### Product and visual language

The refreshed system uses five surface modes:

- `stock-editorial`: default page material, generous whitespace, crisp type.
- `oxford-intelligence`: high-contrast chapter for product evidence, trust, or decisions.
- `product-evidence`: diagrams, UI fragments, source lines, and system metadata.
- `image-led`: founder, office, or product photography with minimal overlays.
- `quiet-transition`: whitespace and hairlines used to reset attention between scenes.

The existing plate component may remain for compatibility, but new composition should not force every section through the same component or height treatment.

## Typography rules

- Instrument Sans is the default for hero copy, navigation, body copy, buttons, and explanatory text.
- Space Mono carries labels and technical metadata.
- Playfair Display is reserved for a small number of thesis moments. It must not be used for every section heading or for navigation.
- Use stronger sans weights and tighter line-height before reaching for a serif accent.
- Headlines should use balanced wrapping and short line lengths; body copy should remain around 55–65 characters per line.

## Motion rules

- One arrival sequence for the site, not a separate theatrical entrance for every section.
- Product evidence can reveal through opacity, masks, and translated layers.
- Interactive states should feel physical but restrained: 200–300ms transitions, visible focus, pressed feedback.
- No autoplay video, WebGL scene, or perpetual ambient animation unless it materially explains Aethria.
- `prefers-reduced-motion` must disable the nonessential motion path.

## Quality bar

- The first viewport must communicate what Aethria is and why it is credible without scrolling.
- Each section needs a distinct job and visual mode; no sequence of interchangeable cards or plates.
- Any visual flourish must be tied to evidence, decision-making, research, or institutional memory.
- Real product imagery and the founder photo take priority over decorative stock imagery.
- The design must remain legible and intentional at mobile widths.
- Existing functionality and public route contracts must remain intact.

## Research references

The direction is informed by current company and award-level references:

- Anthropic company page: thesis → purpose → disciplines → values. <https://www.anthropic.com/company?type=company>
- Sierra about page: human positioning → principles → founders → proof. <https://sierra.ai/about>
- Harvey company page: measurable proof, customer credibility, team, and CTA. <https://www.harvey.ai/company>
- Runway about page: thesis-led company story with research, product, imagery, and careers. <https://runway.com/about>
- Webby-winning State of AI report: interactive and multimedia storytelling used to make technical material legible. <https://winners.webbyawards.com/2024/websites-and-mobile-sites/features-design/best-individual-editorial-feature-indbrandorg/280457/state-of-ai-report>
- Flowstep: product UI and editable interface examples used as the primary proof of the product. <https://flowstep.ai/>

## Out of scope

- Backend or API changes.
- New marketing claims, metrics, customer logos, or awards not backed by repository evidence.
- Replacing the existing React/Vite/SSG stack.
- Rebuilding the authenticated operator app in this pass.
- Adding a new animation or UI library.

## Implementation acceptance

- Home and team are redesigned around distinct visual scenes rather than repeated plates.
- Playfair usage is reduced and verified by source review.
- Existing access flow, navigation, route behavior, and metadata continue to work.
- `npm run lint`, `npm run build`, `npm run check:bundle`, `npm run check:marketing`, `npm run check:contrast`, and `npm run check:waitlist` pass in `web-front-end`.
- `git diff --check` passes.
