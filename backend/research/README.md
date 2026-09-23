# research

The shared retrieval chain and evidence-quality filters (ARCHITECTURE.md's
"web retrieval chain": Exa → Firecrawl → DuckDuckGo), independent of any one
agent's internals.

## Purpose

Give Scout (and the identity resolvers) a provider-neutral way to search and
verify sources, so agent code never talks to a provider SDK or parses a raw
provider payload directly.

## Inputs

A query, category, and optional filters (domain, date, recency window).

## Outputs

`ProviderSearchResults` — the shared, Aethria-native domain shape every
provider response is normalised into before anything downstream sees it.

## Responsibilities

- `exa_client.py` / `firecrawl_client.py`: provider SDK/HTTP wrappers.
- `search_providers.py`: provider selection/chaining (`ChainedSearchProvider`,
  `get_provider`) — the abstraction Scout and the resolvers call instead of a
  provider SDK.
- `search_results.py`: the shared `ProviderSearchResults` shape.
- `retrieval_grounding.py`: the cache-aware retrieval entrypoint
  (`retrieve_source_pack`), wiring providers to `retrieval_cache` and excluding
  scraped HTTP error pages before sources reach evidence consumers.
- `reference_validation.py` / `reference_verify.py` / `source_corroboration.py`:
  source quality — URL/domain validation, reachability probing, anchor and
  corroboration checks. Consumed broadly (scout, identity, resolver) since
  evidence quality isn't any one agent's private concern.
- `recency.py`: shared recency-window policy for prompts and queries.

## Non-responsibilities

- `utils.openai_client` and `utils.retry` are deliberately **not** part of
  this package: `openai_client` is a generic model-client factory used across
  scout/reviewer/partner/meta/fund_thesis, and `retry` is a generic backoff
  helper — neither is research-specific in concept.
- Does not decide what to do with a source once verified (that's `context/`
  and the agents).

## Dependencies

`metrics`, `security.prompt_safety`, `retrieval_cache`, stdlib `urllib`/`ssl`
+ `certifi` for direct HTTP calls.

## Public API

Import from `research` directly (`from research import provider_search`).
See `research/__init__.py` for the full re-export list.

## Testing

`tests/test_exa_provider.py`, `tests/test_firecrawl_provider.py`,
`tests/test_search_providers.py`, `tests/test_retrieval_grounding.py`,
`tests/test_retrieval_concurrency.py`, `tests/test_reference_verify.py`,
`tests/test_source_corroboration.py`, `tests/test_megacap_detection.py`.
