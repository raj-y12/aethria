-- Provider-neutral per-user activity boundary.
create table if not exists public.user_state (
    user_id text primary key,
    last_seen_at timestamptz not null default now()
);
