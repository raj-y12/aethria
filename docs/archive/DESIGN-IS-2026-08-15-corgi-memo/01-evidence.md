# Evidence — Corgi Insurance investment memo

## Screenshot key

- **S1**: cover, recommendation, decision record, blocker, next move, opening deciding question.
- **S2**: deciding question, prior rulings, The Read.
- **S3**: capability slope and Snapshot opening.
- **S4**: complete Snapshot.
- **S5**: Founder and Why Now.
- **S6**: What Limits Conviction and Assessment.
- **S7**: Path to a 9, competition, business model, thesis alignment.
- **S8**: upper risk register.
- **S9**: remaining risks, missing evidence, mitigation.

## Structural evidence

- Five visible controls in S1–S9: Add context, IC pack (PDF), Close, Prior rulings, and Show less. Source: `MemoMasthead.tsx:38-61`, `MemoPrecedentStrip.tsx:71-87`, `InvestmentMemoContent.tsx:128-155`.
- Primary component depth is five levels through confirmation: `InvestmentMemo → InvestmentMemoContent → OpportunityIntelligence → HumanRulingComposer → RulingConfirmation`. Source: `InvestmentMemo.tsx:80-89`, `InvestmentMemoContent.tsx:1404-1410`, `OpportunityIntelligence.tsx:177-184`, `HumanRulingComposer.tsx:158-174`.
- Two repeated affordance families appear: disclosure toggles and show-more/list toggles. The appendix alone can contain up to seven custom disclosures. Source: `InvestmentMemoContent.tsx:1129-1401`.
- One dead callback contract exists: `onDecisionResolved` is forwarded and declared but not consumed; completion closes the memo directly. Source: `InvestmentMemo.tsx:12-20,80-89`, `InvestmentMemoContent.tsx:96-109,208-220,1404-1410`.

## Visual evidence

- The memo uses three base hues: paper `#D9D7D4`, Oxford `#0A1629`, and burgundy `#6E2A3C`; display/body/metadata use Playfair Display, Instrument Sans, and Space Mono. Source: `InvestmentMemoContent.css:8-24`.
- The canonical spacing scale is `[3, 5, 8, 13, 21, 34, 55, 89, 144]`, but the memo declares or derives dozens of off-scale values between 1 and 104 px. Source: `design-system/tokens.ts:30-40`, `InvestmentMemoContent.css`.
- Main prose contrast is strong: body ink is about 8.12:1 against paper. Small muted text is about 4.21:1 and faint text about 3.17:1; both are used at roughly 9–11 px and fail WCAG AA for normal text. Source: `InvestmentMemoContent.css:13-16,132-139,193-208,356-365,727-737`.
- S6 has visible text collision in Assessment: evidence labels overprint reviewer takeaways. The relevant reviewer layout reserves only 44 px for the score column and 40 px at the narrow breakpoint. Source: `InvestmentMemoContent.css:1462-1485,2098-2101`.
- S5 shows stretched word spacing and mid-word hyphenation caused by on-screen justified text and automatic hyphenation. Source: `InvestmentMemoContent.css:711-720,1168-1180`.
- Nine viewport captures reach only through risk mitigation, before the appendix and final human ruling. The design combines large section gaps with locally dense prose.

## State and accessibility evidence

- Empty, loading/partial, error, ready, focus, disabled, read-only, reduced-motion, and print states are represented in source. Source: `InvestmentMemoContent.tsx:208-326,626-682`, `InvestmentMemoContent.css:1946-2000`.
- The modal has a focus trap, Escape close, and focus restoration. Source: `InvestmentMemo.tsx:31-38`, `hooks/useFocusTrap.ts:3-74`.
- Closed custom disclosure bodies use `aria-hidden` and visual collapse but not `hidden` or `inert`; descendant links remain in the focus-trap selector and can enter the Tab sequence while invisible. Source: `InvestmentMemoContent.tsx:175-204,1207-1375`, `InvestmentMemoContent.css:1855-1882`, `hooks/useFocusTrap.ts:3-8`.
- Score-row buttons expose `aria-expanded` without an `aria-controls` relationship. Source: `AssessmentScorecard.tsx:147-177`.
- No memo skip link exists; the sticky ruling jump appears after the actual ruling composer in DOM order. Source: `InvestmentMemoContent.tsx:1404-1442`.

## Copy, decision integrity, and honesty evidence

