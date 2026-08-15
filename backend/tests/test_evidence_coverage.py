"""A low persona score must be readable as thin evidence, not as a judgement.

The full scoring trace is kept only on the primary snapshot, so Skeptical and
Opportunist published a bare number with its provenance discarded — a 2.0
meaning "almost nothing was evidenced" looked identical to a 2.0 meaning "bad
company", next to a summary the model wrote independently.
"""
from reviewer.engine import _evidence_coverage_from_trace


def _trace(**per_dim) -> dict:
    return {
        dim: {"criteria": {
            f"c{i}": {"missing_data_applied": missing}
            for i, missing in enumerate(flags)
        }}
        for dim, flags in per_dim.items()
    }


def test_coverage_is_the_evidenced_fraction_of_criteria():
    trace = _trace(market=[False, False], execution=[True, True])
    assert _evidence_coverage_from_trace(trace) == 0.5


def test_fully_unevidenced_trace_reports_zero_not_none():
    assert _evidence_coverage_from_trace(_trace(market=[True, True])) == 0.0


def test_trace_without_criteria_is_unknown_coverage_not_zero():
    # None and 0.0 mean different things: "we don't know" must not render as
    # "0% evidenced".
    assert _evidence_coverage_from_trace({"market": {"score": 7.0}}) is None
    assert _evidence_coverage_from_trace({}) is None
