"""Explicit per-task Batch 2 snapshot context."""

from contextvars import ContextVar
from typing import Any

from batch2.repository import Batch2State

_current_state: ContextVar[Batch2State | None] = ContextVar("batch2_state", default=None)


def set_state(state: Batch2State):
    return _current_state.set(state)


def reset_state(token: Any) -> None:
    _current_state.reset(token)


def get_state() -> Batch2State | None:
    return _current_state.get()
