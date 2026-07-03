import { describe, it, expect, beforeEach } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import { hydrateWarmStart, persistWarmSnapshot } from '../warmStart';

const USER = 'user_abc';

describe('warmStart', () => {
  beforeEach(() => localStorage.clear());

  it('round-trips warm keys through localStorage and preserves snapshot age', () => {
    const writer = new QueryClient();
    const startups = [{ id: 's1', name: 'Acme' }];
    writer.setQueryData(['startups', 'list'], startups);
    writer.setQueryData(['escalations'], []);
    persistWarmSnapshot(writer, USER);

    const reader = new QueryClient();
    hydrateWarmStart(reader, USER);

    expect(reader.getQueryData(['startups', 'list'])).toEqual(startups);
    expect(reader.getQueryData(['escalations'])).toEqual([]);
    // dataUpdatedAt reflects the snapshot's save time so normal staleness
    // rules decide whether a background refetch happens.
    const state = reader.getQueryState(['startups', 'list']);
    expect(state?.dataUpdatedAt).toBeGreaterThan(0);
    expect(state?.dataUpdatedAt).toBeLessThanOrEqual(Date.now());
  });

  it('is per-user: another user hydrates nothing', () => {
    const writer = new QueryClient();
    writer.setQueryData(['startups', 'list'], [{ id: 's1' }]);
    persistWarmSnapshot(writer, USER);

    const reader = new QueryClient();
    hydrateWarmStart(reader, 'user_other');
    expect(reader.getQueryData(['startups', 'list'])).toBeUndefined();
  });

  it('ignores corrupt snapshots', () => {
    localStorage.setItem(`aethria:warm:v1:${USER}`, '{not json');
    const reader = new QueryClient();
    expect(() => hydrateWarmStart(reader, USER)).not.toThrow();
    expect(reader.getQueryData(['startups', 'list'])).toBeUndefined();
  });

  it('does not persist keys outside the warm list', () => {
    const writer = new QueryClient();
    writer.setQueryData(['meta', 'reports'], [{ big: 'blob' }]);
    writer.setQueryData(['startups', 'list'], []);
    persistWarmSnapshot(writer, USER);

    const reader = new QueryClient();
    hydrateWarmStart(reader, USER);
    expect(reader.getQueryData(['meta', 'reports'])).toBeUndefined();
  });
});
