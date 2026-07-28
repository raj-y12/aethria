import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ prepareCrmExport: vi.fn(), approveCrmExport: vi.fn() }));
vi.mock('../../../api/crmExport', async (original) => ({
  ...(await original<typeof import('../../../api/crmExport')>()),
  prepareCrmExport: api.prepareCrmExport,
  approveCrmExport: api.approveCrmExport,
}));

import CrmExportAction from '../CrmExportAction';

function wrapper(children: React.ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>);
}

describe('CrmExportAction', () => {
  beforeEach(() => {
    Object.values(api).forEach((mock) => mock.mockReset());
    api.prepareCrmExport.mockResolvedValue({
      workflow_action_id: 'action-1',
      status: 'pending_approval',
      generated_content: {
        external_write_performed: false,
        crm_row: { dedupe_key: 'acme.ai', company_name: 'Acme', decision: 'INVEST', rationale: 'Retention held.' },
      },
    });
    api.approveCrmExport.mockResolvedValue({ workflow_action_id: 'action-1', status: 'approved' });
  });

  it('shows the prepared row and states that nothing has been sent yet', async () => {
    wrapper(<CrmExportAction opportunityId="opportunity-1" companyName="Acme" />);
    fireEvent.click(screen.getByRole('button', { name: /prepare crm export/i }));
    expect(await screen.findByText('acme.ai')).toBeInTheDocument();
    expect(screen.getByText(/nothing has been sent/i)).toBeInTheDocument();
  });

  it('requires an explicit approval click before the export is approved', async () => {
    wrapper(<CrmExportAction opportunityId="opportunity-1" companyName="Acme" />);
    fireEvent.click(screen.getByRole('button', { name: /prepare crm export/i }));
    await screen.findByText('acme.ai');
    expect(api.approveCrmExport).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /approve and download/i }));
    await waitFor(() => expect(api.approveCrmExport).toHaveBeenCalledWith('action-1'));
  });

  it('surfaces a failure without claiming the export succeeded', async () => {
    api.prepareCrmExport.mockRejectedValue(new Error('Opportunity not found'));
    wrapper(<CrmExportAction opportunityId="opportunity-1" companyName="Acme" />);
    fireEvent.click(screen.getByRole('button', { name: /prepare crm export/i }));
    expect(await screen.findByText(/could not prepare/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /approve and download/i })).not.toBeInTheDocument();
  });
});
