import { createElement } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import appSource from '../../App.tsx?raw';
import type { Settings } from '../../api/settings';
import {
  createDefaultFundConfiguration,
  type FundConfiguration,
} from '../../lib/fundConfiguration';
import operationsSource from '../OperationsStrip.tsx?raw';
import railSource from '../SettingsRail.tsx?raw';
import topBarSource from '../SettingsTopBar.tsx?raw';
import source from '../SettingsPage.tsx?raw';
import SettingsPage from '../SettingsPage';

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  fetchSettings: vi.fn(),
  patchSettings: vi.fn(),
  publishPolicy: vi.fn(),
  setConfiguration: vi.fn(),
  saveLocalConfiguration: vi.fn(),
}));

vi.mock('react-router', async () => {
  const actual = await vi.importActual<typeof import('react-router')>('react-router');
  return { ...actual, useNavigate: () => mocks.navigate };
});

vi.mock('@clerk/react-router', async () => {
  const actual = await vi.importActual<typeof import('@clerk/react-router')>('@clerk/react-router');
  return { ...actual, useAuth: () => ({ userId: 'user-settings-layout-test' }) };
});

vi.mock('../../api/settings', async () => {
  const actual = await vi.importActual<typeof import('../../api/settings')>('../../api/settings');
  return {
    ...actual,
    fetchSettings: mocks.fetchSettings,
    patchSettings: mocks.patchSettings,
    publishPolicy: mocks.publishPolicy,
  };
});

vi.mock('../../api/agents', async () => {
  const actual = await vi.importActual<typeof import('../../api/agents')>('../../api/agents');
  return {
    ...actual,
    fetchAgentsStatus: vi.fn(() => Promise.resolve({
      supabase_configured: true,
      openai_configured: true,
      worker_ready: true,
      agents_infrastructure_ready: true,
      lookup_infrastructure_ready: true,
      execution_prerequisites_ready: true,
      published_policy_ready: true,
      agents_will_run: true,
      lookup_will_run: true,
    })),
  };
});

vi.mock('../../api/fundThesis', async () => {
  const actual = await vi.importActual<typeof import('../../api/fundThesis')>('../../api/fundThesis');
  return {
    ...actual,
    fetchFundThesisSummary: vi.fn(() => Promise.resolve({ active_version_number: null })),
  };
});

let liveConfiguration: FundConfiguration;

vi.mock('../../hooks', async () => {
  const actual = await vi.importActual<typeof import('../../hooks')>('../../hooks');
  return {
    ...actual,
    usePrefersReducedMotion: () => true,
    useFundConfiguration: () => ({
      configuration: liveConfiguration,
      setConfiguration: mocks.setConfiguration,
      save: mocks.saveLocalConfiguration,
    }),
  };
});

const settings: Settings = {
  fund_identity: {
    fund_name: 'Default Identity',
    stage_focus: 'Seed',
    geographic_focus: 'Europe',
  },
  agent_config: {
    scouts_enabled: true,
    reviewers_enabled: true,
    partners_enabled: true,
    max_agents_per_run: 4,
    confidence_threshold: 0.65,
    scout_region: 'europe',
  },
  cost_budget: {
    enabled: true,
    max_tokens_per_run: 80_000,
    daily_cost_ceiling: 25,
    weekly_cost_ceiling: 100,
    cooldown_seconds: 300,
  },
  portfolio: {
    auto_watchlist: true,
    signal_scan_frequency: 'daily',
    memo_verbosity: 'standard',
  },
};

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  queryClient.setQueryData(['settings'], settings);
  return render(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(SettingsPage),
    ),
  );
}

function renderUnavailablePage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(SettingsPage),
    ),
  );
}

