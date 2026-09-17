"""Semantic evaluation providers. Import a specific provider directly
(`from semantic_evaluation.providers.mock import MockSemanticEvaluationProvider`)
— there is no registry here yet; `service.py` resolves
`SEMANTIC_EVALUATION_PROVIDER` to a provider instance itself, since there is
currently exactly one real choice (`mock`) plus a not-yet-implemented `jev`.
A `research.search_providers`-style registry is worth adding once there are
enough providers to warrant one.
"""
