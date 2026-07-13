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
      removeItem: (storageKey: string) => values.delete(storageKey),
    };

    savePolicyPublishRecovery(storage, key, settings, settings.fund_config!);
    expect(loadPolicyPublishRecovery(storage, key, settings)).toMatchObject(settings.fund_config!);
    const metadataOnlyChange: Settings = {
      ...settings,
      fund_config: {
        ...settings.fund_config!,
        version: 42,
        versionLabel: 'Fund Thesis v42',
        activePolicyVersionId: 'server-managed-policy-id',
        draftPolicyHash: 'server-managed-draft-hash',
        publishedPolicyHash: 'server-managed-published-hash',
        lastPublishedAt: '2026-07-13T12:00:00.000Z',
      },
    };
    expect(loadPolicyPublishRecovery(storage, key, metadataOnlyChange)).not.toBeNull();
    expect(loadPolicyPublishRecovery(storage, key, otherFund)).toBeNull();

    values.set(key, '{not json');
    expect(loadPolicyPublishRecovery(storage, key, settings)).toBeNull();
    values.set(key, JSON.stringify({ version: 1, fundScope: 'Recovery Fund', fundConfig: {} }));
    expect(loadPolicyPublishRecovery(storage, key, settings)).toBeNull();
  });

  it('removes a checkpoint whose deployable content differs from newer authoritative settings', () => {
    const checkpointSettings = createSettings('Recovery Fund');
    const authoritativeSettings = createSettings('Recovery Fund');
    authoritativeSettings.fund_config = {
      ...authoritativeSettings.fund_config!,
      mandate: {
        ...authoritativeSettings.fund_config!.mandate,
        mandateName: 'Newer authoritative mandate',
      },
    };
    const key = getPolicyPublishRecoveryStorageKey('user-a', checkpointSettings)!;
    const values = new Map<string, string>();
    const storage = {
      getItem: (storageKey: string) => values.get(storageKey) ?? null,
      setItem: (storageKey: string, value: string) => { values.set(storageKey, value); },
      removeItem: vi.fn((storageKey: string) => { values.delete(storageKey); }),
    };

    savePolicyPublishRecovery(storage, key, checkpointSettings, checkpointSettings.fund_config!);

    expect(loadPolicyPublishRecovery(storage, key, authoritativeSettings)).toBeNull();
    expect(storage.removeItem).toHaveBeenCalledWith(key);
    expect(values.has(key)).toBe(false);
  });

  it('rejects a stale checkpoint even when removing it from storage fails', () => {
    const checkpointSettings = createSettings('Recovery Fund');
    const authoritativeSettings = createSettings('Recovery Fund');
    authoritativeSettings.fund_config = {
      ...authoritativeSettings.fund_config!,
      thresholds: {
        ...authoritativeSettings.fund_config!.thresholds,
        escalation: 82,
      },
    };
    const key = getPolicyPublishRecoveryStorageKey('user-a', checkpointSettings)!;
    const values = new Map<string, string>();
    const storage = {
      getItem: (storageKey: string) => values.get(storageKey) ?? null,
      setItem: (storageKey: string, value: string) => { values.set(storageKey, value); },
      removeItem: vi.fn(() => { throw new Error('remove blocked'); }),
    };

    savePolicyPublishRecovery(storage, key, checkpointSettings, checkpointSettings.fund_config!);

    expect(loadPolicyPublishRecovery(storage, key, authoritativeSettings)).toBeNull();
    expect(storage.removeItem).toHaveBeenCalledWith(key);
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
