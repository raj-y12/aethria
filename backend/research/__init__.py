"""Shared research capability: the retrieval chain and evidence-quality
filters Scout (and identity/resolver) consume, kept independent of any one
agent's internals (ARCHITECTURE.md's "web retrieval chain": Exa -> Firecrawl
-> DuckDuckGo).

External code should import from `research` directly
(`from research import provider_search`); the submodule split below is an
internal detail.

- exa_client / firecrawl_client: provider SDK/HTTP wrappers, normalised to
  `ProviderSearchResults` at the boundary — downstream code never sees raw
  provider payloads.
- search_providers: the provider-selection/chaining abstraction
  (`ChainedSearchProvider`, `get_provider`) Scout and the resolvers call
  instead of talking to a provider SDK directly.
- search_results: the shared `ProviderSearchResults` domain shape.
- retrieval_grounding: the durable-cache-aware retrieval entrypoint
  (`retrieve_source_pack`) that wires providers to `retrieval_cache`.
- reference_validation / reference_verify / source_corroboration: source
  quality — URL/domain validation, reachability probing, anchor/corroboration
  checks — consumed broadly (scout, identity, resolver) since evidence
  quality is not any one agent's private concern.
- recency: shared recency-window policy for prompts and queries.

`utils.openai_client` and `utils.retry` are deliberately not part of this
package: `openai_client` is a generic model-client factory used across
scout/reviewer/partner/meta/fund_thesis (not research-specific), and `retry`
is a generic backoff helper.
"""
from __future__ import annotations

from research.exa_client import exa_search, is_company_domain, query_intent, semantic_query
from research.firecrawl_client import firecrawl_scrape, firecrawl_search
from research.recency import (
    coarse_time_range,
    memo_recency_note,
    recency_query,
    recency_window_days,
    reviewer_recency_directive,
    scout_recency_directive,
)
from research.reference_validation import (
    is_generic_reference,
    is_megacap_company,
    validate_references_not_only_incumbent_domains,
)
from research.reference_verify import (
    extract_http_urls,
    filter_references_anchor_conflicts,
    filter_references_by_company_relevance,
    filter_references_by_url_probe,
    filter_references_to_allowlist,
    finalize_scout_references,
    hostname_from_user_hint,
    is_parallel_same_slug_different_registrable,
    normalize_url_for_match,
    reference_has_anchor_conflict,
    registrable_domain,
)
from research.retrieval_grounding import (
    configure_retrieval_cache,
    log_pre_filter_cited_urls,
    render_sources_for_prompt,
    retrieve_source_pack,
    retrieve_source_pack_merged,
)
from research.search_providers import (
    SEARCH_CATEGORIES,
    ChainedSearchProvider,
    FirecrawlSearchProvider,
    extract_pages,
    get_provider,
    normalize_category,
    provider_name,
    provider_search,
    register_provider,
    reset_providers,
    search_source_pack,
)
from research.search_results import ProviderSearchResults
from research.source_corroboration import (
    TRUSTED_CORROBORATION_DOMAINS,
    filter_sources_to_anchor,
    host_of,
    is_anchor_host,
    keep_source_for_anchor,
    source_mentions_company,
)

__all__ = [
    "ChainedSearchProvider",
    "FirecrawlSearchProvider",
    "ProviderSearchResults",
    "SEARCH_CATEGORIES",
    "TRUSTED_CORROBORATION_DOMAINS",
    "coarse_time_range",
    "configure_retrieval_cache",
    "exa_search",
    "extract_http_urls",
    "extract_pages",
    "filter_references_anchor_conflicts",
    "filter_references_by_company_relevance",
    "filter_references_by_url_probe",
    "filter_references_to_allowlist",
    "filter_sources_to_anchor",
    "finalize_scout_references",
    "firecrawl_scrape",
    "firecrawl_search",
    "get_provider",
    "host_of",
    "hostname_from_user_hint",
    "is_anchor_host",
    "is_company_domain",
    "is_generic_reference",
    "is_megacap_company",
    "is_parallel_same_slug_different_registrable",
    "keep_source_for_anchor",
    "log_pre_filter_cited_urls",
    "memo_recency_note",
    "normalize_category",
    "normalize_url_for_match",
    "provider_name",
    "provider_search",
    "query_intent",
    "recency_query",
    "recency_window_days",
    "reference_has_anchor_conflict",
    "register_provider",
    "registrable_domain",
    "render_sources_for_prompt",
    "reset_providers",
    "retrieve_source_pack",
    "retrieve_source_pack_merged",
    "reviewer_recency_directive",
    "scout_recency_directive",
    "search_source_pack",
    "semantic_query",
    "source_mentions_company",
    "validate_references_not_only_incumbent_domains",
]
