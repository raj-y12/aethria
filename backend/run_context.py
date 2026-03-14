"""
Run context: current user_id for this request or agent run.
Used by settings_loader and supabase_doc_store so all storage is scoped by user.
"""
from contextvars import ContextVar
from typing import Optional

_current_run_user_id: ContextVar[Optional[str]] = ContextVar("run_user_id", default=None)


def set_run_user_id(user_id: Optional[str]) -> None:
    """Set the user_id for this run. Call at start of run_system or when handling an API request."""
    _current_run_user_id.set(user_id)


def get_run_user_id() -> Optional[str]:
    """Return the current run's user_id if set."""
    return _current_run_user_id.get()
