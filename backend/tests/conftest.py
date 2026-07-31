"""Test-wide safety net: never let the suite reach a live retrieval provider.

`api.py` calls a bare `load_dotenv()`, which walks parent directories and finds
the developer's real `.env` — including inside a git worktree. Any test that
imports `api` therefore inherits real provider API keys, and retrieval tests
start making live HTTP calls: slow, flaky, credit-burning, and dependent on
whatever the live web returns today.

This bit until now only because the older tests monkeypatch `tavily_search`. The
Firecrawl→Tavily chain calls Firecrawl *first*, and nothing patched that, so a
configured Firecrawl key turned every unpatched retrieval test into a live call.

Blanking the keys by default makes the unpatched path fail closed (the providers
return `disabled`/`missing_api_key`) instead of silently going to the network. A
test that genuinely wants a key sets it explicitly with `monkeypatch.setenv`,
which still wins.
"""
from __future__ import annotations

import pytest

_PROVIDER_KEYS = ("FIRECRAWL_API_KEY", "TAVILY_API_KEY", "OPENAI_API_KEY")


@pytest.fixture(autouse=True)
def _no_live_provider_calls(monkeypatch):
    for name in _PROVIDER_KEYS:
        monkeypatch.delenv(name, raising=False)
    yield
