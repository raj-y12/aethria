-- Aethria: startups table (Clerk user_id = text, RLS via auth.jwt() ->> 'sub')
-- Run this in Supabase Dashboard → SQL Editor, or: supabase db push

create table if not exists public.startups (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  startup_id text not null,
  scout_info jsonb not null,
  review_info jsonb,
  partner_info jsonb,
  financials jsonb not null,
  version integer not null default 1,
  human_resolution jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create unique index if not exists startups_user_startup_id_idx
  on public.startups (user_id, startup_id);

create index if not exists startups_user_id_idx on public.startups (user_id);
create index if not exists startups_scout_info_gin_idx on public.startups using gin (scout_info);
create index if not exists startups_review_info_gin_idx on public.startups using gin (review_info);
create index if not exists startups_partner_info_gin_idx on public.startups using gin (partner_info);

alter table public.startups enable row level security;

drop policy if exists "Users manage own startups" on public.startups;
create policy "Users manage own startups"
  on public.startups for all
  using (auth.jwt() ->> 'sub' = user_id)
  with check (auth.jwt() ->> 'sub' = user_id);

drop policy if exists "Service role full access startups" on public.startups;
create policy "Service role full access startups"
  on public.startups for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');
