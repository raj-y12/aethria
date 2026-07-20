import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { RecommendationState } from '../../../api/evaluations';

const api = vi.hoisted(() => ({ createHumanRuling: vi.fn() }));

vi.mock('../../../api/decisions', async (original) => ({
  ...(await original<typeof import('../../../api/decisions')>()),
  createHumanRuling: api.createHumanRuling,
}));

import HumanRulingComposer from '../HumanRulingComposer';

type ComposerProps = {
  opportunityId: string;
  recommendationId: string | null;
  recommendedDecision?: RecommendationState | null;
};

const initialProps: ComposerProps = {
  opportunityId: 'opportunity-1',
  recommendationId: 'recommendation-1',
};

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function composer(props: ComposerProps, queryClient: QueryClient) {
  return (
    <QueryClientProvider client={queryClient}>
      <HumanRulingComposer {...props} />
    </QueryClientProvider>
  );
}

function renderComposer(recommendedDecision?: RecommendationState) {
  const queryClient = createQueryClient();
  return render(
    composer({ ...initialProps, recommendedDecision }, queryClient),
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

  it.each([
    ['opportunity identity', { opportunityId: 'opportunity-2' }, 'Advance'],
    ['recommendation identity', { recommendationId: 'recommendation-2' }, 'Advance'],
    ['recommendation state', { recommendedDecision: 'monitor' as const }, 'Monitor'],
  ])('clears draft state at the %s boundary', (_boundary, changedProps, expectedDecision) => {
    const queryClient = createQueryClient();
    const props: ComposerProps = { ...initialProps, recommendedDecision: 'advance' };
    const view = render(composer(props, queryClient));

    fireEvent.click(screen.getByRole('button', { name: 'Pass' }));
    fireEvent.change(screen.getByLabelText('Ruling rationale'), {
      target: { value: 'This rationale belongs only to opportunity A.' },
    });
    fireEvent.change(screen.getByLabelText('Override attribution'), {
      target: { value: 'timing' },
    });

    view.rerender(composer({ ...props, ...changedProps }, queryClient));

    expect(screen.getByRole('button', { name: expectedDecision })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByLabelText('Ruling rationale')).toHaveValue('');
    expect(screen.queryByLabelText('Override attribution')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Pass' }));
    expect(screen.getByLabelText('Override attribution')).toHaveValue('');
  });

  it('does not preselect a ruling for insufficient evidence', () => {
    renderComposer('insufficient_evidence');

    for (const label of ['Advance', 'Monitor', 'Pass', 'Invest']) {
      expect(screen.getByRole('button', { name: label })).toHaveAttribute('aria-pressed', 'false');
    }
  });
});
