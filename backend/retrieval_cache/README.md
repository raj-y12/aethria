# retrieval_cache

Durable retrieval-cache domain: observations about external retrieval, not
canonical knowledge.

## Purpose

Give Scout's research chain (`research/retrieval_grounding.py`) a
tenant-scoped, TTL'd cache so identical queries don't re-hit Exa/Firecrawl.

## Inputs

A retrieval identity (query + category + optional time window/target ids)
and, for the repository, a `user_id` and PostgreSQL pool.

## Outputs

Cached `ProviderSearchResults`-shaped rows, or a cache miss signal.

## Responsibilities

- `cache.py`: query/URL normalisation, category TTL policy, in-process
  per-identity locking (`key_lock`), and the `RetrievalCache` boundary.
- `repository.py`: the durable Postgres-backed `RetrievalCacheRepository`.

## Non-responsibilities

- Does not call any search provider itself — `research/retrieval_grounding.py`
  wires this cache in front of `research.search_providers`.
- Not canonical evidence; a cache entry is an observation about a past
  retrieval, never treated as ground truth.

## Dependencies

`tenant_context`.

## Public API

Import from `retrieval_cache` directly (`from retrieval_cache import
RetrievalCache`).

## Testing

`tests/test_retrieval_cache.py`.