describe('Settings focused-mode layout contract', () => {
  it('dissolves the app spine like the front door (bare chrome)', () => {
    // The chrome decision must NOT force Settings to 'full'; it joins the
    // bare/takeover surfaces alongside the front door.
    expect(appSource).toContain("chrome={!isPortfolioRoute && !isFundRoute && !isFlowRoute ? 'bare' : 'full'}");
    expect(appSource).not.toContain("!isSettingsRoute && !isPortfolioRoute");
  });

  it('is a top bar + navigation rail over one scrolling reading column', () => {
    expect(source).toContain('<SettingsTopBar');
    expect(source).toContain('<SettingsRail');
    expect(source).toContain('<SettingsMobileNav');
    expect(source).toContain('ref={contentScrollRef}');
    expect(source).toContain('overscroll-contain bg-paper');
  });

  it('keeps the settings rail on the app spine geometry', () => {
    expect(railSource).toContain("import { SPINE_WIDTH } from '../components/AppSpine';");
    expect(railSource).toContain('style={{ width: SPINE_WIDTH }}');
    expect(railSource).toContain('px-phi-4 pb-phi-4 pt-phi-5');
  });

  it('states the persistence model truthfully', () => {
    expect(source).toContain('title="Fund thesis"');
    expect(source).toContain('title="Decision policy"');
    expect(source).toContain('title="Workspace runtime"');
    expect(source).toContain('title="System"');
    expect(source).toContain('Changes stay in draft until you deploy a new policy version.');
    expect(source).toContain('Changes here save immediately and affect the running system.');
    expect(operationsSource).toContain('These controls save immediately.');
    expect(operationsSource).toContain('aria-label="Pipeline controls"');
  });

  it('replaces tabs with a scroll-spy of stacked sections', () => {
    expect(source).toContain('IntersectionObserver');
    expect(source).toContain("divide-y divide-oxford/[0.06]");
    expect(source).not.toContain("role=\"tablist\"");
    expect(source).not.toContain('activeTab');
    expect(source).not.toContain('lg:grid-cols-[minmax(0,61.8fr)_minmax(0,38.2fr)]');
  });

  it('offsets mobile section targets below the sticky navigator without changing desktop', () => {
    expect(source).toContain('scroll-mt-16');
    expect(source).toContain('lg:scroll-mt-0');
  });

  it('keeps every configuration section in the single column', () => {
    expect(source).toContain('The mandate');
    expect(source).toContain('Decision mechanics');
    expect(source).toContain('Scoring weights');
    expect(source).toContain('Memo output');
    expect(source).toContain('Ruling workflow');
    expect(source).toContain('Cost budget');
    expect(source).toContain('System state');
    expect(source).not.toContain('function SettingsSection');
  });

  it('does not hijack the spine — it removes it', () => {
    expect(source).not.toContain('setSpineOverride');
    expect(source).not.toContain('SpineNavButton');
  });

  it('keeps the rounded switch language', () => {
    expect(source).toContain('rounded-full');
    expect(source).toContain('rounded-full border transition-colors');
    expect(operationsSource).toContain('rounded-full');
  });

  it('uses safe top-bar action language and 44px targets', () => {
    expect(topBarSource).toContain('Restore defaults');
    expect(topBarSource).toContain('min-h-11');
    expect(source).toContain('requestExit');
  });

  it('sizes solid recovery and deployment actions to the log-out button scale', () => {
    // Canonical btn-aethria-solid (11px, 36px) — no 12px or 44px override.
    expect(source).toContain('btn-aethria-solid disabled');
    expect(source).not.toContain('btn-aethria-solid min-h-11');
    expect(topBarSource).toContain('btn-aethria-solid shrink-0 disabled');
    expect(topBarSource).not.toContain('btn-aethria-solid min-h-11');
  });

  it('shows exact execution-policy readiness separately from infrastructure', () => {
    expect(source).toContain('agentsStatus.execution_prerequisites_ready');
    expect(source).toContain('agentsStatus.execution_prerequisite_detail');
    expect(source).toContain('label="Execution policy"');
  });
});

