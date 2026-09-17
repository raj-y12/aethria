"""Scout-owned tools: not reusable outside Scout's own discovery/grounding flow.

- discovery_queries: builds Scout's discovery search queries.
- financials_grounding: deterministic source-citation gate for financial
  values Scout proposes (`ground_financials`) — kept out of the LLM prompt
  path since it's a pass/fail grounding check, not a judgment call.
"""
from __future__ import annotations

from scout.tools.discovery_queries import build_discovery_queries, build_discovery_recency_query, thesis_terms
from scout.tools.financials_grounding import ground_financials

__all__ = [
    "build_discovery_queries",
    "build_discovery_recency_query",
    "ground_financials",
    "thesis_terms",
]

