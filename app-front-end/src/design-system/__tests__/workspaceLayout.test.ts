import { describe, expect, it } from 'vitest';

import { workspaceLayout } from '../workspaceLayout';

describe('workspaceLayout', () => {
  it('defines one outer shell for Flow, Portfolio, and Fund', () => {
    expect(workspaceLayout.maxWidth).toBe('1180px');
    expect(workspaceLayout.shell).toBe('mx-auto w-full max-w-[var(--room-max)] px-phi-5');
  });

  it('keeps peer-page vertical spacing aligned', () => {
    expect(workspaceLayout.pageTop).toBe('pt-phi-6');
    expect(workspaceLayout.pageBottom).toBe('pb-phi-5');
    expect(workspaceLayout.headerBottom).toBe('pb-phi-5');
  });
});
