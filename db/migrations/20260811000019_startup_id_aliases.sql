-- Additive, tenant-scoped identity aliases for legacy startup identifiers.
-- Runtime resolution uses approved rows only; portfolio_startups remains intact.

create table if not exists public.startup_id_aliases (
  user_id text not null,
  legacy_startup_id text not null check (length(btrim(legacy_startup_id)) > 0),
  canonical_startup_id text not null check (length(btrim(canonical_startup_id)) > 0),
  source text not null check (length(btrim(source)) > 0),
  source_reference text,
  source_observation_id uuid,
  verification_state text not null default 'candidate'
    check (verification_state in ('candidate','approved','revoked','rejected')),
  verification_evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  primary key (user_id, legacy_startup_id),
  foreign key (user_id, canonical_startup_id)
    references public.startups (user_id, startup_id),
  foreign key (user_id, source_observation_id)
    references public.source_observations (user_id, observation_id)
);

create index if not exists startup_id_aliases_canonical_idx
  on public.startup_id_aliases (user_id, canonical_startup_id);
create index if not exists startup_id_aliases_approved_idx
  on public.startup_id_aliases (user_id, legacy_startup_id)
  where verification_state = 'approved';
