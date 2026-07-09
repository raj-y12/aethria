export const DISPATCH_LOOKUP_STORAGE_VERSION = 1;
export const DISPATCH_LOOKUP_MAX_AGE_MS = 24 * 60 * 60 * 1000;
const DISPATCH_LOOKUP_STORAGE_PREFIX = 'aethria.dispatch.lookups.v1';
const LOOKUP_ID_RE = /^[a-zA-Z0-9_-]{8,128}$/;
const MAX_BACKGROUND_LOOKUPS = 8;

export type PersistedDispatchLookup = {
  lookupId: string;
  queryLabel: string;
  autoOpened: boolean;
  /** Post-hoc re-review: identity already resolved, only review + decide run. */
  isRerun?: boolean;
};

export type DispatchLookupSnapshot = {
  pendingLookup: PersistedDispatchLookup | null;
  backgroundLookups: PersistedDispatchLookup[];
};

type StoredDispatchLookupSnapshot = DispatchLookupSnapshot & {
  version: number;
  updatedAt: number;
};

export function getDispatchLookupStorageKey(userId: string | null | undefined): string | null {
  const id = userId?.trim();
  return id ? `${DISPATCH_LOOKUP_STORAGE_PREFIX}:${id}` : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function normalizeLookup(value: unknown): PersistedDispatchLookup | null {
  if (!isRecord(value)) return null;
  const lookupId = typeof value.lookupId === 'string' ? value.lookupId.trim() : '';
  const queryLabel = typeof value.queryLabel === 'string' ? value.queryLabel.trim() : '';
  if (!LOOKUP_ID_RE.test(lookupId) || !queryLabel) return null;
  return {
    lookupId,
    queryLabel,
    autoOpened: Boolean(value.autoOpened),
    isRerun: Boolean(value.isRerun),
  };
}

function normalizeSnapshot(value: unknown, now: number, maxAgeMs: number): DispatchLookupSnapshot {
  if (!isRecord(value)) return emptySnapshot();
  if (value.version !== DISPATCH_LOOKUP_STORAGE_VERSION) return emptySnapshot();
  const updatedAt = typeof value.updatedAt === 'number' ? value.updatedAt : 0;
  if (!Number.isFinite(updatedAt) || now - updatedAt > maxAgeMs) return emptySnapshot();

  const pendingLookup = normalizeLookup(value.pendingLookup);
  const seen = new Set<string>();
  if (pendingLookup) seen.add(pendingLookup.lookupId);

  const backgroundLookups = Array.isArray(value.backgroundLookups)
    ? value.backgroundLookups
        .map(normalizeLookup)
        .filter((lookup): lookup is PersistedDispatchLookup => {
          if (!lookup || seen.has(lookup.lookupId)) return false;
          seen.add(lookup.lookupId);
          return true;
        })
        .slice(0, MAX_BACKGROUND_LOOKUPS)
    : [];

  return { pendingLookup, backgroundLookups };
}

function emptySnapshot(): DispatchLookupSnapshot {
  return { pendingLookup: null, backgroundLookups: [] };
}

export function loadDispatchLookupSnapshot(
  storage: Pick<Storage, 'getItem'> | null | undefined,
  key: string | null,
  now = Date.now(),
  maxAgeMs = DISPATCH_LOOKUP_MAX_AGE_MS,
): DispatchLookupSnapshot {
  if (!storage || !key) return emptySnapshot();
  try {
    const raw = storage.getItem(key);
    if (!raw) return emptySnapshot();
    return normalizeSnapshot(JSON.parse(raw), now, maxAgeMs);
  } catch {
    return emptySnapshot();
  }
}

export function saveDispatchLookupSnapshot(
  storage: Pick<Storage, 'setItem' | 'removeItem'> | null | undefined,
  key: string | null,
  snapshot: DispatchLookupSnapshot,
  now = Date.now(),
): void {
  if (!storage || !key) return;
  const normalized = normalizeSnapshot(
    {
      version: DISPATCH_LOOKUP_STORAGE_VERSION,
      updatedAt: now,
      pendingLookup: snapshot.pendingLookup,
      backgroundLookups: snapshot.backgroundLookups,
    },
    now,
    DISPATCH_LOOKUP_MAX_AGE_MS,
  );
  if (!normalized.pendingLookup && normalized.backgroundLookups.length === 0) {
    storage.removeItem(key);
    return;
  }
  const stored: StoredDispatchLookupSnapshot = {
    version: DISPATCH_LOOKUP_STORAGE_VERSION,
    updatedAt: now,
    ...normalized,
  };
  storage.setItem(key, JSON.stringify(stored));
}
