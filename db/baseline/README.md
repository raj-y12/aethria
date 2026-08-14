# Portable PostgreSQL baseline

This directory will contain the one-time, provider-neutral schema snapshot for
the post-Supabase application. It must be generated from the verified live
schema and reviewed before the first Cloud SQL cutover; it is not a copy of the
historical Supabase migration chain.

The baseline must contain application tables, constraints, indexes, triggers,
and `pgcrypto`, but must not contain Supabase `auth` objects, PostgREST roles,
Supabase grants, or `supabase_migrations`.
