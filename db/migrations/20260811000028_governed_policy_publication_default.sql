-- Match the live canonical policy contract for newly-created draft versions.

alter table public.governed_policy_versions
  alter column publication_source set default 'proposal';
