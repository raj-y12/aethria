-- Admin dashboard audit log.
-- Server-only table: backend writes with the Supabase service role.

create table if not exists public.admin_audit_log (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default timezone('utc', now()),
  event text not null,
  success boolean not null default true,
  actor text not null default 'admin_dashboard',
  client_host text,
  detail jsonb not null default '{}'::jsonb
);

create index if not exists admin_audit_log_created_at_idx
  on public.admin_audit_log (created_at desc);

create index if not exists admin_audit_log_event_created_at_idx
  on public.admin_audit_log (event, created_at desc);

alter table public.admin_audit_log enable row level security;

