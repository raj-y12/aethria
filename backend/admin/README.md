# admin

The operator admin surface: separate secret-based login, audit log, and
overview aggregation (ARCHITECTURE.md §7 "Admin surface").

## Purpose

Everything the `/admin` routes need that is deliberately **not** the
end-user Clerk JWT path.

## Inputs

An admin secret (for `auth.py`) or an already-issued admin token; Clerk
Backend API reads for `clerk.py`.

## Outputs

An admin session token, audit log rows, and an aggregated overview payload.

## Responsibilities

- `auth.py`: issue/verify a short-lived admin token from the admin secret.
- `audit.py`: append-only `admin_audit_log` writes.
- `clerk.py`: read-only Clerk Backend API calls (session/user listing) —
  distinct from `auth_clerk.py`, which verifies *end-user* JWTs.
- `service.py`: aggregates overview data using `clerk.py`.

## Non-responsibilities

- Does not verify end-user requests — that's `auth_clerk.py` +
  `security/request_guards.py`.
- Does not decide business/decision policy.

## Dependencies

`jwt` (PyJWT, already a core dependency), stdlib `urllib` for the Clerk
Backend API calls.

## Public API

Import from `admin` directly (`from admin import build_admin_overview`).

## Testing

`tests/test_admin_auth.py`, `tests/test_admin_audit_postgres.py`,
`tests/test_admin_service.py`, `tests/test_security_api.py`.
