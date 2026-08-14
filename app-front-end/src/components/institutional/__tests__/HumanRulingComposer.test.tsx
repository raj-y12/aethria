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

/**
 * A ruling is irreversible, so committing one is a two-step act: review, then
 * confirm. Tests drive both steps rather than asserting the old single click.
 */
function commitThroughConfirmation() {
  fireEvent.click(screen.getByRole('button', { name: 'Review ruling' }));
  fireEvent.click(screen.getByRole('button', { name: 'Commit this ruling' }));
}

describe('HumanRulingComposer', () => {
  beforeEach(() => {
    api.createHumanRuling.mockReset();
    api.createHumanRuling.mockResolvedValue({ ruling_id: 'ruling-1', decision: 'advance' });
  });

  it('offers the three opportunity dispositions and submits Advance', async () => {
    renderComposer();

    expect(screen.getAllByRole('button').map((button) => button.textContent)).toEqual([
      'Advance',
      'Monitor',
      'Pass',
      'Review ruling',
    ]);

    fireEvent.click(screen.getByRole('button', { name: 'Advance' }));
    fireEvent.change(screen.getByLabelText('Ruling rationale'), {
      target: { value: 'Proceed to diligence based on the verified customer signal.' },
    });
    commitThroughConfirmation();

    await waitFor(() => expect(api.createHumanRuling).toHaveBeenCalledWith(
      'opportunity-1',
      expect.objectContaining({ decision: 'advance' }),
    ));
  });

  it('invalidates the shared startup list after recording a ruling', async () => {
    const queryClient = createQueryClient();
    queryClient.setQueryData(['startups', 'list'], []);
    render(composer(initialProps, queryClient));

    fireEvent.click(screen.getByRole('button', { name: 'Pass' }));
    fireEvent.change(screen.getByLabelText('Ruling rationale'), {
      target: { value: 'The evidence does not support advancing this company.' },
    });
    commitThroughConfirmation();

    await waitFor(() => expect(queryClient.getQueryState(['startups', 'list'])?.isInvalidated).toBe(true));
  });

  it('invalidates portfolio history and positions after recording a ruling', async () => {
    const queryClient = createQueryClient();
    queryClient.setQueryData(['portfolio-decision-history', 100], []);
    queryClient.setQueryData(['portfolio-positions', 100], []);
    render(composer(initialProps, queryClient));

    fireEvent.click(screen.getByRole('button', { name: 'Pass' }));
    fireEvent.change(screen.getByLabelText('Ruling rationale'), {
      target: { value: 'The evidence does not support advancing this company.' },
    });
    commitThroughConfirmation();

    await waitFor(() => {
      expect(queryClient.getQueryState(['portfolio-decision-history', 100])?.isInvalidated).toBe(true);
      expect(queryClient.getQueryState(['portfolio-positions', 100])?.isInvalidated).toBe(true);
    });
  });

  it('preselects a recommended Advance ruling', () => {
    renderComposer('advance');

    expect(screen.getByRole('button', { name: 'Advance' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Review ruling' })).toBeDisabled();
  });

  it('asks for override attribution on a true recommendation disagreement', () => {
    renderComposer('monitor');

    fireEvent.click(screen.getByRole('button', { name: 'Pass' }));

    expect(screen.getByLabelText('Override attribution')).toBeInTheDocument();
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
    expect(screen.getByLabelText('Override attribution')).toHaveValue('__unanswered');
  });

  it('does not preselect a ruling for insufficient evidence', () => {
    renderComposer('insufficient_evidence');

    for (const label of ['Advance', 'Monitor', 'Pass']) {
      expect(screen.getByRole('button', { name: label })).toHaveAttribute('aria-pressed', 'false');
    }
  });

  it('clears a draft when an unresolved recommendation resolves to insufficient evidence', () => {
    const queryClient = createQueryClient();
    const view = render(composer(initialProps, queryClient));

    fireEvent.click(screen.getByRole('button', { name: 'Pass' }));
    fireEvent.change(screen.getByLabelText('Ruling rationale'), {
      target: { value: 'This draft was entered while the recommendation was loading.' },
    });

    view.rerender(composer({
      ...initialProps,
      recommendedDecision: 'insufficient_evidence',
    }, queryClient));

    for (const label of ['Advance', 'Monitor', 'Pass']) {
      expect(screen.getByRole('button', { name: label })).toHaveAttribute('aria-pressed', 'false');
    }
    expect(screen.getByLabelText('Ruling rationale')).toHaveValue('');
    expect(screen.queryByLabelText('Override attribution')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Pass' }));
    expect(screen.getByLabelText('Override attribution')).toHaveValue('__unanswered');
  });

  it('does not write the ruling until the confirmation is accepted', async () => {
    renderComposer();

    fireEvent.click(screen.getByRole('button', { name: 'Advance' }));
    fireEvent.change(screen.getByLabelText('Ruling rationale'), {
      target: { value: 'Advance on the verified customer signal.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Review ruling' }));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(api.createHumanRuling).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Keep editing' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(api.createHumanRuling).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Ruling rationale')).toHaveValue(
      'Advance on the verified customer signal.',
    );
  });

  it('acknowledges the recorded ruling instead of a silent success line', async () => {
    renderComposer();

    fireEvent.click(screen.getByRole('button', { name: 'Pass' }));
    fireEvent.change(screen.getByLabelText('Ruling rationale'), {
      target: { value: 'The evidence does not support advancing this company.' },
    });
    commitThroughConfirmation();

    expect(await screen.findByText('Recorded')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Done' })).toBeInTheDocument();
  });
});
