import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import type { Settings } from '../../api/settings';
import { patchSettings } from '../../api/settings';
import ThresholdControls from '../ThresholdControls';

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
    confidence_threshold: 0.3,
    scout_region: 'europe',
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

function renderControls(props: Partial<React.ComponentProps<typeof ThresholdControls>> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const onSettingsChange = vi.fn();
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  render(
    <ThresholdControls
      settings={settings}
      storageUnavailable={false}
      onSettingsChange={onSettingsChange}
      {...props}
    />,
    { wrapper: Wrapper },
  );
  return { queryClient, onSettingsChange };
}

describe('ThresholdControls', () => {
  beforeEach(() => {
    vi.mocked(patchSettings).mockReset();
  });

  it('renders the review threshold as a percentage', () => {
    renderControls();
    expect(screen.getByLabelText('Review threshold')).toHaveValue(30);
  });

  it('saves a changed threshold as a 0-1 fraction on blur', async () => {
    const live = { ...settings, agent_config: { ...settings.agent_config, confidence_threshold: 0.4 } };
    vi.mocked(patchSettings).mockResolvedValue({ data: live });
    const { onSettingsChange } = renderControls();

    const input = screen.getByLabelText('Review threshold');
    fireEvent.change(input, { target: { value: '40' } });
    fireEvent.blur(input);

    await waitFor(() => expect(onSettingsChange).toHaveBeenCalledWith(live));
    expect(patchSettings).toHaveBeenCalledWith({
      agent_config: { ...settings.agent_config, confidence_threshold: 0.4 },
    });
  });

  it('rolls back to the last saved value and shows an error on failure', async () => {
    vi.mocked(patchSettings).mockResolvedValue({
      error: { message: 'confidence_threshold must be between 0 and 1', errors: [] },
    });
    renderControls();

    const input = screen.getByLabelText('Review threshold');
    fireEvent.change(input, { target: { value: '90' } });
    fireEvent.blur(input);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('confidence_threshold must be between 0 and 1');
    });
    expect(input).toHaveValue(30);
  });

  it('disables the input when storage is unavailable', () => {
    renderControls({ storageUnavailable: true });
    expect(screen.getByLabelText('Review threshold')).toBeDisabled();
  });
});
