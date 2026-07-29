# Product

## Vision

Venture capital runs on judgement that is rarely written down, rarely versioned,
and almost never measured. Aethria's premise is that a fund's investment thesis
can be treated as an executable policy: written once, versioned, applied
consistently to every company that crosses the desk, and improved from outcomes.

Aethria is therefore not a CRM, a dashboard, or a database of startups. It is an
**investment operating system** — an autonomous pipeline with a human principal.
Its job is to put the principal in command of the instrument, with three
non-negotiables:

1. **Traceability over output.** Every score, decision, and memo carries the
   evidence, the policy version, and the agent stage that produced it.
2. **Fail closed, not confidently wrong.** Missing thesis, ambiguous company
   identity, or thin evidence blocks the decision with a named reason rather than
   producing a plausible guess.
3. **The human owns the ruling.** The pipeline recommends and escalates; a
   person rules, and that ruling is the authoritative record.

## Primary users

| User | What they need from Aethria |
|---|---|
| **Investment associate / analyst** | Continuous top-of-funnel coverage, fast triage, and a memo they can defend in an IC meeting. |
| **Partner** | A decision-ready recommendation with the reasoning attached, and a queue of only the cases that genuinely need a human. |
| **Platform / ops** | Pipeline health, escalation backlog, cost budget, and confidence that tenancy and policy governance actually hold. |

## Jobs to be done

- Discover and triage opportunities continuously, against *this* fund's mandate.
- Review each opportunity through a normalised, versioned scoring rubric.
- Produce a decision-ready investment memo with provenance.
- Escalate genuinely uncertain decisions to a human, with the reason named.
- Track portfolio-level implications: signals, concentration, watchlist quality.
- Improve the process from its own outcomes rather than from intuition.

---

## Product surfaces

| Surface | Path | Purpose |
|---|---|---|
| Operator console | `app-front-end` (`/v1`) | Authenticated deal-flow workspace |
| Settings / control room | `/v1/settings` | Fund thesis, agent toggles, cost budget, decision thresholds, policy publishing |
| Fund room | `/v1/fund` | Mandate, system intelligence, meta-agent state |
| Portfolio | `/v1/portfolio` | Positions, signals, concentration |
| Flow / deal | `/v1/flow`, `/v1/deal/*` | Deal grid and memo detail |
| Admin | `/admin` | Operator/ops overview behind a separate secret |
| Marketing site | `web-front-end` | Public positioning and `/request-access` waitlist |

---

## Core flows

### 1. Sign-in and session gating

App routes require Clerk sign-in. The shell waits for token readiness before
loading any API-backed view, and paints a per-user warm-start snapshot so the
first frame after login is not empty.

### 2. Mandate first

The fund thesis is authored in Settings as free text; the backend parses it into
a structured mandate, versions it, and embeds it for alignment scoring. Publishing
a new version is an explicit, confirmed action — and it is the gate on everything
downstream. Without an active thesis the periodic pipeline does not run.

### 3. Autonomous deal flow

With agents enabled, the console triggers a pipeline cycle on load and a per-user
loop keeps cycling. Scouts discover real companies, reviewers score them against
the mandate, and the partner engine issues INVEST / PASS / MONITOR. New rows and
state changes are pushed to the open console over SSE.

### 4. On-demand lookup ("dispatch")

The operator types a company name, domain, or a sentence of context. The lookup
is queued with a stable `lookup_id`, resolved to a canonical company (with
disambiguation when several candidates match), evaluated end-to-end, and opened
as a memo when the decision lands. Lookup is mandate-aware but never
thesis-blocked. Failures surface explicitly via lookup status rather than
silently stalling.

### 5. Progressive memo

The memo endpoint renders while the pipeline is still working:

- `generating` — show the scout / review / partner slices that exist so far
- `ready` — show the full markdown memo
- `failed` — show the error alongside whatever partial context exists

### 6. Identity review

When an observation cannot be confidently matched to a canonical company, it
becomes an identity case rather than a silent merge. The operator resolves,
defers, or rejects it explicitly, and the ruling propagates to every linked
observation.

### 7. Evidence and rulings

An opportunity carries an evidence ledger — artifacts, claims, links, trust and
verification classes — that the operator can inspect, correct, and extend with a
bounded diligence plan. The evaluation is immutable and bound to a policy
version. The human ruling sits on top and is the authoritative record; workflow
actions and approvals hang off it.

### 8. Escalation resolution

Deals flagged `human_review_required` appear in the escalation queue. Resolving
one writes an explicit decision, notes, and timestamp against the deal.

### 9. Monitoring and refresh budgets

Each opportunity has a service level (0–5). Refreshing reserves a resource/cost
envelope before doing work, so monitoring cost stays bounded and predictable.

### 10. Learning loop

The meta-agent analyses outcomes on its own interval and proposes changes:
mutated scout prompts, reweighted personas, recalibrated reviewer thresholds.
Prompt promotion can be gated behind an evaluation pass. Fund intelligence turns
outcome patterns into attributed policy proposals, which a human previews and
accepts, edits, rejects, or defers — an accepted edit creates a *draft*, never an
unreviewed live policy change.

---

## Functional requirements

- **Auth** — every private API requires a valid Clerk bearer token.
- **Tenancy** — data is scoped to `user_id` end to end.
- **Async work** — pipeline and lookup work never blocks a request handler.
- **Durability** — in production, accepted work survives a process restart.
- **Resilience** — the console stays usable when the worker is busy or a stage
  is incomplete.
- **Traceability** — decision artefacts carry rationale, confidence, evidence and
  timestamps.
- **Governed control plane** — settings and policy mutations are server-validated
  and versioned.
- **Observability** — system health and agent status are queryable by the UI.

## Non-functional requirements

- Responsive across desktop and mobile.
- Deterministic API contracts on polling-heavy screens.
- Thin list payloads; heavy blobs only on explicit detail fetches.
- Graceful degradation when Supabase or OpenAI is not configured — features
  return an explicit `503`/skip reason rather than failing obscurely.

## Scope boundaries

- The backend is the source of truth for all pipeline and analytics state.
- The frontend never replicates decision logic locally.
- Agent execution is server-side only.
- App and marketing site are separate frontends with different intents.
- Causal inference on outcomes is explicitly **not** supported; the outcomes API
  discloses coverage and valence without claiming causality.
