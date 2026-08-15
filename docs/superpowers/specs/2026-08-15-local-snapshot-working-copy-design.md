# Local Snapshot Working-Copy Design

## Goal

Keep one immutable golden copy of the local production snapshot and provide a
separate mutable PostgreSQL working copy for local migrations and testing.

## Design

The existing custom-format dump outside the repository is the golden source:

`/Users/rajyendamuri/aethria-backups/aethria_prod_snapshot_20260814.dump`

The Docker volume used by `run.py` becomes the working snapshot volume. It is
initialized from the golden dump and may be changed by local testing. The
golden dump is never mounted by the application and is never changed by
startup.

`run.py` continues to use the working snapshot database at
`127.0.0.1:15432/aethria_prod_snapshot`. Normal startup verifies that the
working database is reachable and has the expected database identity, but does
not compare mutable row counts against the golden manifest. The strict
manifest comparison runs after a reset, while the working copy is known to
have been restored from the golden source.

An explicit reset workflow stops the working database, recreates only the
working volume, restores the golden dump, runs the strict manifest check, and
then leaves the working database ready for `run.py`. Reset is intentionally
destructive to the working copy and never targets the golden backup.

A successful local migration is promoted as reviewed SQL in
`db/migrations/` through the normal deployment process. Local database files
are never copied directly into Supabase or another production database.

## Safety boundaries

- The golden backup remains outside the repository and is never overwritten.
- The working volume has a distinct name from the previous snapshot volume.
- Reset requires an explicit command and targets only the named working volume.
- Normal startup does not reject legitimate working-copy changes.
- A missing golden backup or failed restore stops before replacing the working
  volume.

## Verification

- Unit tests cover working-volume selection, reset command construction, and
  mutable snapshot startup behavior.
- The reset workflow verifies the restored working database against the golden
  manifest.
- A live `run.py` startup confirms Colima, PostgreSQL, backend, and both
  frontends can start from the working copy.
