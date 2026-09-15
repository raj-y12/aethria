import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import PipelineProvenanceInspector from '../PipelineProvenanceInspector';
import { buildMemoDecisionBrief } from '../../../lib/memoDecisionBrief';

const props = {
  startup: { id: 'private-run', scout: { id: 's1', scout_type: 'test', name: '', one_line: '', sector: '', why_now: '', confidence: 0 } },
  brief: buildMemoDecisionBrief({}),
  scorecardEnabled: true,
};
afterEach(() => { cleanup(); vi.unstubAllEnvs(); });
describe('development provenance inspector', () => {
  it('renders nothing in production', () => {
    vi.stubEnv('DEV', false);
    const { container } = render(<PipelineProvenanceInspector {...props} />);
    expect(container.innerHTML).toBe('');
  });
  it('offers a collapsed inspector in development', () => {
    vi.stubEnv('DEV', true);
    render(<PipelineProvenanceInspector {...props} />);
    expect(screen.getByText('Development provenance').closest('details')).not.toHaveAttribute('open');
  });
});
