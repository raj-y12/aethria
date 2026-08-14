-- Live policy rows all carry a publication source; make that contract explicit.

alter table public.governed_policy_versions
  alter column publication_source set not null;
