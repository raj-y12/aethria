-- Canonical competition slice: minimal tenant-scoped competitor relationships.
-- Factual claims and evidence remain authoritative in the existing ledger.

create table if not exists public.company_competitors (
  relationship_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  target_company_id uuid not null,
  competitor_company_id uuid not null,
  relationship_type text not null check (relationship_type in ('product_overlap','segment_overlap','geography_overlap','competitor')),
  confidence double precision not null default 0 check (confidence between 0 and 1),
  status text not null default 'probable' check (status in ('verified','probable','conflicting','unknown','stale')),
  source_claim_id uuid,
  valid_from timestamptz,
  valid_to timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, relationship_id),
  unique (user_id, target_company_id, competitor_company_id, relationship_type),
  check (target_company_id <> competitor_company_id),
  foreign key (user_id, target_company_id) references public.companies (user_id, company_id),
  foreign key (user_id, competitor_company_id) references public.companies (user_id, company_id),
  foreign key (user_id, source_claim_id) references public.claims (user_id, claim_id)
);
create index if not exists company_competitors_target_idx on public.company_competitors (user_id, target_company_id);
create index if not exists company_competitors_competitor_idx on public.company_competitors (user_id, competitor_company_id);

alter table public.company_competitors enable row level security;
drop policy if exists company_competitors_service_role_all on public.company_competitors;
create policy company_competitors_service_role_all on public.company_competitors
  for all to service_role using (true) with check (true);
revoke all on table public.company_competitors from anon, authenticated;
grant select, insert, update, delete on table public.company_competitors to service_role;
