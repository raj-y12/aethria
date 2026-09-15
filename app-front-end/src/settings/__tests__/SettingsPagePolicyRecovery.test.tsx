import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import type { Settings } from '../../api/settings';
import { FUND_CONFIG_STORAGE_KEY, createDefaultFundConfiguration } from '../../lib/fundConfiguration';
import SettingsPage from '../SettingsPage';

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  fetchSettings: vi.fn(),
  patchSettings: vi.fn(),
  publishPolicy: vi.fn(),
}));

vi.mock('react-router', async () => {
  const actual = await vi.importActual<typeof import('react-router')>('react-router');
  return { ...actual, useNavigate: () => mocks.navigate };
});

vi.mock('@clerk/react-router', async () => {
  const actual = await vi.importActual<typeof import('@clerk/react-router')>('@clerk/react-router');
  return { ...actual, useAuth: () => ({ userId: 'user-settings-test' }) };
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

vi.mock('../../hooks', async () => {
  const actual = await vi.importActual<typeof import('../../hooks')>('../../hooks');
  return { ...actual, usePrefersReducedMotion: () => true };
});

function createSettings(fundName = 'Original Fund'): Settings {
  const base: Settings = {
    fund_identity: {
      fund_name: fundName,
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
  return { ...base, fund_config: createDefaultFundConfiguration(base) };
}

function withMandateName(settings: Settings, mandateName: string): Settings {
  return {
    ...settings,
    fund_config: settings.fund_config
      ? {
          ...settings.fund_config,
          mandate: { ...settings.fund_config.mandate, mandateName },
        }
      : settings.fund_config,
  };
}

function renderPage(settings: Settings) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  queryClient.setQueryData(['settings'], settings);
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { ...render(<SettingsPage />, { wrapper: Wrapper }), queryClient };
}

function withPublishedPolicy(settings: Settings, policyId: string): Settings {
  return {
    ...settings,
    fund_config: settings.fund_config
      ? { ...settings.fund_config, activePolicyVersionId: policyId }
      : settings.fund_config,
  };
}

async function failAfterSettingsPatch(initial: Settings, deployed: Settings) {
  mocks.fetchSettings.mockResolvedValue(deployed);
  mocks.patchSettings.mockResolvedValue({ data: deployed });
  mocks.publishPolicy.mockRejectedValueOnce(new Error('Policy service unavailable'));
  const view = renderPage(initial);

  fireEvent.change(await screen.findByLabelText('Fund name'), { target: { value: 'Recovery Fund' } });
  fireEvent.click(screen.getByRole('button', { name: 'Deploy changes' }));
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Deploy policy changes' }));
  await waitFor(() => expect(mocks.publishPolicy).toHaveBeenCalledTimes(1));
  return view;
}

describe('SettingsPage durable policy publish recovery', () => {
  it('explains Partner judgment without exposing retired automatic decision sliders', async () => {
    const settings = createSettings();
    mocks.fetchSettings.mockResolvedValue(settings);
    renderPage(settings);
    expect(await screen.findByRole('heading', { name: 'Investment decisions' })).toBeInTheDocument();
    expect(screen.getByText(/Partner weighs the completed review/)).toBeInTheDocument();
    expect(screen.queryByText('Review threshold')).not.toBeInTheDocument();
    expect(screen.queryByText('Decision thresholds')).not.toBeInTheDocument();
  });

  beforeEach(() => {
    mocks.navigate.mockReset();
    mocks.fetchSettings.mockReset();
    mocks.patchSettings.mockReset();
    mocks.publishPolicy.mockReset();
    window.localStorage.removeItem(FUND_CONFIG_STORAGE_KEY);
    for (const key of Object.keys(window.localStorage)) {
      if (key.startsWith('aethria.settings.policy-publish.v1:')) window.localStorage.removeItem(key);
    }
    Object.defineProperty(window, 'IntersectionObserver', {
      configurable: true,
      value: class { observe() {} disconnect() {} },
    });
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    });
  });

  it('reconciles a clean editor with the authoritative settings response on entry', async () => {
    const cached = withMandateName(createSettings(), 'Cached mandate');
    const fresh = withMandateName(createSettings(), 'Fresh mandate');
    let resolveFresh: ((settings: Settings) => void) | undefined;
    mocks.fetchSettings.mockImplementationOnce(() => new Promise<Settings>((resolve) => {
      resolveFresh = resolve;
    }));

    renderPage(cached);

    expect(await screen.findByRole('textbox', { name: 'Mandate name' })).toHaveValue('Cached mandate');
    await waitFor(() => expect(mocks.fetchSettings).toHaveBeenCalledTimes(1));
    resolveFresh?.(fresh);

    await waitFor(() => expect(screen.getByRole('textbox', { name: 'Mandate name' })).toHaveValue('Fresh mandate'));
  });

  it('preserves an edited draft when the authoritative settings response arrives', async () => {
    const cached = withMandateName(createSettings(), 'Cached mandate');
    const fresh = withMandateName(createSettings(), 'Fresh mandate');
    let resolveFresh: ((settings: Settings) => void) | undefined;
    mocks.fetchSettings.mockImplementationOnce(() => new Promise<Settings>((resolve) => {
      resolveFresh = resolve;
    }));

    const { queryClient } = renderPage(cached);

    const mandateName = await screen.findByRole('textbox', { name: 'Mandate name' });
    await waitFor(() => expect(mocks.fetchSettings).toHaveBeenCalledTimes(1));
    fireEvent.change(mandateName, { target: { value: 'My unsaved mandate' } });
    resolveFresh?.(fresh);

    await waitFor(() => expect(queryClient.getQueryData(['settings'])).toEqual(fresh));
    expect(mandateName).toHaveValue('My unsaved mandate');
  });

  it('keeps later draft edits visible through a real-hook retry and returns them to ordinary draft state', async () => {
    const initial = createSettings();
    const deployed = createSettings('Recovery Fund');
    await failAfterSettingsPatch(initial, deployed);

    fireEvent.change(screen.getByRole('textbox', { name: 'Mandate name' }), {
      target: { value: 'Later draft mandate' },
    });

    mocks.publishPolicy.mockResolvedValueOnce({ policy: { policy_version_id: 'policy-recovered' } });
    mocks.fetchSettings.mockResolvedValue(withPublishedPolicy(deployed, 'policy-recovered'));
    fireEvent.click(screen.getByRole('button', { name: /Retry publish|Deploy changes/ }));

    await waitFor(() => expect(mocks.publishPolicy).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByRole('textbox', { name: 'Mandate name' })).toHaveValue('Later draft mandate'));
    expect(screen.getByRole('status')).toHaveTextContent('Draft changes · 1 pending');
    expect(screen.getByRole('button', { name: 'Deploy changes' })).toBeEnabled();
    expect(mocks.patchSettings).toHaveBeenCalledTimes(1);
  });

  it('distinguishes checkpoint-only recovery from a checkpoint with newer draft edits', async () => {
    const initial = createSettings();
    const deployed = createSettings('Recovery Fund');
    await failAfterSettingsPatch(initial, deployed);

    expect(screen.getByRole('alert')).toHaveTextContent('Scoring policy publish pending');
    expect(screen.getByRole('button', { name: 'Retry publish' })).toBeEnabled();

    fireEvent.change(screen.getByRole('textbox', { name: 'Mandate name' }), {
      target: { value: 'Later draft mandate' },
    });

    expect(screen.getByRole('status')).toHaveTextContent('Scoring policy publish pending · 1 newer draft change');
    expect(screen.getByRole('button', { name: 'Retry publish' })).toBeEnabled();
  });

  it('restores a user-and-fund-scoped checkpoint after remount and clears it only after retry succeeds', async () => {
    const initial = createSettings();
    const deployed = createSettings('Recovery Fund');
    const first = await failAfterSettingsPatch(initial, deployed);

    const recoveryKeys = Object.keys(window.localStorage).filter((key) =>
      key.startsWith('aethria.settings.policy-publish.v1:'),
    );
    expect(recoveryKeys).toHaveLength(1);
    expect(recoveryKeys[0]).toContain('user-settings-test');
    expect(recoveryKeys[0]).toContain('Recovery%20Fund');

    first.unmount();
    mocks.publishPolicy.mockResolvedValueOnce({ policy: { policy_version_id: 'policy-remount' } });
    mocks.fetchSettings.mockResolvedValue(withPublishedPolicy(deployed, 'policy-remount'));
    renderPage(deployed);

    await waitFor(() => expect(screen.getByRole('button', { name: 'Retry publish' })).toBeEnabled());
    expect(screen.getByRole('status')).toHaveTextContent('Scoring policy publish pending');
    fireEvent.click(screen.getByRole('button', { name: 'Retry publish' }));

    await waitFor(() => expect(mocks.publishPolicy).toHaveBeenCalledTimes(2));
    expect(mocks.patchSettings).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Deploy changes' })).toBeDisabled());
    expect(window.localStorage.getItem(recoveryKeys[0])).toBeNull();
  });

  it('does not retry a stale checkpoint when newer authoritative deployable content exists', async () => {
    const initial = createSettings();
    const deployed = createSettings('Recovery Fund');
    const first = await failAfterSettingsPatch(initial, deployed);
    const recoveryKey = Object.keys(window.localStorage).find((key) =>
      key.startsWith('aethria.settings.policy-publish.v1:'),
    )!;
    first.unmount();

    let newer = createSettings('Recovery Fund');
    newer.fund_config = {
      ...newer.fund_config!,
      mandate: { ...newer.fund_config!.mandate, mandateName: 'Newer authoritative mandate' },
    };
    newer = withPublishedPolicy(newer, 'newer-authoritative-policy');
    const removeSpy = vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('storage cleanup blocked');
    });
    try {
      renderPage(newer);

      await waitFor(() => expect(screen.getByRole('textbox', { name: 'Mandate name' }))
        .toHaveValue('Newer authoritative mandate'));
      expect(screen.queryByRole('button', { name: 'Retry publish' })).not.toBeInTheDocument();
      await waitFor(() => expect(screen.getByRole('button', { name: 'Deploy changes' })).toBeDisabled());
      expect(mocks.publishPolicy).toHaveBeenCalledTimes(1);
      expect(window.localStorage.getItem(recoveryKey)).not.toBeNull();
    } finally {
      removeSpy.mockRestore();
    }
  });

  it('keeps checkpoint retry primary while Restore defaults can be undone exactly', async () => {
    const initial = createSettings();
    const deployed = createSettings('Recovery Fund');
    deployed.fund_config = {
      ...deployed.fund_config!,
      mandate: { ...deployed.fund_config!.mandate, mandateName: 'Custom recovery mandate' },
    };
    mocks.fetchSettings.mockResolvedValue(deployed);
    mocks.patchSettings.mockResolvedValue({ data: deployed });
    mocks.publishPolicy.mockRejectedValueOnce(new Error('Policy service unavailable'));
    renderPage(initial);

    fireEvent.change(await screen.findByLabelText('Fund name'), { target: { value: 'Recovery Fund' } });
    fireEvent.change(screen.getByRole('textbox', { name: 'Mandate name' }), {
      target: { value: 'Custom recovery mandate' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Deploy changes' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Deploy policy changes' }));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Scoring policy publish pending'));
    expect(screen.queryByRole('button', { name: 'Undo' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry publish' })).toBeEnabled();

    fireEvent.click(screen.getByRole('button', { name: 'Restore defaults' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Restore defaults' }));

    expect(screen.getByRole('status')).toHaveTextContent('Scoring policy publish pending');
    expect(screen.getByRole('button', { name: 'Undo' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Retry publish' })).toBeEnabled();
    expect(screen.getByRole('textbox', { name: 'Mandate name' })).toHaveValue('Seed mandate');

    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));

    expect(screen.getByRole('textbox', { name: 'Mandate name' })).toHaveValue('Custom recovery mandate');
    expect(screen.getByRole('status')).toHaveTextContent('Scoring policy publish pending');
    expect(screen.queryByRole('button', { name: 'Undo' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry publish' })).toBeEnabled();
    expect(mocks.publishPolicy).toHaveBeenCalledTimes(1);
  });
});
