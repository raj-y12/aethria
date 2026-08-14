-- Safe compatibility repairs for an existing Supabase schema.
-- These are additive and preserve historical rows.

create unique index if not exists fund_thesis_versions_user_id_id_idx
  on public.fund_thesis_versions (user_id, id);

alter table public.security_limits
  add column if not exists lock_owner_token text;

alter table public.evaluation_runs
  add column if not exists judgment_audit jsonb not null default '{}'::jsonb;

do $$
begin
  if not exists (
    select 1
      from pg_constraint
     where conrelid = 'public.fund_thesis'::regclass
       and conname = 'fund_thesis_active_version_tenant_fk'
  ) then
    alter table public.fund_thesis
      add constraint fund_thesis_active_version_tenant_fk
      foreign key (user_id, active_version_id)
      references public.fund_thesis_versions (user_id, id)
      deferrable initially deferred;
  end if;
end
$$;

do $$
begin
  if not exists (
    select 1
      from pg_constraint
     where conrelid = 'public.startups'::regclass
       and conname = 'startups_user_startup_id_unique'
  ) then
    if not exists (
      select 1
        from pg_indexes
       where schemaname = 'public'
         and tablename = 'startups'
         and indexname = 'startups_user_startup_id_idx'
         and indexdef like '%UNIQUE INDEX%'
    ) then
      raise exception 'required startups tenant unique index is missing';
    end if;
    alter table public.startups
      add constraint startups_user_startup_id_unique
      unique using index startups_user_startup_id_idx;
  end if;
end
$$;

do $$
begin
  if not exists (
    select 1
      from pg_constraint
     where conrelid = 'public.startup_pipeline_state'::regclass
       and conname = 'startup_pipeline_state_startup_fk'
  ) then
    if exists (
      select 1
        from public.startup_pipeline_state state
       where not exists (
         select 1
           from public.startups startup
          where startup.user_id = state.user_id
            and startup.startup_id = state.startup_id
       )
    ) then
      alter table public.startup_pipeline_state
        add constraint startup_pipeline_state_startup_fk
        foreign key (user_id, startup_id)
        references public.startups (user_id, startup_id)
        on delete cascade
        not valid;
    else
      alter table public.startup_pipeline_state
        add constraint startup_pipeline_state_startup_fk
        foreign key (user_id, startup_id)
        references public.startups (user_id, startup_id)
        on delete cascade;
    end if;
  end if;
end
$$;
