export type PipelineAvailability = 'unavailable' | 'off' | 'ready' | 'blocked';

export function derivePipelineAvailability(status: {
  user_agents_enabled?: boolean;
  agents_will_run: boolean;
} | null): { state: PipelineAvailability; detail: string | null } {
  if (!status) return { state: 'unavailable', detail: null };
  if (status.user_agents_enabled === false) {
    return {
      state: 'off',
      detail: 'Enable at least one agent in Pipeline controls to run the pipeline.',
    };
  }
  return status.agents_will_run
    ? { state: 'ready', detail: null }
    : { state: 'blocked', detail: null };
}
