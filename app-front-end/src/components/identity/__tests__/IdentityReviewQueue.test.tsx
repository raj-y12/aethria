import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  fetchIdentityCaseGroups: vi.fn(),
  fetchObservations: vi.fn(),
  resolveIdentityCase: vi.fn(),
  resolveIdentityCaseGroup: vi.fn(),
}));
vi.mock('../../../api/identity', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../api/identity')>()),
  ...mocks,
}));
vi.mock('../../../api/jobs', () => ({ retryJob: vi.fn() }));

import IdentityReviewQueue from '../IdentityReviewQueue';
import type { IdentityCaseGroup, IdentityResolutionCase } from '../../../api/identity';

function caseFor(id: string, observationId: string): IdentityResolutionCase {
  return {
    identity_case_id: id,
    observation_id: observationId,
    status: 'open',
    reason_code: 'insufficient_verified_identifier',
    candidates: [
      { company_id: 'company-1', canonical_name: 'Acme', canonical_domain: 'acme.com', confidence: 0.9, evidence_urls: [], reason: 'Domain match.' },
    ],
    created_at: '2026-07-15T12:00:00Z',
    updated_at: '2026-07-15T12:00:00Z',
  };
}

const group: IdentityCaseGroup = {
  group_key: 'acme.com',
  canonical_domain: 'acme.com',
  observation_count: 2,
  observed_names: ['Acme Inc'],
  sources: ['manual_lookup', 'autonomous_discovery'],
  cases: [caseFor('case-1', 'observation-1'), caseFor('case-2', 'observation-2')],
};

function renderQueue() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <IdentityReviewQueue />
    </QueryClientProvider>,
  );
}

describe('IdentityReviewQueue', () => {
  beforeEach(() => {
    mocks.fetchIdentityCaseGroups.mockReset().mockResolvedValue([group]);
    mocks.fetchObservations.mockReset().mockResolvedValue([]);
    mocks.resolveIdentityCase.mockReset();
    mocks.resolveIdentityCaseGroup.mockReset().mockResolvedValue({ group_key: 'acme.com', results: [] });
  });

  it('renders one row per canonical identity with an observation count, not one per duplicate', async () => {
    renderQueue();

    await waitFor(() => expect(screen.getByText('Acme Inc')).toBeInTheDocument());
    expect(screen.getAllByText(/2 observations/).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: 'Review identity' })).toHaveLength(1);
  });

  it('resolving a grouped case calls the group endpoint, not the single-case endpoint', async () => {
    renderQueue();

    await waitFor(() => expect(screen.getByText('Acme Inc')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Review identity' }));

    fireEvent.click(await screen.findByRole('radio', { name: /Acme/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Match selected company' }));

    await waitFor(() => expect(mocks.resolveIdentityCaseGroup).toHaveBeenCalledWith('acme.com', {
      action: 'match',
      selected_company_id: 'company-1',
      resolution_note: undefined,
    }));
    expect(mocks.resolveIdentityCase).not.toHaveBeenCalled();
  });
});
