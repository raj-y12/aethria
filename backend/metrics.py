"""Prometheus metrics for Aethria — dependency-free.

Exposes pipeline throughput/latency, on-demand lookup outcomes, queue depth, and
SSE subscriber count at ``GET /metrics`` in the Prometheus text exposition
format (v0.0.4). We emit the format by hand rather than depend on
``prometheus_client`` — the surface here is tiny (a few counters, one histogram,
a handful of gauges) and avoiding the dependency keeps the install lean.

Single-process design (one uvicorn worker per instance). The ``/metrics``
endpoint is a sync handler (runs in FastAPI's threadpool) while instrumentation
is called from the event loop, so all shared state is guarded by a lock.
"""
from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("metrics")

# Always available — no optional dependency. Kept for API compatibility with
# callers/tests that branch on it.
ENABLED = True
CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

_lock = threading.Lock()

LabelKey = Tuple[Tuple[str, str], ...]


def _format_labels(label_names: Tuple[str, ...], values: LabelKey) -> str:
    if not label_names:
        return ""
    parts = [f'{name}="{_escape(val)}"' for name, val in values]
    return "{" + ",".join(parts) + "}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class _Counter:
    def __init__(self, name: str, help_text: str, label_names: Tuple[str, ...] = ()):
        self.name = name
        self.help = help_text
        self.label_names = label_names
        self._values: Dict[LabelKey, float] = {}

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = tuple((n, labels[n]) for n in self.label_names)
        self._values[key] = self._values.get(key, 0.0) + amount

    def render(self) -> List[str]:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} counter"]
        for key, val in sorted(self._values.items()):
            lines.append(f"{self.name}{_format_labels(self.label_names, key)} {_num(val)}")
        return lines


class _Gauge:
    def __init__(self, name: str, help_text: str):
        self.name = name
        self.help = help_text
        self._value = 0.0

    def set(self, value: float) -> None:
        self._value = float(value)

    def render(self) -> List[str]:
        return [
            f"# HELP {self.name} {self.help}",
            f"# TYPE {self.name} gauge",
            f"{self.name} {_num(self._value)}",
        ]


class _Histogram:
    def __init__(self, name: str, help_text: str, buckets: Tuple[float, ...]):
        self.name = name
        self.help = help_text
        self.buckets = tuple(sorted(buckets))
        self._bucket_counts: List[int] = [0] * len(self.buckets)
        self._sum = 0.0
        self._count = 0

    def observe(self, value: float) -> None:
        self._sum += value
        self._count += 1
        for i, upper in enumerate(self.buckets):
            if value <= upper:
                self._bucket_counts[i] += 1

    def render(self) -> List[str]:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} histogram"]
        cumulative = 0
        for i, upper in enumerate(self.buckets):
            cumulative += self._bucket_counts[i]
            lines.append(f'{self.name}_bucket{{le="{_num(upper)}"}} {cumulative}')
        lines.append(f'{self.name}_bucket{{le="+Inf"}} {self._count}')
        lines.append(f"{self.name}_sum {_num(self._sum)}")
        lines.append(f"{self.name}_count {self._count}")
        return lines


def _num(value: float) -> str:
    """Render a number the way Prometheus expects (ints without a trailing .0)."""
    if value == int(value):
        return str(int(value))
    return repr(value)


# --- Metric instances -------------------------------------------------------
PIPELINE_CYCLES = _Counter("aethria_pipeline_cycles_total", "Pipeline cycles run, by outcome.", ("outcome",))
PIPELINE_CYCLE_DURATION = _Histogram(
    "aethria_pipeline_cycle_duration_seconds",
    "Wall-clock duration of a full pipeline cycle.",
    (1, 2, 5, 10, 20, 30, 60, 120, 300, 600),
)
PIPELINE_STAGE_ITEMS = _Counter(
    "aethria_pipeline_stage_items_total", "Items produced per pipeline stage.", ("stage",)
)
LOOKUPS = _Counter("aethria_lookups_total", "On-demand lookups, by outcome.", ("outcome",))
SSE_SUBSCRIBERS = _Gauge("aethria_sse_subscribers", "Open SSE stream connections across all users.")
AGENT_QUEUE_DEPTH = _Gauge("aethria_agent_queue_depth", "Pending jobs in the periodic-pipeline queue.")
LOOKUP_QUEUE_DEPTH = _Gauge("aethria_lookup_queue_depth", "Pending jobs in the on-demand lookup queue.")
PERSISTENT_LOOPS = _Gauge("aethria_persistent_agent_loops", "Active per-user persistent agent loops.")

_ALL = [
    PIPELINE_CYCLES,
    PIPELINE_CYCLE_DURATION,
    PIPELINE_STAGE_ITEMS,
    LOOKUPS,
    SSE_SUBSCRIBERS,
    AGENT_QUEUE_DEPTH,
    LOOKUP_QUEUE_DEPTH,
    PERSISTENT_LOOPS,
]


# ---------------------------------------------------------------------------
# Instrumentation helpers — never raise (metrics must not break the pipeline).
# ---------------------------------------------------------------------------
def observe_pipeline_cycle(duration_seconds: float, *, outcome: str) -> None:
    try:
        with _lock:
            PIPELINE_CYCLES.inc(outcome=outcome)
            if outcome == "success" and duration_seconds >= 0:
                PIPELINE_CYCLE_DURATION.observe(duration_seconds)
    except Exception as e:  # pragma: no cover - defensive
        logger.debug("observe_pipeline_cycle failed: %s", e)


def inc_stage(stage: str, amount: int) -> None:
    if not amount:
        return
    try:
        with _lock:
            PIPELINE_STAGE_ITEMS.inc(amount, stage=stage)
    except Exception as e:  # pragma: no cover
        logger.debug("inc_stage failed: %s", e)


def inc_lookup(outcome: str) -> None:
    try:
        with _lock:
            LOOKUPS.inc(outcome=outcome)
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
    try:
        with _lock:
            if sse_subscribers is not None:
                SSE_SUBSCRIBERS.set(sse_subscribers)
            if agent_queue_depth is not None:
                AGENT_QUEUE_DEPTH.set(agent_queue_depth)
            if lookup_queue_depth is not None:
                LOOKUP_QUEUE_DEPTH.set(lookup_queue_depth)
            if persistent_loops is not None:
                PERSISTENT_LOOPS.set(persistent_loops)
            lines: List[str] = []
            for metric in _ALL:
                lines.extend(metric.render())
        return ("\n".join(lines) + "\n").encode("utf-8")
    except Exception as e:  # pragma: no cover
        logger.debug("metrics render failed: %s", e)
        return b"# aethria metrics render error\n"
