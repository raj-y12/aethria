from contextvars import ContextVar
from typing import Any

from batch3.repository import Batch3State

_current_state: ContextVar[Batch3State | None] = ContextVar("batch3_state", default=None)


def set_state(state: Batch3State):
    return _current_state.set(state)


def reset_state(token: Any) -> None:
    _current_state.reset(token)


def get_state() -> Batch3State | None:
    return _current_state.get()
