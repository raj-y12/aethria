# Scope — Corgi Insurance investment memo

## Audited surface

The Corgi Insurance investment memo shown across nine supplied screenshots (approximately 666–729 px wide), plus the current source path that renders the memo:

- `app-front-end/src/components/InvestmentMemo.tsx`
- `app-front-end/src/components/InvestmentMemoContent.tsx`
- `app-front-end/src/components/InvestmentMemoContent.css`
- `app-front-end/src/components/memo/`
- `app-front-end/src/components/scoring/AssessmentScorecard.tsx`
- Relevant reviewer, scoring, thesis, partner-policy, and evidence-provenance code in `backend/` and `resources/config/`

## User and task

- Primary user: a VC partner or investment-team operator.
- Primary task: decide whether the opportunity deserves investment, rejection, monitoring, or additional diligence, then record a human ruling.
- Secondary tasks: understand why the system reached its recommendation, verify the evidence behind material claims, export an IC pack, and add context for re-review.

## Constraints

- Preserve the Aethria editorial brand where it helps comprehension.
- Existing stack: React, TypeScript, Vite, Framer Motion, and the repository design system.
- This is an audit, not an implementation pass.
- Existing user changes in the target source files were treated as read-only.
- The repository prohibits point-in-time audit files at its root, so these required audit artifacts live under `docs/archive/`.
- Accessibility floor: WCAG 2.2 AA.

## Reference evidence

- Nine screenshots supplied by the user, captured on 15 August 2026.
- [Corgi's official website](https://www.corgi.insure/)
- [Corgi's YC company profile](https://www.ycombinator.com/companies/corgi-insurance)
- [Corgi's January 2026 funding and approval announcement](https://www.prnewswire.com/news-releases/corgi-insurance-raises-108-million-receives-regulatory-approval-to-launch-the-first-full-stack-insurance-carrier-for-startups-302657727.html)
- [TechCrunch's July 2026 report on the reported $4B round](https://techcrunch.com/2026/07/23/insurance-startup-corgi-reportedly-raised-more-money-at-4b-its-third-round-in-eight-weeks/)

## Known gaps

- No live authenticated DOM, network trace, screen-reader pass, or Lighthouse run was available.
- The screenshots do not show the appendix or final human-ruling composer.
- Runtime content is data-dependent; screenshot evidence takes precedence where current working-tree source differs from the captured rendering.
