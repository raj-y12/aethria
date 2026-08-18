# Company Identity LLM Disambiguation — Design

## Goal

Company Resolver picks which candidate domain/company matches a typed
lookup name using regex/token/slug heuristics (`_slug_similarity`,
`_text_name_match`, `_profile_matches_anchor`). For common or short company
names, several unrelated companies routinely score high enough to look like
plausible matches, and the heuristics have needed four separate targeted
patches this month for four distinct collision shapes (Vercel/Hashimoto
misattribution, Anthropic vs. anthropic.io, General Electric vs. General
Motors, Notion vs. Notion Technologies/Notionink/Notion State). Each patch
was correct for its own case; the underlying problem is that text-similarity
matching has a ceiling no further patch removes.

This adds a grounded LLM disambiguation step that reads the actual candidate
content and decides — replacing threshold-based guessing with judgment,
while keeping a safe fallback (`NEEDS_REVIEW`) for genuinely ambiguous cases.

**Priority ordering for this design, explicitly**: correctness/trust over
cost. This check runs on every eligible lookup, not gated behind existing
ambiguity heuristics — the whole point is to stop trusting those heuristics
as the sole signal. Cost is tracked (via `CostController`, same as every
other LLM call in this codebase) but not used to skip the check.

## Where it runs

Inserted into `resolve_company()` (`backend/resolver/company_resolver.py`),
after phase-1/phase-2 source collection and scoring
(`_score_and_collect_sources`) complete, before `_assign_identity_fields`
picks `resolution.website`.

**Skipped when `website_hint` is supplied.** An explicit operator-provided
website is already an authoritative human disambiguation — there is nothing
left to check. This is a correctness exception, not a cost exception.

**Skipped when there is only one `official_site`-scored candidate.** With
nothing to disambiguate between, there is no judgment call for the LLM to
make; the existing single-candidate path is unchanged.

## Input

- The typed company name (the lookup query).
- Every candidate classified `source_type == "official_site"` by
  `_score_and_collect_sources` (i.e. `slug_sim >= 0.55` or an exact anchor
  match — the same bar that already exists in that function; not the full
  16-source evidence pool, just the competing *company* candidates). Each
  candidate carries its title, snippet, and domain from the search result
  already collected; no additional page fetches.

## Output (structured, matching the existing Scout/Partner JSON pattern)

```json
{
  "picked_url": "https://notion.com",
  "confidence": 0.92,
  "reasoning": "The typed query 'Notion' most directly matches notion.com's own description as a workspace/docs product; notiontechnologies.com and notionink.com describe unrelated businesses (industrial sensors, a design studio)."
}
```

`picked_url` may be `null` when the LLM judges none of the candidates is a
confident match for the typed company (distinct from "matches the
heuristic's pick" and from "confidently a different candidate").

## Decision logic

| LLM output | Action |
|---|---|
| Agrees with the heuristic's pick | Proceed as today; `reasoning` is stored on the resolution record for transparency (same spirit as the existing Company Resolver transparency line). |
| Disagrees, confidence ≥ bar | `resolution.website` is corrected to the LLM's pick. The heuristic's original pick is demoted into `resolution.alternative_matches` (not discarded — the existing "here's what else matched" transparency stays intact). A note records the correction: was X, now Y, why. |
| Disagrees, confidence < bar, or `picked_url` is `null` | `resolution_status = NEEDS_REVIEW`, same as today's existing ambiguous-identity path. Nothing is silently guessed. |
| LLM call fails/times out/malformed response | Fail closed to `NEEDS_REVIEW` — never silently fall back to trusting the un-checked heuristic pick as if it were confirmed. |

Confidence bar starts at **0.85** (high bar for auto-correction, biased
toward `NEEDS_REVIEW` when uncertain) and lives as a named value in
`resources/config/` per AGENTS.md invariant #3 — never a bare literal in
Python. This starting number is a conservative placeholder by design, meant
to be tuned after observing real lookups, not a considered final value.

## Cost tracking

Every call goes through `CostController`, identical to existing Scout/
Reviewer/Partner LLM calls. This is call-tracking for budget visibility,
not a gate that skips the call to save money — those are different
concerns and this design deliberately keeps them separate.

## What this does not change

- `_profile_matches_anchor`'s existing anchor-filtering logic (the fix
  shipped today for `_merge_resolution_sources`) is unchanged — that's a
  downstream evidence-citability filter, a different job from picking the
  primary identity.
- Founder Resolver, Scout's own LLM call, and the rest of the lookup
  pipeline are unaffected; this only changes how `resolution.website` gets
  picked.
- No change to the `NEEDS_REVIEW` UI/transparency surfaces already in
  place — this feeds them the same way the existing heuristic does, just
  with a better-grounded input.

## Testing

- Unit tests on the new disambiguation function in isolation: agrees with
  heuristic, confidently overrides, uncertain → review, `picked_url: null`
  → review, LLM call failure → review (fail-closed).
- Regression tests confirming the `website_hint` and single-candidate skip
  paths don't invoke the LLM at all (no wasted calls on the common,
  unambiguous case).
- A test reproducing today's live-observed Notion/Anthropic/General
  Electric collision shapes, asserting the LLM path would have picked
  correctly (mocked LLM response, not a live call in CI).
- Live-dispatch validation against a real ambiguous lookup before this
  ships, same as every other fix this session.
