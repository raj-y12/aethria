-- Provider-neutral tenant-scoped JSONB memory document.
create table if not exists public.memory (
    user_id text not null,
    key text not null default 'default',
    data jsonb not null default '{}'::jsonb,
    primary key (user_id, key)
);

create index if not exists memory_user_id_idx
    on public.memory (user_id);
