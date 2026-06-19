from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from routers import fund_thesis as _ftr
from fund_thesis import ActiveThesisMeta


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
    monkeypatch.setattr(_ftr, "_require_supabase_for_thesis", lambda: None)
    monkeypatch.setattr(_ftr, "get_service_client", lambda: _FailingClient())
    monkeypatch.setattr(_ftr, "compute_thesis_alignment_stats", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        _ftr,
        "get_active_thesis_metadata",
        lambda _client, _user_id: ActiveThesisMeta(
            thesis_id="thesis_1",
            version_id="version_2",
            version_number=2,
            raw_text="Invest in B2B software.",
            parsed_json={"sectors": ["B2B SaaS"]},
            has_embeddings=False,
            embedding_model="none",
            embedding_dim=0,
        ),
    )

    request = SimpleNamespace(state=SimpleNamespace(user_id="user_123"))

    with pytest.raises(HTTPException) as exc:
        _ftr.get_fund_thesis_runtime(request)

    assert exc.value.status_code == 503
    assert exc.value.detail == "Thesis query failed; please retry"
