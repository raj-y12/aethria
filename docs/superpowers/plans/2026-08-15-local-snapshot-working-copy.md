# Local Snapshot Working-Copy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate the immutable local production snapshot backup from the mutable PostgreSQL copy used by `run.py` for local testing.

**Architecture:** Keep the existing custom-format dump as the golden source and use a new external Docker volume for the working copy. Add an explicit reset script that recreates only the working volume from the golden dump and verifies it against the existing manifest; normal `run.py` startup uses the working copy without treating its intentional drift as corruption.

**Tech Stack:** Python 3.12+, FastAPI/Uvicorn launcher, Docker Compose, PostgreSQL 16, `pg_restore`, pytest.

**Spec:** `docs/superpowers/specs/2026-08-15-local-snapshot-working-copy-design.md`

## Global Constraints

- Never modify or delete the golden backup at `/Users/rajyendamuri/aethria-backups/aethria_prod_snapshot_20260814.dump`.
- Reset may delete only the explicitly named working Docker volume `aethria-prod-working-data`.
- Do not bypass the existing strict manifest verifier during a reset.
- Normal working-copy startup must not compare mutable row counts to the golden manifest.
- Do not copy local database files directly into Supabase; promote migrations as reviewed SQL files.
- Preserve unrelated existing worktree changes and do not commit generated database output.

---

### Task 1: Add failing tests for the working-copy contract

**Files:**
- Modify: `backend/tests/test_root_process_supervision.py`
- Test: `backend/tests/test_local_snapshot_working_copy.py`

- [x] **Step 1: Write tests for the new working volume and normal startup policy.** Assert that the snapshot compose file names `aethria-prod-working-data`, that the golden manifest verifier is not selected during ordinary working-copy startup, and that reset requires a golden backup path.

- [x] **Step 2: Run the focused tests and confirm they fail for the missing helpers/configuration.**

```bash
python3 -m pytest backend/tests/test_root_process_supervision.py backend/tests/test_local_snapshot_working_copy.py -q -o asyncio_mode=auto
```

- [x] **Step 3: Keep the failure limited to the new working-copy behavior, fixing only test setup errors if necessary.**

### Task 2: Switch Compose to a dedicated working volume

**Files:**
- Modify: `docker-compose.snapshot.yml`
- Modify: `run.py`
- Modify: `docs/operations/docker.md`

- [x] **Step 1: Rename the snapshot volume declaration and Compose project labeling to the working-copy names.** Keep the database name `aethria_prod_snapshot` and port `15432` stable so the existing `.env` URL remains valid.

- [x] **Step 2: Add a `WORKING_SNAPSHOT_VOLUME` constant and helper in `run.py` that returns `aethria-prod-working-data`.** Use the helper in the compose lifecycle and tests.

- [x] **Step 3: Change ordinary snapshot startup to report that it is using the mutable working copy and skip strict manifest verification.** Continue to wait for PostgreSQL readiness before starting the backend.

- [x] **Step 4: Run the focused root launcher tests.**

### Task 3: Implement the explicit reset workflow

**Files:**
- Create: `backend/scripts/reset_local_snapshot.py`
- Modify: `run.py`
- Test: `backend/tests/test_local_snapshot_working_copy.py`

- [x] **Step 1: Write a failing test for reset command construction.** The command must stop/remove only `aethria-prod-working-data`, restore the configured golden dump into a fresh PostgreSQL working database, and invoke `backend/scripts/verify_local_snapshot.py` before reporting success.

- [x] **Step 2: Implement the reset script with explicit arguments.** Use `--backup-path`, `--database-url`, and `--volume-name`; validate that the backup file exists, stop the working Compose service, remove only the named working volume, recreate the Compose service, copy the dump into the running container, run `pg_restore --no-owner --no-privileges`, and run the strict verifier. On any failure before verification, stop the container and return nonzero without touching the golden file.

- [x] **Step 3: Add `run.py --reset-local-snapshot` as a thin subprocess entry point.** It should start the Docker/Colima daemon if needed, invoke the reset script with the configured backup path and working database URL, then exit without starting the application services.

- [x] **Step 4: Run the reset-script unit tests and syntax checks.**

### Task 4: Register the golden backup path and document operations

**Files:**
- Modify: `backend/env_config.py`
- Modify: `.env.example`
- Modify: `DEVELOPMENT.md`
- Modify: `docs/operations/docker.md`

- [x] **Step 1: Register `LOCAL_SNAPSHOT_GOLDEN_BACKUP_PATH` with the environment registry and regenerate `.env.example`.** Default it to `../aethria-backups/aethria_prod_snapshot_20260814.dump` for this checkout while allowing an explicit absolute path.

- [x] **Step 2: Document the two-copy model, normal startup, reset command, and migration promotion boundary.**

- [x] **Step 3: Run configuration-registry tests and the focused snapshot tests.**

### Task 5: Initialize and verify the working copy

**Files:**
- No repository source changes beyond the tasks above; external state only: `aethria-prod-working-data`.

- [x] **Step 1: Confirm the golden backup path and current Docker context without deleting the old `aethria-prod-snapshot-data` volume.**

- [x] **Step 2: Run `python3 run.py --reset-local-snapshot` to create the new working volume from the golden dump.**

- [x] **Step 3: Run `python3 run.py` and verify the backend, app, and web ports accept connections.** Stop it with Ctrl+C after the startup probe.

- [x] **Step 4: Run the focused tests, `python3 -m py_compile`, and `git diff --check`.**
