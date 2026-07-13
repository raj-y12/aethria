import { describe, expect, it } from 'vitest';
import { createDefaultFundConfiguration } from '../../lib/fundConfiguration';
import { getDeploymentConfirmation, serializeDecisionConfig } from '../settingsModel';

describe('settings deployment confirmation gate', () => {
  it('does not interrupt a memo-only deployment', () => {
    const live = createDefaultFundConfiguration();
    const draft = { ...live, memo: { ...live.memo, style: 'detailed' as const } };

    expect(getDeploymentConfirmation(draft, serializeDecisionConfig(live), true)).toBeNull();
  });

  it('does not interrupt a scoring-only deployment', () => {
    const live = createDefaultFundConfiguration();
    const draft = {
      ...live,
      thresholds: { ...live.thresholds, staleAfterHours: 72 },
    };

    expect(getDeploymentConfirmation(draft, serializeDecisionConfig(live), true)).toBeNull();
  });

  it('requires review when any mandate field changes', () => {
    const live = createDefaultFundConfiguration();
    const draft = {
      ...live,
      mandate: { ...live.mandate, thesisText: 'Back technical founders building critical infrastructure.' },
    };

    expect(getDeploymentConfirmation(draft, serializeDecisionConfig(live), true)?.changes).toEqual([
      {
        key: 'thesisText',
        label: 'Thesis notes',
        previous: 'Not set',
        proposed: 'Back technical founders building critical infrastructure.',
      },
    ]);
  });

  it('requires first-publication review when no active thesis exists', () => {
    const draft = createDefaultFundConfiguration();
    const confirmation = getDeploymentConfirmation(
      draft,
      serializeDecisionConfig(draft),
      false,
    );

    expect(confirmation?.firstPublication).toBe(true);
    expect(confirmation?.changes[0].previous).toBe('No thesis currently deployed');
  });
});