- S1 says `Pass`, `80% partner confidence`, `Panel 3 · Split`, `Outside mandate`, `Human ruling required`, and `Required next move: Pass` at once. The user cannot tell whether the system decided, recommended, blocked, or deferred.
- `80% partner confidence` is not calibrated probability. Partner code assigns conviction 8 in an incomplete-coverage critical-risk branch and the UI divides the stored confidence by one and formats it as a percentage. Source: `backend/partner/decision.py:924-951,1620-1658`, `InvestmentMemoContent.tsx:518-535`.
- S7's `25% confidence` is a hard-coded rule-mode sentinel, while `5/10` is a small keyword tally for sector, stage, and geography. It is not a statistical confidence or a measured ten-point model. Source: `backend/fund_thesis.py:220-221,263-340`.
- `Regulatory or execution impossibility` is a generic policy label. Partner logic treats the presence of configured regulatory terms as a critical risk, allowing expansion risk to become present-tense impossibility. Source: `resources/config/reviewer_rules/v2.json:25-29`, `resources/config/partner_rules/v4.json:54-61`, `backend/partner/decision.py:1452-1460`.
- The reviewer prompt explicitly says to distinguish current operation from future expansion risk, but the displayed memo does not. Source: `backend/reviewer/base.py:1017-1020`.
- S8–S9 display combinations such as `evidence-backed · Missing data · Reviewer red flag`. `evidence-backed` is assigned whenever a generated source label is nonempty; the label is not a citation. Source: `app-front-end/src/lib/adverseRegister.ts:93-99,125-137`.
- Inline claims have no claim-level citations. Sources are optional, collapsed, and rendered in an appendix. Source: `InvestmentMemoContent.tsx:1350-1376`, `memoContentHelpers.tsx:47-65`.
- S6 shows numeric `2.0` reviewer scores with `0% evidenced`; the scorecard's own method says unsupported dimensions should read `Not scored`. Source: `AssessmentScorecard.tsx:49-53,115-124`, `InvestmentMemoContent.tsx:570-587`.
- The Corgi founders and their roles are readily available on YC, yet S5 says roles and histories were not retrieved. This is a retrieval failure presented as evidence scarcity.
- S5 dates regulatory approval to January 2026. Corgi's public materials place approval in July 2025; January 2026 was the public funding/launch announcement.
- S4 presents `$4B post-money` as settled fact. Contemporary reporting described the round as reported and noted uncertainty; the memo strips the qualifier.
- `Rapid valuation increases signal strong demand for AI-enabled insurance models` mistakes investor demand for equity for customer demand, underwriting quality, or profitable policies.

## Repetition and category errors

- Four of five High risks in S8 are paraphrases of regulatory expansion risk. Deduplication compares normalized exact strings, so semantic duplicates survive. Source: `app-front-end/src/lib/adverseRegister.ts:63-66`.
- `Gap ≥4 between highest and lowest dimension` is an internal process diagnostic, not a company risk, yet it is counted as High and material.
- `What Limits Conviction` renders adverse items and `Risks` renders them again. Source: `memoContentHelpers.tsx:438-460`, `InvestmentMemoContent.tsx:891-903,1051-1085`.
- The Read's obvious question is profitability; its supposedly different deciding question is durable profitable growth. The reframe is a restatement, despite policy saying forced reframes should be omitted. Source: `reviewer_rules/v2.json:65-67`.
- Capability slope claims Corgi handles multi-line underwriting and pricing `at scale`, while the same memo says technical execution and scalability are unvalidated and no policy/retention/unit-economics evidence was retrieved.
- `Relying on third-party data without developing a data moat` appears under `Downhill from there`; that is a strategic weakness, not a demonstrated easier adjacency.
- Why Now has one overloaded timing paragraph followed by four bullets that repeat product positioning, mandate metadata, or the same regulatory/fundraising claims.
- Snapshot, descriptor, Why Now, reviewer summaries, competitive landscape, and business model repeatedly reuse the same `AI-native/full-stack/regulatory clearance/fundraising momentum` language.
- `Mitigation` contains diligence requests, not business-risk mitigations. `Path to a 9` mostly lists information the analyst failed to retrieve, not company changes that would create a nine-quality investment.

## Product weight and friction

- Existing build output has five initial JS files totaling 547,122 raw bytes / 171,395 gzip bytes, plus 121,565 raw / 22,383 gzip bytes of CSS. Source: `dist/index.html` and `dist/assets/`.
- Initial static request floor is eight: document, five JS files, CSS, and favicon. Fonts and runtime/API calls add more.
- Framer Motion is eagerly preloaded at 126,579 raw / 41,409 gzip bytes. PDF dependencies are correctly lazy. Source: `vite.config.ts:17-43`, `memoIcPack.ts:577-578`.
- No looping idle animation is present. The populated memo can trigger roughly nine one-shot entrance/reveal animations. Source: `InvestmentMemoContent.tsx:614-675,715-1126`.
- TTI was not measured. A source-only estimate is roughly 2.5–5 seconds on Fast-3G-class conditions; this is not a lab result.

## Per-principle evidence map

1. Innovative: editorial dossier presentation refreshes a familiar investment-memo pattern but does not create a demonstrably new interaction.
2. Useful: key decision data appears first, but contradictory state, duplicated sections, buried action, and missing inline evidence obstruct the primary task.
3. Aesthetic: typography and palette are coherent; S6 overlap, S5 justification artifacts, off-scale spacing, and faint microcopy are visible failures.
4. Understandable: multiple incompatible confidence figures and Pass/block/human-ruling states make the actual decision status unclear.
5. Unobtrusive: chrome is quiet, but excessive whitespace, reveal motion, and repeated prose increase attention cost.
6. Honest: labels and numbers repeatedly imply calibration, provenance, and certainty that the underlying rules do not provide.
7. Long-lasting: restrained editorial styling is durable, though faux-broadsheet justification and tracked mono microcopy are trend-specific.
8. Thorough: many states exist, but the success view visibly breaks, collapsed content can remain focusable, and AA contrast fails for microcopy.
9. Environmentally friendly: no idle animation and PDF code is lazy, but initial JS exceeds 500 KB raw and motion is eagerly preloaded.
10. As little design as possible: the memo repeats the same claims and risks across an opening, The Read, seven numbered sections, appendix, and ruling workspace.
