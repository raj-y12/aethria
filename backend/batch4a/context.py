from contextvars import ContextVar
from typing import Any

from batch4a.repository import Batch4AState

_current_state: ContextVar[Batch4AState | None] = ContextVar("batch4a_state", default=None)


def set_state(state: Batch4AState):
    return _current_state.set(state)


def reset_state(token: Any) -> None:
    _current_state.reset(token)


def get_state() -> Batch4AState | None:
    return _current_state.get()
