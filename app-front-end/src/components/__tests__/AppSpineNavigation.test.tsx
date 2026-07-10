import { describe, expect, it } from 'vitest';

import { SPINE_WIDTH, SPINE_WORKSPACES } from '../AppSpine';

describe('AppSpine navigation', () => {
  it('keeps the original single-line workspace configuration', () => {
    expect(SPINE_WORKSPACES).toEqual([
      { href: '/v1', label: 'Home', shortcut: '1' },
      { href: '/v1/flow', label: 'Flow', shortcut: '2' },
      { href: '/v1/portfolio', label: 'Portfolio', shortcut: '3' },
      { href: '/v1/fund', label: 'Fund', shortcut: '4' },
    ]);
  });

  it('keeps the original spine width', () => {
    expect(SPINE_WIDTH).toBe('clamp(204px, 15vw, 248px)');
  });
});
