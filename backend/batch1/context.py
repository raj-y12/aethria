"""Async-task-local Batch 1 snapshot context."""

from contextvars import ContextVar
from typing import Any

from batch1.repository import Batch1State

_current_state: ContextVar[Batch1State | None] = ContextVar(
    "batch1_state", default=None
)


def set_state(state: Batch1State):
    return _current_state.set(state)


def reset_state(token: Any) -> None:
    _current_state.reset(token)


def get_state() -> Batch1State | None:
    return _current_state.get()
