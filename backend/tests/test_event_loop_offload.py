"""
Event-loop responsiveness: pipeline orchestration must not run blocking Supabase
I/O directly on the serving loop. Deliberately slow sync dependencies are
injected at two boundaries — the settings store and engine construction — and a
concurrent heartbeat coroutine must keep ticking while the cycle runs. Fails if
the asyncio.to_thread offloads in pipeline_runner regress.
"""
import asyncio
import time

import pytest

import pipeline_runner

# Runnable standalone (python -m pytest tests/test_event_loop_offload.py) —
# does not depend on CI's `-o asyncio_mode=auto`.
pytestmark = pytest.mark.asyncio

BLOCK_S = 0.5


async def _max_heartbeat_gap(stop: asyncio.Event) -> float:
    """Tick every 10ms until stopped; return the worst observed scheduling gap."""
    worst = 0.0
    last = time.perf_counter()
    while not stop.is_set():
        await asyncio.sleep(0.01)
        now = time.perf_counter()
        worst = max(worst, now - last)
        last = now
    return worst


async def _run_cycle_with_heartbeat(expect_error: type[Exception] | None = None) -> float:
    """Run one pipeline cycle with a live heartbeat; return the worst loop gap."""
    stop = asyncio.Event()
    heartbeat = asyncio.create_task(_max_heartbeat_gap(stop))
    # Let the heartbeat take its first tick before the cycle starts, otherwise a
    # cycle that blocks the loop immediately would run before the heartbeat's
    # baseline is set and the stall would go unobserved.
    await asyncio.sleep(0.05)

    try:
        if expect_error is not None:
            with pytest.raises(expect_error):
                await pipeline_runner._run_one_pipeline_cycle_inner("user_loop_lag_test")
        else:
            await pipeline_runner._run_one_pipeline_cycle_inner("user_loop_lag_test")
    finally:
        stop.set()
    return await heartbeat


def _assert_loop_stayed_free(worst_gap: float, boundary: str) -> None:
    # With the boundary offloaded to a thread the loop stays free; if it runs
    # inline the heartbeat stalls for the full BLOCK_S.
    assert worst_gap < BLOCK_S / 2, (
        f"event loop blocked for {worst_gap:.3f}s during {boundary} — "
        "sync I/O is running on the serving loop instead of asyncio.to_thread"
    )


async def test_slow_sync_settings_store_does_not_block_event_loop(monkeypatch):
    def slow_load_settings(user_id, *, use_cache=True):
        time.sleep(BLOCK_S)  # simulates a stalled Supabase read
        return {"agent_config": {}}  # all stages disabled -> cycle exits after settings

    monkeypatch.setattr(pipeline_runner, "load_settings", slow_load_settings)
    monkeypatch.setattr(pipeline_runner.env_config, "use_supabase_storage", lambda: True)

    worst_gap = await _run_cycle_with_heartbeat()
    _assert_loop_stayed_free(worst_gap, "settings load")


class _EngineBuildReached(RuntimeError):
    """Sentinel proving the cycle got as far as engine construction."""


class _FakeThesis:
    embedding = [0.1]  # non-empty -> skips the embedding backfill

    def as_engine_context(self):
        return object()


async def test_slow_engine_construction_does_not_block_event_loop(monkeypatch):
    """Engine constructors do blocking I/O (DealMemory doc-store read,
    ReviewerEngine settings/policy load, CostController budget state); the cycle
    must offload construction, not just per-call storage access."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.setattr(pipeline_runner.env_config, "use_supabase_storage", lambda: True)
    monkeypatch.setattr(
        pipeline_runner,
        "load_settings",
        lambda user_id, *, use_cache=True: {"agent_config": {"scouts_enabled": True}},
    )
    monkeypatch.setattr(pipeline_runner, "_build_storage_sync", lambda user_id: object())
    monkeypatch.setattr(
        pipeline_runner, "_load_active_thesis_sync", lambda user_id, **kw: _FakeThesis()
    )

    def slow_build_engines(**kwargs):
        time.sleep(BLOCK_S)  # simulates DealMemory/CostController/policy reads stalling
        raise _EngineBuildReached()  # abort the cycle here; construction is the boundary under test

    monkeypatch.setattr(pipeline_runner, "_build_pipeline_engines", slow_build_engines)

    worst_gap = await _run_cycle_with_heartbeat(expect_error=_EngineBuildReached)
    _assert_loop_stayed_free(worst_gap, "engine construction")
