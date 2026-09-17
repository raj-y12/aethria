-- Semantic evaluation observations (shadow-only). Never read by any
-- authoritative Scout/Reviewer/Partner code path; see backend/semantic_evaluation/.
-- Append-only: rows are never updated, only inserted.

create table if not exists public.semantic_evaluations (
  evaluation_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  pipeline_run_id text,
  workflow_run_id text,
  startup_id text,
  opportunity_id text,
  evaluation_type text not null
    check (evaluation_type in ('evidence_relevance', 'claim_support', 'research_usefulness')),
  evaluation_version text not null,
  criteria_version text not null,
  rollout_mode text not null check (rollout_mode in ('disabled', 'shadow')),
  provider text not null,
  model text,
  provider_model_version text,
  status text not null
    check (status in ('success', 'timeout', 'provider_error', 'budget_skipped', 'disabled')),
  input_digest text not null,
  claim_ids jsonb not null default '[]'::jsonb,
  source_ids jsonb not null default '[]'::jsonb,
  selected_answer text,
  confidence double precision,
  distribution jsonb not null default '[]'::jsonb,
  latency_ms double precision,
  tokens integer,
  estimated_cost_usd double precision,
  error text,
  created_at timestamptz not null default now()
);

create index if not exists semantic_evaluations_user_type_created_idx
  on public.semantic_evaluations (user_id, evaluation_type, created_at desc);

create index if not exists semantic_evaluations_pipeline_run_idx
  on public.semantic_evaluations (pipeline_run_id)
  where pipeline_run_id is not null;

create index if not exists semantic_evaluations_startup_idx
  on public.semantic_evaluations (startup_id)
  where startup_id is not null;
