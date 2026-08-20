"""Regression: get_system_health used to crash /api/settings entirely when the
portfolio store's calibration-metrics file couldn't be read (e.g.
'PortfolioStore: local_storage_disabled; remote storage is required' when only
remote storage is configured). Every other optional field in this function
already degrades gracefully via try/except + health_errors.append(...); the
calibration_warning read was the one field that didn't, so its exception
propagated uncaught out of get_settings and 500'd the whole endpoint."""

import routers.deps as deps


class _RaisingPortfolioStore:
    """Mirrors the real crash: files is populated, but reading one raises."""

    files = {"agent_metrics": "agent_metrics.json"}

    def _read_file(self, _path):
        raise RuntimeError("PortfolioStore: local_storage_disabled; remote storage is required")

    def get_all_watchlist(self):
        return []


def test_get_system_health_survives_calibration_read_failure(monkeypatch):
    monkeypatch.setattr(deps, "get_portfolio_store", lambda user_id: _RaisingPortfolioStore())

    result = deps.get_system_health(
        None,
        user_id="user-1",
        settings={},
        pending_escalations=0,
        unreviewed=0,
        undecided=0,
    )

    assert "calibration_warning_unavailable" in result["errors"]
    assert result["status"] == "degraded"
