-- Append-only tenant scoring policy versions.
create table if not exists public.fund_policy_versions (
  user_id text not null,
  id text not null,
  data jsonb not null,
  created_at timestamptz not null default timezone('utc', now()),
  primary key (user_id, id)
);

alter table public.fund_policy_versions enable row level security;

drop policy if exists "Users read own fund policy versions" on public.fund_policy_versions;
create policy "Users read own fund policy versions"
on public.fund_policy_versions
for select
using (auth.uid()::text = user_id);

drop policy if exists "Service role full access fund policy versions" on public.fund_policy_versions;
create policy "Service role full access fund policy versions"
on public.fund_policy_versions
for all
using (auth.role() = 'service_role')
with check (auth.role() = 'service_role');
