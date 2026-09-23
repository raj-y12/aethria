import { useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Settings } from '../../api/settings';
import { fetchSettings, patchSettings } from '../../api/settings';
import { SettingsDock } from '../AppSpine';

// The panel itself is covered by settings tests; here it is a stub that closes
// when the dock asks it to (the clean-draft path of requestExit).
vi.mock('../../settings/SettingsPage', () => ({
  default: function SettingsPageStub({ onClose, backSignal }: { onClose?: () => void; backSignal?: number }) {
    useEffect(() => {
      if (backSignal) onClose?.();
    }, [backSignal, onClose]);
    return <div data-testid="settings-panel" data-back-signal={backSignal ?? 0} />;
  },
}));

vi.mock('../../api/settings', async () => {
  const actual = await vi.importActual<typeof import('../../api/settings')>('../../api/settings');
  return { ...actual, fetchSettings: vi.fn(), patchSettings: vi.fn() };
});

const settings: Settings = {
  agent_config: {
    scouts_enabled: true,
    reviewers_enabled: true,
    partners_enabled: false,
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
  portfolio: { auto_watchlist: true, signal_scan_frequency: 'daily', memo_verbosity: 'standard' },
};

beforeEach(() => {
  vi.mocked(fetchSettings).mockReset().mockResolvedValue(settings);
  vi.mocked(patchSettings).mockReset();
});

function renderDock() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SettingsDock />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('SettingsDock cog / back button', () => {
  it('is the only back control: the cog becomes back inside a category and returns to the cog at the menu', async () => {
    const { container } = renderDock();
    const dock = container.querySelector('.aethria-settings-dock')!;

    // Closed: a cog.
    expect(screen.getByRole('button', { name: 'Open settings categories' })).toBeInTheDocument();
    expect(dock).not.toHaveClass('is-panel');

    // Menu: still a cog, now closing the menu.
    fireEvent.click(screen.getByRole('button', { name: 'Open settings categories' }));
    expect(screen.getByRole('navigation', { name: 'Settings categories' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close settings categories' })).toBeInTheDocument();

    // Category: the menu is gone and the same button is now Back — and nothing else is.
    fireEvent.click(screen.getByRole('button', { name: 'Fund thesis' }));
    expect(screen.getByTestId('settings-panel')).toBeInTheDocument();
    // The menu fades out (AnimatePresence) rather than vanishing, so wait for it.
    await waitFor(() => expect(screen.queryByRole('navigation', { name: 'Settings categories' })).toBeNull());
    expect(dock).toHaveClass('is-panel');
    // Every control on screen: just the one dock button, no stray back/menu control.
    expect(screen.getAllByRole('button').map((button) => button.getAttribute('aria-label') ?? button.textContent)).toEqual([
      'Back to settings menu',
    ]);
    expect(screen.getAllByRole('button', { name: /back|menu/i })).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Back to settings menu' })).toBeInTheDocument();

    // Back: asks the panel to exit, then the menu returns and the button is a cog again.
    fireEvent.click(screen.getByRole('button', { name: 'Back to settings menu' }));
    expect(screen.getByTestId('settings-panel')).toHaveAttribute('data-back-signal', '1');
    await waitFor(() => expect(screen.queryByTestId('settings-panel')).toBeNull());
    expect(screen.getByRole('navigation', { name: 'Settings categories' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close settings categories' })).toBeInTheDocument();
    expect(dock).not.toHaveClass('is-panel');
  });

  it('shows the pipeline switches in the menu, and a toggle saves through patchSettings', async () => {
    vi.mocked(patchSettings).mockResolvedValue({
      data: { ...settings, agent_config: { ...settings.agent_config, scouts_enabled: false } },
    } as Awaited<ReturnType<typeof patchSettings>>);
    renderDock();

    // Nothing is fetched until the menu is opened.
    expect(fetchSettings).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Open settings categories' }));

    const scouts = await screen.findByRole('switch', { name: 'Scouts' });
    expect(screen.getAllByRole('switch').map((toggle) => toggle.getAttribute('aria-label'))).toEqual([
      'Scouts',
      'Reviewers',
      'Partners',
      'Cost budget',
    ]);
    expect(scouts).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('switch', { name: 'Partners' })).toHaveAttribute('aria-checked', 'false');

    fireEvent.click(scouts);

    await waitFor(() => expect(patchSettings).toHaveBeenCalledWith({
      agent_config: { ...settings.agent_config, scouts_enabled: false },
    }));
    await waitFor(() => expect(screen.getByRole('switch', { name: 'Scouts' })).toHaveAttribute('aria-checked', 'false'));
  });

  it('reverts a switch and says why when the save fails', async () => {
    vi.mocked(patchSettings).mockResolvedValue({
      error: { message: 'Storage is down', errors: [] },
    } as unknown as Awaited<ReturnType<typeof patchSettings>>);
    renderDock();
    fireEvent.click(screen.getByRole('button', { name: 'Open settings categories' }));

    fireEvent.click(await screen.findByRole('switch', { name: 'Reviewers' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Storage is down');
    expect(screen.getByRole('switch', { name: 'Reviewers' })).toHaveAttribute('aria-checked', 'true');
  });
});
