import type { FundConfiguration } from '../lib/fundConfiguration';

export type SettingsPersistenceGroup = 'thesis' | 'policy' | 'runtime' | 'system';

export type SectionId =
  | 'thesis'
  | 'version'
  | 'thresholds'
  | 'sensitivity'
  | 'weights'
  | 'memo'
  | 'workflow'
  | 'budget'
  | 'governance'
  | 'system';

export interface PendingChange {
  label: string;
  stages: string;
}

export interface FundThesisChange {
  key: keyof FundConfiguration['mandate'];
  label: string;
  previous: string;
  proposed: string;
}

export interface FundThesisChangeSet {
  firstPublication: boolean;
  changes: FundThesisChange[];
}

export const SETTINGS_GROUPS = [
  { id: 'thesis', label: 'Fund thesis', persistence: 'Publishes a thesis version' },
  { id: 'policy', label: 'Decision policy', persistence: 'Publishes a policy version' },
  { id: 'runtime', label: 'Workspace runtime', persistence: 'Saves immediately' },
  { id: 'system', label: 'System', persistence: 'Diagnostics and governed agent changes' },
] as const;

export const SETTINGS_SECTIONS = [
  { id: 'thesis', label: 'Mandate', short: 'Thesis', group: 'thesis' },
  { id: 'version', label: 'Version context', short: 'Version', group: 'thesis' },
  { id: 'thresholds', label: 'Decision thresholds', short: 'Thresholds', group: 'policy' },
  { id: 'sensitivity', label: 'Escalation sensitivity', short: 'Sensitivity', group: 'policy' },
  { id: 'weights', label: 'Scoring weights', short: 'Weights', group: 'policy' },
  { id: 'memo', label: 'Memo output', short: 'Memo', group: 'policy' },
  { id: 'workflow', label: 'Ruling workflow', short: 'Workflow', group: 'policy' },
  { id: 'budget', label: 'Cost budget', short: 'Budget', group: 'runtime' },
  { id: 'governance', label: 'Agent governance', short: 'Governance', group: 'system' },
  { id: 'system', label: 'System state', short: 'System', group: 'system' },
] as const satisfies readonly {
  id: SectionId;
  label: string;
  short: string;
  group: SettingsPersistenceGroup;
}[];

export function sectionForDeploymentError(error: string): SectionId {
  const value = error.toLowerCase();
  if (value.includes('weight')) return 'weights';
  if (value.includes('threshold') || value.includes('score band')) return 'thresholds';
  if (value.includes('memo')) return 'memo';
  if (value.includes('risk') || value.includes('ruling')) return 'workflow';
  return 'thesis';
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

const THESIS_FIELDS: ReadonlyArray<{
  key: keyof FundConfiguration['mandate'];
  label: string;
}> = [
  { key: 'fundName', label: 'Fund name' },
  { key: 'mandateName', label: 'Mandate name' },
  { key: 'preferredStages', label: 'Preferred stages' },
  { key: 'geographies', label: 'Geographies' },
  { key: 'customGeography', label: 'Custom geography' },
  { key: 'sectors', label: 'Sectors' },
  { key: 'customSectors', label: 'Custom sectors' },
  { key: 'excludedSectors', label: 'Excluded sectors' },
  { key: 'businessModels', label: 'Preferred business models' },
  { key: 'checkSizeMin', label: 'Minimum cheque size' },
  { key: 'checkSizeMax', label: 'Maximum cheque size' },
  { key: 'ownershipTarget', label: 'Ownership target' },
  { key: 'minimumTraction', label: 'Minimum traction' },
  { key: 'thesisText', label: 'Thesis notes' },
];

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en', {
    style: 'currency',
    currency: 'USD',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}

function formatThesisValue(
  key: keyof FundConfiguration['mandate'],
  value: FundConfiguration['mandate'][keyof FundConfiguration['mandate']] | undefined,
): string {
  if (Array.isArray(value)) return value.length ? value.join(', ') : 'Not set';
  if (value == null || value === '') return 'Not set';
  if ((key === 'checkSizeMin' || key === 'checkSizeMax') && typeof value === 'number') {
    return formatCurrency(value);
  }
  if (key === 'ownershipTarget' && typeof value === 'number') return `${value}%`;
  return String(value);
}

export function getFundThesisChangeSet(
  draft: FundConfiguration,
  savedSnapshot: string,
  firstPublication: boolean,
): FundThesisChangeSet | null {
  let saved: Partial<FundConfiguration> | null = null;
  try {
    saved = savedSnapshot
      ? (JSON.parse(savedSnapshot) as Partial<FundConfiguration>)
      : null;
  } catch {
    saved = null;
  }

  const previousMandate = saved?.mandate;
  const forceReview = firstPublication || previousMandate == null;
  const changes = THESIS_FIELDS.flatMap<FundThesisChange>((field) => {
    const previous = formatThesisValue(field.key, previousMandate?.[field.key]);
    const proposed = formatThesisValue(field.key, draft.mandate[field.key]);
    if (proposed === 'Not set' && forceReview) return [];
    if (!forceReview && previous === proposed) return [];
    return [{
      key: field.key,
      label: field.label,
      previous: firstPublication ? 'No thesis currently deployed' : previous,
      proposed,
    }];
  });

  return changes.length ? { firstPublication, changes } : null;
}

export function getDeploymentConfirmation(
  draft: FundConfiguration,
  savedSnapshot: string,
  hasActiveThesis: boolean,
): FundThesisChangeSet | null {
  return getFundThesisChangeSet(draft, savedSnapshot, !hasActiveThesis);
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
