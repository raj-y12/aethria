# Local Snapshot Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep the restored local production snapshot isolated from disposable test data, prevent `run.py` from migrating it, and preserve an external backup with startup drift detection.

**Architecture:** The normal compose stack keeps its disposable test volume. A separate snapshot compose stack owns an explicitly created external volume and exposes the snapshot database on the same local port when selected by `run.py`. Snapshot startup verifies a versioned manifest and skips migrations; intentional restoration remains an explicit operator action.

**Tech Stack:** Python, Docker Compose, PostgreSQL, pytest, JSON manifest, `pg_dump` custom-format backup.

**Spec:** User request: implement protections 1, 3, and 4 from the local snapshot safety recommendations.

## Global Constraints

- Preserve all pre-existing worktree changes.
- Do not commit, push, or edit applied migrations.
- Do not add secrets or generated database dumps to the repository.
- Normal `run.py` startup must never migrate the production snapshot database.
- The snapshot manifest is verification metadata only; it must not contain row data or credentials.

### Task 1: Add snapshot startup policy and tests

**Files:**
- Modify: `run.py`
- Test: `backend/tests/test_root_process_supervision.py`

- [ ] Add failing tests for detecting the snapshot database, selecting the snapshot compose file, and skipping migrations for that database.
- [ ] Implement the smallest helpers and startup branch needed to pass those tests.
- [ ] Run the focused root-runner tests.

### Task 2: Separate Docker storage

**Files:**
- Create: `docker-compose.snapshot.yml`
- Modify: `run.py`
- Modify: `docs/operations/docker.md`

- [ ] Define an external `aethria-prod-snapshot-data` volume for the snapshot-only compose stack.
- [ ] Keep the existing disposable test volume in `docker-compose.yml`.
- [ ] Document the two stacks and the explicit snapshot-volume lifecycle.

### Task 3: Add manifest verification and tests

**Files:**
- Create: `backend/scripts/verify_local_snapshot.py`
- Create: `backend/tests/test_local_snapshot_manifest.py`
- Create: `db/snapshots/aethria_prod_snapshot_manifest.json`
- Modify: `run.py`

- [ ] Write failing unit tests for manifest validation and fail-closed mismatch behavior.
- [ ] Implement read-only verification of database identity, migration head, table counts, and startup timestamp bounds.
- [ ] Invoke verification before the backend starts when the selected database is the snapshot.
- [ ] Run focused verification tests and the local snapshot test.

### Task 4: Create and verify external recovery backup

**Files:**
- Outside repository: `/Users/rajyendamuri/aethria-backups/aethria_prod_snapshot_20260814.dump`

- [ ] Create the separate Docker volume and copy the restored snapshot into it.
- [ ] Create a custom-format `pg_dump` outside the repository.
- [ ] Verify the new snapshot counts and manifest against the backup/volume.
- [ ] Leave containers stopped and report the exact recovery artifact path.

## Verification

- Focused pytest tests for startup policy and manifest verification.
- Compose config validation for both stacks.
- Live read-only count and Flow probe against the isolated snapshot volume.
- Confirm `git status` shows only the intended source/config/docs additions among the existing dirty worktree.
