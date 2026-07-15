import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  importCsv: vi.fn(), fetchOpportunityByLegacyStartup: vi.fn(), fetchOutcomes: vi.fn(),
  createOutcome: vi.fn(), fetchOutcomeCoverage: vi.fn(),
}));
vi.mock('../../../api/channelsOutcomes', async (original) => ({
  ...(await original<typeof import('../../../api/channelsOutcomes')>()),
  importCsv: api.importCsv, fetchOutcomes: api.fetchOutcomes, createOutcome: api.createOutcome,
  fetchOutcomeCoverage: api.fetchOutcomeCoverage,
}));
vi.mock('../../../api/identity', async (original) => ({
  ...(await original<typeof import('../../../api/identity')>()),
  fetchOpportunityByLegacyStartup: api.fetchOpportunityByLegacyStartup,
}));

import CsvImportDrawer from '../CsvImportDrawer';
import OutcomePanel from '../OutcomePanel';

function wrapper(children: React.ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>);
}

describe('channel intake and outcomes', () => {
  beforeEach(() => {
    Object.values(api).forEach((mock) => mock.mockReset());
    api.importCsv.mockResolvedValue({ import_batch_id: 'batch-1', status: 'completed', total_rows: 2, resolved_rows: 1, review_rows: 1 });
    api.fetchOpportunityByLegacyStartup.mockResolvedValue({ opportunity_id: 'opportunity-1', company_id: 'company-1', service_level: 3 });
    api.fetchOutcomes.mockResolvedValue([]);
    api.fetchOutcomeCoverage.mockResolvedValue({ total_companies: 10, companies_with_outcomes: 4, coverage_rate: 0.4, verified_outcomes: 2 });
    api.createOutcome.mockResolvedValue({ outcome_observation_id: 'outcome-1' });
  });

  it('previews CSV rows before committing with an idempotency key', async () => {
    wrapper(<CsvImportDrawer open onClose={() => undefined} />);
    fireEvent.change(screen.getByLabelText('CSV data'), { target: { value: 'company_name,website\nAcme,acme.ai\nBeta,beta.com' } });
    fireEvent.click(screen.getByRole('button', { name: 'Preview import' }));

    expect(screen.getByText('2 rows ready for bounded import')).toBeInTheDocument();
    expect(api.importCsv).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Commit import' }));
    await waitFor(() => expect(api.importCsv).toHaveBeenCalledWith(expect.objectContaining({
      csv_text: expect.stringContaining('Acme,acme.ai'), idempotency_key: expect.stringMatching(/^csv-/),
    })));
    expect(await screen.findByText(/batch-1/i)).toBeInTheDocument();
  });

  it('discloses outcome coverage and records attributed company outcomes', async () => {
    wrapper(<OutcomePanel startupId="startup-1" />);
    expect(await screen.findByText('40% coverage')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Outcome summary'), { target: { value: 'Closed a verified seed financing.' } });
    fireEvent.change(screen.getByLabelText('Outcome materiality'), { target: { value: '4' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }));
    await waitFor(() => expect(api.createOutcome).toHaveBeenCalledWith('company-1', expect.objectContaining({
      opportunity_id: 'opportunity-1', outcome_type: 'financing', summary: 'Closed a verified seed financing.', materiality: 4,
    })));
  });
});
