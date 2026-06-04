"""Best-effort teardown of per-cycle LLM clients and thread pools.

Pipeline engines are rebuilt on every cycle (see ``pipeline_runner``). Each
Scout, Reviewer, the partner decision engine, and the meta mutator open an
``OpenAI`` client (which holds an ``httpx`` connection pool / sockets) and a
``ThreadPoolExecutor`` (worker threads). Leaving these to garbage collection /
``__del__`` leaks file descriptors and worker threads across cycles and is a
primary cause of slow RSS growth -> OOM on small instances.

Closing them explicitly at the end of each cycle keeps memory flat. Every
helper here is defensive: cleanup must never raise into the pipeline.
"""
import logging
from typing import Any

logger = logging.getLogger("resource_cleanup")


def close_openai_client(client: Any) -> None:
    """Close an OpenAI/httpx client if it exposes a close() method."""
    if client is None:
        return
    try:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("OpenAI client close failed: %s", exc)


def shutdown_executor(executor: Any) -> None:
    """Shut down a ThreadPoolExecutor without blocking on in-flight work.

    Cycle work is complete by the time we tear down, so ``wait=False`` lets the
    idle worker threads exit promptly. ``cancel_futures`` is best-effort (3.9+).
    """
    if executor is None:
        return
    try:
        executor.shutdown(wait=False, cancel_futures=True)
    except TypeError:
        # Python < 3.9 has no cancel_futures kwarg.
        try:
            executor.shutdown(wait=False)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Executor shutdown failed: %s", exc)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Executor shutdown failed: %s", exc)
