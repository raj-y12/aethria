"""Regression: probe_url_status() must fall back HEAD->GET on ANY hard-negative
HEAD status, not just 405/501. Live-verified 2026-08-18 on thenextweb.com
(HEAD returns 404, GET returns 200 for the identical URL) -- this was silently
hard-dropping every otherwise-valid Scout reference citing such a URL, via
filter_references_by_url_probe's non-lenient path, which had been starving
Scout discovery of any real company entirely (0 startups created across an
entire pipeline run)."""

from urllib.error import HTTPError

import research.reference_verify as reference_verify


class _FakeResponse:
    def __init__(self, status: int):
        self.status = status

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_head_404_falls_back_to_get_and_succeeds(monkeypatch):
    def fake_urlopen(req, timeout=4.0, context=None):
        if req.get_method() == "HEAD":
            raise HTTPError(req.full_url, 404, "Not Found", hdrs=None, fp=None)
        return _FakeResponse(200)

    monkeypatch.setattr(reference_verify, "urlopen", fake_urlopen)

    assert reference_verify.probe_url_status("https://example.com/article") == "reachable"


def test_head_and_get_both_404_stays_unreachable(monkeypatch):
    def fake_urlopen(req, timeout=4.0, context=None):
        raise HTTPError(req.full_url, 404, "Not Found", hdrs=None, fp=None)

    monkeypatch.setattr(reference_verify, "urlopen", fake_urlopen)

    assert reference_verify.probe_url_status("https://example.com/gone") == "unreachable"


def test_head_reachable_does_not_bother_with_get(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=4.0, context=None):
        calls.append(req.get_method())
        return _FakeResponse(200)

    monkeypatch.setattr(reference_verify, "urlopen", fake_urlopen)

    assert reference_verify.probe_url_status("https://example.com/fine") == "reachable"
    assert calls == ["HEAD"]
