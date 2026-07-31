"""The result type every retrieval provider returns.

This lived in `tavily_client.py` for as long as Tavily was the only provider.
It was already provider-neutral by the time Firecrawl and Exa adopted it — the
import path was simply lying about ownership, and deleting Tavily forced the
move that DEC-004 recorded as debt.

`ProviderSearchResults` is a `list` subclass on purpose: callers that only want
rows can treat it as one and stay unaware of provider mechanics, while the
`.diagnostics` payload keeps an outage distinguishable from a genuinely empty
result set. That distinction is what stops a dark retrieval failure from looking
like "nothing matched".
"""
from __future__ import annotations

from typing import Any, Dict, List


class ProviderSearchResults(list):
    """List-compatible provider results with bounded, structured diagnostics."""

    def __init__(self, results: List[Dict[str, str]], diagnostics: Dict[str, Any]):
        super().__init__(results)
        self.diagnostics = dict(diagnostics)
