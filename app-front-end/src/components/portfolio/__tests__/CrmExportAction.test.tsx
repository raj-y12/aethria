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
import { crmRowToCsv, type CrmRow } from '../../../api/crmExport';

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

  it('surfaces an approval failure instead of rendering nothing', async () => {
    api.approveCrmExport.mockRejectedValue(new Error('Action already approved'));
    wrapper(<CrmExportAction opportunityId="opportunity-1" companyName="Acme" />);
    fireEvent.click(screen.getByRole('button', { name: /prepare crm export/i }));
    await screen.findByText('acme.ai');

    fireEvent.click(screen.getByRole('button', { name: /approve and download/i }));
    expect(await screen.findByText(/could not approve/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /approve and download/i })).toBeInTheDocument();
  });

  it('disables the approve control once approval has succeeded, preventing a second click', async () => {
    // jsdom has no createObjectURL — stub it so the download side effect
    // doesn't throw and mask the success state under test.
    vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:mock'), revokeObjectURL: vi.fn() });
    // A real browser never navigates on this click — the `download` attribute
    // triggers a file save instead. jsdom doesn't model that and logs a
    // "Not implemented: navigation" error; stub click() so the component's
    // download trick doesn't hit jsdom's unimplemented navigation path.
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    wrapper(<CrmExportAction opportunityId="opportunity-1" companyName="Acme" />);
    fireEvent.click(screen.getByRole('button', { name: /prepare crm export/i }));
    await screen.findByText('acme.ai');

    fireEvent.click(screen.getByRole('button', { name: /approve and download/i }));
    await waitFor(() => expect(api.approveCrmExport).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/approved and downloaded/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /approve and download/i })).not.toBeInTheDocument();
    expect(clickSpy).toHaveBeenCalledTimes(1);
    clickSpy.mockRestore();
    vi.unstubAllGlobals();
  });
});

describe('crmRowToCsv', () => {
  it('neutralizes a leading formula character so it is not executed by Excel/Sheets', () => {
    const row = {
      dedupe_key: 'evil.ai',
      company_name: '=HYPERLINK("https://evil.example","click")',
      decision: 'INVEST',
      rationale: '+cmd|/c calc',
    } as CrmRow;
    const csv = crmRowToCsv(row);
    expect(csv).toContain('"\'=HYPERLINK(""https://evil.example"",""click"")"');
    expect(csv).toContain('"\'+cmd|/c calc"');
  });

  it('leaves ordinary text untouched', () => {
    const row = { dedupe_key: 'acme.ai', company_name: 'Acme', decision: 'INVEST', rationale: 'Solid retention.' } as CrmRow;
    const csv = crmRowToCsv(row);
    expect(csv).toContain('"Acme"');
    expect(csv).toContain('"Solid retention."');
  });
});
