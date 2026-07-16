import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { resolveIdentityCase } = vi.hoisted(() => ({ resolveIdentityCase: vi.fn() }));
vi.mock('../../../api/identity', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../../api/identity')>()),
  resolveIdentityCase,
}));

import IdentityResolutionDrawer from '../IdentityResolutionDrawer';
import type { IdentityResolutionCase, SourceObservation } from '../../../api/identity';

const identityCase: IdentityResolutionCase = {
  identity_case_id: 'case-12345678',
  observation_id: 'observation-1',
  status: 'open',
  reason_code: 'multiple_strong_candidates',
  candidates: [
    {
      company_id: 'company-1', canonical_name: 'Acme AI', canonical_domain: 'acme.ai',
      confidence: 0.91, evidence_urls: ['https://acme.ai/about'], reason: 'Domain and founder names align.',
    },
    {
      company_id: 'company-2', canonical_name: 'Acme Systems', canonical_domain: 'acmesystems.com',
      confidence: 0.76, evidence_urls: ['https://acmesystems.com'], reason: 'Name match only.',
    },
  ],
  created_at: '2026-07-15T12:00:00Z',
  updated_at: '2026-07-15T12:00:00Z',
};

const observation: SourceObservation = {
  observation_id: 'observation-1', channel: 'referral', observed_name: 'Acme', observed_domain: 'acme.ai',
  identity_status: 'needs_review', identity_confidence: 0.72,
  observed_at: '2026-07-15T12:00:00Z', created_at: '2026-07-15T12:00:00Z', updated_at: '2026-07-15T12:00:00Z',
};

function renderDrawer() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <IdentityResolutionDrawer identityCase={identityCase} observation={observation} onClose={() => undefined} />
    </QueryClientProvider>,
  );
}

describe('IdentityResolutionDrawer', () => {
  beforeEach(() => resolveIdentityCase.mockReset());

  it('compares candidates without auto-selecting one', () => {
    renderDrawer();

    expect(screen.getByText('Acme AI')).toBeInTheDocument();
    expect(screen.getByText('Acme Systems')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Acme AI/i })).not.toBeChecked();
    expect(screen.getByRole('radio', { name: /Acme Systems/i })).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Match selected company' })).toBeDisabled();
  });

  it('submits the operator-selected company with an audit note', async () => {
    resolveIdentityCase.mockResolvedValue({ status: 'resolved', opportunity_id: 'opportunity-1' });
    renderDrawer();

    fireEvent.click(screen.getByRole('radio', { name: /Acme AI/i }));
    fireEvent.change(screen.getByLabelText('Resolution note'), { target: { value: 'Confirmed from the referral and official domain.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Match selected company' }));

    await waitFor(() => expect(resolveIdentityCase).toHaveBeenCalledWith('case-12345678', {
      action: 'match', selected_company_id: 'company-1',
      resolution_note: 'Confirmed from the referral and official domain.',
    }));
  });

  it('requires an operator-confirmed name and domain to create a canonical company', async () => {
    resolveIdentityCase.mockResolvedValue({ status: 'resolved', opportunity_id: 'opportunity-1' });
    renderDrawer();

    fireEvent.click(screen.getByRole('tab', { name: 'Create new company' }));
    expect(screen.getByRole('button', { name: 'Confirm new company' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Canonical name'), { target: { value: 'Acme' } });
    fireEvent.change(screen.getByLabelText('Canonical domain'), { target: { value: 'acme.ai' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirm new company' }));

    await waitFor(() => expect(resolveIdentityCase).toHaveBeenCalledWith('case-12345678', expect.objectContaining({
      action: 'create', canonical_name: 'Acme', canonical_domain: 'acme.ai',
    })));
  });
});
