import utils.openai_client as oc


class _FakeOpenAI:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def _patch(monkeypatch):
    captured = {}

    def factory(**kwargs):
        captured.update(kwargs)
        return _FakeOpenAI(**kwargs)

    monkeypatch.setattr(oc, "OpenAI", factory)
    return captured


def test_defaults_applied_when_no_env(monkeypatch):
    captured = _patch(monkeypatch)
    monkeypatch.delenv("OPENAI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("OPENAI_MAX_RETRIES", raising=False)
    oc.build_openai_client("sk-test")
    assert captured["api_key"] == "sk-test"
    assert captured["timeout"] == 120.0
    assert captured["max_retries"] == 2


def test_env_overrides_defaults(monkeypatch):
    captured = _patch(monkeypatch)
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "5")
    oc.build_openai_client("sk-x")
    assert captured["timeout"] == 30.0
    assert captured["max_retries"] == 5


def test_explicit_args_win_over_env(monkeypatch):
    captured = _patch(monkeypatch)
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "9")
    oc.build_openai_client("sk-x", timeout=10.0, max_retries=0)
    assert captured["timeout"] == 10.0
    assert captured["max_retries"] == 0


def test_invalid_env_falls_back_to_default(monkeypatch):
    captured = _patch(monkeypatch)
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "not-a-number")
    monkeypatch.delenv("OPENAI_MAX_RETRIES", raising=False)
    oc.build_openai_client("sk-x")
    assert captured["timeout"] == 120.0
