import { fireEvent, render, screen } from '@testing-library/react';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import type { Settings } from '../../api/settings';
import SettingsRoomChrome from '../SettingsRoomChrome';

vi.mock('../OperationsStrip', () => ({
  default: () => <div data-testid="operations-strip">Pipeline controls</div>,
}));

const settings: Settings = {
  agent_config: {
    scouts_enabled: true,
    reviewers_enabled: true,
    partners_enabled: true,
    max_agents_per_run: 4,
    confidence_threshold: 0.65,
    scout_region: 'europe',
    scout_grounded_citations_enabled: true,
    scout_fail_closed_on_empty_retrieval: true,
  },
  cost_budget: {
    enabled: true,
    max_tokens_per_run: 80_000,
    daily_cost_ceiling: 24,
    weekly_cost_ceiling: 120,
    cooldown_seconds: 300,
  },
  portfolio: {
    auto_watchlist: true,
    signal_scan_frequency: 'daily',
    memo_verbosity: 'standard',
  },
};

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: true,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

function renderChrome(overrides: Partial<React.ComponentProps<typeof SettingsRoomChrome>> = {}) {
  const props: React.ComponentProps<typeof SettingsRoomChrome> = {
    activeTab: 'decision',
    settings,
    storageUnavailable: false,
    pendingChanges: [{ label: 'Mandate', stages: 'Scout · Reviewer' }],
    saving: false,
    thesisVersion: 'Fund Thesis v5',
    policyVersion: 'policy-v4',
    onSettingsChange: vi.fn(),
    onTabChange: vi.fn(),
    onTabKeyDown: vi.fn(),
    onDeploy: vi.fn(),
    onReset: vi.fn(),
    ...overrides,
  };
  render(<SettingsRoomChrome {...props} />);
  return props;
}

describe('SettingsRoomChrome', () => {
  it('uses the Fund room hierarchy and keeps operations above the tabs', () => {
    renderChrome();

    expect(screen.getByRole('heading', { name: /^settings\s*\.$/i })).toBeInTheDocument();
    expect(screen.getByText('The operating model')).toBeInTheDocument();
    expect(screen.getByText('Draft')).toBeInTheDocument();
    expect(screen.getByText('1 pending')).toBeInTheDocument();
    expect(screen.getByText('Fund Thesis v5')).toBeInTheDocument();
    expect(screen.getByText('policy-v4')).toBeInTheDocument();
    expect(screen.getByTestId('operations-strip').compareDocumentPosition(
      screen.getByRole('tablist'),
    ) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('exposes Fund-style tabs and deployment actions', () => {
    const props = renderChrome();

    expect(screen.getByRole('tab', { name: 'Decision' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'Administration' })).toHaveAttribute('aria-selected', 'false');
    fireEvent.click(screen.getByRole('tab', { name: 'Administration' }));
    fireEvent.click(screen.getByRole('button', { name: 'Deploy changes' }));
    fireEvent.click(screen.getByRole('button', { name: 'Reset' }));

    expect(props.onTabChange).toHaveBeenCalledWith('admin');
    expect(props.onDeploy).toHaveBeenCalledTimes(1);
    expect(props.onReset).toHaveBeenCalledTimes(1);
  });

  it('shows the live state and disables deployment when nothing is pending', () => {
    renderChrome({ pendingChanges: [] });

    expect(screen.getByText('Live')).toBeInTheDocument();
    expect(screen.getByText('No pending changes')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Deploy changes' })).toBeDisabled();
  });
});
