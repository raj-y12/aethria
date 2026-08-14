-- Keep Supabase's platform RLS event trigger helper out of the public RPC surface.

do $$
begin
  if to_regprocedure('public.rls_auto_enable()') is not null then
    execute 'alter function public.rls_auto_enable() set search_path = pg_catalog';
    execute 'revoke all on function public.rls_auto_enable() from public, anon, authenticated';
  end if;
end;
$$;
