import { describe, expect, it, vi } from 'vitest';
import type { Settings } from '../../api/settings';
import { createDefaultFundConfiguration } from '../../lib/fundConfiguration';
import {
  clearPolicyPublishRecovery,
  getPolicyPublishRecoveryStorageKey,
  loadPolicyPublishRecovery,
  savePolicyPublishRecovery,
} from '../policyPublishRecovery';

function createSettings(fundName: string): Settings {
  const settings: Settings = {
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
  return { ...settings, fund_config: createDefaultFundConfiguration(settings) };
}

describe('policy publish recovery storage', () => {
  it('scopes checkpoints by both Clerk user and authoritative fund identity', () => {
    const alpha = createSettings('Alpha Fund');
    const beta = createSettings('Beta Fund');

    expect(getPolicyPublishRecoveryStorageKey('user-a', alpha))
      .not.toBe(getPolicyPublishRecoveryStorageKey('user-b', alpha));
    expect(getPolicyPublishRecoveryStorageKey('user-a', alpha))
      .not.toBe(getPolicyPublishRecoveryStorageKey('user-a', beta));
    expect(getPolicyPublishRecoveryStorageKey(null, alpha)).toBeNull();
    expect(getPolicyPublishRecoveryStorageKey('user-a', undefined)).toBeNull();
  });

  it('round-trips a valid checkpoint and rejects malformed or wrong-fund payloads', () => {
    const settings = createSettings('Recovery Fund');
    const otherFund = createSettings('Other Fund');
    const key = getPolicyPublishRecoveryStorageKey('user-a', settings)!;
    const values = new Map<string, string>();
    const storage = {
      getItem: (storageKey: string) => values.get(storageKey) ?? null,
      setItem: (storageKey: string, value: string) => values.set(storageKey, value),
    };

    savePolicyPublishRecovery(storage, key, settings, settings.fund_config!);
    expect(loadPolicyPublishRecovery(storage, key, settings)).toMatchObject(settings.fund_config!);
    expect(loadPolicyPublishRecovery(storage, key, otherFund)).toBeNull();

    values.set(key, '{not json');
    expect(loadPolicyPublishRecovery(storage, key, settings)).toBeNull();
    values.set(key, JSON.stringify({ version: 1, fundScope: 'Recovery Fund', fundConfig: {} }));
    expect(loadPolicyPublishRecovery(storage, key, settings)).toBeNull();
  });

  it('fails safely when browser storage access throws', () => {
    const settings = createSettings('Recovery Fund');
    const key = getPolicyPublishRecoveryStorageKey('user-a', settings)!;
    const error = new Error('storage unavailable');
    const storage = {
      getItem: vi.fn(() => { throw error; }),
      setItem: vi.fn(() => { throw error; }),
      removeItem: vi.fn(() => { throw error; }),
    };

    expect(loadPolicyPublishRecovery(storage, key, settings)).toBeNull();
    expect(() => savePolicyPublishRecovery(storage, key, settings, settings.fund_config!)).not.toThrow();
    expect(() => clearPolicyPublishRecovery(storage, key)).not.toThrow();
  });
});
