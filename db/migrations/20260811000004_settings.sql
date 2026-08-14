-- Portable tenant-scoped settings document store.
create table if not exists public.settings (
    user_id text not null,
    key text not null,
    data jsonb not null default '{}'::jsonb,
    primary key (user_id, key)
);

create index if not exists settings_user_id_idx
    on public.settings (user_id);
