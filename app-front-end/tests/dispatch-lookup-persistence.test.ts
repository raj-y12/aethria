import { describe, it } from 'vitest';
import assert from 'node:assert/strict';
import {
  DISPATCH_LOOKUP_STORAGE_VERSION,
  getDispatchLookupStorageKey,
  loadDispatchLookupSnapshot,
  saveDispatchLookupSnapshot,
} from '../src/lib/dispatchLookupPersistence.ts';

class MemoryStorage implements Storage {
  private data = new Map<string, string>();
  get length() {
    return this.data.size;
  }
  clear() {
    this.data.clear();
  }
  getItem(key: string) {
    return this.data.get(key) ?? null;
  }
  key(index: number) {
    return Array.from(this.data.keys())[index] ?? null;
  }
  removeItem(key: string) {
    this.data.delete(key);
  }
  setItem(key: string, value: string) {
    this.data.set(key, value);
  }
}

describe('dispatch lookup persistence', () => {
  it('saves, dedupes, expires, and clears lookup snapshots', () => {
    const storage = new MemoryStorage();
    const key = getDispatchLookupStorageKey('user_123');
    const now = Date.parse('2026-06-02T12:00:00.000Z');

    assert.equal(key, 'aethria.dispatch.lookups.v2:user_123');

    saveDispatchLookupSnapshot(storage, key, {
      pendingLookup: {
        lookupId: 'lookup-active-1', queryLabel: 'Perplexity AI', autoOpened: false, isRerun: true,
        jobId: 'job-active-123', acceptedAt: '2026-06-02T12:00:00Z', pipelineRunId: 'run-active-123',
        durableStatus: 'retry_wait',
      },
      backgroundLookups: [
        {
          lookupId: 'lookup-background-1', queryLabel: 'Aethria', autoOpened: false, isRerun: false,
          jobId: 'job-background-123', acceptedAt: '2026-06-02T12:00:01Z', pipelineRunId: 'run-background-123',
          durableStatus: 'accepted',
        },
        {
          lookupId: 'lookup-active-1', queryLabel: 'Duplicate', autoOpened: false, isRerun: false,
          jobId: 'job-duplicate-123', acceptedAt: '2026-06-02T12:00:02Z', pipelineRunId: 'run-duplicate-123',
          durableStatus: 'accepted',
        },
      ],
    }, now);

    assert.deepEqual(loadDispatchLookupSnapshot(storage, key, now + 5_000), {
      pendingLookup: {
        lookupId: 'lookup-active-1', queryLabel: 'Perplexity AI', autoOpened: false, isRerun: true,
        jobId: 'job-active-123', acceptedAt: '2026-06-02T12:00:00Z', pipelineRunId: 'run-active-123',
        durableStatus: 'retry_wait',
      },
      backgroundLookups: [
        {
          lookupId: 'lookup-background-1', queryLabel: 'Aethria', autoOpened: false, isRerun: false,
          jobId: 'job-background-123', acceptedAt: '2026-06-02T12:00:01Z', pipelineRunId: 'run-background-123',
          durableStatus: 'accepted',
        },
      ],
    });

    const raw = storage.getItem(key);
    assert.ok(raw);
    const parsed = JSON.parse(raw);
    assert.equal(parsed.version, DISPATCH_LOOKUP_STORAGE_VERSION);
    assert.equal(parsed.updatedAt, now);

    storage.setItem(key, '{bad json');
    assert.deepEqual(loadDispatchLookupSnapshot(storage, key, now), {
      pendingLookup: null,
      backgroundLookups: [],
    });

    storage.setItem(key, JSON.stringify({
      version: DISPATCH_LOOKUP_STORAGE_VERSION,
      updatedAt: now - 25 * 60 * 60 * 1000,
      pendingLookup: { lookupId: 'stale-lookup', queryLabel: 'Old', autoOpened: false },
      backgroundLookups: [],
    }));
    assert.deepEqual(loadDispatchLookupSnapshot(storage, key, now), {
      pendingLookup: null,
      backgroundLookups: [],
    });

    saveDispatchLookupSnapshot(storage, key, {
      pendingLookup: null,
      backgroundLookups: [],
    }, now);
    assert.equal(storage.getItem(key), null);
  });

  it('invalidates the pre-durable v1 snapshot instead of inferring execution', () => {
    const storage = new MemoryStorage();
    const key = getDispatchLookupStorageKey('user_123')!;
    const now = Date.parse('2026-06-02T12:00:00.000Z');

    storage.setItem(key, JSON.stringify({
      version: 1,
      updatedAt: now,
      pendingLookup: { lookupId: 'legacy-lookup-1', queryLabel: 'Legacy Co', autoOpened: false },
      backgroundLookups: [],
    }));

    assert.deepEqual(loadDispatchLookupSnapshot(storage, key, now + 1_000), {
      pendingLookup: null,
      backgroundLookups: [],
    });
  });
});
