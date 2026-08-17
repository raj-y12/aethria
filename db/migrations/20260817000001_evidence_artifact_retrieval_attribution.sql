-- Sub-project 4, Phase B: canonical evidence artifacts had no retrieval
-- provider/query attribution at all -- discarded before reaching
-- ingest_artifact even though retrieval_grounding.py already captures it.

alter table public.evidence_artifacts
  add column if not exists retrieval_provider text,
  add column if not exists retrieval_query text;