describe('Settings safe draft actions', () => {
  beforeEach(() => {
    liveConfiguration = {
      ...createDefaultFundConfiguration(settings),
      mandate: {
        ...createDefaultFundConfiguration(settings).mandate,
        fundName: 'Last Live Fund',
      },
      activePolicyVersionId: 'policy-live',
    };
    settings.fund_config = liveConfiguration;
    mocks.navigate.mockReset();
    mocks.fetchSettings.mockReset();
    mocks.fetchSettings.mockResolvedValue(settings);
    mocks.patchSettings.mockReset();
    mocks.publishPolicy.mockReset();
    mocks.setConfiguration.mockReset();
    mocks.saveLocalConfiguration.mockReset();
    mocks.saveLocalConfiguration.mockImplementation((configuration: FundConfiguration) => configuration);
    for (const key of Object.keys(window.localStorage)) {
      if (key.startsWith('aethria.settings.policy-publish.v1:')) window.localStorage.removeItem(key);
    }
    Object.defineProperty(window, 'IntersectionObserver', {
      configurable: true,
      value: class {
        observe() {}
        disconnect() {}
      },
    });
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    });
  });

  it('confirms restore, changes only the draft, and offers an exact Undo', async () => {
    renderPage();
    const fundName = await screen.findByLabelText('Fund name');
    fireEvent.change(fundName, { target: { value: 'Working Draft Fund' } });

    fireEvent.click(screen.getByRole('button', { name: 'Restore defaults' }));
    const restoreDialog = screen.getByRole('dialog', { name: 'Restore default settings?' });
    fireEvent.click(within(restoreDialog).getByRole('button', { name: 'Restore defaults' }));

    await waitFor(() => expect(screen.getByLabelText('Fund name')).toHaveValue('Default Identity'));
    expect(mocks.patchSettings).not.toHaveBeenCalled();
    expect(mocks.publishPolicy).not.toHaveBeenCalled();
    expect(mocks.setConfiguration).not.toHaveBeenCalled();
    expect(screen.getByText('Defaults restored')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Aethria/i }));
    expect(screen.getByRole('dialog', { name: 'Leave settings?' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Keep editing' }));
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Leave settings?' })).not.toBeInTheDocument());
    expect(mocks.navigate).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(screen.getByLabelText('Fund name')).toHaveValue('Working Draft Fund');
    expect(screen.getByRole('status')).toHaveTextContent('Draft changes · 1 pending');
  });

  it('keeps a partial policy publish retryable and skips the already-deployed thesis step', async () => {
    const deployedConfiguration = {
      ...liveConfiguration,
      mandate: { ...liveConfiguration.mandate, fundName: 'Retryable Fund' },
    };
    const deployedSettings = { ...settings, fund_config: deployedConfiguration };
    mocks.fetchSettings.mockResolvedValueOnce(settings).mockResolvedValue(deployedSettings);
    mocks.patchSettings.mockResolvedValue({ data: deployedSettings });
    mocks.publishPolicy
      .mockRejectedValueOnce(new Error('Policy service unavailable'))
      .mockResolvedValueOnce({ policy: { policy_version_id: 'policy-retry' } });
    renderPage();

    fireEvent.change(await screen.findByLabelText('Fund name'), { target: { value: 'Retryable Fund' } });
    fireEvent.click(screen.getByRole('button', { name: 'Deploy changes' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Confirm update' }));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('scoring policy did not publish'));
    expect(screen.getByRole('button', { name: 'Retry publish' })).not.toBeDisabled();
    expect(mocks.patchSettings).toHaveBeenCalledTimes(1);
    expect(mocks.publishPolicy).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Retry publish' }));

    await waitFor(() => expect(mocks.publishPolicy).toHaveBeenCalledTimes(2));
    expect(mocks.patchSettings).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('configuration is live'));
    expect(screen.getByRole('button', { name: 'Deploy changes' })).toBeDisabled();
  });

  it('clears deployment state and exposes an actionable error when settings PATCH rejects', async () => {
    mocks.patchSettings.mockRejectedValue(new Error('Settings network unavailable'));
    renderPage();

    fireEvent.change(await screen.findByLabelText('Fund name'), { target: { value: 'Rejected Deploy Fund' } });
    fireEvent.click(screen.getByRole('button', { name: 'Deploy changes' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Confirm update' }));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Settings network unavailable'));
    expect(screen.getByRole('button', { name: 'Deploy changes' })).not.toBeDisabled();
    expect(screen.getByRole('button', { name: 'Restore defaults' })).not.toBeDisabled();
  });

  it('publishes the retry checkpoint without overwriting edits made after the failure', async () => {
    const checkpointConfiguration = {
      ...liveConfiguration,
      mandate: { ...liveConfiguration.mandate, fundName: 'Checkpoint Fund' },
    };
    const checkpointSettings = { ...settings, fund_config: checkpointConfiguration };
    mocks.fetchSettings.mockResolvedValueOnce(settings).mockResolvedValue(checkpointSettings);
    mocks.patchSettings.mockResolvedValue({ data: checkpointSettings });
    mocks.publishPolicy
      .mockRejectedValueOnce(new Error('Policy service unavailable'))
      .mockResolvedValueOnce({ policy: { policy_version_id: 'policy-checkpoint' } });
    renderPage();

    fireEvent.change(await screen.findByLabelText('Fund name'), { target: { value: 'Checkpoint Fund' } });
    fireEvent.click(screen.getByRole('button', { name: 'Deploy changes' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Confirm update' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('scoring policy did not publish'));

    fireEvent.change(screen.getByRole('textbox', { name: 'Mandate name' }), { target: { value: 'Later draft mandate' } });
    fireEvent.click(screen.getByRole('button', { name: 'Retry publish' }));

    await waitFor(() => expect(mocks.publishPolicy).toHaveBeenCalledTimes(2));
    expect(mocks.patchSettings).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('textbox', { name: 'Mandate name' })).toHaveValue('Later draft mandate');
    expect(screen.getByRole('status')).toHaveTextContent('Draft changes · 1 pending');
    expect(screen.getByRole('button', { name: 'Deploy changes' })).not.toBeDisabled();
  });

  it('keeps editing or discards to the last live configuration before leaving', async () => {
    renderPage();
    const fundName = await screen.findByLabelText('Fund name');
    fireEvent.change(fundName, { target: { value: 'Exit Draft Fund' } });

    fireEvent.click(screen.getByRole('button', { name: /Aethria/i }));
    expect(screen.getByRole('dialog', { name: 'Leave settings?' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Keep editing' }));
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Leave settings?' })).not.toBeInTheDocument());
    expect(mocks.navigate).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /Aethria/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Discard and leave' }));
    expect(screen.getByLabelText('Fund name')).toHaveValue('Last Live Fund');
    expect(mocks.navigate).toHaveBeenCalledWith('/v1');
  });

  it('navigates immediately when no deployable policy changes exist', async () => {
    renderPage();
    await screen.findByLabelText('Fund name');

    fireEvent.click(screen.getByRole('button', { name: /Aethria/i }));

    expect(mocks.navigate).toHaveBeenCalledWith('/v1');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('offers retry and back actions when settings are unavailable', async () => {
    let finishRetry: ((value: null) => void) | undefined;
    const retryRequest = new Promise<null>((resolve) => { finishRetry = resolve; });
    mocks.fetchSettings
      .mockRejectedValueOnce(new Error('settings unavailable'))
      .mockImplementationOnce(() => retryRequest);
    renderUnavailablePage();

    const retry = await screen.findByRole('button', { name: 'Retry' });
    fireEvent.click(retry);

    await waitFor(() => expect(mocks.fetchSettings).toHaveBeenCalledTimes(2));
    expect(retry).toBeDisabled();
    expect(retry).toHaveAttribute('aria-busy', 'true');

    fireEvent.click(screen.getByRole('button', { name: 'Back to Aethria' }));
    expect(mocks.navigate).toHaveBeenCalledWith('/v1');

    finishRetry?.(null);
    await waitFor(() => expect(retry).not.toBeDisabled());
  });

  it('routes a deployment validation error to the affected section', async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoView,
    });
    mocks.patchSettings.mockResolvedValue({
      error: { message: 'Fund thesis is required', errors: [] },
    });
    renderPage();

    fireEvent.change(await screen.findByLabelText('Fund name'), {
      target: { value: 'Validation Route Fund' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Deploy changes' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Confirm update' }));

    const thesisSection = document.getElementById('thesis');
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Fund thesis is required'));
    await waitFor(() => expect(thesisSection).toHaveFocus());
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'auto', block: 'start' });
    expect(screen.getByRole('button', { name: /Mandate — Needs attention/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Thesis — Needs attention' })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Fund name'), {
      target: { value: 'Corrected Thesis Fund' },
    });
    expect(screen.getByRole('button', { name: /Mandate — Needs attention/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Thesis — Needs attention' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Restore defaults' }));
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Restore default settings?' })).getByRole('button', { name: 'Restore defaults' }));
    expect(screen.getByRole('button', { name: /Mandate — Needs attention/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(screen.getByRole('button', { name: /Mandate — Needs attention/ })).toBeInTheDocument();

    const correctedConfiguration = {
      ...liveConfiguration,
      mandate: { ...liveConfiguration.mandate, fundName: 'Corrected Thesis Fund' },
    };
    const correctedSettings = { ...settings, fund_config: correctedConfiguration };
    mocks.patchSettings.mockResolvedValueOnce({ data: correctedSettings });
    mocks.publishPolicy.mockResolvedValueOnce({ policy: { policy_version_id: 'policy-corrected' } });
    mocks.fetchSettings.mockResolvedValue(correctedSettings);
    fireEvent.click(screen.getByRole('button', { name: 'Deploy changes' }));
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Confirm the new mandate' })).getByRole('button', { name: 'Confirm update' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: /Mandate — Needs attention/ })).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Restore defaults' }));
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Restore default settings?' })).getByRole('button', { name: 'Restore defaults' }));
    expect(screen.queryByRole('button', { name: /Mandate — Needs attention/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(screen.queryByRole('button', { name: /Mandate — Needs attention/ })).not.toBeInTheDocument();
  });
});
