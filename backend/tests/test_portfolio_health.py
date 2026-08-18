"""Regression coverage for HealthMonitor's check methods (audit HIGH-H3):
each used to compute a real severity/description and then unconditionally
`return None`, discarding the finding entirely. They now return the
check_type string when an issue is found, so a caller can at least tell
which checks fired instead of every check being permanently silent."""

from portfolio.health import HealthMonitor


class _FakeStore:
    def __init__(self, startups=None, decisions=None):
        self._startups = startups or []
        self._decisions = decisions or []
        self.files = {}

    def get_all_startups(self):
        return self._startups

    def get_all_decisions(self):
        return self._decisions


def _monitor(**kwargs):
    return HealthMonitor(_FakeStore(**kwargs))


def test_check_duplicates_returns_the_check_type_when_duplicates_found():
    monitor = _monitor(
        startups=[{"name": "Acme"}, {"name": "Acme"}, {"name": "Beacon"}]
    )
    assert monitor._check_duplicates() == "duplicate_detection"


def test_check_duplicates_returns_none_when_no_duplicates():
    monitor = _monitor(startups=[{"name": "Acme"}, {"name": "Beacon"}])
    assert monitor._check_duplicates() is None


def test_check_inactivity_returns_the_check_type_when_stale():
    monitor = _monitor(decisions=[{"decided_at": "2020-01-01T00:00:00+00:00"}])
    assert monitor._check_inactivity() == "inactivity"


def test_check_memory_bloat_returns_the_check_type_when_large_files_found(tmp_path):
    big_file = tmp_path / "startups.json"
    big_file.write_bytes(b"0" * (11 * 1024 * 1024))
    monitor = _monitor()
    monitor.store.files = {"startups": big_file}
    assert monitor._check_memory_bloat() == "memory_bloat"


def test_check_health_surfaces_which_checks_fired():
    monitor = _monitor(
        startups=[{"name": "Acme"}, {"name": "Acme"}],
        decisions=[{"decided_at": "2020-01-01T00:00:00+00:00"}],
    )
    fired = monitor.check_health()
    assert "duplicate_detection" in fired
    assert "inactivity" in fired
