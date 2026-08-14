# Portable PostgreSQL migrations

Future schema changes for direct PostgreSQL persistence belong here. Files use
the `YYYYMMDDHHMMSS_name.sql` naming convention and are applied by
`backend/db/migration_runner.py`.

The runner records applied files in `app_migrations.schema_migrations` and
applies each migration and its ledger entry in one transaction. Historical
files under `supabase/migrations/` are not edited or re-applied by this system.

When `migrate_postgres.py --supabase-overlays` detects an existing Supabase
`supabase_migrations` ledger but no application ledger, it adopts only the
verified legacy-equivalent portable versions. Missing additive migrations are
then applied normally. Adoption is guarded by table and tenant-identity
preflight checks and refuses to proceed on unexpected schema drift.
