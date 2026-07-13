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
import topBarSource from '../SettingsTopBar.tsx?raw';
import source from '../SettingsPage.tsx?raw';
import SettingsPage from '../SettingsPage';

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  patchSettings: vi.fn(),
  publishPolicy: vi.fn(),
  setConfiguration: vi.fn(),
  saveLocalConfiguration: vi.fn(),
}));

vi.mock('react-router', async () => {
  const actual = await vi.importActual<typeof import('react-router')>('react-router');
  return { ...actual, useNavigate: () => mocks.navigate };
});

vi.mock('../../api/settings', async () => {
  const actual = await vi.importActual<typeof import('../../api/settings')>('../../api/settings');
  return {
    ...actual,
    fetchSettings: vi.fn(() => Promise.resolve(settings)),
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
      agents_will_run: true,
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

  it('states the persistence model truthfully', () => {
    expect(source).toContain('title="Fund policy"');
    expect(source).toContain('Changes here stay in draft until you deploy a new version.');
    expect(source).toContain('title="Live runtime"');
    expect(source).toContain('Changes here save immediately and affect the running system.');
    expect(operationsSource).toContain('These controls save immediately.');
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
    mocks.patchSettings.mockReset();
    mocks.publishPolicy.mockReset();
    mocks.setConfiguration.mockReset();
    mocks.saveLocalConfiguration.mockReset();
    Object.defineProperty(window, 'IntersectionObserver', {
      configurable: true,
      value: class {
        observe() {}
        disconnect() {}
      },
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
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });
    expect(screen.getByRole('button', { name: /Fund thesis — Needs attention/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Thesis — Needs attention' })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Fund name'), {
      target: { value: 'Corrected Thesis Fund' },
    });
    expect(screen.queryByRole('button', { name: /Fund thesis — Needs attention/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Thesis — Needs attention' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Deploy changes' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Confirm update' }));
    await waitFor(() => expect(screen.getByRole('button', { name: /Fund thesis — Needs attention/ })).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Restore defaults' }));
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Restore default settings?' })).getByRole('button', { name: 'Restore defaults' }));
    expect(screen.queryByRole('button', { name: /Fund thesis — Needs attention/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(screen.queryByRole('button', { name: /Fund thesis — Needs attention/ })).not.toBeInTheDocument();
  });
});
