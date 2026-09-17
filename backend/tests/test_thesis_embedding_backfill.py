"""Tests for fund_thesis.ops.backfill_thesis_embeddings (tenant-scoped, idempotent)."""
import fund_thesis.ops as ops


class _Query:
    def __init__(self, table):
        self.table = table
        self._filters = {}

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def execute(self):
        return type("R", (), {"data": self.table._rows_for(self._filters)})()

    def upsert(self, row, on_conflict=None):
        self.table._upsert(row)
        return self

    def insert(self, row):
        self.table._rows.append(dict(row))
        return self

    def update(self, patch):
        self.table._pending_update = patch
        return self


class _Table:
    def __init__(self, db, name):
        self.db = db
        self.name = name
        self._rows = db.data.setdefault(name, [])
        self._pending_update = None

    def _rows_for(self, filters):
        rows = [r for r in self._rows if all(r.get(k) == v for k, v in filters.items())]
        return [dict(r) for r in rows]

    def _upsert(self, row):
        for r in self._rows:
            if r.get("version_id") == row.get("version_id"):
                r.update(row)
                return
        self._rows.append(dict(row))


class FakeClient:
    def __init__(self):
        self.data = {}

    def table(self, name):
        return _Query(_Table(self, name))


def _seed(client, *, versions, embeddings, active_version_id=None):
    client.data["fund_thesis_versions"] = list(versions)
    client.data["fund_thesis_embeddings"] = list(embeddings)
    client.data["fund_thesis"] = [{"user_id": "u1", "active_version_id": active_version_id}]


def test_dry_run_counts_eligible_without_api_key(monkeypatch):
    client = FakeClient()
    _seed(
        client,
        versions=[
            {"id": "v1", "user_id": "u1", "version_number": 2, "raw_text": "thesis A"},
            {"id": "v2", "user_id": "u1", "version_number": 1, "raw_text": "thesis B"},
        ],
        embeddings=[{"version_id": "v1", "user_id": "u1", "embedding_vector": [0.1, 0.2], "model": "text-embedding-3-small"}],
    )
    result = ops.backfill_thesis_embeddings(client, "u1", api_key="", dry_run=True)
    assert result["scanned"] == 2
    assert result["eligible"] == 1  # v2 has no embedding row
    assert result["embedded"] == 0


def test_backfill_embeds_missing_and_empty(monkeypatch):
    client = FakeClient()
    _seed(
        client,
        versions=[
            {"id": "v1", "user_id": "u1", "version_number": 2, "raw_text": "needs embedding"},
            {"id": "v2", "user_id": "u1", "version_number": 1, "raw_text": "empty vector"},
            {"id": "v3", "user_id": "u1", "version_number": 0, "raw_text": "already good"},
        ],
        embeddings=[
            {"version_id": "v2", "user_id": "u1", "embedding_vector": [], "model": "none"},
            {"version_id": "v3", "user_id": "u1", "embedding_vector": [0.5], "model": "text-embedding-3-small"},
        ],
    )
    monkeypatch.setattr(ops, "embed_text_for_thesis", lambda text, ak, model=None: [0.9, 0.9, 0.9])
    monkeypatch.setattr(ops, "_DEFAULT_EMBED_MODEL", "text-embedding-3-small")
    # invalidate_thesis_cache is imported lazily inside the function; stub the module fn.
    import fund_thesis
    monkeypatch.setattr(fund_thesis, "invalidate_thesis_cache", lambda uid: None)

    result = ops.backfill_thesis_embeddings(client, "u1", api_key="sk-test")
    assert result["embedded"] == 2  # v1 (missing) + v2 (empty)
    assert result["failed"] == 0
    rows = {r["version_id"]: r for r in client.data["fund_thesis_embeddings"]}
    assert rows["v1"]["embedding_vector"] == [0.9, 0.9, 0.9]
    assert rows["v2"]["embedding_vector"] == [0.9, 0.9, 0.9]
    assert rows["v3"]["embedding_vector"] == [0.5]  # untouched


def test_backfill_requires_key_when_not_dry_run():
    client = FakeClient()
    _seed(client, versions=[], embeddings=[])
    try:
        ops.backfill_thesis_embeddings(client, "u1", api_key="")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_ensure_active_thesis_embedding_is_best_effort():
    # No api key -> no-op, returns False, never raises.
    assert ops.ensure_active_thesis_embedding(FakeClient(), "u1", "") is False
