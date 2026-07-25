-- Canonical portfolio positions are created only by an explicit INVEST ruling.
create table if not exists public.canonical_portfolio_positions (
  position_id uuid primary key default gen_random_uuid(),
  user_id text not null,
  opportunity_id uuid not null,
  company_id uuid not null,
  ruling_id uuid not null,
  status text not null default 'active' check (status in ('active','exited','written_off')),
  entry_rationale text not null,
  investor_confidence double precision not null check (investor_confidence between 0 and 1),
  entered_at timestamptz not null default now(),
  exited_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  unique (user_id, position_id),
  unique (user_id, opportunity_id),
  foreign key (user_id, opportunity_id) references public.opportunities (user_id, opportunity_id),
  foreign key (user_id, company_id) references public.companies (user_id, company_id),
  foreign key (user_id, ruling_id) references public.human_rulings (user_id, ruling_id)
);

create index if not exists canonical_portfolio_positions_tenant_status_idx
  on public.canonical_portfolio_positions (user_id, status, entered_at desc);

alter table public.canonical_portfolio_positions enable row level security;
drop policy if exists canonical_portfolio_positions_service_role_all on public.canonical_portfolio_positions;
create policy canonical_portfolio_positions_service_role_all
  on public.canonical_portfolio_positions for all to service_role
  using (true) with check (true);
