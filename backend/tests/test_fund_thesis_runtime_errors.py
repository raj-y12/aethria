from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

import api
from fund_thesis import ActiveThesis


class _FailingQuery:
    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        raise httpx.RemoteProtocolError("connection terminated")


class _FailingClient:
    def table(self, _name):
        return _FailingQuery()


def test_fund_thesis_runtime_transient_transport_error_returns_503(monkeypatch):
    monkeypatch.setattr(api, "_require_supabase_for_thesis", lambda: None)
    monkeypatch.setattr(api, "get_service_client", lambda: _FailingClient())
    monkeypatch.setattr(api, "compute_thesis_alignment_stats", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        api,
        "get_active_thesis",
        lambda _client, _user_id: ActiveThesis(
            thesis_id="thesis_1",
            version_id="version_2",
            version_number=2,
            raw_text="Invest in B2B software.",
            parsed_json={"sectors": ["B2B SaaS"]},
            embedding=[],
            embedding_model="none",
        ),
    )

    request = SimpleNamespace(state=SimpleNamespace(user_id="user_123"))

    with pytest.raises(HTTPException) as exc:
        api.get_fund_thesis_runtime(request)

    assert exc.value.status_code == 503
    assert exc.value.detail == "Thesis query failed; please retry"
