# Audit P1-P3 Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close every P1-P3 audit item that is actionable in the repository and explicitly record production-only acceptance checks that cannot be verified locally.

**Architecture:** Harden the existing tenant-scoped FastAPI and React Query boundaries in place. Prefer narrow helpers, existing API clients, and explicit deployment guards over broad rewrites; keep durable Supabase work row-level and user-scoped.

**Tech Stack:** FastAPI, Supabase service-role storage, Clerk JWT, React, TanStack Query, Vite, Vitest, Playwright, GitHub Actions.

## Global Constraints

- Every backend storage operation receives an explicit `user_id`.
- Supabase schema changes require a new migration and RLS review.
- Frontend network calls remain inside `src/api/` and use Clerk auth.
- No unrelated local screenshots or tool artifacts are staged.
- Every completed item gets focused tests and an audit verification note.

## Workstreams

1. Auth, tenant, cancellation, local-data, and modal hardening (P1-4, P1-5, P1-7, P1-8, P2-5).
2. Retrieval fallback and observability (P1-9, P2-8), with provider failure tests.
3. Query fan-out, test depth, packaging, E2E, and bundle hygiene (P1-2, P2-3, P2-9, P2-10, P2-11, P3).
4. Audit documentation and production-only acceptance gates (P1-1, P2-12, release timing).

Each workstream is independently verified before the next begins. Items requiring deployed credentials, a second process, or external proxy timing are documented as release gates rather than falsely marked locally complete.
