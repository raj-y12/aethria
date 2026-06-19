import { describe, it, expect } from 'vitest';
import { formatDate, formatDateTime } from '../dates';

describe('formatDate', () => {
  it('formats an ISO date in en-GB editorial register', () => {
    expect(formatDate('2026-05-30T14:12:00.000Z')).toBe('30 May 2026');
  });

  it('returns an em dash for null/undefined/empty', () => {
    expect(formatDate(null)).toBe('—');
    expect(formatDate(undefined)).toBe('—');
    expect(formatDate('')).toBe('—');
  });

  it('returns an em dash for an unparseable string', () => {
    expect(formatDate('not-a-date')).toBe('—');
  });
});

describe('formatDateTime', () => {
  it('joins date and 24h time with a middot', () => {
    const out = formatDateTime('2026-05-30T14:12:00.000Z');
    expect(out).toContain('30 May 2026');
    expect(out).toContain('·');
    // 24h, zero-padded HH:MM (exact hour depends on the test runner TZ, so just
    // assert the shape rather than a specific hour).
    expect(out).toMatch(/\d{2}:\d{2}$/);
  });

  it('returns an em dash for bad input', () => {
    expect(formatDateTime(null)).toBe('—');
    expect(formatDateTime('nope')).toBe('—');
  });
});
