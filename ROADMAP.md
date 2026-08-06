# Roadmap and Technical Debt

Two things live here: the debt that is real in the code **today**, and the
direction of travel that is identifiable from the codebase and its planning
record. Nothing below is a commitment or a date.

Historical audits and superseded plans are in [`docs/archive/`](docs/archive/).
Several findings in those documents have since been fixed; this file reflects
what was verified against the current source.

---

## Part 1 — Known technical debt

### D1 · Identity cases are keyed per observation, not per company

**Where:** `backend/identity/repository.py` — `open_identity_case` upserts on
`(user_id, observation_id) where status = 'open'`.

Source observations are created per discovery event, per scout persona, per
manual lookup, and per import. Uniqueness prevents a duplicate case for the same
*observation*, but not for the same *company*. The identity review queue
therefore shows the same company more than once, once per unresolved observation.

The fix is not to group in the UI — that hides an inconsistent identity graph
behind a tidier list. It needs: normalised identity keys (verified domain and
provider IDs ahead of company name), a relationship from one case to all
observations that refer to the same identity, grouped resolution that transitions
every linked observation together, and name-only ambiguous matches kept separate
until a human confirms.

*Impact: operator-visible. Priority: high.*

### D2 · Two coexisting data models mid-rollout

The original `startups` model and the canonical `companies` / `opportunities`
model both exist. The migration is deliberately staged behind
`RolloutMode` (`legacy → shadow → backfill → canonical_write → canonical_read`)
with a compatibility projection keeping the legacy read models populated
(`backend/evaluation_v2/compatibility.py`, `backend/authority/projection.py`).

This is a sound migration strategy, but until it completes it means two write
paths, two read models, a projection to keep correct, and reconciliation
machinery to operate. Cost is ongoing and grows with every feature added before
the cutover finishes.

*Impact: developer velocity and correctness surface. Priority: high — finish the
cutover rather than adding surface to both models.*

### D3 · `backend/api.py` remains a 3,800-line module

Sixteen domain routers have been extracted into `backend/routers/`, but the
startups, lookup, agents, settings, policy, escalations, admin, SSE, and
lifespan code all still live in `api.py`, alongside the in-process queue
implementation. New endpoints have a clear home; the existing ones do not.

*Impact: merge conflicts, hard to test in isolation. Priority: medium.*

### D4 · The pipeline runs inside the API process

