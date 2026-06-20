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
    PERSISTENT_LOOPS = Gauge(
        "aethria_persistent_agent_loops",
        "Active per-user persistent agent loops.",
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


def inc_lookup(outcome: str) -> None:
    if not ENABLED:
        return
    try:
        LOOKUPS.labels(outcome=outcome).inc()
    except Exception as e:  # pragma: no cover
        logger.debug("inc_lookup failed: %s", e)


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
