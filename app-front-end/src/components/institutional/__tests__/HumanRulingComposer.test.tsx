import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ createHumanRuling: vi.fn() }));

vi.mock('../../../api/decisions', async (original) => ({
  ...(await original<typeof import('../../../api/decisions')>()),
  createHumanRuling: api.createHumanRuling,
}));

import HumanRulingComposer from '../HumanRulingComposer';

function renderComposer(recommendedDecision?: 'advance' | 'monitor' | 'pass' | 'invest') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <HumanRulingComposer
        opportunityId="opportunity-1"
        recommendationId="recommendation-1"
        recommendedDecision={recommendedDecision}
      />
    </QueryClientProvider>,
  );
}

describe('HumanRulingComposer', () => {
  beforeEach(() => {
    api.createHumanRuling.mockReset();
    api.createHumanRuling.mockResolvedValue({ ruling_id: 'ruling-1', decision: 'advance' });
  });

  it('offers every human ruling action and submits Advance', async () => {
    renderComposer();

    expect(screen.getAllByRole('button').map((button) => button.textContent)).toEqual([
      'Advance',
      'Monitor',
      'Pass',
      'Invest',
      'Commit ruling',
    ]);

    fireEvent.click(screen.getByRole('button', { name: 'Advance' }));
    fireEvent.change(screen.getByLabelText('Ruling rationale'), {
      target: { value: 'Proceed to diligence based on the verified customer signal.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Commit ruling' }));

    await waitFor(() => expect(api.createHumanRuling).toHaveBeenCalledWith(
      'opportunity-1',
      expect.objectContaining({ decision: 'advance' }),
    ));
  });

  it('preselects a recommended Advance ruling', () => {
    renderComposer('advance');

    expect(screen.getByRole('button', { name: 'Advance' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Commit ruling' })).toBeDisabled();
  });
});
