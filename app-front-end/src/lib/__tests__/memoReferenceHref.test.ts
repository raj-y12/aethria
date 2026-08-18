import { describe, expect, it } from 'vitest';
import { safeHref } from '../memoReferenceHref';

describe('safeHref', () => {
  it('passes through a real https URL', () => {
    expect(safeHref('https://acme.example/team')).toBe('https://acme.example/team');
  });

  it('passes through a real http URL', () => {
    expect(safeHref('http://acme.example')).toBe('http://acme.example');
  });

  it('rejects a javascript: URL', () => {
    expect(safeHref('javascript:alert(1)')).toBeUndefined();
  });

  it('rejects a data: URL', () => {
    expect(safeHref('data:text/html,<script>alert(1)</script>')).toBeUndefined();
  });

  it('rejects null, undefined, and empty string', () => {
    expect(safeHref(null)).toBeUndefined();
    expect(safeHref(undefined)).toBeUndefined();
    expect(safeHref('')).toBeUndefined();
  });

  it('rejects a bare domain with no scheme', () => {
    expect(safeHref('acme.example')).toBeUndefined();
  });
});
