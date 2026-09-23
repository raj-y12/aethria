// Vitest provides Node's filesystem APIs at runtime; the app's browser build has no Node typings.
// @ts-expect-error Node-only test helper.
import { readFileSync } from 'node:fs';
// @ts-expect-error Node-only test helper.
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import {
  SPINE_WIDTH,
  SPINE_WORKSPACES,
  resolveSpinePathname,
} from '../AppSpine';

declare const process: { cwd(): string };

describe('AppSpine navigation', () => {
  it('keeps the original single-line workspace configuration', () => {
    expect(SPINE_WORKSPACES).toEqual([
      { href: '/v1', label: 'Home', shortcut: '1' },
      { href: '/v1/flow', label: 'Flow', shortcut: '2' },
      { href: '/v1/portfolio', label: 'Portfolio', shortcut: '3' },
      { href: '/v1/fund', label: 'Fund', shortcut: '4' },
    ]);
  });

  it('freezes the outgoing active route during the dock exit', () => {
    expect(resolveSpinePathname('/v1', false, '/v1/portfolio')).toBe(
      '/v1/portfolio',
    );
    expect(resolveSpinePathname('/v1/portfolio', true, '/v1')).toBe(
      '/v1/portfolio',
    );
  });

  // The spine and the Settings paper rail read one width. Asserting the literal
  // here would only prove this file still says it, so check both halves: the
  // spine defers to the shared token, and the token still resolves to the
  // original measurement.
  it('keeps the original spine width, via the shared rail token', () => {
    expect(SPINE_WIDTH).toBe('var(--spine-width)');
    const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');
    expect(css).toContain('--spine-width: clamp(204px, 15vw, 248px);');
  });

  it('does not propagate the dock exit into duplicate workspace nav layers', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'src/components/AppSpine.tsx'),
      'utf8',
    );
    expect(source).toMatch(/<AnimatePresence initial=\{false\}>\s*<motion\.nav/);
  });
});
