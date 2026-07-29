# Diagnosis — Settings "fund thesis" section shows a stale thesis

**Date:** 2026-07-14
**Symptom (reported):** The fund-thesis section on the Settings page doesn't update to the most recently saved thesis.
**Status:** Root-cause investigation only. No fix applied yet.

---

## TL;DR

There are **two independent mechanisms** that can leave the Settings mandate editor showing an
out-of-date thesis. Only one is reachable through today's UI:

- **Root cause A (primary, reachable today):** the Settings page **seeds its editable state once**
  from the shared `['settings']` React-Query cache, and that cache is **`STATIC` (never refetches on
  mount/focus/interval)** and can be primed with an older snapshot by **warm-start**. When a fresher
  copy lands in the cache moments later, the page's seed-once guards throw it away for the rest of the
  visit. → the mandate fields render the stale thesis on entry.

- **Root cause B (latent, backend-only today):** the mandate the editor reads
  (`settings.fund_config`) and the actual `fund_thesis` versions are kept in sync **one-way only**
  (`fund_config → thesis`). Creating/activating a thesis version directly
  (`POST /api/fund-thesis/versions`, `PATCH /api/fund-thesis/active`) does **not** write back to
  `settings.fund_config`. Those endpoints have **no frontend callers today**, so this only bites if a
  thesis is changed server-side (pipeline/admin/another client) — but then the Settings "Live thesis"
  version number would advance while the mandate content stays frozen.

---

## How the data actually flows

The "fund thesis" the user edits in Settings is **not** loaded from the `/api/fund-thesis` endpoint.
It lives in `settings.fund_config.mandate` and is rendered from the local `draft` state.

```
GET /api/settings ──► ['settings'] cache ──► SettingsPage.settings (seed once)
                                                    │
                                                    ▼
                                    loadFundConfiguration(settings)  ──► draft.mandate  ──► the form
```

Separately, `fetchFundThesisSummary()` (GET `/api/fund-thesis`) is fetched once on mount and feeds
only the **"Live thesis vN"** line and the version metadata — not the editable mandate fields.

Relevant code:

- `app-front-end/src/settings/SettingsPage.tsx:334` — the `['settings']` query, `getQueryConfig('STATIC')`.
- `app-front-end/src/settings/SettingsPage.tsx:342` — `seededRef`: copies `settingsQuery.data` into
  local `settings` state **exactly once**.
- `app-front-end/src/settings/SettingsPage.tsx:360` — `draftSeededRef`: builds `draft` from
  `loadFundConfiguration(settings)` **exactly once**.
- `app-front-end/src/lib/fundConfiguration.ts:411` — `loadFundConfiguration`: when
  `settings.fund_config` exists it is authoritative (localStorage is only a no-backend fallback).

---

## Root cause A — seed-once over a never-refetching, warm-primed cache

### The three interacting pieces

1. **`STATIC` intent** (`app-front-end/src/lib/queryIntent.ts:58`):

   ```
   staleTime: Infinity, refetchOnMount: false, refetchOnWindowFocus: false,
   refetchInterval: false, refetchOnReconnect: false
   ```

   The `['settings']` query **never refreshes on its own**. It only changes via an explicit
   `invalidateQueries(['settings'])` or `setQueryData(['settings'], …)`.

2. **Warm-start** (`app-front-end/src/lib/warmStart.ts`): on login it hydrates `['settings']` from a
   per-user **localStorage snapshot**, preserving the snapshot's original age
   (`setQueryData(key, data, { updatedAt: snapshot.at })`, line 57). Because `staleTime` is `Infinity`,
   the hydrated value is treated as fresh forever, so **no mount-time fetch happens**. Warm-start
   compensates with a **single idle invalidate ~500 ms after mount, and only if the snapshot is
   >90 s old** (lines 111–121). The snapshot is persisted debounced 2 s after cache writes and on
   `pagehide` (lines 123–131).

3. **Seed-once guards** (SettingsPage): `seededRef` and `draftSeededRef` latch on the **first**
   non-null value. Any later, fresher `settingsQuery.data` is dropped:

   ```ts
   useEffect(() => {
     if (seededRef.current || !settingsQuery.data) return;   // <-- fresh data ignored after first seed
     seededRef.current = true;
     setSettings(settingsQuery.data);
   }, [settingsQuery.data]);
   ```

`SettingsPage` is rendered inside `AppFrame`, and `App.tsx` calls `useSystemData()` (which runs
`useWarmStart()` and mounts the `['settings']` observer) at the top level on **every** route,
including `/v1/settings` — so all of the above applies to the Settings page.

### Why it goes stale

- On entry, `settingsQuery.data` is **whatever is already in the cache** — a warm-hydrated snapshot or
  a value fetched before the thesis changed. `seededRef` latches onto it at ~0 ms.
- The warm-start correction (fresh refetch) lands in the cache at ~600 ms, but by then `seededRef`
  (and `draftSeededRef`) are already `true`, so the fresh settings **never reach `draft`**. The stale
  thesis is sticky for the entire visit.

The seed-once guard exists for a good reason — it protects in-progress edits from being clobbered by a
background refetch. But it currently also blocks *legitimate* first-load reconciliation.

### Reproduction conditions

Any of:

