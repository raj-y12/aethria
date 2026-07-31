"""Prometheus metrics for Aethria.

Exposes pipeline throughput/latency, on-demand lookup outcomes, queue depth, and
SSE subscriber count at ``GET /metrics``. Single-process design (one uvicorn
worker per instance), so the default in-process registry is correct; if the API
is ever run multi-worker, switch to ``prometheus_client.multiprocess``.

Graceful degradation: if ``prometheus_client`` isn't installed the module loads
as a no-op so the app still boots and instrumentation calls are harmless. The
endpoint then reports that metrics are unavailable instead of 500-ing.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger("metrics")

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    ENABLED = True
except ImportError:  # pragma: no cover - exercised only when dep is absent
    ENABLED = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

# Dedicated registry so we control exactly what is exported (no default process
# collectors unless we opt in).
if ENABLED:
    REGISTRY = CollectorRegistry()

    PIPELINE_CYCLES = Counter(
        "aethria_pipeline_cycles_total",
        "Pipeline cycles run, by outcome.",
        ["outcome"],  # success | error
        registry=REGISTRY,
    )
    PIPELINE_CYCLE_DURATION = Histogram(
        "aethria_pipeline_cycle_duration_seconds",
        "Wall-clock duration of a full pipeline cycle.",
        buckets=(1, 2, 5, 10, 20, 30, 60, 120, 300, 600),
        registry=REGISTRY,
    )
    PIPELINE_STAGE_ITEMS = Counter(
        "aethria_pipeline_stage_items_total",
        "Items produced per pipeline stage.",
        ["stage"],  # startups_found | reviewed | decided | escalations
        registry=REGISTRY,
    )
    PIPELINE_STAGE_DURATION = Histogram(
        "aethria_pipeline_stage_duration_seconds",
        "Wall-clock duration of a bounded pipeline stage.",
        ["pipeline", "stage", "outcome"],
        buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120),
        registry=REGISTRY,
    )
    DECISION_READY_COST = Histogram(
        "aethria_decision_ready_cost_usd",
        "Measured model/search cost for a decision-ready current-pipeline opportunity.",
        ["cohort"],
        buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2),
        registry=REGISTRY,
    )
    DECISION_READY_TOKENS = Histogram(
        "aethria_decision_ready_tokens",
        "Measured tokens for a decision-ready current-pipeline opportunity.",
        ["cohort"],
        buckets=(100, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000),
        registry=REGISTRY,
    )
    MODEL_PROVIDER_TOKENS = Counter(
        "aethria_model_provider_tokens_total",
        "Recorded model tokens by bounded stage, model, and provider dimensions.",
        ["stage", "model", "provider"],
        registry=REGISTRY,
    )
    # TEMPORARY: compare retrieval providers before choosing a long-term default.
    RETRIEVAL_PROVIDER_REQUESTS = Counter(
        "aethria_retrieval_provider_requests_total",
        "Temporary retrieval-provider comparison requests.",
        ["provider", "outcome", "extraction_ok"],
        registry=REGISTRY,
    )
    RETRIEVAL_PROVIDER_RESULTS = Histogram(
        "aethria_retrieval_provider_results",
        "Temporary retrieval-provider comparison result counts.",
        ["provider", "outcome", "extraction_ok"],
        buckets=(0, 1, 2, 3, 5, 10, 15, 25, 50, 100),
        registry=REGISTRY,
    )
    RETRIEVAL_PROVIDER_LATENCY = Histogram(
        "aethria_retrieval_provider_latency_seconds",
        "Temporary retrieval-provider comparison latency.",
        ["provider", "outcome", "extraction_ok"],
        buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120),
        registry=REGISTRY,
    )
    RETRIEVAL_PROVIDER_CREDITS = Histogram(
        "aethria_retrieval_provider_credits",
        "Temporary retrieval-provider comparison reported credits.",
        ["provider", "outcome", "extraction_ok"],
        buckets=(0, 1, 2, 5, 10, 25, 50, 100),
        registry=REGISTRY,
    )
    EVALUATION_MANIFESTS = Counter(
        "aethria_evaluation_manifest_total",
        "Evaluation manifest writes by path and outcome.",
        ["path", "outcome"],
        registry=REGISTRY,
    )
    LOOKUPS = Counter(
        "aethria_lookups_total",
        "On-demand lookups, by outcome.",
        ["outcome"],  # success | not_found | error
        registry=REGISTRY,
    )
    SSE_SUBSCRIBERS = Gauge(
        "aethria_sse_subscribers",
        "Open SSE stream connections across all users.",
        registry=REGISTRY,
    )
    AGENT_QUEUE_DEPTH = Gauge(
        "aethria_agent_queue_depth",
        "Pending jobs in the periodic-pipeline queue.",
        registry=REGISTRY,
    )
    LOOKUP_QUEUE_DEPTH = Gauge(
        "aethria_lookup_queue_depth",
        "Pending jobs in the on-demand lookup queue.",
        registry=REGISTRY,
    )
    DURABLE_JOB_TRANSITIONS = Counter(
        "aethria_durable_jobs_total",
        "Durable job transitions by bounded job type and transition.",
        ["job_type", "transition"],
        registry=REGISTRY,
    )
    DURABLE_JOB_WAIT = Histogram(
        "aethria_durable_job_wait_seconds",
        "Time from durable acceptance to claim.",
        ["job_type"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 300),
        registry=REGISTRY,
    )
    DURABLE_JOB_RUN = Histogram(
        "aethria_durable_job_run_seconds",
        "Durable handler execution duration by outcome.",
        ["job_type", "outcome"],
        buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600),
        registry=REGISTRY,
    )
    DURABLE_JOB_HEARTBEAT_FAILURES = Counter(
        "aethria_durable_job_heartbeat_failures_total",
        "Rejected or failed durable lease heartbeats.",
        ["job_type"],
        registry=REGISTRY,
    )
    DURABLE_JOB_QUEUE_DEPTH = Gauge(
        "aethria_durable_job_queue_depth",
        "Durable job counts by bounded job type and status.",
        ["job_type", "status"],
        registry=REGISTRY,
    )
    OUTBOX_PUBLICATIONS = Counter(
        "aethria_outbox_publications_total",
        "Transactional outbox publication attempts by outcome.",
        ["outcome"],
        registry=REGISTRY,
    )
    OUTBOX_BACKLOG = Gauge(
        "aethria_outbox_backlog",
        "Unpublished transactional outbox events.",
        registry=REGISTRY,
    )
    PERSISTENT_LOOPS = Gauge(
        "aethria_persistent_agent_loops",
        "Active per-user persistent agent loops.",
        registry=REGISTRY,
    )
    EVENT_LOOP_LAG = Gauge(
        "aethria_event_loop_lag_seconds",
        "Most recent sampled asyncio event-loop lag (scheduling delay). Sustained "
        "values above ~0.1s mean sync I/O is blocking the serving loop.",
        registry=REGISTRY,
    )
    API_REQUESTS = Counter(
        "aethria_api_requests_total",
        "HTTP requests by method, path, and status.",
        ["method", "path", "status"],
        registry=REGISTRY,
    )
    API_REQUEST_DURATION = Histogram(
        "aethria_api_request_duration_seconds",
        "HTTP request duration by method and path.",
        ["method", "path"],
        buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
        registry=REGISTRY,
    )
else:  # no-op placeholders
    REGISTRY = None


# ---------------------------------------------------------------------------
# Instrumentation helpers — safe to call whether or not the dep is present.
# ---------------------------------------------------------------------------
def observe_pipeline_cycle(duration_seconds: float, *, outcome: str) -> None:
    if not ENABLED:
        return
    try:
        PIPELINE_CYCLES.labels(outcome=outcome).inc()
        if outcome == "success" and duration_seconds >= 0:
            PIPELINE_CYCLE_DURATION.observe(duration_seconds)
    except Exception as e:  # pragma: no cover - never let metrics break the pipeline
        logger.debug("observe_pipeline_cycle failed: %s", e)


def inc_stage(stage: str, amount: int) -> None:
    if not ENABLED or not amount:
        return
    try:
        PIPELINE_STAGE_ITEMS.labels(stage=stage).inc(amount)
    except Exception as e:  # pragma: no cover
        logger.debug("inc_stage failed: %s", e)


def observe_pipeline_stage(
    duration_seconds: float,
    *,
    pipeline: str,
    stage: str,
    outcome: str,
) -> None:
    """Observe a stage without tenant/job labels, keeping metric cardinality bounded."""
    if not ENABLED or duration_seconds < 0:
        return
    try:
        PIPELINE_STAGE_DURATION.labels(
            pipeline=pipeline,
            stage=stage,
            outcome=outcome,
        ).observe(duration_seconds)
    except Exception as e:  # pragma: no cover
        logger.debug("observe_pipeline_stage failed: %s", e)


_DECISION_READY_COHORTS = {"manual_lookup", "autonomous_discovery"}
_EVALUATION_PATHS = {"manual_lookup", "autonomous_discovery", "rerun"}
_OUTCOMES = {"success", "error", "incomplete"}
_JOB_TYPES = {"pipeline_cycle", "company_lookup"}
_JOB_TRANSITIONS = {
    "accepted",
    "claimed",
    "completed",
    "retried",
    "dead_lettered",
    "cancelled",
}
_JOB_STATUSES = {
    "queued",
    "running",
    "retry_wait",
    "blocked",
    "succeeded",
    "failed",
    "dead_letter",
    "cancelled",
}


def _allowlisted(value: str, allowed: set[str]) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in allowed else "unknown"


def observe_decision_ready_usage(*, cohort: str, cost_usd: float, tokens: int) -> None:
    if not ENABLED:
        return
    try:
        label = _allowlisted(cohort, _DECISION_READY_COHORTS)
        DECISION_READY_COST.labels(cohort=label).observe(max(0.0, float(cost_usd)))
        DECISION_READY_TOKENS.labels(cohort=label).observe(max(0, int(tokens)))
    except Exception as e:  # pragma: no cover
        logger.debug("observe_decision_ready_usage failed: %s", e)


def observe_model_provider_usage(
    *, stage: str, model: str, provider: str, tokens: int
) -> None:
    if not ENABLED or tokens <= 0:
        return
    try:
        stage_label = _allowlisted(stage, {"scout", "reviewer", "partner"})
        provider_label = _allowlisted(provider, {"openai", "tavily", "unknown"})
        model_label = str(model or "unknown").strip()[:80] or "unknown"
        MODEL_PROVIDER_TOKENS.labels(
            stage=stage_label,
            model=model_label,
            provider=provider_label,
        ).inc(max(0, int(tokens)))
    except Exception as e:  # pragma: no cover
        logger.debug("observe_model_provider_usage failed: %s", e)


def observe_retrieval_provider(
    *, provider: str, outcome: str, result_count: int, extraction_ok: bool,
    latency_seconds: float, credits: int | None,
) -> None:
    """TEMPORARY: record bounded A/B retrieval-provider comparison metrics."""
    if not ENABLED:
        return
    try:
        provider_label = _allowlisted(
            provider, {"firecrawl", "tavily", "duckduckgo_html_fallback", "unknown"}
        )
        outcome_label = _allowlisted(outcome, {"success", "empty", "error", "disabled"})
        extraction_label = "true" if extraction_ok else "false"
        labels = {"provider": provider_label, "outcome": outcome_label, "extraction_ok": extraction_label}
        RETRIEVAL_PROVIDER_REQUESTS.labels(**labels).inc()
        RETRIEVAL_PROVIDER_RESULTS.labels(**labels).observe(max(0, int(result_count)))
        RETRIEVAL_PROVIDER_LATENCY.labels(**labels).observe(max(0.0, float(latency_seconds)))
        if credits is not None:
            RETRIEVAL_PROVIDER_CREDITS.labels(**labels).observe(max(0, int(credits)))
    except Exception as e:  # pragma: no cover
        logger.debug("observe_retrieval_provider failed: %s", e)


def inc_evaluation_manifest(*, path: str, outcome: str) -> None:
    if not ENABLED:
        return
    try:
        EVALUATION_MANIFESTS.labels(
            path=_allowlisted(path, _EVALUATION_PATHS),
            outcome=_allowlisted(outcome, _OUTCOMES),
        ).inc()
    except Exception as e:  # pragma: no cover
        logger.debug("inc_evaluation_manifest failed: %s", e)


def inc_durable_job(*, job_type: str, transition: str) -> None:
    if not ENABLED:
        return
    try:
        DURABLE_JOB_TRANSITIONS.labels(
            job_type=_allowlisted(job_type, _JOB_TYPES),
            transition=_allowlisted(transition, _JOB_TRANSITIONS),
        ).inc()
    except Exception as e:  # pragma: no cover
        logger.debug("inc_durable_job failed: %s", e)


def observe_durable_job_wait(*, job_type: str, seconds: float) -> None:
    if not ENABLED or seconds < 0:
        return
    try:
        DURABLE_JOB_WAIT.labels(
            job_type=_allowlisted(job_type, _JOB_TYPES)
        ).observe(seconds)
    except Exception as e:  # pragma: no cover
        logger.debug("observe_durable_job_wait failed: %s", e)


def observe_durable_job_run(*, job_type: str, outcome: str, seconds: float) -> None:
    if not ENABLED or seconds < 0:
        return
    try:
        DURABLE_JOB_RUN.labels(
            job_type=_allowlisted(job_type, _JOB_TYPES),
            outcome=_allowlisted(outcome, {"success", "retry", "cancelled", "error"}),
        ).observe(seconds)
    except Exception as e:  # pragma: no cover
        logger.debug("observe_durable_job_run failed: %s", e)


def inc_durable_heartbeat_failure(*, job_type: str) -> None:
    if not ENABLED:
        return
    try:
        DURABLE_JOB_HEARTBEAT_FAILURES.labels(
            job_type=_allowlisted(job_type, _JOB_TYPES)
        ).inc()
    except Exception as e:  # pragma: no cover
        logger.debug("inc_durable_heartbeat_failure failed: %s", e)


def inc_outbox_publication(*, outcome: str) -> None:
    if not ENABLED:
        return
    try:
        OUTBOX_PUBLICATIONS.labels(
            outcome=_allowlisted(outcome, {"published", "failed"})
        ).inc()
    except Exception as e:  # pragma: no cover
        logger.debug("inc_outbox_publication failed: %s", e)


def set_durable_depths(depths: dict[str, int]) -> None:
    if not ENABLED:
        return
    try:
        for key, count in depths.items():
            job_type, _, status = str(key).partition(":")
            if job_type == "outbox" and status == "pending":
                OUTBOX_BACKLOG.set(max(0, int(count)))
            elif job_type in _JOB_TYPES and status in _JOB_STATUSES:
                DURABLE_JOB_QUEUE_DEPTH.labels(
                    job_type=job_type, status=status
                ).set(max(0, int(count)))
    except Exception as e:  # pragma: no cover
        logger.debug("set_durable_depths failed: %s", e)


def set_event_loop_lag(seconds: float) -> None:
    if not ENABLED:
        return
    try:
        EVENT_LOOP_LAG.set(max(0.0, seconds))
    except Exception as e:  # pragma: no cover
        logger.debug("set_event_loop_lag failed: %s", e)


def inc_lookup(outcome: str) -> None:
    if not ENABLED:
        return
    try:
        LOOKUPS.labels(outcome=outcome).inc()
    except Exception as e:  # pragma: no cover
        logger.debug("inc_lookup failed: %s", e)


def observe_api_request(method: str, path: str, status: int, duration_seconds: float) -> None:
    if not ENABLED:
        return
    try:
        # Keep metrics bounded: IDs are normalized by the caller before this point.
        API_REQUESTS.labels(method=method, path=path, status=str(status)).inc()
        API_REQUEST_DURATION.labels(method=method, path=path).observe(max(0.0, duration_seconds))
    except Exception as e:  # pragma: no cover
        logger.debug("observe_api_request failed: %s", e)


def render(
    *,
    sse_subscribers: Optional[int] = None,
    agent_queue_depth: Optional[int] = None,
    lookup_queue_depth: Optional[int] = None,
    persistent_loops: Optional[int] = None,
) -> bytes:
    """Refresh live gauges from the supplied snapshots and render the exposition.

    Gauges that reflect instantaneous state are sampled at scrape time (passed in
    by the endpoint) rather than tracked continuously.
    """
    if not ENABLED:
        return b"# aethria metrics unavailable: prometheus_client not installed\n"
    try:
        if sse_subscribers is not None:
            SSE_SUBSCRIBERS.set(sse_subscribers)
        if agent_queue_depth is not None:
            AGENT_QUEUE_DEPTH.set(agent_queue_depth)
        if lookup_queue_depth is not None:
            LOOKUP_QUEUE_DEPTH.set(lookup_queue_depth)
        if persistent_loops is not None:
            PERSISTENT_LOOPS.set(persistent_loops)
        return generate_latest(REGISTRY)
    except Exception as e:  # pragma: no cover
        logger.debug("metrics render failed: %s", e)
        return b"# aethria metrics render error\n"
