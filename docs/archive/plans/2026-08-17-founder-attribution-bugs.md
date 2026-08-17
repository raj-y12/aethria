# Founder Misattribution — Investigation and Fix

**Reported:** live on a real Vercel dispatch (17 Aug 2026, ~13:44 UTC), viewed in the
running app. The memo's Founder section showed **"Mitchell Hashimoto"** — he is
HashiCorp's co-founder, who joined *Vercel's board* in March 2026, per the memo's own
"Why Now" text. Not a Vercel founder. Investigated per user request; confident enough
in both root causes to implement directly rather than just propose.

## Two separate bugs, not one

Pulled the real `scout_info` JSON for this dispatch from Postgres. Found **two
independently wrong values in two different fields**, both wrong, for different
reasons:

1. `founder_resolution.founders[0].name` = **"YUR.tv AG"** — a company name, not a
   person. Source: Malte Ubl's LinkedIn snippet, which correctly says "CTO at
   Vercel" but also lists an unrelated past/side role, "### CEO - YUR.tv AG".
   `resolver/founder_resolver.py`'s `_ROLE_THEN_NAME_RE` pattern (`"CEO -
   YUR.tv AG"`) matched "YUR.tv AG" as if it were a person's name — it's
   domain-shaped (`YUR.tv`) plus a corporate suffix (`AG`), and nothing in
   `_is_person_name` rejected either signal.
2. Top-level `scout_info.founder_names` = **"Mitchell Hashimoto"** — Scout's own
   LLM output (or `resolver/company_resolver.py`'s deterministic
   `_extract_founders` fallback), misreading a BusinessWire headline genuinely
   about Vercel ("Vercel Appoints Mitchell Hashimoto, Co-Founder of HashiCorp...
   to Board of Directors") as naming a Vercel founder.

The frontend's `buildFounderSectionModel` (`app-front-end/src/lib/founderMemo.ts`)
already has a `completeResolverMatchesCompany` check that **correctly rejected**
bug #1's candidate and fell back to `scoutFounderNames` — which is how bug #2's
value ended up on screen instead. The fallback logic worked as designed; both
inputs feeding it were wrong.

## Fixes

**Bug #1 — `resolver/founder_resolver.py`:**
- Added `"ag"`, `"sa"`, `"nv"`, `"bv"`, `"kg"`, `"oy"`, `"ab"`, `"spa"`, `"sarl"`,
  `"plc"` to `_ORG_NAME_MARKERS` (only `inc`/`llc`/`ltd`/`gmbh`/`corp` were listed —
  the common non-US corporate suffixes were missing entirely).
- Added `_DOMAIN_SHAPED_WORD_RE` (`[A-Za-z]{2,}\.[a-z]{2,4}$`) and a check in
  `_is_person_name` rejecting any candidate word shaped like a domain
  (`YUR.tv`, `example.com`) — a more general guard than suffix-listing, since a
  LinkedIn bio lists every role a person has held and any of them can be an
  unrelated company. Verified this doesn't reject legitimate abbreviated
  initials ("J.K. Rowling") — that was already rejected by a pre-existing,
  unrelated check (trailing-period sentence-end guard).
- Test: `tests/test_founder_resolver.py::test_a_persons_other_role_at_a_different_company_is_not_extracted_as_a_name`,
  using the real Vercel/Malte Ubl snippet text.

**Bug #2 — `resolver/company_resolver.py`:**
- `_extract_founders` now takes `company: str` and rejects a founder-role match
  when the text immediately following it reads `"of <OtherCompany>"` where
  `OtherCompany` doesn't match the target (via the existing `_compact_name`
  normalizer, reused from the source-anchor-matching code). Applied to all
  three call sites (`company_resolver.py` ×2, `scout/base.py`'s deterministic
  fallback ×1).
- Verified directly against the real BusinessWire headline text: without the
  fix, this specific text didn't actually match any `_FOUNDER_PATTERNS` regex
  in isolation (checked) — meaning bug #2's actual live value most likely came
  from Scout's own LLM output, not this deterministic path. The fix is still
  correct and real (a genuine gap in the regex path for cases that DO match),
  but **does not fully explain what was seen live** — see "Unresolved" below.
- Tests: `tests/test_company_resolver.py::test_extract_founders_rejects_role_attributed_to_a_different_company`
  and `test_extract_founders_still_finds_a_real_founder_of_the_target_company`.

## Verified

- Both fixes tested directly against the real retrieved text pulled from the
  live Vercel dispatch's stored `scout_info`, not a synthetic approximation.
- `tests/test_founder_resolver.py`, `tests/test_founder_evidence.py`,
  `tests/test_founder_enrichment.py`, `tests/test_founder_context.py`,
  `tests/test_founder_team_pages.py`, `tests/test_company_resolver.py`: 110
  passed.
- Full backend suite: 2259 passed, same 39 pre-existing Postgres-container
  failures (need a live Postgres on 5432, unrelated), zero regressions.

## Bug #3 (closes the loop on #2) — the model's own claim wasn't cross-checked

Confirmed: the BusinessWire headline never matched `_FOUNDER_PATTERNS` in
isolation, meaning bug #2's live value came from Scout's own LLM structured
output (`founder_names`), not the deterministic regex fallback — the fallback
only runs `if not out.get("founder_names")`, and the model had supplied one.
Nothing validated the model's own claim against the evidence it was given.

**Fix — `scout/base.py`:** added `_reject_misattributed_founder_names(names,
source_pack, company)`, applied to `founder_names` *whenever the model
supplies one*, not just the deterministic-fallback path. For each claimed
name, searches the retrieved evidence for "`<role>` of `<OtherCompany>`"
appearing near that name and drops the name if `OtherCompany` doesn't match
the target (reusing `_compact_name` from `company_resolver.py`).

Found and fixed a real bug in the fix itself while verifying: the guard
regex used `re.IGNORECASE` on the whole pattern, which makes `[A-Z]` (meant
to bound the company-name capture to capitalized words) match lowercase
letters too — "founder of Vercel, said today." over-captured into "Vercel,
said today." as the "other company," which would have wrongly rejected
Vercel's real founder (Guillermo Rauch) in a legitimate "Guillermo Rauch,
founder of Vercel" sentence. Fixed by scoping case-insensitivity to only the
role-word alternation (`(?i:co-?founder|founder)`), matching the convention
already used elsewhere in this codebase, and re-verified: the real headline
is still rejected, a legitimate founder mention is kept, and a name with no
nearby role mention at all is left untouched.

Tests: `tests/test_scout_payload_coercion.py` — 3 new tests, including the
exact regression this bug produced.

## Remaining, genuinely open

The three fixes now cover: a domain/org-shaped string mis-parsed as a person
(bug #1), a real person's role at an unrelated company being deterministically
extracted (bug #2's regex path), and a real person's role at an unrelated
company being *modeled* (bug #2's actual live path, bug #3). Not covered: a
model naming a person as founder with **no** textual "of `<other company>`"
pattern to check against at all — e.g. a flat hallucination with no evidence
basis whatsoever. That failure mode needs a different mitigation (requiring
the model to cite which source supports a founder claim, then verifying the
citation) and is a larger change, not attempted here.
