# Task 5 — Authority status and certification evidence

## Delivered

- Added an authenticated typed authority API client for status, optimistic-lock
  transition, and rollback calls.
- Added `useAuthority()` plus transition/rollback mutations backed by TanStack
  Query. Successful mutations invalidate authority, system-status, startup,
  escalation, and institutional-opportunity query families.
- Integrated authority state into `useSystemData` and `App`: the legacy queue
  remains enabled until reconciled canonical-read status is active; rollout,
  reconciliation, and rollback-recovery state are visible without deriving
  authority from legacy startup rows.
- Added executable frontend and backend certification coverage, including
  authenticated lookup admission in legacy/shadow modes and a canonical-write
  compatibility-projection receipt.
- Extended Phase 8 readiness and documentation for the authority-control
  migration and target-PostgreSQL RLS/policy verification.

## TDD evidence

- RED: `npm test -- src/api/authority.test.ts src/hooks/useAuthority.test.tsx`
  initially failed because the authority client and hook modules did not exist.
- RED: readiness certification initially failed because the authority migration
  constant and RLS check did not exist.
- GREEN: targeted frontend tests: 2 files, 6 tests passed; authority
  certification plus readiness-schema coverage: 12 passed.

## Full verification

```text
pytest -q backend/tests/authority backend/tests/identity backend/tests/decisions backend/tests/evaluation_v2 -rs
716 passed, 4 skipped, 1 existing FastAPI TestClient deprecation warning

cd app-front-end && npm test
61 files passed, 280 tests passed

cd app-front-end && npm run lint && npm run build
exit 0; build transformed 868 modules

python3 backend/scripts/check_phase8_readiness.py --json
authority migration file passed; authority RLS/policy and direct-DSN checks are
blocked because DATABASE_URL/SUPABASE_DB_URL is absent; ready=false
```

## Constraints / concerns

- Target PostgreSQL migration application and authority RLS/service-role policy
  enforcement are intentionally not claimed: this workspace has no direct DSN.
- The prescribed `--runInBand` option is a Jest option and this project uses
  Vitest 2.1.9, which rejects it. The equivalent targeted and full `npm test`
  commands were used.
- No manual lookup redesign, evidence/evaluation/recommendation/portfolio UI,
  historical backfill, or canonical read DTO work was added in this slice.
