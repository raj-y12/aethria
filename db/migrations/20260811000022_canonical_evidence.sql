-- Provider-neutral canonical evidence and claim ledger.

create table if not exists public.evidence_artifacts (
  artifact_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  company_id uuid,
  opportunity_id uuid,
  source_observation_id uuid,
  artifact_type text not null check (artifact_type in ('web_page','database_response','pitch_deck','email','interview_note','operator_context','news','registry','crm','other')),
  source_uri text,
  title text,
  content_hash text not null check (length(content_hash) >= 8),
  storage_reference text,
  trust_class text not null check (trust_class in ('official','regulatory','independent','founder','operator','model','unknown')),
  access_class text not null default 'public' check (access_class in ('public','tenant_confidential','restricted')),
  retention_policy text not null default 'standard',
  parser_version text,
  untrusted_input boolean not null default true,
  prompt_injection_detected boolean not null default false,
  published_at timestamptz,
  effective_at timestamptz,
  retrieved_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique (user_id, artifact_id),
  unique (user_id, content_hash, access_class),
  foreign key (user_id, company_id) references public.companies (user_id, company_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id),
  foreign key (user_id, source_observation_id) references public.source_observations (user_id, observation_id)
);
create index if not exists evidence_artifacts_opportunity_idx
  on public.evidence_artifacts (user_id, opportunity_id, retrieved_at desc);

create table if not exists public.evidence_items (
  evidence_item_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  artifact_id uuid not null,
  item_type text not null,
  normalized_value jsonb not null default '{}'::jsonb,
  display_excerpt text not null check (length(display_excerpt) between 1 and 2000),
  source_locator text,
  effective_at timestamptz,
  expires_at timestamptz,
  verification_state text not null default 'unverified' check (verification_state in ('unverified','verified','disputed','revoked')),
  source_quality double precision not null default 0 check (source_quality between 0 and 1),
  extraction_confidence double precision not null default 0 check (extraction_confidence between 0 and 1),
  extractor_version text,
  operator_attribution text,
  created_at timestamptz not null default now(),
  unique (user_id, evidence_item_id),
  foreign key (user_id, artifact_id) references public.evidence_artifacts (user_id, artifact_id) on delete cascade
);
create index if not exists evidence_items_artifact_idx on public.evidence_items (user_id, artifact_id);

create table if not exists public.claims (
  claim_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  company_id uuid not null,
  opportunity_id uuid,
  claim_type text not null,
  normalized_value jsonb not null default '{}'::jsonb,
  unit text,
  period text,
  display_text text not null check (length(display_text) between 1 and 2000),
  assertion_class text not null check (assertion_class in ('externally_verified','founder_asserted','operator_asserted','model_inferred','conflicted','unverified')),
  status text not null default 'current' check (status in ('current','stale','contradicted','superseded','withdrawn')),
  confidence double precision not null default 0 check (confidence between 0 and 1),
  material boolean not null default true,
  operator_attribution text,
  supersedes_claim_id uuid,
  created_by text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, claim_id),
  foreign key (user_id, company_id) references public.companies (user_id, company_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id),
  foreign key (user_id, supersedes_claim_id) references public.claims (user_id, claim_id)
);
create index if not exists claims_opportunity_current_idx
  on public.claims (user_id, opportunity_id, claim_type) where status = 'current';

create table if not exists public.claim_evidence_links (
  link_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  claim_id uuid not null,
  evidence_item_id uuid not null,
  relationship text not null check (relationship in ('supports','contradicts','contextualizes','partially_establishes')),
  support_strength double precision not null default 0 check (support_strength between 0 and 1),
  rationale text not null default '',
  created_at timestamptz not null default now(),
  unique (user_id, link_id),
  unique (user_id, claim_id, evidence_item_id, relationship),
  foreign key (user_id, claim_id) references public.claims (user_id, claim_id) on delete cascade,
  foreign key (user_id, evidence_item_id) references public.evidence_items (user_id, evidence_item_id)
);

create table if not exists public.evidence_plans (
  evidence_plan_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  opportunity_id uuid not null,
  trigger_type text not null,
  status text not null default 'planned' check (status in ('planned','in_progress','completed','cancelled','failed')),
  missing_evidence jsonb not null default '[]'::jsonb,
  search_questions jsonb not null default '[]'::jsonb,
  max_artifacts integer not null default 5 check (max_artifacts between 1 and 20),
  budget_usd numeric(12,6) not null default 0 check (budget_usd >= 0),
  plan_hash text not null,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  unique (user_id, evidence_plan_id),
  unique (user_id, opportunity_id, plan_hash),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id)
);

create table if not exists public.claim_corrections (
  correction_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  claim_id uuid not null,
  actor_id text not null,
  action text not null check (action in ('withdraw','contradict','mark_stale','supersede')),
  rationale text not null,
  created_at timestamptz not null default now(),
  unique (user_id, correction_id),
  foreign key (user_id, claim_id) references public.claims (user_id, claim_id)
);
