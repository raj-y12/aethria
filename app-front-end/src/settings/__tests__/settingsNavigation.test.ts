import { describe, expect, it } from 'vitest';
import { createDefaultFundConfiguration } from '../../lib/fundConfiguration';
import {
  SETTINGS_SECTIONS,
  getPendingChanges,
  serializeDecisionConfig,
  tabForSection,
} from '../settingsModel';

describe('settings navigation model', () => {
  it('maps each settings section to its owning tab', () => {
    expect(tabForSection('mandate')).toBe('decision');
    expect(tabForSection('weights')).toBe('decision');
    expect(tabForSection('policy')).toBe('admin');
    expect(tabForSection('system')).toBe('admin');
    expect(SETTINGS_SECTIONS.filter((item) => item.tab === 'decision')).toHaveLength(5);
    expect(SETTINGS_SECTIONS.filter((item) => item.tab === 'admin')).toHaveLength(3);
  });

  it('reports only deployable decision changes', () => {
    const live = {
      ...createDefaultFundConfiguration(),
      activePolicyVersionId: 'policy-v4',
    };
    const savedSnapshot = serializeDecisionConfig(live);
    const changed = {
      ...live,
      risk: { ...live.risk, sensitivity: 'conservative' as const },
    };

    expect(getPendingChanges(live, savedSnapshot)).toEqual([]);
    expect(getPendingChanges(changed, savedSnapshot)).toEqual([
      { label: 'Ruling', stages: 'Decision flow' },
    ]);
  });

  it('ignores deployment metadata when comparing the decision draft', () => {
    const live = {
      ...createDefaultFundConfiguration(),
      activePolicyVersionId: 'policy-v4',
      lastPublishedAt: '2026-07-13T09:00:00Z',
    };
    const savedSnapshot = serializeDecisionConfig(live);
    const refreshed = {
      ...live,
      lastPublishedAt: '2026-07-13T10:00:00Z',
      versionLabel: 'Fund Thesis v5',
    };

    expect(getPendingChanges(refreshed, savedSnapshot)).toEqual([]);
  });
});
