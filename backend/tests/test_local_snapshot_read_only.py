import api


def test_local_snapshot_read_only_flag_is_explicit(monkeypatch):
    monkeypatch.setenv("LOCAL_SNAPSHOT_READ_ONLY", "1")

    assert api._local_snapshot_read_only()


def test_local_snapshot_read_only_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("LOCAL_SNAPSHOT_READ_ONLY", raising=False)

    assert not api._local_snapshot_read_only()