- **Cross-session close-then-reopen:** deploy a thesis, then close the tab / navigate away **within
  ~2 s** (before the debounced warm-snapshot write captures the post-deploy state). Next login,
  warm-start hydrates the pre-deploy snapshot; open Settings before the 600 ms correction → stale.
- **Cross-device / second open client:** device A deploys; device B (app already open, cache never
  re-fetched because `STATIC`) opens Settings → stale.
- **Race on fresh login:** land directly on `/v1/settings` from a warm snapshot; the mandate seeds
  from the stale snapshot before warm-start's idle invalidate corrects the cache.

Note: opening Settings **after** the cache has been corrected (e.g. after visiting another workspace
that triggered a refresh) shows the correct thesis — which is exactly why this looks intermittent.

### Same-session deploy is NOT the trigger

The deploy path reconciles correctly in-session: `performDeploy` calls `fetchSettings()` directly,
`setSettings(liveSettings)`, re-seeds `draft` from the live config, and
`invalidateQueries(['settings'])` (which refetches the active `useSystemData` observer regardless of
`staleTime`). So the editor updates right after a deploy. The bug is about **re-entering** Settings,
not the deploy itself.

---

## Root cause B — one-way `fund_config → thesis` sync (latent)

- `PATCH /api/settings` (`backend/api.py:1808`) treats `settings.fund_config` as canonical: it saves
  settings and then calls `sync_fund_config_to_active_thesis(...)` (lines 1868–1891) to derive the
  thesis from the mandate. Good — the editor and thesis stay consistent for this path.
- But `POST /api/fund-thesis/versions` (`backend/routers/fund_thesis.py:276`) and
  `PATCH /api/fund-thesis/active` (line 316) create/activate a thesis version and **never write back
  to `settings.fund_config`**. So a thesis changed through those endpoints would advance the active
  version while the Settings mandate content (read from `fund_config`) stays frozen.

**Reachability:** `postFundThesisVersion` / `patchFundThesisActiveVersion` are **defined but unused**
across `app-front-end` and `packages` (verified by grep). So today only a server-side actor
(pipeline, admin, migration, another integration) can trigger B. It is a real source-of-truth split
worth closing, but it is not the everyday user path.

---

## Lower-probability contributors (checked, not the primary cause)

- **Two observers, two queryFns on `['settings']`:** `SettingsPage` uses
  `fetchSettings().catch(() => null)` while `useSystemData` uses bare `fetchSettings`. Same key, so
  they share data, but React Query uses the most-recently-mounted observer's `queryFn` for refetches.
  This is a smell, not the staleness cause.
- **`mergeFundConfiguration` / `createDefaultFundConfiguration` dropping fields:** would produce
  *consistently* wrong fields, not "won't update to the latest," so it doesn't match the symptom.
  Not investigated in depth.

---

## Candidate fixes (for a later change — not applied)

Aimed at Root cause A (primary):

1. **Reconcile on fresh data instead of seed-once.** Replace the hard `seededRef` latch with: re-seed
   `draft` from incoming `settings` when the server identity/version changes **and** there are no
   unsaved edits (compare `serializeDecisionConfig(draft)` to `savedSnapshot`). Preserves edit
   protection while accepting genuine updates.
2. **Force a fresh read on Settings entry.** Give the Settings page's `['settings']` observer
   `refetchOnMount: 'always'` (or `staleTime: 0`), so opening Settings always reconciles against the
   server. Cheapest change; costs one request per Settings open.
3. **Invalidate `['settings']` when entering the Settings route**, then let the seed run against the
   corrected cache.

For Root cause B (defense in depth): after `create/activate` thesis version, write the derived mandate
back into `settings.fund_config` (or have the Settings mandate read the active thesis as the source of
truth), so the two representations can't diverge.

**Recommended next step:** option 1 or 2. Before implementing, add a failing test that mounts
`SettingsPage` with a stale `['settings']` cache entry, pushes a fresh value into the cache, and
asserts the mandate fields reflect the fresh thesis (no unsaved edits present).

---

## Evidence index

| Claim | Location |
|---|---|
| Settings query is `STATIC` | `app-front-end/src/settings/SettingsPage.tsx:334`, `app-front-end/src/lib/queryIntent.ts:58` |
| `settings` state seeded once | `app-front-end/src/settings/SettingsPage.tsx:342` |
| `draft` seeded once | `app-front-end/src/settings/SettingsPage.tsx:360` |
| Mandate read from `settings.fund_config` | `app-front-end/src/lib/fundConfiguration.ts:411` |
| Warm-start hydrates `['settings']` with old age; idle-only correction | `app-front-end/src/lib/warmStart.ts:24`, `:57`, `:111` |
| Settings runs under `useSystemData` on every route | `app-front-end/src/App.tsx:41`, `:101` |
| `useSystemData` mounts `['settings']` STATIC | `app-front-end/src/hooks/useSystemData.ts:258` |
| Deploy reconciles in-session | `app-front-end/src/settings/SettingsPage.tsx:516`–`613` |
| `patch_settings` syncs `fund_config → thesis` (one way) | `backend/api.py:1808`, `:1868` |
| Direct thesis endpoints don't touch `fund_config` | `backend/routers/fund_thesis.py:276`, `:316` |
| Direct thesis endpoints unused in UI | grep: no callers in `app-front-end`/`packages` |
