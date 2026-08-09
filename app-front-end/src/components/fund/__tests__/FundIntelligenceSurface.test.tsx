import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import type { FundHypothesis, FundObservation } from '../../../api/fundIntelligence';

vi.mock('../../../hooks/useFundIntelligence', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../hooks/useFundIntelligence')>()),
  useFundReplayPreview: () => ({
    data: {
      hypothesis_id: 'hypothesis-1',
      hypothesis_family: 'segment_specific_behavior',
      affected_segment: { dimension: 'sector', value: 'Infrastructure' },
      replay_status: 'not_replayable',
      historical_cases_evaluated: [],
      cases_changed: [],
      cases_unchanged: [],
      cases_indeterminate: ['case-1'],
      original_recommendations: [],
      simulated_recommendations: [],
      mandate_versions: ['mandate-v2'],
      policy_versions: ['policy-v3'],
      time_window: { from: '2025-01-01', to: '2026-01-01' },
      limitations: ['A deterministic policy delta is not defined.'],
      outcome_context_used_for_replay: false,
    },
    isLoading: false,
    isError: false,
  }),
}));

import { FundHypothesesPanel, FundObservationsPanel } from '../FundIntelligenceSurface';

const observation: FundObservation = {
  observation_id: 'observation-1',
  observation_type: 'criterion_tradeoff',
  segment: { dimension: 'sector', value: 'Infrastructure' },
  direction: 'strong technical conviction / weak distribution',
  supporting_case_ids: ['case-1', 'case-2'],
  contradictory_case_ids: ['case-3'],
  sample_size: 3,
  time_window: { from: '2025-01-01', to: '2026-01-01' },
  thesis_versions: ['mandate-v2'],
  mandate_versions: ['mandate-v2'],
  policy_versions: ['policy-v3'],
  metric: {},
  sufficiency: 'moderate',
  descriptive_confidence: 0.72,
  limitations: ['Descriptive association only.'],
  interpretation_as_of: 'latest_retrospective',
  interpretation_provenance: [{
    case_id: 'case-1', ruling_id: 'ruling-1', interpretation_id: 'interpretation-1', version: 2,
    source: 'retrospective_extraction',
  }],
};

const hypothesis: FundHypothesis = {
  hypothesis_id: 'hypothesis-1',
  hypothesis_family: 'segment_specific_behavior',
  statement: 'The fund appears to override more often in Infrastructure.',
  source_observation_ids: ['observation-1'],
  source_observation_types: ['override_rate'],
  segment: { dimension: 'sector', value: 'Infrastructure' },
  supporting_case_ids: ['case-1', 'case-2'],
  contradictory_case_ids: ['case-3'],
  sample_size: 3,
  sufficiency: 'moderate',
  descriptive_confidence: 0.72,
  mandate_versions: ['mandate-v2'],
  thesis_versions: ['mandate-v2'],
  policy_versions: ['policy-v3'],
  time_window: { from: '2025-01-01', to: '2026-01-01' },
  limitations: ['This is a descriptive hypothesis.'],
  status: 'descriptive_hypothesis',
};

function renderPanel(panel: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{panel}</QueryClientProvider>);
}

describe('Fund Intelligence surfaces', () => {
  it('leads with a partner-facing observation and keeps evidence inspectable', () => {
    renderPanel(<FundObservationsPanel data={{
      observations: [observation], hypotheses: [], proposals: [],
      observationsLoading: false, hypothesesLoading: false, observationsError: false, hypothesesError: false,
      retryObservations: vi.fn(), retryHypotheses: vi.fn(),
    }} />);

    expect(screen.getByText('The fund appears to tolerate weak Distribution when Technical Conviction is strong.')).toBeInTheDocument();
    expect(screen.getByText('Criterion trade-off')).toBeInTheDocument();
    expect(screen.getByText('2 supporting')).toBeInTheDocument();
    expect(screen.queryByText(/prompt mutation|scout weights|calibration cycle/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Inspect evidence →' }));
    const inspector = screen.getByRole('dialog', { name: /the fund appears/i });
    expect(within(inspector).getByText('Decision reference · case-1')).toBeInTheDocument();
    expect(within(inspector).getByText(/Retrospective interpretation provenance/)).toBeInTheDocument();
  });

  it('contains inspector focus and restores focus to the evidence opener', () => {
    renderPanel(<FundObservationsPanel data={{
      observations: [observation], hypotheses: [], proposals: [],
      observationsLoading: false, hypothesesLoading: false, observationsError: false, hypothesesError: false,
      retryObservations: vi.fn(), retryHypotheses: vi.fn(),
    }} />);

    const opener = screen.getByRole('button', { name: 'Inspect evidence →' });
    opener.focus();
    fireEvent.click(opener);

    const inspector = screen.getByRole('dialog', { name: /the fund appears/i });
    const close = within(inspector).getByRole('button', { name: 'Close evidence inspector' });
    expect(screen.getByRole('heading', { name: /the fund appears/i })).toHaveFocus();

    close.focus();
    const forwardTab = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
    document.dispatchEvent(forwardTab);
    expect(forwardTab.defaultPrevented).toBe(true);
    expect(close).toHaveFocus();

    const reverseTab = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true });
    document.dispatchEvent(reverseTab);
    expect(reverseTab.defaultPrevented).toBe(true);
    expect(close).toHaveFocus();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it('keeps hypotheses tentative and exposes governed replay status on inspection', () => {
    renderPanel(<FundHypothesesPanel data={{
      observations: [observation], hypotheses: [hypothesis], proposals: [{
        proposal_id: 'proposal-1', source_hypothesis_id: 'hypothesis-1', source_hypothesis_family: 'segment_specific_behavior',
        proposal_status: 'insufficient_basis', replay_compatibility: 'not_ready', supporting_case_ids: ['case-1', 'case-2'],
        contradictory_case_ids: ['case-3'], limitations: ['No deterministic policy delta.'],
      }],
      observationsLoading: false, hypothesesLoading: false, observationsError: false, hypothesesError: false,
      retryObservations: vi.fn(), retryHypotheses: vi.fn(),
    }} />);

    expect(screen.getByText('Tentative hypothesis · segment specific behavior')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Inspect basis →' }));
    const inspector = screen.getByRole('dialog', { name: hypothesis.statement });
    expect(within(inspector).getByText('Replay: Not replayable')).toBeInTheDocument();
    expect(within(inspector).getByText('Counterfactual: Insufficient basis')).toBeInTheDocument();
    expect(within(inspector).getByText(/No later outcome observations were used/)).toBeInTheDocument();
  });
});
