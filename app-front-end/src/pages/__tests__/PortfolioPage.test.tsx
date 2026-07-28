import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  fetchPortfolioPositions: vi.fn(),
  fetchOutcomeCoverage: vi.fn(),
  fetchOpportunityByLegacyStartup: vi.fn(),
  fetchOutcomes: vi.fn(),
  prepareCrmExport: vi.fn(),
  approveCrmExport: vi.fn(),
}));
vi.mock('../../api/portfolio', async (original) => ({
  ...(await original<typeof import('../../api/portfolio')>()),
  fetchPortfolioPositions: api.fetchPortfolioPositions,
}));
vi.mock('../../api/channelsOutcomes', async (original) => ({
  ...(await original<typeof import('../../api/channelsOutcomes')>()),
  fetchOutcomeCoverage: api.fetchOutcomeCoverage,
  fetchOutcomes: api.fetchOutcomes,
}));
vi.mock('../../api/identity', async (original) => ({
  ...(await original<typeof import('../../api/identity')>()),
  fetchOpportunityByLegacyStartup: api.fetchOpportunityByLegacyStartup,
}));
vi.mock('../../api/crmExport', async (original) => ({
  ...(await original<typeof import('../../api/crmExport')>()),
  prepareCrmExport: api.prepareCrmExport,
  approveCrmExport: api.approveCrmExport,
}));

import PortfolioPage from '../PortfolioPage';
import type { SystemData } from '../../hooks/useSystemData';

const systemData = {
  startups: [
    {
      id: 'startup-1',
      scout: { name: 'Acme', sector: 'Fintech', funding_stage: 'Seed' },
      review: { overall_score: 7.4 },
      partner: { recommendation: 'MONITOR' },
      human_resolution: { decision: 'MAYBE', resolved_at: '2026-07-19T12:00:00Z' },
    },
    {
      id: 'startup-2',
      scout: { name: 'Zeta', sector: 'Health' },
      partner: { recommendation: 'PASS' },
      human_resolution: { decision: 'NO', resolved_at: '2026-07-18T12:00:00Z' },
    },
  ],
  signals: [],
  watchlistAnalytics: { total: 0, stale: 0, avg_days: 0, entries: [] },
  concentrationAnalytics: { by_sector: {}, most_concentrated_sector: null },
} as unknown as SystemData;

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PortfolioPage data={systemData} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PortfolioPage', () => {
  beforeEach(() => {
    Object.values(api).forEach((mock) => mock.mockReset());
    api.fetchOutcomeCoverage.mockResolvedValue({ coverage_ratio: 0.5, limitations: [] });
    api.fetchOpportunityByLegacyStartup.mockResolvedValue({ opportunity_id: 'opportunity-1', company_id: 'company-1' });
    api.fetchOutcomes.mockResolvedValue([]);
    api.fetchPortfolioPositions.mockResolvedValue([
      {
        position_id: 'position-1',
        opportunity_id: 'opportunity-1',
        company_id: 'company-1',
        ruling_id: 'ruling-1',
        status: 'active',
        entry_rationale: 'Retention held through the pricing change.',
        investor_confidence: 0.72,
        entered_at: '2026-07-20T12:00:00Z',
        canonical_name: 'Acme',
        legacy_startup_id: 'startup-1',
      },
    ]);
  });

  it('renders holdings from the canonical positions endpoint', async () => {
    renderPage();
    const rows = await waitFor(() => {
      const found = screen.getAllByTestId('position-row');
      expect(found).toHaveLength(1);
      return found;
    });
    expect(within(rows[0]).getByText('Acme')).toBeInTheDocument();
    expect(within(rows[0]).getByText('Fintech')).toBeInTheDocument();
    expect(api.fetchPortfolioPositions).toHaveBeenCalled();
  });

  it('does not render decided-but-not-held companies as holdings', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('position-row')).toHaveLength(1));
    expect(screen.queryByText('Zeta')).not.toBeInTheDocument();
  });

  it('shows the entry rationale, because why we hold it is the record', async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText('Retention held through the pricing change.')).toBeInTheDocument(),
    );
  });

  it('explains the empty state without inventing positions', async () => {
    api.fetchPortfolioPositions.mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(screen.getByText(/No positions yet/i)).toBeInTheDocument());
  });

  it('offers outcome recording on a position that has a legacy bridge', async () => {
    renderPage();
    const toggle = await screen.findByRole('button', { name: /record outcome/i });
    expect(toggle).toBeEnabled();
  });

  it('offers CRM export preparation on a rendered position', async () => {
    renderPage();
    const button = await screen.findByRole('button', { name: /prepare crm export/i });
    expect(button).toBeEnabled();
    expect(api.prepareCrmExport).not.toHaveBeenCalled();
  });

  it('omits outcome recording when the position has no legacy bridge', async () => {
    api.fetchPortfolioPositions.mockResolvedValue([
      {
        position_id: 'position-2',
        opportunity_id: 'opportunity-2',
        company_id: 'company-2',
        ruling_id: 'ruling-2',
        status: 'active',
        entry_rationale: 'Team quality.',
        investor_confidence: 0.6,
        entered_at: '2026-07-21T12:00:00Z',
        canonical_name: 'Beta',
        legacy_startup_id: null,
      },
    ]);
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('position-row')).toHaveLength(1));
    expect(screen.queryByRole('button', { name: /record outcome/i })).not.toBeInTheDocument();
  });

  it('shows outcome coverage as the headline instrument metric', async () => {
    api.fetchOutcomeCoverage.mockResolvedValue({
      coverage_ratio: 0.5,
      limitations: ['Coverage is operator-reported and not causal.'],
    });
    renderPage();
    expect(await screen.findByText('50%')).toBeInTheDocument();
    expect(screen.getByText(/not causal/i)).toBeInTheDocument();
  });

  it('shows a dash instead of a fabricated 0% when coverage fails to load', async () => {
    api.fetchOutcomeCoverage.mockRejectedValue(new Error('network error'));
    renderPage();
    const section = await waitFor(() => screen.getByLabelText('Outcome coverage'));
    await waitFor(() => expect(within(section).getByText(/unavailable right now/i)).toBeInTheDocument());
    expect(within(section).getByText('—')).toBeInTheDocument();
    expect(within(section).queryByText('0%')).not.toBeInTheDocument();
  });

  it('computes concentration from the positions on screen', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('position-row')).toHaveLength(1));
    expect(screen.getByTestId('concentration-row-Fintech')).toHaveTextContent('100%');
  });

  it('does not show watchlist signals on the portfolio surface', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('position-row')).toHaveLength(1));
    expect(screen.queryByLabelText('Signals')).not.toBeInTheDocument();
  });
});
