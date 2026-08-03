# Known Issues

Open problems that are reproducible and diagnosed but not yet fixed. Broader
architectural debt is in [../ROADMAP.md](../ROADMAP.md); this file is for
specific defects.

---

## Duplicate companies in the identity review queue

**Status:** open · **Surface:** operator-visible · **Verified in:** `backend/identity/repository.py`

The identity review list renders one row per open identity-resolution case, so
the same company can appear several times.

### Root cause

`open_identity_case` upserts on `(user_id, observation_id) where status = 'open'`.
That prevents a duplicate case for the same *observation*, but not for the same
*company*, domain, or provider identity. Source observations are created per
discovery event and per scout persona by design, and repeated discoveries, manual
lookups, and imports each produce another observation for one real company. The
frontend is rendering the data faithfully — each case has a distinct
`identity_case_id`.

### Fix direction

1. Normalise reliable identity keys first, prioritising verified domain and
   provider IDs over company name.
2. Introduce a relationship between one identity case and every observation that
   refers to that identity.
3. Group the review list by canonical identity, showing the number of supporting
   observations and their sources.
4. Resolve or reject the grouped identity as a unit, transitioning all linked
   observations consistently.
5. Keep observations that match only on an ambiguous name separate until a human
   confirms they are the same company.

### What not to do

Do not group or de-duplicate in the UI alone. That makes the list look correct
while leaving the underlying identity graph inconsistent — the next stage to read
it will still see several unrelated companies.

---

## A real person from an unrelated role is attributed as a founder

**Status:** open · **Surface:** operator-visible, affects decisions · **Verified in:** `backend/resolver/founder_resolver.py`

A LinkedIn profile lists every role its subject has held. The founder resolver
extracts `(person, role)` pairs from the whole snippet, so a role belonging to a
*different company* on the same page is attributed to the company being resolved.

Live instance (CameraMatics, 2026-07-31): `"### CEO - Blueprint Sales Solutions"`
appeared on the profile of CameraMatics' CRO and was resolved as a founder named
"Blueprint Sales Solutions", role CEO. It then became "the founders' industry
pedigree" — the strongest positive in the exported IC pack.

### Root cause

`_collect_name_role_pairs` matches role/name patterns across a snippet with no
notion of *which company* the role belongs to. Proximity to the target company's
name is never checked.

The company-shaped half of this is now fixed: business descriptors ("Solutions",
"Technologies", "Analytics", …) are org markers, so the live case is rejected and
resolution fails closed to `NOT_FOUND`. **The person-shaped half is not.**
`"### CEO - John Smith"` from an unrelated employer still passes every check and
reads as entirely credible.

### Fix direction

1. Bind an extracted pair to the company it sits next to, not to the page.
   Segment profile text by employer heading before matching roles.
2. Require the target company's name (or a resolved alias/domain) within a
   bounded window of the role match.
3. Where the binding is ambiguous, emit the candidate with a `conflicts` entry
   rather than silently attributing it — the resolver already has that contract.

### What not to do

Do not extend the org-marker denylist to cover this. The failing values are real
personal names; no wordlist distinguishes them. The missing information is
*which employer the role belongs to*, and that has to come from structure.

---

## The reviewer can assert claims its inputs do not support

**Status:** open · **Surface:** operator-visible, affects decisions · **Verified in:** `backend/reviewer/`

`review_info.team_analysis` claimed *"founders are fleet industry veterans with
prior background in fleet operations"* for a record whose only resolved founder
was a company name at confidence 0.6, with `founder_resolution.resolution_status
= PARTIAL` and no employment history at all.

### Root cause

Reviewer prose is generated from a prompt containing the scout payload, but
nothing checks the output against the structured fields it purports to describe.
A claim about founder pedigree is accepted whether or not any founder was
resolved, and per-field confidence and `PARTIAL` status are not treated as
constraints on what may be asserted.

### Fix direction

1. Gate claim *categories* on the evidence that supports them: no team assertion
   when founder resolution is `PARTIAL`/`NOT_FOUND` or no founder carries
   employment history.
