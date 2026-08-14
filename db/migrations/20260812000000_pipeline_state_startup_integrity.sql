-- Keep transient pipeline state owned by the startup row it describes.
-- Scoring trails are intentionally append-only and are not cascaded.

delete from public.startup_pipeline_state state
where not exists (
  select 1
    from public.startups startup
   where startup.user_id = state.user_id
     and startup.startup_id = state.startup_id
);

alter table public.startups
  add constraint startups_user_startup_id_unique
  unique using index startups_user_startup_id_idx;

alter table public.startup_pipeline_state
  add constraint startup_pipeline_state_startup_fk
  foreign key (user_id, startup_id)
  references public.startups (user_id, startup_id)
  on delete cascade;
