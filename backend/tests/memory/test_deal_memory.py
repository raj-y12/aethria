import json

import pytest

from memory import DealMemory


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_exc):
        return False


class _Connection:
    def __init__(self):
        self.documents = {}

    async def fetchrow(self, _sql, user_id, key):
        data = self.documents.get((user_id, key))
        return {"data": json.dumps(data)} if data is not None else None

    async def execute(self, _sql, user_id, key, encoded):
        self.documents[(user_id, key)] = json.loads(encoded)


class _Pool:
    def __init__(self):
        self.connection = _Connection()

    def acquire(self):
        return _Acquire(self.connection)


@pytest.mark.asyncio
async def test_deal_memory_initializes_and_round_trips_document_values():
    pool = _Pool()
    memory = DealMemory("user-a", pool)

    await memory.initialize()
    await memory.record_scout_discovery("Fintech", "Payments € thesis")
    await memory.record_failed_assumptions(["Unknown null value"])

    assert await memory.get_oversaturated_sectors() == ["Fintech"]
    assert await memory.get_recent_failed_assumptions() == ["Unknown null value"]
    assert await memory.is_duplicate_thesis("Payments € thesis") is True


@pytest.mark.asyncio
async def test_deal_memory_is_tenant_scoped():
    pool = _Pool()
    first = DealMemory("user-a", pool)
    second = DealMemory("user-b", pool)

    await first.initialize()
    await first.record_scout_discovery("Fintech", "Only tenant A")
    await second.initialize()

    assert await first.is_duplicate_thesis("Only tenant A") is True
    assert await second.is_duplicate_thesis("Only tenant A") is False
