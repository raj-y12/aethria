import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { Settings } from '../../api/settings';
import { createDefaultFundConfiguration } from '../../lib/fundConfiguration';
import { useFundConfiguration } from '../useFundConfiguration';

function createSettings(): Settings {
  return {
    fund_config: createDefaultFundConfiguration(),
    agent_config: {
      scouts_enabled: true,
      reviewers_enabled: true,
      partners_enabled: true,
      max_agents_per_run: 4,
      confidence_threshold: 0.65,
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
}

describe('useFundConfiguration', () => {
  it('preserves an unsaved decision draft across an operations-only settings update', async () => {
    const initial = createSettings();
    const { result, rerender } = renderHook(
      ({ settings }: { settings: Settings }) => useFundConfiguration(settings),
      { initialProps: { settings: initial } },
    );

    act(() => {
      result.current.setConfiguration((current) => ({
        ...current,
        mandate: { ...current.mandate, fundName: 'Unsaved decision draft' },
      }));
    });

    rerender({
      settings: {
        ...initial,
        fund_config: { ...initial.fund_config! },
        agent_config: { ...initial.agent_config, scouts_enabled: false },
      },
    });

    await waitFor(() => {
      expect(result.current.configuration.mandate.fundName).toBe('Unsaved decision draft');
    });
  });
});
