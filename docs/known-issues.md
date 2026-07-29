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
