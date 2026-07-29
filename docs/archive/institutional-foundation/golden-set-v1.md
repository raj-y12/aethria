# Golden evaluation set v1

Date: 2026-07-15

## Result

Golden set `v1` is executable and passes all nine current-pipeline cases:

```text
9 passed, 0 failed
```

Run it with:

```bash
cd backend
python3 scripts/run_golden_set.py --version v1 --json
```

The corresponding test gate is:

```bash
cd backend
pytest -q tests/test_golden_set_v1.py
```

## What v1 pins

Each redacted or synthetic snapshot asserts only invariants that the current pipeline legitimately exposes:

- resolver outcome;
- external-reference validation state;
- five current reviewer dimension scores;
- legacy partner recommendation;
- partner confidence range;
- human-review requirement;
- completeness of the evaluation dependency manifest.

The corpus covers strong evidence and fit, an outside-mandate company, polished but weak materials, sparse pre-seed evidence, conflicting founder/traction assertions, ambiguous identity, unsupported founder narrative, a strategic-exception hard pass, and repeat execution with unchanged inputs.

## Limits

This is an offline contract corpus. It makes no web, retrieval-provider, Supabase, or model calls. It detects behavioural/schema drift in frozen current-pipeline outputs; it does not measure live model quality or prove production database configuration.

Later phases extend the same versioned corpus rather than retroactively making v1 assert records that do not yet exist:

- v2: canonical identity and source observations;
- v3: evidence and claims;
- v4: immutable evaluation snapshots and recommendation policy;
- v5: human rulings and workflow actions;
- v6: Fund Intelligence proposal governance.
