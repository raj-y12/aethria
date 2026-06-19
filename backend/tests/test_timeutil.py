from datetime import datetime, timezone, timedelta

from utils.timeutil import utcnow, ensure_aware, parse_iso


def test_utcnow_is_aware_utc():
    now = utcnow()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_ensure_aware_coerces_naive_to_utc():
    naive = datetime(2026, 6, 19, 12, 0, 0)
    aware = ensure_aware(naive)
    assert aware.tzinfo is not None
    assert aware.utcoffset() == timedelta(0)
    # Naive value is assumed to already be UTC (not shifted).
    assert aware.hour == 12


def test_ensure_aware_passthrough_none():
    assert ensure_aware(None) is None


def test_ensure_aware_normalizes_other_offset_to_utc():
    plus_two = datetime(2026, 6, 19, 12, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    aware = ensure_aware(plus_two)
    assert aware.utcoffset() == timedelta(0)
    assert aware.hour == 10  # 12:00+02:00 == 10:00 UTC


def test_naive_and_aware_are_comparable_after_coercion():
    # The whole point: a legacy naive ISO string must not crash when subtracted
    # from an aware utcnow().
    legacy_naive_iso = "2026-06-01T00:00:00"
    parsed = ensure_aware(datetime.fromisoformat(legacy_naive_iso))
    delta = utcnow() - parsed
    assert delta.total_seconds() > 0


def test_parse_iso_handles_z_suffix_and_naive():
    assert parse_iso("2026-06-19T12:00:00Z").utcoffset() == timedelta(0)
    assert parse_iso("2026-06-19T12:00:00").utcoffset() == timedelta(0)
    assert parse_iso("2026-06-19T12:00:00+02:00").hour == 10


def test_parse_iso_returns_none_on_bad_input():
    assert parse_iso("") is None
    assert parse_iso(None) is None
    assert parse_iso("not-a-date") is None
    assert parse_iso(12345) is None
