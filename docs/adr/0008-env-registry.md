# ADR-0008 — One registry for every environment variable

**Status:** Accepted

## Context

The backend had grown to roughly a hundred distinct environment variables read
through scattered `os.getenv("X", "default")` calls. Defaults drifted between
call sites for the same variable, there was no single place to see the
configuration surface, and there was no `.env.example` to onboard from. A
misconfigured deployment failed in a way nobody could diagnose from the code.

## Decision

`backend/env_config.py` is the canonical registry. Each variable is one
`EnvVar(name, kind, default, section, description, required, example)` entry, and
two things derive from it:

- `render_env_example()` generates the repository-root `.env.example`.
- `tests/test_config_registry.py` asserts that every `os.getenv` name appearing
  anywhere in the codebase is registered, and that `.env.example` is in sync.

A new environment variable therefore cannot be added without being documented —
the test fails otherwise.

Accessors read `os.environ` **at call time**, not at import. Much of the pipeline
re-reads settings each cycle and the test suite monkeypatches environment
variables after import; a frozen settings singleton would break both. Boolean
parsing is uniform: truthy iff the lowercased value is `1`, `true`, or `yes`.

## Consequences

**Good.** The full configuration surface is one file. Defaults exist exactly
once. `.env.example` cannot go stale. Onboarding and production configuration
read from the same source.

**Cost.** Adding a variable is two steps rather than one, and the drift test is
a build-time gate that will occasionally block someone in a hurry. That is the
intent. Call-time reads mean configuration is not validated once at boot, so a
malformed value surfaces at first use.

## Alternatives considered

- **`pydantic-settings` singleton.** Type-safe and validated at boot, but frozen
  at import — incompatible with per-cycle re-reads and with tests that
  monkeypatch environment variables.
- **A `.env.example` maintained by hand.** This is what existed. It did not exist,
  in fact, which is the point.
