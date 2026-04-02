# Aethria — Product Requirements Document & Documentation Artifacts

**Generated:** 2026-02-03  
**Repository:** Aethria (AI-powered DealFlow OS for VC firms)  
**Phase:** Phase 1 — MVP

---

## Table of Contents

1. [Product Requirements Document (PRD)](#1-product-requirements-document-prd)
2. [Product Overview / Executive One-Pager](#2-product-overview--executive-one-pager)
3. [Feature Inventory](#3-feature-inventory)
4. [Technical Inventory (Feature → Code Mapping)](#4-technical-inventory-feature--code-mapping)
5. [API & Data Model Summary](#5-api--data-model-summary)
6. [MVP Backlog](#6-mvp-backlog)
7. [6–8 Week Launch Roadmap](#7-68-week-launch-roadmap)
8. [Launch Success Metrics](#8-launch-success-metrics)
9. [UX Key Screens & Microcopy](#9-ux-key-screens--microcopy)
10. [Security & GDPR Checklist](#10-security--gdpr-checklist)
11. [Tests & CI Plan](#11-tests--ci-plan)
12. [Risks & Gaps](#12-risks--gaps)
13. [Appendix: File Citations](#13-appendix-file-citations)

---

## 1. Product Requirements Document (PRD)

### 1.1 Product Name & Tagline

**Product Name:** Aethria  
**Tagline:** Intelligent investment discovery and evaluation system  
**Source:** `app-front-end/src/components/EnterSystemPage.tsx` (line 64), `docs/README.md`, `run.py` (banner).

### 1.2 Who It's For (Personas)

**Primary Persona — Emma, VC Analyst**

- **Description:** Emma is a VC analyst at an early-stage fund. She spends hours each week triaging inbound startup ideas and preparing memos for partners. She needs fast, consistent scoring and one-page memos so partners can decide quickly.
- **Current pain:**
  - Time wasted on initial triage and research.
  - Inconsistent scoring across analysts.
  - No single place to see scout → review → decision and export a memo.
- **What they need:** Automatic scouting and review, configurable rubric, simple memo view and export (e.g. markdown from API).
- **Example user story:** “As Emma, I want the system to surface scored startups with verdicts and memos so that I can focus on the best leads and share memos with partners.”

**Secondary Persona — Partner (GP)**

- **Description:** Partner at a small fund who wants a clear YES/NO/MAYBE with rationale and next action, and optional human review flag for edge cases.
- **Source (inferred):** `backend/partner/decision.py` (human_review_required, next_action, conviction_level), `docs/VERDICT_MEMO_AND_REVIEWER_SCORING.md`.

**Confidence:** High (UI labels, backend decision model, and docs align with analyst/partner roles).

### 1.3 Problem We're Solving

- **From repo:** Aethria is an “autonomous DealFlow OS” that discovers, evaluates, and makes investment decisions via a pipeline: Scout → Reviewer → Partner → Portfolio (`docs/ARCHITECTURE.md`, `docs/README.md`). README states: “Run everything: `python run.py`” for backend, frontend, and agents.
- **Market timing (ASSUMPTION):** VC teams are overloaded with inbound deal flow; agent automation reduces manual triage and standardizes scoring. *Validate by: user interviews or product owner confirmation.*

### 1.4 User Journey (with Component/Endpoint Mapping)

| Step | Description | Where in repo |
|------|-------------|---------------|
| 1. Land / Enter | User sees “Aethria” and “Enter System”; session stored in localStorage. | `EnterSystemPage.tsx` (lines 11–94), `App.tsx` (hasValidSession, handleEnter, STORAGE_KEY). |
| 2. Loading | “Loading Intelligence Data” for ≥2s while startups fetched. | `LoadingAnimation.tsx`, `App.tsx` (MIN_LOADING_MS, fetchStartups). |
| 3. Main feed | Work grid of startups; global clock, system bar (scout count). | `MainLayout.tsx`, `WorkGrid.tsx`, `SystemBar.tsx`, `GlobalClock.tsx`. |
| 4. Select startup | Click card → memo or verdict modal. | `MainLayout.tsx` (handleStartupClick, selectedStartup), `InvestmentMemo.tsx`, `VerdictModal.tsx`. |
| 5. View memo | Full memo (markdown) from API. | `GET /api/startups/{id}/memo` (`api.py` 174–183), `fetchMemo` in `api/startups.ts`. |
| 6. View verdict | Partner decision, rationale, next action. | `VerdictModal.tsx`, `partner` on Startup type. |
| 7. Settings | Toggle scouts/reviewers/partners; cost budget; portfolio options. | `SettingsPage.tsx`, `GET/PATCH /api/settings` (`api.py` 194–212), `api/settings.ts`. |
| 8. Idle timeout | After 20 min idle, session cleared and user returned to Enter. | `App.tsx` (IDLE_MS, useIdleTimeout). |

**Confidence:** High (flows traceable in code).

### 1.5 MVP Features (P0/P1)

| # | Feature | What | User Story | Success Criteria | Priority | Files / Evidence |
|---|---------|------|------------|------------------|----------|------------------|
| 1 | Automatic Scouting Agent | Four scout types (market-driven, builder/technical, pain-point, contrarian) run on interval; one LLM call per scout per cycle; persist to storage. | As Emma, I want the system to discover startup ideas automatically so that I have a steady pipeline. | At least one scout returns valid discovery per cycle; stored in `data/startups.json`. | P0 | `backend/scout/base.py`, `scout/scouts.py`, `scout/engine.py` (run_cycle, add_discovery), `storage.py` (add_discovery). |
| 2 | Reviewer Layer | Evaluates unreviewed discoveries; scores (market, product, technical, execution, optional defensibility); verdict STRONG/MEDIUM/WEAK; one LLM call per review. | As Emma, I want each discovery scored and verdicted so that I can triage quickly. | Unreviewed entries get review; verdict and scores stored. | P0 | `backend/reviewer/base.py`, `reviewer/reviewer.py`, `reviewer/engine.py`, `reviewer/schema.py`, `resources/config/active.json`, `resources/config/reviewer_rules/v1.json`, `resources/config/evaluation_rubric/v1.json`. |
| 3 | Partner Decision Layer | Rule-based YES/NO/MAYBE from verdict + scores; optional LLM fallback for edge cases; next_action, human_review_required. | As a partner, I want a clear decision and next action so that I know what to do. | Every reviewed startup gets a decision; rationale and next_action stored. | P0 | `backend/partner/decision.py`, `partner/engine.py`, `resources/config/active.json`, `resources/config/partner_rules/v1.json`. |
| 4 | Investment Memo | Markdown memo from Startup (Scout + Review + Partner + Financials). | As Emma, I want a one-page memo per startup so that I can share with partners. | Memo contains overview, scores, verdict, decision, next steps; API returns markdown. | P0 | `backend/memo_generator.py` (generate_memo), `GET /api/startups/{id}/memo`, `resources/contracts/memos/investment_memo_v1.json`. |
| 5 | Single-Run Dev Experience | One command starts backend (8000), frontend (3000), and agents. | As a developer, I want `python run.py` to run the full stack so that I can demo locally. | Backend, Vite, and agents start; logs stream with [Backend]/[Frontend]/[Agents]. | P0 | `run.py` (lines 72–164). |
| 6 | Startup List API | GET /api/startups returns all startups (frontend shape). | As the frontend, I need the list of startups to show the feed. | 200 + JSON array; each item has id, scout, review, partner, timestamps. | P0 | `backend/api.py` (_backend_to_frontend, get_startups), `app-front-end/src/api/startups.ts`. |
| 7 | Settings API & UI | GET/PATCH /api/settings; UI for cost_budget, agent_config (scouts/reviewers/partners toggles), portfolio. | As Emma, I want to turn scouts/reviewers/partners on or off and set cost limits. | PATCH persists to `data/settings.json`; engines respect toggles via `settings_loader`. | P1 | `backend/api.py` (get_settings, patch_settings, _validate_settings), `settings_loader.py`, `SettingsPage.tsx`, `api/settings.ts`. |
| 8 | Responsive Frontend + Enter + Feed | Enter screen, loading, main feed (work grid), memo and verdict modals, layout primitives. | As a user, I want a clean, responsive UI to enter, see startups, and open memos/verdicts. | Works on desktop; Enter → Loading → Feed; click startup → memo or verdict. | P1 | `App.tsx`, `EnterSystemPage.tsx`, `MainLayout.tsx`, `WorkGrid.tsx`, `InvestmentMemo.tsx`, `VerdictModal.tsx`, `layout/`, `design-system/`. |
| 9 | Portfolio Layer | Memory: startups, decisions, portfolio, rejections, watchlist, signals, agent_metrics. | As the system, I need long-term memory and routing of decisions. | Partner decisions flow to portfolio store; execution/signals/feedback/health run. | P1 | `backend/portfolio/engine.py`, `portfolio/store.py`, `portfolio/execution.py`, `portfolio/signals.py`, `portfolio/feedback.py`, `portfolio/health.py`. |

### 1.6 NOT in MVP (Explicitly Excluded)

- **Crunchbase / PitchBook / AngelList integrations:** Not present in repo (no API clients or env vars). Context says “integrations planned”; excluded from MVP until implemented.
- **Postgres / Redis:** Storage is JSON file (`data/startups.json`, `data/settings.json`, `data/portfolio/*.json`). Migration to Postgres is documented as future (`docs/ARCHITECTURE.md`, `docs/AUDIT_DEALFLOW.md`).
- **Docker / docker-compose:** No Dockerfile or docker-compose in repo; run is local via `run.py`.
- **Multi-partner voting / Meta-layer:** Single partner engine; no meta-layer (noted in ARCHITECTURE.md).
- **GDPR/RBAC implementation:** No consent, retention, or role-based access code found; compliance is future work.
- **web-front-end:** Separate app in `web-front-end/`; MVP uses `app-front-end/` only.

### 1.7 Metrics (Suggested)

- **First 30 days:**  
  - Memos viewed (count of memo API calls or frontend memo opens).  
  - Startups with partner decision (count from storage or API).  
  - Demo signups (ASSUMPTION: track via form or CRM; not in repo).
- **Months 2–3:**  
  - Deals scouted per week (Scout cycle count × discoveries per cycle).  
  - Reviewer/Partner cycle success rate (from agent logs).  
  - Daily active users (ASSUMPTION: add analytics; not in repo).
- **Measurement:** Add analytics hooks in frontend (e.g. memo open, settings save); backend already logs discovery/review/decision counts. *Confidence: Medium (instrumentation not present; method is standard).*

### 1.8 Look & Feel

- **From repo:** Palette: oxford (#002147), charcoal (#2f333b), ivory (#fcfcfc), bone/mist (#f2f4f8). Typography: Libre Baskerville (wordmark/display), Inter (body). No cards/boxed UI; vertical rhythm, thin dividers, max-width for content (`docs/DESIGN_SYSTEM.md`, `app-front-end/src/design-system/tokens.ts`).
- **Descriptive words:** Calm, precise, institutional, restrained, editorial.
- **Principles:** Hierarchy via size/weight/spacing; no gradients; system elements (wordmark, global clock, system bar) full-width; content column 80% or panel for feed.

---

## 2. Product Overview / Executive One-Pager

- **Product:** Aethria — AI-powered DealFlow OS for VC firms.
- **Tagline:** Intelligent investment discovery and evaluation system.
- **Mission:** Automate early-stage startup scouting, produce concise investment memos, and score startups against customizable VC rubrics.
- **Phase:** Phase 1 MVP: single-run dev experience, Scout → Reviewer → Partner → Portfolio pipeline, responsive app front-end, settings, memo API, demo-ready UI.
- **Launch goal:** Demo to 3–5 VC contacts with a stable, single-command run and clear scout → memo → score → decision flow.
- **Tech:** React + TypeScript (Vite) frontend, FastAPI backend, Python agents (OpenAI), file-based storage; Postgres/Redis/integrations planned later.

---

## 3. Feature Inventory

| Feature | Status | Owner / Notes | Key Files |
|---------|--------|---------------|-----------|
| Scout (4 types) | Implemented | Scout engine | `scout/base.py`, `scout/scouts.py`, `scout/engine.py`, `scout/schema.py` |
| Reviewer | Implemented | Reviewer engine | `reviewer/base.py`, `reviewer/reviewer.py`, `reviewer/engine.py`, `reviewer/schema.py` |
| Partner (rule-based) | Implemented | Partner engine | `partner/decision.py`, `partner/engine.py`, `partner/schema.py` |
| Portfolio (memory + execution + signals + feedback + health) | Implemented | Portfolio engine | `portfolio/engine.py`, `portfolio/store.py`, `portfolio/execution.py`, `portfolio/signals.py`, `portfolio/feedback.py`, `portfolio/health.py` |
| Storage (thread-safe JSON) | Implemented | Backend | `storage.py`, `models.py`, `adapters.py` |
| Memo generator | Implemented | Backend | `memo_generator.py` |
| GET /api/startups | Implemented | API | `api.py` (get_startups, _backend_to_frontend) |
| GET /api/startups/:id/memo | Implemented | API | `api.py` (get_startup_memo) |
| GET/PATCH /api/settings | Implemented | API | `api.py`, `settings_loader.py` |
| Single-run entrypoint | Implemented | Repo root | `run.py` |
| Enter + Loading + Feed UI | Implemented | App front-end | `App.tsx`, `EnterSystemPage.tsx`, `LoadingAnimation.tsx`, `MainLayout.tsx`, `WorkGrid.tsx` |
| Memo & Verdict modals | Implemented | App front-end | `InvestmentMemo.tsx`, `VerdictModal.tsx` |
| Settings page | Implemented | App front-end | `SettingsPage.tsx`, `api/settings.ts` |
| Design system & layout | Implemented | App front-end | `design-system/`, `layout/` |
| Crunchbase/PitchBook/AngelList | Not in repo | — | — |
| Postgres / Redis | Not in repo | Planned | docs/ARCHITECTURE.md |
| GDPR / RBAC | Not in repo | Planned | — |
| Docker | Not in repo | — | — |

---

## 4. Technical Inventory (Feature → Code Mapping)

| Claim | Location (file: lines or function) |
|-------|------------------------------------|
| Single entrypoint runs backend + frontend + agents | `run.py` (full file); backend uvicorn, frontend npm run dev, agents run_system.py |
| Scout base and one LLM call per scout | `backend/scout/base.py` (_call_llm_sync, discover); `scout/engine.py` (run_cycle) |
| Four scout types | `backend/scout/scouts.py`; `scout/engine.py` (MarketDrivenScout, BuilderTechnicalScout, PainPointScout, ContrarianScout) |
| Reviewer uses rubric and reviewer_rules | `backend/reviewer/base.py` (_load_reviewer_resources, _build_system_prompt); `resources/config/active.json`, `resources/config/reviewer_rules/v1.json`, `resources/config/evaluation_rubric/v1.json`, `backend/core/policy_resolver.py` |
| Partner rule-based decision (YES/NO/MAYBE) | `backend/partner/decision.py` (decide, _create_decision); `resources/config/active.json`, `resources/config/partner_rules/v1.json` |
| Storage thread-safe, atomic writes | `backend/storage.py` (_atomic_update, fcntl LOCK_EX, temp file + rename) |
| Startup model (ScoutInfo, ReviewInfo, PartnerInfo, Financials) | `backend/models.py` (Startup, ScoutInfo, ReviewInfo, PartnerInfo, Financials) |
| Memo from Startup | `backend/memo_generator.py` (MemoGenerator.generate_memo); format ref `resources/contracts/memos/investment_memo_v1.json` |
| Settings from data/settings.json | `backend/settings_loader.py` (load_settings, get_settings_path); `api.py` (get_settings, patch_settings) |
| Frontend fetches startups and memo | `app-front-end/src/api/startups.ts` (fetchStartups, fetchMemo); proxy to backend in `vite.config.ts` |
| Enter → session → main feed | `app-front-end/src/App.tsx` (hasValidSession, hasEntered, handleEnter, STARTUPS_POLL_MS) |
| Idle timeout 20 min | `app-front-end/src/App.tsx` (IDLE_MS, useIdleTimeout) |
| Design tokens (oxford, charcoal, ivory, motion) | `app-front-end/src/design-system/tokens.ts` |
| Layout primitives | `app-front-end/src/layout/` (PageWrapper, Section, Divider, ContentColumn) |

---

## 5. API & Data Model Summary

### OpenAPI-Style Endpoints

| Method | Path | Purpose | Inputs | Outputs |
|--------|------|---------|--------|---------|
| GET | /api/startups | List all startups (frontend shape) | — | 200, array of { id, scout, review?, partner?, timestamps } |
| GET | /api/startups/{startup_id}/memo | Full investment memo (markdown) | startup_id path | 200 { memo: string } or 404 |
| GET | /health | Health check | — | 200 { status: "ok" } |
| GET | /api/settings | Get control-plane settings | — | 200 { cost_budget, agent_config, portfolio } |
| PATCH | /api/settings | Update settings (partial) | body: { cost_budget?, agent_config?, portfolio? } | 200 merged settings or 422 validation errors |

**CORS:** Allow origin `http://localhost:3000`, `http://127.0.0.1:3000` (`api.py` lines 20–27).

### Data Model (Summary)

- **Discovery pipeline:** One JSON file (`data/startups.json` or `STORAGE_PATH`). Each record is a **Startup**: `startup_id`, `scout_info` (ScoutInfo), `review_info` (ReviewInfo | null), `partner_info` (PartnerInfo | null), `financials`, `created_at`, `updated_at`.
- **ScoutInfo:** name, one_line, sector, problem, solution, target_users, why_now, scout_type, confidence_score, funding_stage?, est_tam?, discovered_at.
- **ReviewInfo:** market/product/technical/execution (and optional defensibility) scores 1–10, overall_summary, key_risks, verdict (STRONG|MEDIUM|WEAK), diligence_red_flags, assumption_feedback, team_analysis?, etc., reviewed_at.
- **PartnerInfo:** decision (YES|NO|MAYBE), rationale, next_action, conviction_level 1–10, human_review_required, partnered_at.
- **Financials:** traction_metrics?, funding_history?, valuation_est?, ip_status?; revenue_missing, funding_missing, valuation_missing.
- **Portfolio store:** `data/portfolio/` — startups.json, decisions.json, portfolio.json, rejections.json, watchlist.json, signals.json, agent_metrics.json (see `portfolio/store.py`).

### 5.1 Architecture & Run Reference

- **Pipeline:** Scout → Reviewer → Partner → Portfolio (see [ARCHITECTURE.md](ARCHITECTURE.md) for full layer detail).
- **Design principles:** Cost-disciplined (one LLM call per scout/review per cycle; Partner rule-based); strict schema validation; thread-safe file ops (fcntl); autonomous long runs.
- **Default storage path:** `data/startups.json` (env `STORAGE_PATH`). Settings: `data/settings.json` (`SETTINGS_PATH`). Portfolio: `data/portfolio/` (`PORTFOLIO_DIR`).
- **Run:** Full stack from repo root: `python run.py` (backend :8000, frontend :3000, agents). Backend-only: `cd backend && python run_system.py`. API-only: `cd backend && uvicorn api:app --reload --host 0.0.0.0 --port 8000`.
- **Environment (required):** `OPENAI_API_KEY`. Optional: `STORAGE_PATH`, `SETTINGS_PATH`, `SCOUT_INTERVAL_SECONDS` (300), `REVIEWER_INTERVAL_SECONDS` (60), `PARTNER_INTERVAL_SECONDS` (30), `SCOUT_MODEL`, `REVIEWER_MODEL`, `PARTNER_USE_LLM`, `PORTFOLIO_DIR`.
- **Known limitations:** Single JSON storage (Postgres planned at scale); no meta-layer; single partner (no multi-partner voting); health monitor detects but does not auto-remediate.

### 5.2 Operations (Wipe Script)

To reset discovery storage to an empty list (e.g. for a clean demo):

```bash
cd backend
python scripts/wipe_startups.py [--path data/startups.json] [--dry-run]
```

- Uses `STORAGE_PATH` when `--path` not given. `--dry-run`: log only, no write. Storage methods: `reset_to_empty()`, `replace_all(list_of_startup_dicts)` for bulk load/migration (see [AUDIT_DEALFLOW.md](AUDIT_DEALFLOW.md)).

---

## 6. MVP Backlog

| Id | Priority | User Story | Acceptance Criteria | Est. (SP / hours) |
|----|----------|------------|---------------------|-------------------|
| B1 | P0 | As a dev, I run `python run.py` and get backend + frontend + agents. | All three start; logs show [Backend]/[Frontend]/[Agents]. | 1 SP / 0–2 h (done) |
| B2 | P0 | As Emma, I see a list of startups after entering. | GET /api/startups returns data; feed shows cards. | 1 SP / 0–2 h (done) |
| B3 | P0 | As Emma, I open a startup and see its memo. | GET /api/startups/:id/memo returns markdown; modal shows memo. | 2 SP / 2–4 h (done) |
| B4 | P0 | As Emma, scouts and reviewers run automatically and new startups appear. | Agents run on interval; new discoveries get reviewed and decided; feed updates on poll. | 2 SP / 2–4 h (done) |
| B5 | P1 | As Emma, I change settings and agents respect them. | PATCH /api/settings; scouts_enabled/reviewers_enabled/partners_enabled toggles; engines read via settings_loader. | 2 SP / 2–4 h (done) |
| B6 | P1 | As a partner, I see verdict and next action for each startup. | Verdict modal shows decision, rationale, next_action, human_review_required. | 1 SP / 0–2 h (done) |
| B7 | P2 | As a dev, I have one E2E test: scout → review → partner → memo. | Single test or script that runs pipeline and asserts memo content. | 5 SP / 8–16 h |
| B8 | P2 | As a PM, we have a short “about” and success/error copy for demos. | Microcopy doc or constants used in UI (see UX section). | 1 SP / 1–2 h |

---

## 7. 6–8 Week Launch Roadmap

| Week | Sprint | Deliverables | QA / Demo | Owners | Risk mitigation |
|------|--------|--------------|-----------|--------|------------------|
| 0 | Setup | Env doc (.env.example), confirm OPENAI_API_KEY, run.py green | Run full stack once | Full stack | If no key: document stub/mock for demo |
| 1 | Stabilize | No new features; fix flaky tests, log noise | test_scouts + test_end_to_end + test_partner_flow pass | Backend | — |
| 2 | Frontend polish | Enter + loading + feed responsive; memo/verdict accessible | Manual pass on desktop + one mobile size | Frontend | — |
| 3 | Settings & control | Settings page and PATCH validated; agents respect toggles | Toggle scouts off, confirm no new discoveries | Full stack | — |
| 4 | Memo & export | Memo API stable; optional “copy memo” or download link in UI | Memo matches backend generator output | Backend + Frontend | — |
| 5 | E2E & docs | One E2E test (scout → memo); PRD and runbook updated | E2E green; runbook runnable by new dev | Backend + Docs | — |
| 6 | Demo prep | About blurb, success/error microcopy, demo script | Internal dry run | PM + Frontend | — |
| 7–8 | Launch | Demo to 3–5 VC contacts; collect feedback | Demo checklist; feedback log | All | If API key limits: reduce scout/reviewer frequency for demo |

---

## 8. Launch Success Metrics

| Metric | Target (first 30 days) | Months 2–3 | Measurement |
|--------|------------------------|------------|-------------|
| Memos viewed | ≥20 | Track trend | Count memo API calls or frontend memo opens |
| Startups with decision | ≥10 | Grow with usage | Count from storage or GET /api/startups |
| Successful demos | 3–5 | — | Manual count / CRM |
| Scout cycles without crash | 100% (or document known failures) | Same | Agent logs / health |
| Time to first memo (new user) | <2 min | — | Manual or analytics |

---

## 9. UX Key Screens & Microcopy

### Onboarding / Enter

- **Headline:** Aethria (Libre Baskerville, as in `EnterSystemPage.tsx`).
- **Subhead:** Intelligent investment discovery and evaluation system.
- **CTA:** Enter System.
- **Footer:** Investment Intelligence Platform.

### Success / Failure (Memo Generation)

- **Success (snackbar/modal):** “Memo loaded.” (or keep current behavior: modal shows memo).
- **Failure (API error):** “Could not load memo. Please try again.” (suggest adding if not present).

### About Blurb (for VC Demo)

- “Aethria is an AI-powered DealFlow OS for venture capital firms. It automatically discovers startup ideas with four scout strategies, scores them on market, product, technical, and execution dimensions, and produces partner decisions (YES/NO/MAYBE) with clear next actions. You see a feed of scored startups and one-page investment memos, and you can control scouts, reviewers, and partners from the settings page. This demo runs the full pipeline locally.”

### Component → Responsibility

- `EnterSystemPage.tsx` — Landing / enter; session start.
- `LoadingAnimation.tsx` — Loading state (“Loading Intelligence Data”).
- `MainLayout.tsx` — Shell: clock, system bar, work grid, memo/verdict modals, judgements panel.
- `WorkGrid.tsx` — Startup cards grid.
- `InvestmentMemo.tsx` — Memo modal (markdown from API).
- `VerdictModal.tsx` — Partner verdict and next action.
- `SystemBar.tsx` — Scout count, nav (e.g. Settings).
- `SettingsPage.tsx` — Control plane (cost, agents, portfolio).
- `LiveIntelligenceFeed.tsx` — Judgements panel content.

---

## 10. Security & GDPR Checklist

- **PII handling:** Startup names, one-liners, and free text (problem, solution, etc.) are stored in JSON; no explicit PII field list or encryption in repo. *Recommendation:* Classify PII and add retention/access rules.
- **GDPR:** No consent flags, data retention policy, export/delete endpoints, or anonymization found. *Recommendation:* Add data retention, export/delete for “my data,” and document in privacy policy.
- **Auth:** No authentication on API endpoints; CORS limited to localhost. *Recommendation:* Add auth before any non-demo deployment.
- **Secrets:** OPENAI_API_KEY from env (`.env` at root); not logged in code. *Recommendation:* Add `.env.example` with placeholders; ensure .env in .gitignore.
- **RBAC:** Not implemented. *Recommendation:* Plan roles (e.g. analyst vs partner) when adding auth.

---

## 11. Tests & CI Plan

### Existing Tests

- **Backend:** `backend/tests/test_scouts.py` (Scout cycle), `test_end_to_end.py` (Scout → Storage → Reviewer), `test_partner_flow.py` (Scout → Reviewer → Partner), `test_portfolio_layer.py` (Portfolio components). No Docker; no `.github` workflows found.
- **Frontend:** Lint script in `app-front-end/package.json` (`lint`); no frontend test script referenced in package.json.

### Three End-to-End Acceptance Tests (Core Flow)

1. **E2E-1 Scout → memo:** Run Scout cycle (at least one discovery), then run Reviewer and Partner cycles until that startup has a decision; call `GET /api/startups/{id}/memo` and assert response contains "Reviewer Analysis" and "Decision" (or "Next Steps"). *Files:* Backend storage + memo_generator + api; test in `backend/tests/` or new `test_memo_e2e.py`.
2. **E2E-2 Score → verdict:** For a startup with review_info, assert Partner decision is one of YES/NO/MAYBE and `next_action` is non-empty. *Files:* `partner/decision.py`, `storage.py`; extend `test_partner_flow.py` or add assertion in existing test.
3. **E2E-3 UI flow (optional):** With backend and frontend running, open app → click Enter System → wait for loading to finish → assert at least one startup card or empty state → click a startup → assert memo modal or verdict modal is visible. *Tool:* Playwright/Cypress; new e2e suite in app-front-end or repo root.

### Proposed Minimum for MVP

1. **Unit:** Keep existing backend tests; add one test that `MemoGenerator.generate_memo` produces expected sections for a fixture Startup.
2. **Integration:** One test: run Scout cycle → add to storage → run Reviewer cycle → run Partner cycle → generate memo; assert verdict and memo contain key strings.
3. **E2E (optional):** Playwright or Cypress: open app → Enter → wait for feed → click first startup → assert memo or verdict visible (requires backend + frontend running).

### CI/CD (Suggested)

- **Pipeline:** On push/PR — install deps, backend tests (`cd backend && pip install -r requirements.txt && python -m pytest tests/` or equivalent), frontend build (`cd app-front-end && npm run build`). No staging/deploy in repo yet.
- **Monitoring:** Use existing agent logs; add alerts on repeated API failures or storage read errors if moving to hosted env.

---

## 12. Risks & Gaps

### 12.1 Codebase Assessment

- **Strengths:** Four-layer pipeline (Scout, Reviewer, Partner, Portfolio) operational; cost discipline (one LLM per scout/review); strict schema validation; thread-safe storage; clear decision rules and memo generator.
- **Risks:** No meta-layer (agent evolution/governance); tests in `backend/tests/` but no full-pipeline integration test; single JSON storage will not scale without Postgres.
- **Verdict:** Production-ready for MVP/demo; deploy with monitoring and address high-priority gaps (env doc, E2E test, auth before non-demo). *Source: CODEBASE_EVALUATION.md.*

### 12.2 Gaps Table

| Gap | Detail | Owner | Priority | ETA |
|-----|--------|-------|----------|-----|
| No .env.example | New devs may not know OPENAI_API_KEY, STORAGE_PATH, etc. | Backend | P0 | 1 day |
| No auth on API | All endpoints open when served. | Backend | P1 | Before non-demo deploy |
| No GDPR/data retention | PII and retention not implemented. | Product/legal | P1 | Per roadmap |
| Single JSON storage at scale | May slow with 1000s of entries; Postgres planned. | Backend | P2 | Post-MVP |
| No Crunchbase/PitchBook/AngelList | No ingest from external sources. | Backend | P2 | Post-MVP |
| Test files in backend/tests | Good; add one E2E for full pipeline. | Backend | P1 | 1–2 days |
| No CI config | No GitHub Actions or other CI. | DevOps | P2 | 1–2 days |
| Scout hypothesis fields not persisted | primary_thesis, key_assumptions, biggest_unknown produced by Scouts but not on ScoutInfo/adapter; Reviewer does not receive them, so investment_thesis/risk_mitigation lack Scout grounding. | Backend | P2 | Post-MVP |
| Team/competitor/business-model input | Scout does not collect founder/team, competitors, or monetization; team_analysis and competition_analysis often [MISSING] in memos. | Backend | P2 | Post-MVP |

**One-sentence checklist for shippable demo:** Backend and frontend start with `python run.py`, OPENAI_API_KEY set, at least one Scout/Reviewer/Partner cycle runs and a startup appears in the feed with a viewable memo and verdict, and settings toggles persist and are respected by the engines.

---

## 13. Appendix: File Citations

- Single run entrypoint: `run.py` (full).
- Scout base and LLM call: `backend/scout/base.py` (e.g. lines 58–126, 142–161).
- Four scouts: `backend/scout/scouts.py`; `backend/scout/engine.py` (56–62, 67–111).
- Reviewer prompt and rubric: `backend/reviewer/base.py` (22–46, 74–127, 190–262); `resources/config/active.json`, `resources/config/reviewer_rules/v1.json`, `resources/config/evaluation_rubric/v1.json`, `backend/core/policy_resolver.py`.
- Partner rules: `backend/partner/decision.py` (65–255); `resources/config/active.json`, `resources/config/partner_rules/v1.json`.
- Storage: `backend/storage.py` (59–86, 85–124, 125–155, 321–334).
- Models: `backend/models.py` (1–157).
- Memo: `backend/memo_generator.py` (43–329); `backend/api.py` (174–183).
- Settings: `backend/settings_loader.py` (32–65); `backend/api.py` (194–212).
- API startups: `backend/api.py` (92–172, 175–183).
- Frontend enter and feed: `app-front-end/src/App.tsx` (17–109); `app-front-end/src/components/EnterSystemPage.tsx`; `app-front-end/src/components/MainLayout.tsx`.
- Frontend API: `app-front-end/src/api/startups.ts`; `app-front-end/src/api/settings.ts`; `app-front-end/vite.config.ts` (proxy).
- Design: `app-front-end/src/design-system/tokens.ts`; `docs/DESIGN_SYSTEM.md`; `docs/LAYOUT_PRIMITIVES.md`.
- Architecture, run, and ops: `docs/ARCHITECTURE.md` (layer detail); `docs/BACKEND.md` (backend quick ref); `docs/VERDICT_MEMO_AND_REVIEWER_SCORING.md` (verdict/memo/scoring); `docs/AUDIT_DEALFLOW.md` (storage/adapters/wipe).
