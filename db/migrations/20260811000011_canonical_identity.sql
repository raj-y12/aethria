-- Provider-neutral canonical identity contract used by IdentityRepository.
create table if not exists public.companies (
  company_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  canonical_name text not null check (length(btrim(canonical_name)) > 0),
  canonical_domain text,
  identity_confidence double precision not null default 0 check (identity_confidence between 0 and 1),
  status text not null default 'active' check (status in ('active','merged','archived')),
  metadata jsonb not null default '{}'::jsonb,
  merged_into_company_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, company_id),
  foreign key (user_id, merged_into_company_id) references public.companies (user_id, company_id)
);
create unique index if not exists companies_canonical_domain_idx on public.companies
  (user_id, canonical_domain) where canonical_domain is not null and status = 'active';
create index if not exists companies_name_search_idx on public.companies (user_id, lower(canonical_name));

create table if not exists public.source_observations (
  observation_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  channel text not null check (channel in ('manual_lookup','autonomous_discovery','inbound','outbound','referral','event','portfolio_intro','import','crm_import','backfill')),
  external_event_key text,
  lookup_id text,
  legacy_startup_id uuid,
  observed_name text not null check (length(btrim(observed_name)) > 0),
  observed_domain text,
  provider_identifiers jsonb not null default '{}'::jsonb,
  source_metadata jsonb not null default '{}'::jsonb,
  resolution_payload jsonb,
  company_id uuid,
  identity_status text not null default 'pending' check (identity_status in ('pending','resolved','ambiguous','deferred','rejected')),
  identity_confidence double precision not null default 0 check (identity_confidence between 0 and 1),
  observed_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  opportunity_id uuid,
  unique (user_id, observation_id),
  foreign key (user_id, company_id) references public.companies (user_id, company_id)
);
create unique index if not exists source_observations_external_event_idx on public.source_observations
  (user_id, channel, external_event_key) where external_event_key is not null;
create index if not exists source_observations_lookup_idx on public.source_observations
  (user_id, lookup_id) where lookup_id is not null;
create index if not exists source_observations_company_idx on public.source_observations
  (user_id, company_id, observed_at desc);

create table if not exists public.company_identifiers (
  identifier_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  company_id uuid not null,
  identifier_type text not null check (identifier_type in ('domain','linkedin','crunchbase','dealroom','yc','registry','external')),
  normalized_value text not null check (length(btrim(normalized_value)) > 0),
  raw_value text not null check (length(btrim(raw_value)) > 0),
  verification_status text not null default 'unverified' check (verification_status in ('unverified','verified','disputed','revoked')),
  confidence double precision not null default 0 check (confidence between 0 and 1),
  is_primary boolean not null default false,
  source_observation_id uuid,
  valid_from timestamptz,
  valid_to timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, identifier_id),
  foreign key (user_id, company_id) references public.companies (user_id, company_id) on delete cascade,
  foreign key (user_id, source_observation_id) references public.source_observations (user_id, observation_id)
);
create unique index if not exists company_identifiers_verified_idx on public.company_identifiers
  (user_id, identifier_type, normalized_value) where verification_status = 'verified';
create index if not exists company_identifiers_company_idx on public.company_identifiers
  (user_id, company_id, is_primary desc);

create table if not exists public.company_aliases (
  alias_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  company_id uuid not null,
  alias text not null check (length(btrim(alias)) > 0),
  normalized_alias text not null check (length(btrim(normalized_alias)) > 0),
  alias_type text not null default 'observed' check (alias_type in ('observed','former_name','product','legal_name','operator')),
  source_observation_id uuid,
  created_at timestamptz not null default now(),
  unique (user_id, alias_id),
  unique (user_id, company_id, normalized_alias, alias_type),
  foreign key (user_id, company_id) references public.companies (user_id, company_id) on delete cascade,
  foreign key (user_id, source_observation_id) references public.source_observations (user_id, observation_id)
);
create index if not exists company_aliases_search_idx on public.company_aliases (user_id, normalized_alias);

create table if not exists public.opportunities (
  opportunity_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  company_id uuid not null,
  context_key text not null default 'primary' check (length(btrim(context_key)) > 0),
  decision_state text not null default 'discovered' check (decision_state in ('discovered','identity_review','active_review','monitor','advance','pass','invested','archived')),
  service_level integer not null default 1 check (service_level between 0 and 5),
  first_observation_id uuid not null,
  latest_observation_id uuid not null,
  legacy_startup_id uuid,
  current_evaluation_id uuid,
  current_recommendation_id uuid,
  current_ruling_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  attention_priority integer not null default 0 check (attention_priority between 0 and 100),
  next_review_at timestamptz,
  lifecycle_reason text,
  unique (user_id, opportunity_id),
  unique (user_id, company_id, context_key),
  foreign key (user_id, company_id) references public.companies (user_id, company_id),
  foreign key (user_id, first_observation_id) references public.source_observations (user_id, observation_id),
  foreign key (user_id, latest_observation_id) references public.source_observations (user_id, observation_id)
);
create index if not exists opportunities_state_idx on public.opportunities (user_id, decision_state, updated_at desc);
create index if not exists opportunities_legacy_projection_idx on public.opportunities (user_id, legacy_startup_id) where legacy_startup_id is not null;

create table if not exists public.identity_resolution_cases (
  identity_case_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  observation_id uuid not null,
  status text not null default 'open' check (status in ('open','resolved','deferred','rejected')),
  reason_code text not null check (length(btrim(reason_code)) > 0),
  candidates jsonb not null default '[]'::jsonb,
  selected_company_id uuid,
  resolution_note text,
  resolved_by text,
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, identity_case_id),
  foreign key (user_id, observation_id) references public.source_observations (user_id, observation_id),
  foreign key (user_id, selected_company_id) references public.companies (user_id, company_id)
);
create unique index if not exists identity_resolution_cases_open_observation_idx on public.identity_resolution_cases
  (user_id, observation_id) where status = 'open';
create index if not exists identity_resolution_cases_open_idx on public.identity_resolution_cases
  (user_id, created_at) where status = 'open';

create or replace function public.touch_identity_updated_at()
returns trigger language plpgsql security invoker set search_path = public as $$
begin new.updated_at = now(); return new; end;
$$;
drop trigger if exists companies_touch_updated_at on public.companies;
create trigger companies_touch_updated_at before update on public.companies for each row execute function public.touch_identity_updated_at();
drop trigger if exists source_observations_touch_updated_at on public.source_observations;
create trigger source_observations_touch_updated_at before update on public.source_observations for each row execute function public.touch_identity_updated_at();
drop trigger if exists company_identifiers_touch_updated_at on public.company_identifiers;
create trigger company_identifiers_touch_updated_at before update on public.company_identifiers for each row execute function public.touch_identity_updated_at();
drop trigger if exists opportunities_touch_updated_at on public.opportunities;
create trigger opportunities_touch_updated_at before update on public.opportunities for each row execute function public.touch_identity_updated_at();
drop trigger if exists identity_resolution_cases_touch_updated_at on public.identity_resolution_cases;
create trigger identity_resolution_cases_touch_updated_at before update on public.identity_resolution_cases for each row execute function public.touch_identity_updated_at();
