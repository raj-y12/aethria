import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import type { Settings } from '../../api/settings';
import { patchSettings } from '../../api/settings';
import OperationsStrip from '../OperationsStrip';

vi.mock('../../api/settings', async () => {
  const actual = await vi.importActual<typeof import('../../api/settings')>('../../api/settings');
  return { ...actual, patchSettings: vi.fn() };
});

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
    enabled: false,
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

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => { resolve = next; });
  return { promise, resolve };
}

function renderStrip(
  props: Partial<React.ComponentProps<typeof OperationsStrip>> = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const onSettingsChange = vi.fn();
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  render(
    <OperationsStrip
      settings={settings}
      storageUnavailable={false}
      onSettingsChange={onSettingsChange}
      {...props}
    />,
    { wrapper: Wrapper },
  );
  return { queryClient, onSettingsChange };
}

describe('OperationsStrip', () => {
  beforeEach(() => {
    vi.mocked(patchSettings).mockReset();
  });

  it('optimistically updates one control and preserves sibling settings in the PATCH', async () => {
    const request = createDeferred<Awaited<ReturnType<typeof patchSettings>>>();
    vi.mocked(patchSettings).mockReturnValue(request.promise);
    renderStrip();

    fireEvent.click(screen.getByRole('switch', { name: /scouts/i }));

    expect(patchSettings).toHaveBeenCalledWith({
      agent_config: { ...settings.agent_config, scouts_enabled: false },
    });
    expect(screen.getByRole('switch', { name: /scouts/i })).toHaveAttribute('aria-checked', 'false');
    expect(screen.getByRole('switch', { name: /scouts/i })).toBeDisabled();
    expect(screen.getByRole('switch', { name: /reviewers/i })).not.toBeDisabled();

    request.resolve({ data: { ...settings, agent_config: { ...settings.agent_config, scouts_enabled: false } } });
    await waitFor(() => expect(screen.getByRole('switch', { name: /scouts/i })).not.toBeDisabled());
  });

  it('reconciles a successful save with the page and shared settings cache', async () => {
    const live = { ...settings, cost_budget: { ...settings.cost_budget, enabled: true } };
    vi.mocked(patchSettings).mockResolvedValue({ data: live });
    const { queryClient, onSettingsChange } = renderStrip();

    fireEvent.click(screen.getByRole('switch', { name: /cost budget/i }));

    await waitFor(() => expect(onSettingsChange).toHaveBeenCalledWith(live));
    expect(patchSettings).toHaveBeenCalledWith({ cost_budget: live.cost_budget });
    expect(queryClient.getQueryData(['settings'])).toEqual(live);
  });

  it('rolls back only the failed control and explains the error', async () => {
    vi.mocked(patchSettings).mockResolvedValue({
      error: { message: 'Could not save this setting', errors: [] },
    });
    renderStrip();

    fireEvent.click(screen.getByRole('switch', { name: /partners/i }));

    await waitFor(() => {
      expect(screen.getByRole('switch', { name: /partners/i })).toHaveAttribute('aria-checked', 'true');
    });
    expect(screen.getByRole('alert')).toHaveTextContent('Could not save this setting');
    expect(screen.getByRole('switch', { name: /reviewers/i })).toHaveAttribute('aria-checked', 'true');
  });

  it('disables runtime changes when storage is unavailable', () => {
    renderStrip({ storageUnavailable: true });

    expect(screen.getByText(/storage unavailable/i)).toBeInTheDocument();
    for (const control of screen.getAllByRole('switch')) {
      expect(control).toBeDisabled();
    }
  });
});
