import { describe, expect, it } from 'vitest';

import { derivePipelineAvailability } from '../pipelineReadiness';

describe('pipeline availability', () => {
  it('reports agents disabled as off rather than blocked', () => {
    expect(derivePipelineAvailability({ user_agents_enabled: false, agents_will_run: false })).toEqual({
      state: 'off',
      detail: 'Enable at least one agent in Pipeline controls to run the pipeline.',
    });
  });

  it('keeps prerequisite failures blocked when agents are enabled', () => {
    expect(derivePipelineAvailability({ user_agents_enabled: true, agents_will_run: false })).toEqual({
      state: 'blocked',
      detail: null,
    });
  });

  it('reports an enabled and ready pipeline as available', () => {
    expect(derivePipelineAvailability({ user_agents_enabled: true, agents_will_run: true })).toEqual({
      state: 'ready',
      detail: null,
    });
  });
});
