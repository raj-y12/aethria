-- Provider-neutral canonical people projection used by founder admission.
create table if not exists public.people (
  person_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  canonical_name text not null check (length(btrim(canonical_name)) > 0),
  normalized_name text not null,
  status text not null default 'active' check (status in ('active','merged','archived')),
  identity_confidence double precision not null default 0 check (identity_confidence between 0 and 1),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, person_id)
);
create index if not exists people_name_idx on public.people (user_id, normalized_name);

create table if not exists public.person_identifiers (
  identifier_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  person_id uuid not null,
  identifier_type text not null check (identifier_type in ('linkedin','github','x','personal_website','other')),
  normalized_value text not null,
  raw_value text not null,
  verification_status text not null default 'unverified' check (verification_status in ('unverified','verified','disputed','revoked')),
  confidence double precision not null default 0 check (confidence between 0 and 1),
  is_primary boolean not null default false,
  valid_from timestamptz,
  valid_to timestamptz,
  source_observation_id uuid,
  created_at timestamptz not null default now(),
  unique (user_id, identifier_id),
  foreign key (user_id, person_id) references public.people (user_id, person_id),
  foreign key (user_id, source_observation_id) references public.source_observations (user_id, observation_id)
);
create unique index if not exists person_identifiers_verified_idx on public.person_identifiers (user_id, identifier_type, normalized_value) where verification_status = 'verified';
create index if not exists person_identifiers_person_idx on public.person_identifiers (user_id, person_id);

create table if not exists public.company_people (
  relationship_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  company_id uuid not null,
  person_id uuid not null,
  relationship_type text not null check (relationship_type in ('founder','cofounder','executive','current_role','prior_role')),
  role text,
  is_current boolean not null default true,
  valid_from timestamptz,
  valid_to timestamptz,
  source_claim_id uuid,
  created_at timestamptz not null default now(),
  unique (user_id, relationship_id),
  foreign key (user_id, company_id) references public.companies (user_id, company_id),
  foreign key (user_id, person_id) references public.people (user_id, person_id),
  foreign key (user_id, source_claim_id) references public.claims (user_id, claim_id)
);
create unique index if not exists company_people_temporal_identity_idx on public.company_people (user_id, company_id, person_id, relationship_type, coalesce(role, ''), coalesce(valid_from, '-infinity'::timestamptz));
create index if not exists company_people_company_idx on public.company_people (user_id, company_id);
create index if not exists company_people_person_idx on public.company_people (user_id, person_id);

create table if not exists public.person_history (
  history_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  person_id uuid not null,
  company_id uuid,
  history_type text not null check (history_type in ('founded_company','worked_at_company','executive_role','education','prior_startup','prior_exit','domain_experience','public_interview')),
  organization_name text not null,
  role text,
  is_current boolean not null default false,
  valid_from timestamptz,
  valid_to timestamptz,
  state text not null default 'unknown' check (state in ('verified','probable','conflicting','unknown')),
  source_claim_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (user_id, history_id),
  foreign key (user_id, person_id) references public.people (user_id, person_id),
  foreign key (user_id, company_id) references public.companies (user_id, company_id),
  foreign key (user_id, source_claim_id) references public.claims (user_id, claim_id)
);
create index if not exists person_history_person_idx on public.person_history (user_id, person_id, valid_from);
