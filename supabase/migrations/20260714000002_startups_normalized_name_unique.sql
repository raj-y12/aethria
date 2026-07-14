-- Make tenant/company duplicate protection race-safe and consistent with the
-- case-insensitive local storage backend. Existing duplicates require an
-- operator decision; fail loudly instead of deleting or merging user data.
do $$
begin
  if exists (
    select 1
    from public.startups
    where nullif(btrim(display_name), '') is not null
    group by user_id, lower(btrim(display_name))
    having count(*) > 1
  ) then
    raise exception using message =
      'duplicate normalized startup names exist; resolve them before applying the unique index';
  end if;
end;
$$;

create unique index if not exists startups_user_normalized_display_name_uidx
on public.startups (user_id, lower(btrim(display_name)))
where nullif(btrim(display_name), '') is not null;
