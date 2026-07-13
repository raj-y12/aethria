import { describe, expect, it } from 'vitest';
import { createDefaultFundConfiguration } from '../../lib/fundConfiguration';
import {
  SETTINGS_SECTIONS,
  getFundThesisChangeSet,
  getPendingChanges,
  serializeDecisionConfig,
  tabForSection,
} from '../settingsModel';

describe('settings navigation model', () => {
  it('maps each settings section to its owning tab', () => {
    expect(tabForSection('thesis')).toBe('decision');
    expect(tabForSection('thresholds')).toBe('decision');
    expect(tabForSection('weights')).toBe('decision');
    expect(tabForSection('sensitivity')).toBe('decision');
    expect(tabForSection('memo')).toBe('admin');
    expect(tabForSection('workflow')).toBe('admin');
    expect(tabForSection('budget')).toBe('admin');
    expect(tabForSection('system')).toBe('admin');
    expect(SETTINGS_SECTIONS.filter((item) => item.tab === 'decision')).toHaveLength(4);
    expect(SETTINGS_SECTIONS.filter((item) => item.tab === 'admin')).toHaveLength(4);
  });

  it('keeps Administration preferences in the deployable pending list', () => {
    const live = {
      ...createDefaultFundConfiguration(),
      activePolicyVersionId: 'policy-v4',
    };
    const savedSnapshot = serializeDecisionConfig(live);
    const changed = {
      ...live,
      memo: { ...live.memo, style: 'detailed' as const },
    };

    expect(getPendingChanges(changed, savedSnapshot)).toContainEqual({
      label: 'Memo output',
      stages: 'Partner memos',
    });
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

  it('describes only changed fund-thesis fields in readable language', () => {
    const base = createDefaultFundConfiguration();
    const live = {
      ...base,
      mandate: { ...base.mandate, preferredStages: ['Pre-seed', 'Seed'] },
    };
    const draft = {
      ...live,
      mandate: {
        ...live.mandate,
        preferredStages: ['Seed', 'Series A'],
        ownershipTarget: 12,
      },
    };

    expect(getFundThesisChangeSet(draft, serializeDecisionConfig(live), false)).toEqual({
      firstPublication: false,
      changes: [
        {
          key: 'preferredStages',
          label: 'Preferred stages',
          previous: 'Pre-seed, Seed',
          proposed: 'Seed, Series A',
        },
        {
          key: 'ownershipTarget',
          label: 'Ownership target',
          previous: '8%',
          proposed: '12%',
        },
      ],
    });
  });

  it('does not request thesis confirmation when the mandate is unchanged', () => {
    const live = createDefaultFundConfiguration();
    expect(getFundThesisChangeSet(live, serializeDecisionConfig(live), false)).toBeNull();
  });

  it('describes first publication without pretending a live thesis exists', () => {
    const draft = createDefaultFundConfiguration();
    const changeSet = getFundThesisChangeSet(draft, serializeDecisionConfig(draft), true);

    expect(changeSet?.firstPublication).toBe(true);
    expect(changeSet?.changes).toContainEqual({
      key: 'mandateName',
      label: 'Mandate name',
      previous: 'No thesis currently deployed',
      proposed: 'Core mandate',
    });
    expect(changeSet?.changes.some((change) => change.proposed === 'Not set')).toBe(false);
  });

  it('fails closed when the saved configuration cannot be parsed', () => {
    const draft = createDefaultFundConfiguration();
    const changeSet = getFundThesisChangeSet(draft, '{bad json', false);

    expect(changeSet?.changes.length).toBeGreaterThan(0);
    expect(changeSet?.changes[0].previous).toBe('Not set');
  });
});