2. State the resolution status and its confidence in the reviewer prompt, so the
   model is told what it does not know.
3. Assert the gate in `backend/tests/reviewer/`: a payload with no resolved
   founders must not yield a populated `team_analysis`.

### What not to do

Do not fix this by post-processing the prose to strip sentences. The claim would
disappear from the memo while the same unsupported reasoning still drives the
score.

---

## Records created before 2026-08-03 carry invented identifiers and founders

**Status:** open · **Surface:** operator-visible · **Verified in:** `startups` table, `aethria-prod`

Until 2026-08-03 the scout prompt asked the model for `"id": "uuid"` and the
server minted one only when the model omitted it, so the model's invented
identifier was persisted as `startup_id`. Discoveries made before the fix keep
those values, and the affected rows also predate the founder and traction fixes.

Confirmed: CameraMatics holds `a1b2c3d4-e5f6-4711-9abc-1234567890ab` — a textbook
placeholder — which printed as "Company ID" on a confidential IC pack. Several
neighbouring rows show the same LLM-generated shape.

### Root cause

Fixed forward in `scout/base.py`; no backfill was run. Identifiers are referenced
by other rows and by exported documents, so rewriting them is a migration, not an
update.

### Fix direction

1. Identify affected rows: `startup_id` values that are not uuid4-shaped, or that
   predate the fix.
2. Decide whether identifiers are rewritten (needs every referencing row updated
   in the same transaction) or annotated as legacy and left alone.
3. Re-running a lookup regenerates identity, founders and traction correctly, but
   writes a **new decision** — that is a product call, not a cleanup.

### What not to do

Do not rewrite `startup_id` in place without tracing every reference first.

---

## Gap-retrieval URLs enter `references` ungated, and the two memo surfaces disagree

**Status:** open · **Surface:** operator-visible · **Verified in:** `backend/utils/scout_post_review_enrichment.py`

The reviewer's gap-retrieval step appends search-result URLs to
`scout_info.references` without requiring that anything was extracted from them.
They are real search hits, not fabrications — but nothing was read from them, and
they are presented alongside sources that were.

The in-app memo (`memoSourceRows`) prefers `source_evidence` and shows only pages
actually read; the IC pack renders `references` and shows all of them. For
CameraMatics that is 4 sources on screen and 6 in the exported PDF. The pack now
marks the unread ones `[surfaced by search; not read]`, but the counts still
differ between surfaces.

### Root cause

`references` is a flat list with no per-URL provenance. `field_provenance` records
that *the list* came from gap retrieval, not which entries did.

### Fix direction

1. Carry provenance per URL (`read` vs `surfaced`) instead of per field.
2. Render both surfaces from the same helper so they cannot drift.
3. Decide whether an unread URL belongs in an IC document at all — it is
   defensible as a diligence pointer, not as corroboration.

### What not to do

Do not silently drop the gap-retrieval URLs. They are genuine leads; the defect
is that they are indistinguishable from evidence, not that they exist.

---

## Traction extraction is pattern-bound

**Status:** open · **Surface:** internal · **Verified in:** `backend/utils/traction_extraction.py`

Firmographics (employees, revenue, founded year, prior rounds) are recovered from
evidence text with regexes tuned to aggregator phrasings. Text expressing the same
facts differently yields nothing, and the reviewer sees no traction.

### Root cause

Deliberate: rules over an LLM call (invariant 8), and a miss is safe by
construction — extraction can only surface facts, never suppress them. The cost is
coverage, and there is no measurement of how often it fires.

### Fix direction

1. Count how often `traction_facts` is populated across real discoveries, and
   whether "missing traction" red flags fall.
2. Add phrasings observed to be missed, driven by that measurement.
3. Only consider a model-based extractor if rule coverage plateaus well short of
   the evidence that is demonstrably present.

### What not to do

Do not let extraction infer or normalise values it did not read verbatim. A
missing fact must stay missing rather than become a plausible guess.

