# Task 2 — Thin-evidence legacy scoring safety

## Implementation

- Made `SCORING_EVIDENCE_CALIBRATION_ENABLED` safe by default, with an explicit
  environment opt-out; registered it in `backend/env_config.py` and regenerated
  the corresponding `.env.example` entry.
- Made both reviewer structured-signal strict switches safe by default. An
  explicit `REVIEWER_SIGNALS_STRICT_EVIDENCE=false` still disables the clamp.
- Replaced bare-label eligibility with grounding-aware eligibility: a component
  needs concrete `value`/`label` plus `evidence` or `rule`. Confidence now
  counts only eligible components, so an unscored dimension reports `0.0`.
- Applied that same shared predicate in policy-criterion aggregation; the later
  criterion pass can no longer restore a score or confidence to rejected
  evidence.
- Converted the thin-evidence characterization to the safe contract and added
  the default clamp regression.
- Updated only directly affected characterization fixtures: default-on
  calibration values for grounded SaaS, metadata-free weak/structured signals
  becoming unscored, one calibrated label value, and a deliberately thin cap
  fixture supplied with concrete evidence so it continues testing the cap.

## Files changed

- `.env.example`
- `backend/config/scoring_config.py`
- `backend/env_config.py`
- `backend/services/scoring/aggregation_layer.py`
- `backend/services/scoring/scoring_engine.py`
- `backend/utils/reviewer_structured_signals_clamp.py`
- `backend/tests/test_scoring_thin_evidence_characterization.py`
- `backend/tests/test_reviewer_structured_signals_clamp.py`
- `backend/tests/test_structured_scoring_engine.py`
- `backend/tests/test_scoring_golden_snapshot.py`
- `backend/tests/test_label_vocabulary_robustness.py`
- `backend/tests/test_scoring_engine_calibration.py`

## RED

Command:

```bash
cd backend && pytest -q tests/test_scoring_thin_evidence_characterization.py tests/test_reviewer_structured_signals_clamp.py
```

Output:

```text
F.F.....                                                                 [100%]
FAILED tests/test_scoring_thin_evidence_characterization.py::test_strong_label_without_grounding_cannot_publish_max_score
E       assert False is True
FAILED tests/test_reviewer_structured_signals_clamp.py::test_ungrounded_label_is_cleared_by_default
E       AssertionError: assert 'strong' is None
2 failed, 6 passed in 0.14s
```

This was the expected failure: the safe defaults were disabled, and the
aggregation path still treated a speculative label as score-eligible. The
explicitly calibrated score assertion itself already passed; the failure then
correctly exposed that the dimension remained scored.

The first full focused attempt after the prescribed changes also exposed the
omitted policy-criterion predicate: it restored `0.104` confidence after
aggregation had rejected the dimension. The controller authorized a narrow
extension to reuse `_has_concrete_evidence()` there. The default-on policy then
produced the documented, directly affected stale fixture changes.

## GREEN

Affected integration regressions:

```bash
cd backend && pytest -q tests/test_config_registry.py tests/test_label_vocabulary_robustness.py tests/test_scoring_engine_calibration.py
```

```text
20 passed in 0.17s
```

Required focused gate:

```bash
cd backend && pytest -q tests/test_scoring_thin_evidence_characterization.py tests/test_reviewer_structured_signals_clamp.py tests/test_structured_scoring_engine.py tests/test_scoring_golden_snapshot.py
```

```text
48 passed in 0.37s
```

Full backend suite:

```bash
cd backend && pytest -q
```

```text
724 passed, 10 skipped, 1 warning in 10.28s
```

The warning is the existing FastAPI/Starlette `TestClient` deprecation for
`httpx`; it is unrelated to this change.

## Self-review

- Confirmed strict reviewer clamping is default-on, with an explicit rollback
  switch covered by a regression test.
- Confirmed scoring eligibility and policy criteria share one grounding-aware
  predicate and eligible-only confidence accounting.
- Confirmed the new environment variable is in both the registry and generated
  example, so registry drift protection remains effective.
- Reviewed all snapshot edits individually; none were blanket regenerated.
- Ran `git diff --check` successfully and verified focused plus full backend
  tests are green.

## Concerns

None. The only test-suite warning is the unrelated `TestClient` deprecation
noted above.
