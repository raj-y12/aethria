"""Test-wide safety net: never let the suite reach a live retrieval provider.

`api.py` calls a bare `load_dotenv()`, which walks parent directories and finds
the developer's real `.env` — including inside a git worktree. Any test that
imports `api` therefore inherits real provider API keys, and retrieval tests
start making live HTTP calls: slow, flaky, credit-burning, and dependent on
whatever the live web returns today.

This bit once because the older tests monkeypatched only the provider that
happened to be first in the chain. Adding a tier ahead of it left that tier
unpatched, so a configured key turned every unpatched retrieval test into a live
call. Blanking every provider key removes the class of bug rather than the
instance — a new provider is covered the day it is added.

Blanking the keys by default makes the unpatched path fail closed (the providers
return `disabled`/`missing_api_key`) instead of silently going to the network. A
test that genuinely wants a key sets it explicitly with `monkeypatch.setenv`,
which still wins.

Blanking keys is not enough on its own. The DuckDuckGo fallback in
`retrieval_grounding` needs **no** key, so it is exactly the tier that key
blanking cannot reach: with every keyed provider disabled, an unpatched
retrieval test falls all the way through and makes a real DDG request. That costs
two 8s endpoint timeouts — 16s per test — whenever DDG happens to be rate-limiting
the runner, which is why a handful of tests could swing the whole suite from ~12s
to ~60s with no code change. `RETRIEVAL_FALLBACK_ENABLED=0` closes that last
hole; a test wanting the fallback re-enables it explicitly.
"""
from __future__ import annotations

import pytest

_PROVIDER_KEYS = ("EXA_API_KEY", "FIRECRAWL_API_KEY", "OPENAI_API_KEY")


@pytest.fixture(autouse=True)
def _no_live_provider_calls(monkeypatch):
    for name in _PROVIDER_KEYS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RETRIEVAL_FALLBACK_ENABLED", "0")
    yield
