# Dispatch Candidate Disambiguation — Design

**Date:** 2026-06-14
**Status:** Approved (design), pending implementation plan
**Area:** On-demand lookup ("Dispatch")

---

## Problem

A typed company name can match **multiple genuinely different companies** — same name, or
different domain extensions (`.ie` / `.com` / `.co`) that belong to unrelated entities. Today the
on-demand lookup resolves to **one** identity, silently guesses when it's ambiguous, and proceeds
to spend LLM (scout → reviewer → partner) on that guess. The only signal to the analyst is a
`NEEDS_REVIEW` note in the memo *after* the work is done.

We want to insert a **human disambiguation gate**: when the resolver can't tell two real companies
apart, show the analyst a short list of candidate snapshots (name, domain with extension, one-line
description, source badges) **inline in the dispatch surface**, let them pick the right one (or
refine with a website), and only *then* run the reviewer pipeline on the chosen entity.

This is strictly better than today on both **correctness** (we analyze the right company) and
**cost** (we don't spend LLM on a wrong guess).

---

## Why this fits the existing architecture

- `backend/resolver/company_resolver.py` is already **deterministic and LLM-free**. It runs as
  stage 1 of every lookup, picks one `website`, demotes same-name / different-domain matches into
  `alternative_matches`, and already flags `resolution_status = "NEEDS_REVIEW"` when a strong
  competing domain exists with no website hint.
- All expensive LLM work (scout → reviewer → partner) happens **after** resolution.
- The scout engine already accepts a website hint (`scout/engine.py`, `website_hint=website`), and
  the queue endpoint (`POST /api/startups/lookup`) already parses a URL out of the typed input.

So the plumbing to "pin the chosen company" already exists. The new work is: (1) make the resolver
emit a ranked list of *distinct candidates*, and (2) add a cheap synchronous resolve step before the
queue, with a frontend picker.

---

## Approach (chosen: A — separate synchronous resolve step)

Split the lookup into two phases with a human gate that appears **only when ambiguous**:

1. **Resolve** (cheap, synchronous, LLM-free): typed name → ranked list of distinct entities.
2. **Decision:**
   - One confident identity → proceed automatically (today's behavior, no extra friction).
   - 2+ distinct entities → return candidates to the dispatch UI; analyst picks one (or refines
     with a website); then phase 3.
   - No credible evidence → prompt the analyst to add a website.
3. **Analyze** (existing pipeline, unchanged): scout → reviewer → partner on the chosen identity,
   pinned via the existing `website_hint` path.

**Rejected alternatives:**
- **B — single queue with a persisted pause/resume state.** Adds stateful pause/resume complexity
  and a new persisted row for no benefit, since resolve is fast enough to be synchronous.
- **C — speculative (analyze best guess, let user correct).** Wastes LLM on the wrong company;
  contradicts the project cost rules.

---

## Trigger rule

The picker appears **only when ambiguous** — i.e. the resolver finds 2+ genuinely distinct
entities and there is no website hint to disambiguate (today's `NEEDS_REVIEW` condition). A single
confident match runs straight through, preserving the "type a name, walk away" flow.

---

## Backend design

### 1. Resolver → distinct candidates

Add a `candidates: List[CompanyCandidate]` field to the resolver output (`CompanyResolution`).

```
CompanyCandidate:
  name: str                      # entity / brand name
  website: str                   # registrable domain (https://example.ie)
  description: str               # one-line snippet from the best source on that domain
  confidence: float              # 0..1, candidate-level match strength
  source_badges: List[str]       # which anchors exist: official / linkedin / crunchbase / news
```

Build candidates by grouping the scored `evidence_sources` by **registrable domain**, ranking by
match_score, and attaching that domain's best snippet as `description`. This **generalizes** the
existing primary + `alternative_matches` logic (which already groups by domain). Distinct
extensions (`.ie` / `.com` / `.co`) naturally fall into separate candidate groups.

**Ambiguity determination** reuses today's condition: 2+ strong/close candidates with no website
hint → `resolution_status = "NEEDS_REVIEW"`. Supplying a website hint collapses to one candidate.

### 2. New endpoint `POST /api/startups/lookup/resolve`

- Protected with `verify_clerk_token` (sets `request.state.user_id`).
- Body: `{ company: str, website_hint?: str }`.
- Runs `resolve_company()` only — **no scout, no LLM, no queue**. Synchronous response.
- Returns:
  ```
  {
    status: "resolved" | "ambiguous" | "not_found",
    canonical_name: str,
    candidates: CompanyCandidate[]   // 1 for resolved, 2+ for ambiguous, [] for not_found
  }
  ```

### 3. No change to the queue / scout / reviewer / partner path

Selection calls the **existing** `POST /api/startups/lookup` with the chosen website, which pins the
entity via the existing `website_hint` resolver path (confidence boost + anchor host). The expensive
pipeline is untouched.

---

## Frontend design

Lives entirely in the **dispatch surface** — the analyst never navigates away and back. Touches
`hooks/useDispatchLookup.ts` and the dispatch components (`AgentDispatch.tsx` /
`DispatchCommandBar`), plus a new client in `api/startups.ts`.

### Flow (`useDispatchLookup`)

1. `submit()` first calls a new `resolveLookupCandidates(value)` client (hits the resolve endpoint).
2. `resolved` → call the existing `queueOnDemandLookup` with the resolved website; rest of the
   existing polling flow unchanged.
3. `ambiguous` → set `candidates` state; render the picker **inline** in the dispatch panel.
4. On pick → `queueOnDemandLookup` with the chosen name + website → existing polling machinery
   resumes (phase label, chips, ready toast, etc. all unchanged).
5. **"None of these"** → reveal a website/domain input → re-call `resolveLookupCandidates` with
   `website_hint` → narrows to one → proceed.
6. `not_found` → message prompting the analyst to add a website (same copy as today's failure path).

### Picker UI

A list of candidate cards rendered in the dispatch surface (not a modal, no route change). Each card:

- Company name
- **Domain with the extension visible** (the `.ie` vs `.com` distinction is the whole point)
- One-line description
- Small source badges (official / LinkedIn / Crunchbase / news)
- Plus a "None of these — add a website" affordance below the list.

Styling consistent with the existing editorial paper system (`railEditorial` / `productSystem`);
Framer Motion for the reveal (per project animation rule).

### Fail-safe

If the resolve endpoint errors, **fall back to today's behavior**: call `queueOnDemandLookup`
directly and let the resolver run inside the pipeline as it does now. The picker is an enhancement,
never a hard dependency — a resolve outage must not break dispatch.

---

## Error handling summary

| Situation | Behavior |
|---|---|
| Resolve endpoint error/timeout | Fall back to direct queue (today's flow) |
| `not_found` | Prompt analyst to add a website |
| Refine-with-website still returns 2+ | Keep showing the picker (rare) |
| User cancels mid-picker | Clear candidates, no work queued (no LLM spent) |

---

## Testing

**Backend** (extend `backend/tests/test_lookup_dispatch.py`):
- Candidate grouping by registrable domain; `.ie` / `.com` / `.co` produce **distinct** candidates.
- Each candidate gets a description from its domain's best source.
- Ambiguity flag set with 2+ strong candidates and no hint; **cleared** when a website hint is given.
- Resolve endpoint returns the correct `status` for resolved / ambiguous / not_found.

**Frontend:**
- Picker renders on `ambiguous`.
- Pick queues the lookup with the chosen website hint.
- "None of these" reveals the website refine input and re-resolves.
- Resolve error falls back to direct queue.

---

## Out of scope

- Changing the periodic pipeline (this is on-demand lookup only).
- Persisting candidate lists / disambiguation history.
- Multi-select (analyst picks exactly one entity).
- Any change to scout / reviewer / partner logic.
