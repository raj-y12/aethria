-- Correct the published-policy upgrade boundary so a stale caller cannot
-- replace unrelated tenant settings. The service sends only governed policy
-- pointer fields; this function merges them into the row read under lock.

create or replace function public.upgrade_fund_policy(
  p_user_id text,
  p_expected_policy_id text,
  p_expected_policy_hash text,
  p_new_policy_id text,
  p_new_policy_hash text,
  p_policy_record jsonb,
  p_settings_data jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_current_settings jsonb;
  v_current_policy_id text;
  v_current_policy_hash text;
  v_existing_policy jsonb;
  v_policy_patch jsonb;
  v_next_settings jsonb;
  v_inserted boolean := false;
  v_rows integer := 0;
begin
  if nullif(btrim(p_user_id), '') is null
     or nullif(btrim(p_new_policy_id), '') is null
     or nullif(btrim(p_new_policy_hash), '') is null then
    raise exception 'tenant and new policy identity are required';
  end if;

  if p_policy_record ->> 'id' is distinct from p_new_policy_id
     or p_policy_record ->> 'policy_version_id' is distinct from p_new_policy_id
     or p_policy_record ->> 'policy_hash' is distinct from p_new_policy_hash then
    raise exception 'new policy record identity does not match request';
  end if;

  if pg_catalog.jsonb_typeof(p_settings_data) is distinct from 'object'
     or p_settings_data - 'fund_config' <> '{}'::jsonb
     or pg_catalog.jsonb_typeof(p_settings_data -> 'fund_config')
          is distinct from 'object' then
    raise exception 'settings payload must be a governed fund policy patch';
  end if;

  v_policy_patch := p_settings_data -> 'fund_config';
  if v_policy_patch - array[
       'activePolicyVersionId',
       'publishedPolicyHash',
       'draftPolicyHash',
       'lastPublishedAt'
     ] <> '{}'::jsonb then
    raise exception 'settings patch contains non-governed fields';
  end if;

  if v_policy_patch ->> 'activePolicyVersionId'
       is distinct from p_new_policy_id
     or v_policy_patch ->> 'publishedPolicyHash'
       is distinct from p_new_policy_hash
     or v_policy_patch ->> 'draftPolicyHash'
       is distinct from p_new_policy_hash
     or nullif(v_policy_patch ->> 'lastPublishedAt', '') is null then
    raise exception 'new settings pointers do not match policy identity';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(p_user_id, 0)
  );

  select data
    into v_current_settings
    from public.settings
   where user_id = p_user_id
     and key = p_user_id
   for update;

  if not found then
    raise exception 'tenant settings record not found';
  end if;
  if pg_catalog.jsonb_typeof(v_current_settings) is distinct from 'object'
     or (
       v_current_settings ? 'fund_config'
       and pg_catalog.jsonb_typeof(v_current_settings -> 'fund_config')
         is distinct from 'object'
     ) then
    raise exception 'tenant settings record is malformed';
  end if;

  v_current_policy_id := nullif(
    v_current_settings #>> '{fund_config,activePolicyVersionId}',
    ''
  );
  v_current_policy_hash := nullif(
    v_current_settings #>> '{fund_config,publishedPolicyHash}',
    ''
  );

  if v_current_policy_id is distinct from nullif(p_expected_policy_id, '')
     or v_current_policy_hash is distinct from nullif(p_expected_policy_hash, '') then
    raise exception 'published policy pointer changed during upgrade'
      using errcode = '40001';
  end if;

  insert into public.fund_policy_versions (user_id, id, data)
  values (p_user_id, p_new_policy_id, p_policy_record)
  on conflict (user_id, id) do nothing;
  get diagnostics v_rows = row_count;
  v_inserted := v_rows = 1;

  select data
    into v_existing_policy
    from public.fund_policy_versions
   where user_id = p_user_id
     and id = p_new_policy_id;

  if v_existing_policy is null
     or v_existing_policy is distinct from p_policy_record then
    raise exception 'policy version identity conflicts with existing immutable row';
  end if;

  v_next_settings := pg_catalog.jsonb_set(
    v_current_settings,
    '{fund_config}',
    coalesce(v_current_settings -> 'fund_config', '{}'::jsonb) || v_policy_patch,
    true
  );

  update public.settings
     set data = v_next_settings
   where user_id = p_user_id
     and key = p_user_id;

  if not found then
    raise exception 'tenant settings pointer update failed';
  end if;

  return pg_catalog.jsonb_build_object(
    'status', 'applied',
    'appended', v_inserted,
    'policy_version_id', p_new_policy_id,
    'policy_hash', p_new_policy_hash
  );
end;
$$;

revoke all on function public.upgrade_fund_policy(
  text, text, text, text, text, jsonb, jsonb
) from public, anon, authenticated;

grant execute on function public.upgrade_fund_policy(
  text, text, text, text, text, jsonb, jsonb
) to service_role;