Scout/reviewer/partner cycles, the durable job worker, SSE fan-out, and per-user
agent loops all share the one uvicorn process, which is why the start command is
pinned to `--workers 1` and why small instances need the memory tuning in
[DEPLOYMENT.md](DEPLOYMENT.md#small-instance-tuning). The durable job store makes
extracting a separate worker process tractable — the jobs table, leases, and
fencing already exist — but nothing extracts it today.

*Impact: scaling ceiling and OOM risk. Priority: medium — the pre-work is done.*

### D5 · Schema is wider than the model needs

[`docs/reference/supabase-schema-audit.md`](docs/reference/supabase-schema-audit.md)
measured 27 tables and 99 indexes against a ~12-table target. Named specifics
that remain: `startups.review_info` dominates row size, several key-value-shaped
tables (settings, memory, meta state, analytics blobs) should collapse into one
document store, and fund-thesis embeddings are stored as JSONB arrays rather than
`pgvector`, costing roughly double the bytes and precluding a real ANN index.

*Impact: egress and query cost. Priority: medium.*

### D6 · Two storage implementations

`backend/utils/storage.py` (local JSON) mirrors the interface of
`backend/supabase_storage.py`. Only the Supabase path is production; the file
path is a dev convenience that must nonetheless be kept behaviourally close, and
divergence between them has caused real bugs historically.

*Impact: duplicated maintenance. Priority: low — but every method added to one
is a decision about the other.*

### D7 · The two frontends have diverged

| | `app-front-end` | `web-front-end` |
|---|---|---|
| React | 19 | 18 |
| Router | `react-router` 8 | `react-router-dom` 6 |
| Build | `vite build` | `vite-react-ssg` |
| Motion | Framer Motion | Framer Motion + GSAP + Lenis |

`packages/product-chrome` shares a small amount of chrome between them, but
design tokens, Tailwind configuration, and most primitives are maintained twice.
Visual parity between the marketing site and the product is currently kept by
hand.

*Impact: duplicated design work, drift. Priority: low-to-medium.*

### D8 · Test and dependency ergonomics

- `asyncio_mode=auto` is passed on the pytest command line in CI and in the docs
  rather than set in `pytest.ini`, so a bare `pytest` behaves differently from
  the documented invocation.
- `backend/requirements.lock` is regenerated by hand (`uv pip compile`); nothing
  verifies the lock still matches `requirements.txt`.
- The PostgreSQL contract job re-lists its migrations inline in
  `.github/workflows/ci.yml`, so a new institutional migration must be added
  there manually or it is simply never exercised.

*Impact: silent gaps. Priority: low, cheap to fix.*

### D9 · Institutional layer is uncertified against a real database

`docs/archive/institutional-foundation/phase-3-8-readiness.md` records that
Phases 3–8 are implemented in code but were **not** certified against a target
PostgreSQL instance — immutability triggers, RLS policies, transaction races, and
service-role permissions had not been exercised at the time of writing. CI now
runs a subset of repository contract tests against `postgres:16`, which closes
part of this gap; the RLS and service-role permission surface is still not fully
covered.

*Impact: production-readiness confidence. Priority: high before relying on the
canonical path in production.*

### D10 · Documentation drift is structural

Point-in-time audits, plans, and design specs accumulated at the repository root
and in feature folders, and several described behaviour that had since been
fixed. They are now under `docs/archive/` and marked historical, but the pattern
will recur unless new planning artefacts are written to `docs/archive/` (or an
ADR) from the start rather than to the root.

*Impact: reader trust. Priority: process, not code.*

### D11 · MetaAgent self-optimization never closes the loop

**Where:** `backend/meta/` — `agent.py`, `mutator.py`, `reweighter.py`,
`calibrator.py`, `analyser.py` (~1,400 lines).

The analysis and proposal-generation machinery is fully wired and runs on
schedule: it reads pipeline outcomes, generates prompt mutation proposals,
scout-weight reweighting proposals, and reviewer-threshold calibration
proposals. But nothing ever promotes a proposal into the live scout/reviewer
engines — `agent.py`'s cycle report hardcodes `"production_mutations_applied":
0` and is explicitly labeled `"analysis_only": True`. `PromptMutator` has a
`_set_agent_prompt()` method that would write a mutation back to a running
engine, but it is never called from `apply()`/`_apply_one()`, which only
persist proposals to a JSON log. `ScoutReweighter.apply()` and
`ThresholdCalibrator.apply()` are similarly defined but never invoked — only
`.decide()` runs. Proposals are visible only via a read-only
`GET /api/meta/prompt-library` (`routers/meta.py`).

So "self-optimisation" (AGENTS.md: "MetaAgent — mutates prompts, reweights
scout personas, recalibrates reviewer thresholds") currently means *proposes*,
not *mutates* — every proposal requires a human to read the log and manually
apply the change elsewhere. That may be the intended safety posture (AGENTS.md
does say "Proposals become drafts, never live changes"), but the *operator
promotion path* itself doesn't exist yet — there's no endpoint or job that
takes an accepted proposal and writes it into a running engine, so today
"become drafts" is the only state a proposal can ever reach.

*Impact: the self-optimization feature is partially built — proposal
generation without a promotion mechanism. Priority: decide deliberately
whether to build the promotion path or trim the analysis machinery to match
what's actually closed-loop today.*

---

## Part 2 — Direction of travel

### Near term — finish what is started

1. **Complete the authority cutover** (D2). Drive `RolloutMode` to
   `canonical_read`, retire the compatibility projection, and delete the legacy
   write path. This unblocks most of the items below.
2. **Certify the institutional layer against a real PostgreSQL** (D9): RLS,
   immutability triggers, and service-role permissions under test.
3. **Group identity cases by canonical identity** (D1).
4. **Extract the pipeline worker from the API process** (D4), using the durable
   job store that already exists.

### Identified product direction

Recorded in `docs/archive/plans/2026-07-14-investor-value-features.md`. The
common thread is that Aethria's strongest asset is the evaluation engine —
versioned theses, deterministic scoring, decision history, per-deal provenance —
and the highest-value moves point that engine at deal flow a fund already has and
at decisions it has already made.

| Direction | What exists today | What is missing |
|---|---|---|
| **Anti-portfolio tracking** — follow what happened to every PASS and expired MONITOR | Signal tracking (`portfolio/signals.py`), outcomes API with coverage/valence disclosure, immutable decision history | The retrospective surface itself: linking later outcomes back to the decision that passed, and the calibration scoreboard over time |
| **Inbound ingestion** — forward a deck, get an IC-grade memo | CSV/CRM/referral intake, confidential artifact registration with access + retention classes, canonical identity admission | Document parsing into the evidence ledger; an email/forwarding entry point |
| **Thesis backtesting** — replay deal flow under a new mandate | Versioned theses, versioned policy, immutable evaluations bound to a policy version, governed preview | A replay runner that re-evaluates a historical cohort under a candidate policy and diffs the outcomes |
| **LP-ready process reporting** | Analytics endpoints (rejections, watchlist, concentration, system health), audit logging, activity summaries | Export/report composition |
| **IC mode** — multi-partner votes on escalations | Escalation queue, rulings, workflow actions, approvals | Multiple authenticated voters on one ruling |
| **Founder dossiers** | Founder resolution with team-page extraction and structured candidates | A durable founder entity with its own evidence ledger |

### Explicitly not planned

- Causal claims about outcomes. The outcomes API deliberately discloses coverage
  and valence and states that causal inference is unsupported. Keep it that way.
- Frontend-side decision logic. The backend stays the single source of truth.
- Direct frontend access to Supabase.
