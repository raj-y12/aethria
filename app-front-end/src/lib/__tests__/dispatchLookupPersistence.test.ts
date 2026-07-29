import { describe, expect, it } from 'vitest';

import {
  DISPATCH_LOOKUP_STORAGE_VERSION,
  loadDispatchLookupSnapshot,
  saveDispatchLookupSnapshot,
  type PersistedDispatchLookup,
} from '../dispatchLookupPersistence';

const KEY = 'aethria.dispatch.lookups.v2:user_1';

function memoryStorage() {
  const map = new Map<string, string>();
  return {
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => void map.set(k, v),
    removeItem: (k: string) => void map.delete(k),
    raw: map,
  };
}

const RERUN: PersistedDispatchLookup = {
  lookupId: 'lookup-1234567890',
  queryLabel: 'Acme',
  autoOpened: false,
  isRerun: true,
  targetStartupId: 'existing-startup',
  acceptedAt: '2026-07-29T12:00:00Z',
};

describe('dispatch lookup persistence', () => {
  it('round-trips the re-review target across a reload', () => {
    // Without this, a reload would strip the target and strand the chip on the
    // rail again — the exact state the target was added to prevent.
    const storage = memoryStorage();
    saveDispatchLookupSnapshot(storage, KEY, {
      pendingLookup: RERUN,
      backgroundLookups: [],
    });
    const loaded = loadDispatchLookupSnapshot(storage, KEY);
    expect(loaded.pendingLookup?.targetStartupId).toBe('existing-startup');
    expect(loaded.pendingLookup?.isRerun).toBe(true);
  });

  it('round-trips targets on backgrounded re-reviews too', () => {
    const storage = memoryStorage();
    saveDispatchLookupSnapshot(storage, KEY, {
      pendingLookup: null,
      backgroundLookups: [RERUN],
    });
    const loaded = loadDispatchLookupSnapshot(storage, KEY);
    expect(loaded.backgroundLookups[0]?.targetStartupId).toBe('existing-startup');
  });

  it('loads payloads stored before targets existed', () => {
    const storage = memoryStorage();
    storage.setItem(
      KEY,
      JSON.stringify({
        version: DISPATCH_LOOKUP_STORAGE_VERSION,
        updatedAt: Date.now(),
        pendingLookup: {
          lookupId: 'lookup-1234567890',
          queryLabel: 'Acme',
          autoOpened: false,
          isRerun: true,
        },
        backgroundLookups: [],
      }),
    );
    const loaded = loadDispatchLookupSnapshot(storage, KEY);
    expect(loaded.pendingLookup?.lookupId).toBe('lookup-1234567890');
    expect(loaded.pendingLookup?.targetStartupId).toBeUndefined();
  });

  it('drops a blank target rather than storing an empty string', () => {
    const storage = memoryStorage();
    saveDispatchLookupSnapshot(storage, KEY, {
      pendingLookup: { ...RERUN, targetStartupId: '   ' },
      backgroundLookups: [],
    });
    expect(loadDispatchLookupSnapshot(storage, KEY).pendingLookup?.targetStartupId).toBeUndefined();
  });

  it('ignores a non-string target', () => {
    const storage = memoryStorage();
    storage.setItem(
      KEY,
      JSON.stringify({
        version: DISPATCH_LOOKUP_STORAGE_VERSION,
        updatedAt: Date.now(),
        pendingLookup: { ...RERUN, targetStartupId: 42 },
        backgroundLookups: [],
      }),
    );
    expect(loadDispatchLookupSnapshot(storage, KEY).pendingLookup?.targetStartupId).toBeUndefined();
  });
});
