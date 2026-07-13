import type { FundConfiguration } from '../lib/fundConfiguration';

export type SettingsTab = 'decision' | 'admin';

export type SectionId =
  | 'thesis'
  | 'thresholds'
  | 'weights'
  | 'sensitivity'
  | 'memo'
  | 'workflow'
  | 'budget'
  | 'system';

export interface PendingChange {
  label: string;
  stages: string;
}

interface SettingsSectionDefinition {
  id: SectionId;
  label: string;
  short: string;
  tab: SettingsTab;
}

export const SETTINGS_SECTIONS = [
  { id: 'thesis', label: 'Fund thesis', short: 'Thesis', tab: 'decision' },
  { id: 'thresholds', label: 'Decision thresholds', short: 'Thresholds', tab: 'decision' },
  { id: 'weights', label: 'Scoring weights', short: 'Weights', tab: 'decision' },
  { id: 'sensitivity', label: 'Escalation sensitivity', short: 'Sensitivity', tab: 'decision' },
  { id: 'memo', label: 'Memo output', short: 'Memo', tab: 'admin' },
  { id: 'workflow', label: 'Ruling workflow', short: 'Workflow', tab: 'admin' },
  { id: 'budget', label: 'Cost budget', short: 'Budget', tab: 'admin' },
  { id: 'system', label: 'System state', short: 'System', tab: 'admin' },
] satisfies ReadonlyArray<SettingsSectionDefinition>;

export function tabForSection(id: SectionId): SettingsTab {
  return SETTINGS_SECTIONS.find((section) => section.id === id)?.tab ?? 'decision';
}

export function serializeDecisionConfig(config: FundConfiguration): string {
  const comparable = { ...config } as Record<string, unknown>;
  for (const key of [
    'lastSavedAt',
    'version',
    'versionLabel',
    'activePolicyVersionId',
    'draftPolicyHash',
    'publishedPolicyHash',
    'lastPublishedAt',
  ]) {
    delete comparable[key];
  }
  return JSON.stringify(comparable);
}

export function getPendingChanges(
  draft: FundConfiguration,
  savedSnapshot: string,
): PendingChange[] {
  const items: PendingChange[] = [];
  let saved: Partial<FundConfiguration> | null = null;
  try {
    saved = savedSnapshot
      ? (JSON.parse(savedSnapshot) as Partial<FundConfiguration>)
      : null;
  } catch {
    saved = null;
  }

  const differs = (left: unknown, right: unknown) =>
    JSON.stringify(left) !== JSON.stringify(right);

  if (saved) {
    if (differs(draft.mandate, saved.mandate)) {
      items.push({ label: 'Mandate', stages: 'Scout · Reviewer' });
    }
    if (
      differs(draft.scoringWeights, saved.scoringWeights)
      || differs(draft.scoreBands, saved.scoreBands)
      || differs(draft.thresholds, saved.thresholds)
    ) {
      items.push({ label: 'Scoring', stages: 'Reviewer · Partner' });
    }
    if (differs(draft.risk, saved.risk)) {
      items.push({ label: 'Ruling', stages: 'Decision flow' });
    }
    if (differs(draft.memo, saved.memo)) {
      items.push({ label: 'Memo output', stages: 'Partner memos' });
    }
    if (!items.length && serializeDecisionConfig(draft) !== savedSnapshot) {
      items.push({ label: 'Configuration', stages: 'Pipeline' });
    }
  }

  if (!draft.activePolicyVersionId) {
    items.push({ label: 'Scoring policy', stages: 'Never published' });
  }
  return items;
}
