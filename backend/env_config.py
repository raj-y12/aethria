"""Canonical registry of every environment variable the backend reads.

Why this exists
---------------
Before this module the backend read ~100 distinct env vars via scattered
``os.getenv("X", "default")`` calls. Defaults drifted between call sites, there
was no single place to see the full configuration surface, and there was no
``.env.example`` to onboard from.

``REGISTRY`` below is the single source of truth for **names, types, defaults,
and docs**. Two things derive from it:

  * ``render_env_example()`` generates the repo-root ``.env.example``.
  * ``tests/test_config_registry.py`` asserts every ``os.getenv`` name in the
    codebase is registered here (drift guard) and that ``.env.example`` is in
    sync — so a new env var cannot be added without documenting it.

Call-time semantics (important)
-------------------------------
Accessors read ``os.environ`` **at call time**, not at import. Much of the
pipeline reads settings fresh each cycle, and the test-suite monkeypatches env
vars after import. A frozen ``pydantic-settings`` singleton would break both, so
these are deliberately live getters with the registry supplying the default.

Boolean parsing matches the codebase convention: truthy iff the lowercased value
is one of ``1``/``true``/``yes`` (the prior inline checks used exactly this set).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

# Truthy tokens — matches the historical inline ``.lower() in ("1","true","yes")``.
_TRUE_TOKENS = {"1", "true", "yes"}


@dataclass(frozen=True)
class EnvVar:
    name: str
    kind: str  # str | int | float | bool | secret
    default: Optional[str]  # None => no default at call sites (required or env-derived)
    section: str
    description: str
    required: bool = False
    example: Optional[str] = None  # value to show in .env.example (for secrets/required)


# ---------------------------------------------------------------------------
# Registry. Defaults mirror the historical call-site defaults exactly.
# ---------------------------------------------------------------------------
REGISTRY: List[EnvVar] = [
    # --- Core / storage ------------------------------------------------------
    EnvVar("USE_SUPABASE_STORAGE", "bool", "", "Legacy Supabase compatibility",
           "Deprecated compatibility switch; normal runtime persistence uses DATABASE_URL.",
           required=False, example="0"),
    EnvVar("DATA_DIR", "str", "data", "Core / storage", "Root dir for local fallback data."),
    EnvVar("PORTFOLIO_DIR", "str", "data/portfolio", "Core / storage",
           "Local fallback dir for the portfolio JSON store."),
    EnvVar("STORAGE_PATH", "str", "data/startups.json", "Core / storage",
           "Local fallback path for the startups store (dev only)."),
    EnvVar("SETTINGS_PATH", "str", "data/settings.json", "Core / storage",
           "Local fallback path for per-user settings (dev only)."),
    EnvVar("LOCAL_SNAPSHOT_READ_ONLY", "bool", "", "Core / storage",
           "Local imported production snapshot mode; keeps repositories readable and disables autonomous writers.",
           example="0"),

    # --- OpenAI / models -----------------------------------------------------
    EnvVar("OPENAI_API_KEY", "secret", "", "OpenAI / models",
           "OpenAI API key. Missing key = pipeline skipped (no silent failure).",
           required=True),
    EnvVar("SCOUT_MODEL", "str", "gpt-5-nano", "OpenAI / models", "Model for scout personas."),
    EnvVar("REVIEWER_MODEL", "str", "gpt-5-nano", "OpenAI / models", "Model for reviewer personas."),
    EnvVar("PARTNER_MODEL", "str", "gpt-5-nano", "OpenAI / models", "Model for partner LLM edge cases."),
    EnvVar("META_AGENT_MODEL", "str", "gpt-5-nano", "OpenAI / models", "Model for the meta-agent."),

    # --- Auth (Clerk) --------------------------------------------------------
    EnvVar("CLERK_JWKS_URL", "str", None, "Auth (Clerk)",
           "Clerk JWKS endpoint for RS256 JWT verification.", required=True,
           example="https://your-app.clerk.accounts.dev/.well-known/jwks.json"),
    EnvVar("CLERK_ISSUER", "str", None, "Auth (Clerk)", "Expected JWT issuer; mismatches fail closed."),
    EnvVar("CLERK_AUDIENCE", "str", None, "Auth (Clerk)", "Optional expected JWT audience."),
    EnvVar("CLERK_SECRET_KEY", "secret", "", "Auth (Clerk)", "Clerk backend API secret (optional)."),
    EnvVar("CLERK_JWT_LEEWAY_SECONDS", "int", "60", "Auth (Clerk)", "Clock-skew leeway for JWT validation."),

    # --- Server / CORS / SSE / limits ---------------------------------------
    EnvVar("ALLOWED_ORIGINS", "str", "", "Server / CORS / SSE",
           "Comma-separated extra CORS origins for production domains.",
           example="https://app.yourdomain.com"),
    EnvVar("ENVIRONMENT", "str", None, "Server / CORS / SSE", "Deployment env (production|prod gates docs)."),
    EnvVar("APP_ENV", "str", None, "Server / CORS / SSE", "Alt deployment env var (see ENVIRONMENT)."),
    EnvVar("FASTAPI_ENV", "str", None, "Server / CORS / SSE", "Alt deployment env var (see ENVIRONMENT)."),
    EnvVar("RENDER", "bool", "", "Server / CORS / SSE", "Render platform marker used when ENVIRONMENT is unset."),
    EnvVar("PUBLIC_API_DOCS_ENABLED", "bool", None, "Server / CORS / SSE",
           "Expose /docs & /openapi.json in production (default off in prod)."),
    EnvVar("SSE_KEEPALIVE_SECONDS", "int", "20", "Server / CORS / SSE", "SSE keepalive comment cadence."),
    EnvVar("SSE_MAX_CONNECTIONS", "int", "200", "Server / CORS / SSE",
           "Hard cap on concurrent SSE streams per process (503 beyond)."),
    EnvVar("STARTUPS_LIST_DEFAULT_LIMIT", "int", "250", "Server / CORS / SSE", "Default GET /api/startups page size."),
    EnvVar("STARTUPS_LIST_MAX_LIMIT", "int", "500", "Server / CORS / SSE", "Max GET /api/startups page size."),

    # --- Concurrency / agent loops ------------------------------------------
    EnvVar("MAX_CONCURRENT_PIPELINE_CYCLES", "int", "1", "Concurrency / loops",
           "Max concurrent pipeline cycles (keep 1 on small instances)."),
    EnvVar("MAX_CONCURRENT_LOOKUPS", "int", "2", "Concurrency / loops", "Max concurrent on-demand lookups."),
    EnvVar("REFERENCE_PROBE_CONCURRENCY", "int", "8", "Concurrency / loops",
           "Per-call reference probe concurrency; the process-wide pool remains capped at 8."),
    EnvVar("LOOKUP_RESOLUTION_TTL_SECONDS", "int", "300", "Concurrency / loops",
           "Lifetime of a server-side dispatch resolution token (capped at 15 minutes)."),
    EnvVar("LOOKUP_RESOLUTION_CACHE_MAX", "int", "512", "Concurrency / loops",
           "Maximum short-lived company resolutions retained per API process."),
    EnvVar("AGENT_LOOP_INTERVAL_SECONDS", "int", "300", "Concurrency / loops", "Per-user persistent loop tick."),
    EnvVar("RESUME_AGENT_LOOPS_ON_STARTUP", "bool", "true", "Concurrency / loops",
           "Resume every user's agent loop at boot (disable on tiny instances)."),
    EnvVar("MAX_RESUMED_AGENT_LOOPS", "int", "0", "Concurrency / loops", "Cap resumed loops after restart (0=no cap)."),
    EnvVar("RSS_SAMPLER_INTERVAL_SECONDS", "int", "60", "Concurrency / loops", "Process RSS sampler cadence (0=off)."),
    EnvVar("LOOP_LAG_SAMPLER_INTERVAL_SECONDS", "int", "5", "Concurrency / loops", "Event-loop lag sampler cadence (0=off)."),
    EnvVar("LOOP_LAG_WARN_SECONDS", "float", "0.25", "Concurrency / loops", "Log a warning when sampled event-loop lag exceeds this."),
    EnvVar("MALLOC_ARENA_MAX", "int", "2", "Concurrency / loops", "glibc malloc arena cap (RSS control)."),
    EnvVar("AGENT_TRIGGER_LOCK_TTL_SECONDS", "int", "900", "Concurrency / loops", "Distributed lock TTL for agent trigger."),
    EnvVar("LOOKUP_LOCK_TTL_SECONDS", "int", "900", "Concurrency / loops", "Distributed lock TTL for lookups."),
    EnvVar("META_TRIGGER_LOCK_TTL_SECONDS", "int", "900", "Concurrency / loops", "Distributed lock TTL for meta trigger."),
    EnvVar("CANCELLED_LOOKUP_MAX", "int", "1000", "Concurrency / loops", "Max remembered cancelled lookup ids."),
    EnvVar("AETHRIA_AGENT_USER_ID", "str", "", "Concurrency / loops",
           "Process-level tenant id for background agent workers."),

    # --- Scout ---------------------------------------------------------------
    EnvVar("SCOUT_INTERVAL_SECONDS", "int", "300", "Scout", "Scout engine interval."),
    EnvVar("SCOUT_BACKPRESSURE_THRESHOLD", "int", "10", "Scout", "Unreviewed backlog that throttles scouting."),
    EnvVar("SCOUT_RAMP_THRESHOLD", "int", "5", "Scout", "Backlog below which scouting ramps up."),
    EnvVar("SCOUT_RAMP_MAX_WAVES", "int", "2", "Scout", "Max scout waves per ramped cycle."),
    EnvVar("SCOUT_RECENCY_RESERVED_SLOTS", "int", "5", "Scout", "Slots reserved for recency/breaking-news scouts."),
    EnvVar("SCOUT_DISCOVERY_MAX_QUERIES", "int", "3", "Scout",
           "Max open-discovery retrieval queries per scout persona (thesis-derived)."),
    EnvVar("SCOUT_RETRIEVAL_MAX_RESULTS", "int", "10", "Scout", "Max web-search results per scout query."),
    EnvVar("SCOUT_RETRIEVAL_MERGED_CAP", "int", "16", "Scout", "Cap on merged retrieval results."),
    EnvVar("SCOUT_ENRICH_MAX_REFERENCES", "int", "12", "Scout", "Max references kept during enrichment."),
    EnvVar("SCOUT_ENRICH_MIN_CONFIDENCE", "float", "0.4", "Scout", "Min confidence to enrich a scout result."),

    # --- Founder resolution --------------------------------------------------
    EnvVar("FOUNDER_RESOLUTION_ENABLED", "bool", "true", "Founder resolution",
           "Run the deterministic founder-resolution stage after company resolution."),
    EnvVar("FOUNDER_RESOLUTION_MIN_CONFIDENCE", "float", "0.35", "Founder resolution",
           "Min candidate confidence to promote a founder name onto ScoutInfo. "
           "The full structured resolution is stored regardless."),
    EnvVar("FOUNDER_RESOLUTION_MAX_NAMES", "int", "8", "Founder resolution",
           "Cap on founder names promoted onto ScoutInfo (ScoutInfo allows at most 8)."),
    EnvVar("FOUNDER_TEAM_PAGE_EXTRACTION", "bool", "true", "Founder resolution",
           "Read the company's own team/about pages in full during founder resolution. "
           "Search snippets truncate these pages, which is why listed founders were missed."),
    EnvVar("FOUNDER_TEAM_PAGE_MAX", "int", "2", "Founder resolution",
           "Max company pages fetched per founder resolution (extract accepts at most 3)."),
    EnvVar("REVIEWER_FOUNDER_FALLBACK_RETRIEVAL", "bool", "false", "Founder resolution",
           "Allow reviewer-side founder resolution to run extra searches when the "
           "reviewer gap-retrieval pack names nobody. Off by default so reviews add no retrieval."),

    # --- Reviewer ------------------------------------------------------------
    EnvVar("REVIEWER_INTERVAL_SECONDS", "int", "60", "Reviewer", "Reviewer engine interval."),
    EnvVar("REVIEWER_BATCH_SIZE", "int", "3", "Reviewer", "Reviewer batch size per cycle."),
    EnvVar("REVIEWER_BACKPRESSURE_THRESHOLD", "int", "10", "Reviewer", "Undecided backlog that throttles review."),
    EnvVar("REVIEWER_RAMP_THRESHOLD", "int", "5", "Reviewer", "Backlog below which review ramps up."),
    EnvVar("REVIEWER_RAMP_BATCH_MAX", "int", "5", "Reviewer", "Max batch size when ramped."),
    EnvVar("REVIEWER_MAX_COMPLETION_TOKENS", "int", "", "Reviewer", "Override max completion tokens (empty=model default)."),
    EnvVar("REVIEWER_GAP_MAX_PER_QUERY", "int", "6", "Reviewer", "Max gap-retrieval results per query."),
    EnvVar("REVIEWER_GAP_MAX_SOURCES", "int", "12", "Reviewer", "Max gap-retrieval sources total."),

    # --- Partner -------------------------------------------------------------
    EnvVar("PARTNER_USE_LLM", "bool", "true", "Partner", "Allow LLM fallback for partner edge cases."),
    EnvVar("PARTNER_INTERVAL_SECONDS", "int", "30", "Partner", "Partner engine interval."),
    EnvVar("PARTNER_BATCH_MAX", "int", "20", "Partner", "Max decisions per partner cycle."),
    EnvVar("PARTNER_LLM_DEBUG_LOGS", "bool", "", "Partner", "Log full partner LLM prompts/responses."),
    EnvVar("PARTNER_LLM_INCLUDE_DEAL_CONTEXT_DIGEST", "bool", "", "Partner", "Include deal-context digest in partner prompt."),

    # --- Meta-agent ----------------------------------------------------------
    EnvVar("META_AGENT_ENABLED", "bool", "true", "Meta-agent", "Enable the self-optimization meta-agent."),
    EnvVar("META_AGENT_INTERVAL_SECONDS", "int", "86400", "Meta-agent", "Meta-agent run interval (daily)."),
    EnvVar("META_AGENT_MIN_DECISIONS", "int", "10", "Meta-agent", "Min decisions before meta acts."),
    EnvVar("META_AGENT_MIN_REVIEWS", "int", "20", "Meta-agent", "Min reviews before meta acts."),
    EnvVar("META_AGENT_MUTATION_COOLDOWN_CYCLES", "int", "3", "Meta-agent", "Cycles between prompt mutations."),
    EnvVar("META_AGENT_PROMPT_AUTO_APPLY", "bool", "false", "Meta-agent", "Auto-apply mutated prompts without review."),
    EnvVar("META_PROMPT_EVAL_CONCURRENCY", "int", "3", "Meta-agent", "Concurrency for prompt evaluation."),
    EnvVar("META_PROMPT_EVAL_MAX_MEAN_DELTA", "float", "2.5", "Meta-agent", "Max acceptable mean score delta in eval."),
    EnvVar("META_PROMPT_EVAL_MAX_STARTUPS", "int", "20", "Meta-agent", "Max startups per prompt eval run."),
    EnvVar("META_PROMPT_EVAL_PASS_TTL_HOURS", "int", "24", "Meta-agent", "How long an eval pass stays fresh."),
    EnvVar("META_PROMPT_EVAL_SET_MAX", "int", "50", "Meta-agent", "Max size of the eval startup set."),
    EnvVar("META_PROMPT_REQUIRE_EVAL_PASS", "bool", "", "Meta-agent",
           "Require a fresh eval pass before a prompt can be promoted."),

    # --- Fund thesis ---------------------------------------------------------
    EnvVar("FUND_THESIS_CACHE_TTL_SECONDS", "int", "10", "Fund thesis", "Active-thesis cache TTL."),
    EnvVar("FUND_THESIS_PARSE_MODEL", "str", "gpt-4o-mini", "Fund thesis", "Model for parsing fund config to thesis."),
    EnvVar("FUND_THESIS_EMBED_MODEL", "str", "text-embedding-3-small", "Fund thesis", "Embedding model for thesis vectors."),
    EnvVar("FUND_THESIS_RUNTIME_ALIGNMENT_ROW_LIMIT", "int", "500", "Fund thesis",
           "Max rows scanned for runtime thesis-alignment stats."),

    # --- Portfolio -----------------------------------------------------------
    EnvVar("PORTFOLIO_EXECUTION_SCAN_LIMIT", "int", "200", "Portfolio", "Max positions scanned per execution cycle."),
    EnvVar("PORTFOLIO_CLUSTER_ANALYSIS_LIMIT", "int", "500", "Portfolio", "Max rows for concentration clustering."),

    # --- Search provider routing ---------------------------------------------
    # Each retrieval category resolves its provider independently, so founder
    # (people) lookups can be routed to a specialised backend without affecting
    # company/news/general retrieval. Values are registered provider names;
    # every category defaults to the configured retrieval chain.
    EnvVar("SEARCH_PROVIDER_GENERAL", "str", "", "Search providers",
           "Provider name for general search (default: configured retrieval chain)."),
    EnvVar("SEARCH_PROVIDER_NEWS", "str", "", "Search providers",
           "Provider name for recency/news search (default: configured retrieval chain)."),
    EnvVar("SEARCH_PROVIDER_COMPANY", "str", "", "Search providers",
           "Provider name for company identity search (default: configured retrieval chain)."),
    EnvVar("SEARCH_PROVIDER_PEOPLE", "str", "", "Search providers",
           "Provider name for founder/people search (default: configured retrieval chain)."),

    # --- Retrieval providers -------------------------------------------------
    EnvVar("RETRIEVAL_PROVIDER_ORDER", "str", "exa,firecrawl", "Search providers",
           "Retrieval chain order, best-first. DuckDuckGo is always the final keyless fallback."),
    EnvVar("RETRIEVAL_PRIMARY_PROVIDER", "str", "", "Search providers",
           "Rollback lever: moves one provider (exa|firecrawl) to the head of the chain."),
    EnvVar("RETRIEVAL_FALLBACK_ENABLED", "bool", "1", "Search providers",
           "Use the keyless DuckDuckGo retrieval when the whole provider chain returns nothing."),
    EnvVar("RETRIEVAL_CACHE_TTL_GENERAL_SECONDS", "int", "86400", "Search providers",
           "Freshness window for general retrieval cache entries."),
    EnvVar("RETRIEVAL_CACHE_TTL_NEWS_SECONDS", "int", "21600", "Search providers",
           "Freshness window for news retrieval cache entries."),
    EnvVar("RETRIEVAL_CACHE_TTL_COMPANY_SECONDS", "int", "604800", "Search providers",
           "Freshness window for company retrieval cache entries."),
    EnvVar("RETRIEVAL_CACHE_TTL_PEOPLE_SECONDS", "int", "604800", "Search providers",
           "Freshness window for people retrieval cache entries."),
    EnvVar("RETRIEVAL_QUERY_CONCURRENCY", "int", "4", "Search providers",
           "Retrieval queries in flight at once within one merged pack (1 = sequential). "
           "Merge order stays deterministic regardless of this value."),

    # --- Exa (semantic search / company discovery) ---------------------------
    # Exa finds the companies; Firecrawl reads their pages. Full Exa page text is
    # never requested — highlights only, and only as a Firecrawl-failure fallback.
    EnvVar("EXA_API_KEY", "secret", "", "Exa", "Exa API key for semantic search and company discovery."),
    EnvVar("EXA_TIMEOUT", "float", "20.0", "Exa", "Exa request timeout (s)."),
    EnvVar("EXA_MAX_RESULTS_CAP", "int", "15", "Exa", "Cap on Exa results per query."),
    EnvVar("EXA_MAX_RETRIES", "int", "2", "Exa", "Retries for Exa 429 and 5xx responses."),
    EnvVar("EXA_SEARCH_TYPE", "str", "auto", "Exa",
           "Exa search mode (auto|fast|instant). Research/agent modes are deliberately not allowed."),
    EnvVar("EXA_HIGHLIGHT_MAX_CHARS", "int", "1200", "Exa", "Max Exa highlight chars kept per result."),
    EnvVar("EXA_ENRICH_WITH_FIRECRAWL", "bool", "1", "Exa", "Scrape top Exa URLs through Firecrawl for page content."),
    EnvVar("EXA_ENRICH_MAX_URLS", "int", "3", "Exa",
           "Max Exa URLs sent to Firecrawl per query (also bounded by FIRECRAWL_SCRAPE_MAX_URLS)."),
    EnvVar("EXA_INCLUDE_DOMAINS", "str", "", "Exa", "Comma-separated domain allowlist for Exa results."),
    EnvVar("EXA_EXCLUDE_DOMAINS", "str", "", "Exa",
           "Comma-separated domain denylist for Exa results (ignored for company/people categories)."),
    EnvVar("FIRECRAWL_API_KEY", "secret", "", "Firecrawl", "Firecrawl v2 API key for retrieval."),
    EnvVar("FIRECRAWL_TIMEOUT", "float", "20.0", "Firecrawl", "Firecrawl request timeout (s)."),
    EnvVar("FIRECRAWL_MAX_RESULTS_CAP", "int", "15", "Firecrawl", "Cap on Firecrawl results per query."),
    EnvVar("FIRECRAWL_MAX_RETRIES", "int", "2", "Firecrawl", "Retries for Firecrawl 429 and 5xx responses."),
    EnvVar("FIRECRAWL_INCLUDE_MARKDOWN", "bool", "1", "Firecrawl", "Request markdown in Firecrawl search results."),
    EnvVar("FIRECRAWL_MARKDOWN_MAX_CHARS", "int", "4500", "Firecrawl", "Max Firecrawl markdown chars kept per result."),
    EnvVar("FIRECRAWL_SCRAPE_MAX_URLS", "int", "3", "Firecrawl", "Max URLs sent to Firecrawl scrape."),


    # --- Legacy Supabase compatibility --------------------------------------
    EnvVar("SUPABASE_URL", "str", "", "Legacy Supabase compatibility",
           "Optional project URL for isolated legacy/test tooling."),
    EnvVar("SUPABASE_SERVICE_ROLE_KEY", "secret", "", "Legacy Supabase compatibility",
           "Optional service-role key for isolated legacy/test tooling."),
    EnvVar("SUPABASE_ANON_KEY", "secret", "", "Legacy Supabase compatibility",
           "Optional anon key for isolated legacy/test tooling."),
    EnvVar("VITE_SUPABASE_URL", "str", "", "Legacy Supabase compatibility",
           "Optional legacy URL fallback; not used by normal runtime."),
    EnvVar("SUPABASE_RETRY_ATTEMPTS", "int", "6", "Legacy Supabase compatibility",
           "Legacy transport retry attempts."),
    EnvVar("SUPABASE_MAX_RETRY_DELAY_SECONDS", "float", "1.5", "Legacy Supabase compatibility",
           "Legacy max backoff between retries."),
    EnvVar("SUPABASE_POOL_MAX_CONNECTIONS", "int", "40", "Legacy Supabase compatibility",
           "Legacy HTTP pool max connections."),
    EnvVar("SUPABASE_POOL_MAX_KEEPALIVE", "int", "20", "Legacy Supabase compatibility",
           "Legacy HTTP pool max keepalive connections."),
    EnvVar("SUPABASE_POOL_KEEPALIVE_EXPIRY", "int", "60", "Legacy Supabase compatibility",
           "Legacy HTTP keepalive expiry (seconds)."),

    # --- Admin dashboard -----------------------------------------------------
    EnvVar("ADMIN_DASHBOARD_ENABLED", "bool", None, "Admin",
           "Enable the admin dashboard (default on outside prod, off in prod unless set)."),
    EnvVar("ADMIN_DASHBOARD_SECRET", "secret", "", "Admin", "Shared secret for admin login."),
    EnvVar("ADMIN_TOKEN_SECRET", "secret", "", "Admin", "HMAC secret for admin session tokens."),
    EnvVar("ADMIN_TOKEN_TTL_MINUTES", "int", "60", "Admin", "Admin session token TTL."),
    EnvVar("ADMIN_LOGIN_MAX_FAILURES", "int", "5", "Admin", "Admin login failures before throttling."),
    EnvVar("ADMIN_LOGIN_WINDOW_SECONDS", "int", "300", "Admin", "Admin login failure window."),

    # --- Observability -------------------------------------------------------
    EnvVar("METRICS_ENABLED", "bool", "true", "Observability",
           "Expose the Prometheus /metrics endpoint."),
    EnvVar("METRICS_TOKEN", "secret", "", "Observability",
           "If set, /metrics requires this value as a Bearer token. Leave empty "
           "only on a trusted/private network."),

    # --- Event bus / multi-instance -----------------------------------------
    EnvVar("EVENT_BUS_BACKPLANE", "str", "memory", "Event bus",
           "SSE event fan-out: 'memory' (single instance) or 'postgres' "
           "(LISTEN/NOTIFY for multi-instance delivery)."),
    EnvVar("ALLOW_PROCESS_LOCAL_STATE", "bool", "false", "Event bus",
           "Explicitly acknowledge single-instance process-local queues/cancellation state."),
    EnvVar("DATABASE_URL", "secret", "", "Event bus",
           "Direct Postgres connection string for the LISTEN/NOTIFY backplane. "
           "Required when EVENT_BUS_BACKPLANE=postgres."),
    EnvVar("SNAPSHOT_DATABASE_URL", "secret", "", "Local snapshot validation",
           "Local production-snapshot DSN used only by bounded import/validation tooling."),
    EnvVar("SUPABASE_DB_URL", "secret", "", "Legacy Supabase compatibility",
           "Deprecated database URL accepted only by historical tooling."),

    # --- Durable jobs -------------------------------------------------------
    EnvVar("DURABLE_JOB_DB_POOL_MIN", "int", "1", "Durable jobs",
           "Minimum direct-Postgres connections reserved for durable jobs."),
    EnvVar("DURABLE_JOB_DB_POOL_MAX", "int", "4", "Durable jobs",
           "Maximum direct-Postgres connections used by durable jobs."),
    EnvVar("DURABLE_JOB_DB_COMMAND_TIMEOUT_SECONDS", "float", "30", "Durable jobs",
           "Database command timeout for durable job operations."),
    EnvVar("DURABLE_JOB_POLL_SECONDS", "float", "2", "Durable jobs",
           "Timed polling backstop when no job notification arrives."),
    EnvVar("DURABLE_JOB_LEASE_SECONDS", "int", "90", "Durable jobs",
           "Duration of an execution lease before another worker may recover it."),
    EnvVar("DURABLE_JOB_HEARTBEAT_SECONDS", "float", "20", "Durable jobs",
           "Heartbeat cadence for extending an active execution lease."),
    EnvVar("DURABLE_JOB_GLOBAL_CONCURRENCY", "int", "1", "Durable jobs",
           "Maximum durable jobs executing concurrently in one API process."),
    EnvVar("DURABLE_JOB_TENANT_CONCURRENCY", "int", "1", "Durable jobs",
           "Maximum durable jobs executing concurrently for one tenant."),
    EnvVar("DURABLE_OUTBOX_POLL_SECONDS", "float", "2", "Durable jobs",
           "Polling cadence for transactional outbox publication."),

    # --- Canonical identity -------------------------------------------------
    EnvVar("IDENTITY_AUTO_RESOLVE_CONFIDENCE", "float", "0.85", "Canonical identity",
           "Minimum deterministic confidence for one picker candidate to be eligible for automatic identity resolution."),

    # --- Attention-triggered enrichment ------------------------------------
    EnvVar("MONITOR_DAILY_BUDGET_USD", "float", "10", "Monitoring",
           "Maximum per-tenant daily reserved plus settled evidence-refresh cost."),

    # --- Scoring / retrieval / misc -----------------------------------------
    EnvVar("USE_STRUCTURED_SCORING", "bool", "true", "Scoring / misc", "Use the deterministic structured scoring engine."),
    EnvVar("SCORING_EVIDENCE_CALIBRATION_ENABLED", "bool", "true", "Scoring / misc",
           "Publish confidence-discounted, evidence-capped legacy display scores."),
    EnvVar("SKIP_READ_ENRICH_SCORES", "bool", "", "Scoring / misc", "Skip score enrichment on read (perf)."),
    EnvVar("DEBUG_SCORING", "bool", "false", "Scoring / misc", "Verbose scoring debug logs."),
    EnvVar("RETRIEVAL_SNIPPET_MAX_CHARS", "int", "2800", "Scoring / misc", "Max chars per retrieval snippet."),
    EnvVar("RECENCY_WINDOW_MONTHS", "int", "12", "Scoring / misc", "Recency window for breaking-news weighting."),
    EnvVar("LOOKUP_WEBSITE_FETCH_TIMEOUT", "float", "5.0", "Scoring / misc", "Timeout fetching a looked-up website."),
    EnvVar("DEAL_CONTEXT_LOG_PIPELINE", "bool", "", "Scoring / misc", "Log deal-context assembly during pipeline."),
    EnvVar("AETHRIA_TOKEN_COST_PER_1K_USD", "float", "0.001", "Scoring / misc", "Assumed $/1k tokens for cost estimates."),

    # --- Local contract tests ------------------------------------------------
    EnvVar("TEST_DATABASE_URL", "secret", "", "Local contract tests",
           "Vanilla PostgreSQL DSN used only by PostgreSQL contract tests."),
]

_BY_NAME = {v.name: v for v in REGISTRY}


# ---------------------------------------------------------------------------
# Call-time accessors
# ---------------------------------------------------------------------------
def _default(name: str) -> Optional[str]:
    v = _BY_NAME.get(name)
    return v.default if v else None


def get_str(name: str) -> str:
    return os.getenv(name, _default(name) or "") or ""


def get_optional_str(name: str) -> Optional[str]:
    val = os.getenv(name, _default(name))
    return val if (val is not None and val != "") else None


def get_bool(name: str) -> bool:
    raw = os.getenv(name, _default(name) or "")
    return str(raw or "").strip().lower() in _TRUE_TOKENS


def get_int(name: str) -> int:
    raw = os.getenv(name, _default(name) or "0")
    try:
        return int(str(raw).strip() or "0")
    except ValueError:
        return int(_default(name) or "0")


def get_float(name: str) -> float:
    raw = os.getenv(name, _default(name) or "0")
    try:
        return float(str(raw).strip() or "0")
    except ValueError:
        return float(_default(name) or "0")


# Convenience typed accessors for the hottest, most-duplicated reads.
def use_supabase_storage() -> bool:
    return get_bool("USE_SUPABASE_STORAGE")


def is_production_env() -> bool:
    """Return whether the application explicitly declares production mode."""
    value = (
        os.getenv("ENVIRONMENT")
        or os.getenv("APP_ENV")
        or os.getenv("FASTAPI_ENV")
        or ""
    )
    normalized = value.strip().lower()
    if normalized in {"local", "dev", "development", "test", "testing"}:
        return False
    if normalized in {"production", "prod"}:
        return True
    if normalized:
        return True
    return False


def is_deployed_env() -> bool:
    """Return whether the process is deployed, including Render.

    Deployed services must not fall back to local state. This is deliberately
    separate from the API's explicit production gate because a single Render
    instance may still use its configured in-process event bus.
    """
    return is_production_env() or get_bool("RENDER")


def allow_process_local_state() -> bool:
    """Whether process/local fallback state has been explicitly acknowledged."""
    return get_bool("ALLOW_PROCESS_LOCAL_STATE")


def local_fallback_allowed() -> bool:
    """Return whether local files/memory are an intentional storage mode.

    Production mode is fail-closed. Non-production processes retain the
    historical local fallback so test/dev workflows remain usable.
    """
    return not is_deployed_env()


def supabase_configured() -> bool:
    """Return whether the server-side Supabase credentials are present."""
    return bool(get_str("SUPABASE_URL").strip() and get_str("SUPABASE_SERVICE_ROLE_KEY").strip())


def require_supabase_configured(component: str) -> None:
    """Raise a diagnostic error instead of allowing a remote-to-local fallback."""
    if use_supabase_storage() and not supabase_configured():
        raise RuntimeError(
            f"{component}: supabase_configuration_missing; "
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required when "
            "USE_SUPABASE_STORAGE=1"
        )


def openai_api_key() -> str:
    return get_str("OPENAI_API_KEY")


def scout_model() -> str:
    return get_str("SCOUT_MODEL")


def reviewer_model() -> str:
    return get_str("REVIEWER_MODEL")


def partner_model() -> str:
    return get_str("PARTNER_MODEL")


# ---------------------------------------------------------------------------
# .env.example generation
# ---------------------------------------------------------------------------
def render_env_example() -> str:
    """Render the canonical .env.example text from REGISTRY (stable ordering)."""
    lines = [
        "# Aethria backend environment variables.",
        "# Generated from backend/config.py REGISTRY — do not edit by hand.",
        "# Regenerate with: python -c \"import env_config; print(env_config.render_env_example())\" > .env.example",
        "# Secrets and required values are shown with placeholders; fill them in your real .env.",
        "",
    ]
    # Preserve section order as first-seen in REGISTRY.
    sections: List[str] = []
    for v in REGISTRY:
        if v.section not in sections:
            sections.append(v.section)
    for section in sections:
        lines.append(f"# === {section} ===")
        for v in [x for x in REGISTRY if x.section == section]:
            tag = "REQUIRED" if v.required else "optional"
            lines.append(f"# {v.description} [{v.kind}, {tag}]")
            if v.example is not None:
                value = v.example
            elif v.kind == "secret":
                value = ""
            elif v.default is None:
                value = ""
            else:
                value = v.default
            lines.append(f"{v.name}={value}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":  # pragma: no cover
    print(render_env_example())
