import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { Startup } from '../../../types/startup';

const api = vi.hoisted(() => ({
  fetchOpportunityByLegacyStartup: vi.fn(),
  fetchEvidenceLedger: vi.fn(),
  fetchCurrentEvaluation: vi.fn(),
  listHumanRulings: vi.fn(),
}));

vi.mock('../../../api/identity', async (original) => ({
  ...(await original<typeof import('../../../api/identity')>()),
  fetchOpportunityByLegacyStartup: api.fetchOpportunityByLegacyStartup,
}));
vi.mock('../../../api/evidence', async (original) => ({
  ...(await original<typeof import('../../../api/evidence')>()),
  fetchEvidenceLedger: api.fetchEvidenceLedger,
}));
vi.mock('../../../api/evaluations', async (original) => ({
  ...(await original<typeof import('../../../api/evaluations')>()),
  fetchCurrentEvaluation: api.fetchCurrentEvaluation,
}));
vi.mock('../../../api/decisions', async (original) => ({
  ...(await original<typeof import('../../../api/decisions')>()),
  listHumanRulings: api.listHumanRulings,
}));

import InvestmentMemoContent from '../../InvestmentMemoContent';

const startup: Startup = {
  id: 'legacy-unavailable',
  scout: {
    id: 'legacy-unavailable',
    scout_type: 'market_driven',
    name: 'Legacy Context Co',
    one_line: 'A company with a prior workflow record.',
    sector: 'B2B SaaS',
    why_now: 'A specific regulatory change creates a buying window.',
    confidence: 0.7,
    founder_names: ['Ada Byron'],
    company_resolution: {
      query: 'Legacy Context Co',
      canonical_name: 'Legacy Context Co',
      founder_names: ['Ada Byron'],
      missing_fields: ['founder_names', 'linkedin_url'],
      notes: ['Evidence is incomplete — missing: founder_names, linkedin_url.'],
    },
    founder_resolution: {
      company: 'Legacy Context Co',
      resolution_status: 'PARTIAL',
      founders: [],
      missing_fields: ['previous_employment', 'linkedin_url'],
    },
  },
  review: {
    overall_score: 4.8,
    overall_summary: 'The reviewer found a credible wedge but incomplete proof.',
    competition_analysis: ['The category has three well-funded incumbents.'],
    business_model_analysis: ['Retention economics remain undisclosed.'],
    team_analysis: ['Multiple founder signals suggest capable execution.'],
  },
  partner: {
    recommendation: 'PASS',
    decision_rationale: 'The prior workflow passed because regulatory execution was unverified.',
    human_review_required: true,
  },
  timestamps: { discovered_at: '2026-08-15T20:00:00Z' },
};

describe('InvestmentMemoContent unavailable decision state', () => {
  beforeEach(() => {
    vi.stubGlobal('IntersectionObserver', class {
      observe() {}
      unobserve() {}
      disconnect() {}
    });
    api.fetchOpportunityByLegacyStartup.mockResolvedValue({
      opportunity_id: 'opportunity-1',
      company_id: 'company-1',
      context_key: 'primary',
      decision_state: 'monitor',
      service_level: 3,
      legacy_startup_id: startup.id,
      current_evaluation_id: null,
      current_recommendation_id: null,
      current_ruling_id: null,
      created_at: '2026-08-15T20:00:00Z',
      updated_at: '2026-08-15T20:00:00Z',
    });
    api.fetchEvidenceLedger.mockResolvedValue({ artifacts: [], items: [], claims: [], links: [], plans: [] });
    api.fetchCurrentEvaluation.mockRejectedValue(new Error('evaluation unavailable'));
    api.listHumanRulings.mockResolvedValue([]);
  });

  it('keeps the canonical failure authoritative while showing the old workflow as reference', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <InvestmentMemoContent startup={startup} embedded />
      </QueryClientProvider>,
    );

    expect(await screen.findByText('Decision data unavailable')).toHaveAttribute('role', 'status');
    expect(screen.getByRole('heading', { name: 'Prior workflow read' })).toBeInTheDocument();
    expect(screen.getByText('Reference only')).toBeInTheDocument();
    expect(screen.getByText('The prior workflow passed because regulatory execution was unverified.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Assessment' })).not.toBeInTheDocument();
    expect(screen.queryByText('Team assessment')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Company resolution/ }));
    const resolution = screen.getByRole('region', { name: 'Company resolution' });
    expect(resolution).not.toHaveTextContent(/founder_names|founder names/i);
  });
});
