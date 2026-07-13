import type { Settings } from '../api/settings';
import {
  createDefaultFundConfiguration,
  type FundConfiguration,
} from '../lib/fundConfiguration';

export const POLICY_PUBLISH_RECOVERY_STORAGE_PREFIX = 'aethria.settings.policy-publish.v1';
const POLICY_PUBLISH_RECOVERY_VERSION = 1;

type StoredPolicyPublishRecovery = {
  version: number;
  fundScope: string;
  fundConfig: FundConfiguration;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function getFundScope(settings: Settings | null | undefined): string | null {
  const identity = settings?.fund_identity;
  const scope = identity?.canonical_website?.trim().toLowerCase()
    || identity?.fund_name?.trim()
    || settings?.fund_config?.mandate.fundName?.trim();
  return scope || null;
}

export function getPolicyPublishRecoveryStorageKey(
  userId: string | null | undefined,
  settings: Settings | null | undefined,
): string | null {
  const normalizedUserId = userId?.trim();
  const fundScope = getFundScope(settings);
  if (!normalizedUserId || !fundScope) return null;
  return `${POLICY_PUBLISH_RECOVERY_STORAGE_PREFIX}:${encodeURIComponent(normalizedUserId)}:${encodeURIComponent(fundScope)}`;
}

function normalizeFundConfig(value: unknown, settings: Settings): FundConfiguration | null {
  if (!isRecord(value)) return null;
  if (
    !isRecord(value.mandate)
    || !isRecord(value.thresholds)
    || !isRecord(value.risk)
    || !isRecord(value.memo)
    || !Array.isArray(value.scoringWeights)
    || !Array.isArray(value.scoreBands)
    || !Array.isArray(value.verdictBadges)
    || !Array.isArray(value.rubric)
  ) return null;
  try {
    return createDefaultFundConfiguration({
      ...settings,
      fund_config: value as unknown as FundConfiguration,
    });
  } catch {
    return null;
  }
}

export function loadPolicyPublishRecovery(
  storage: Pick<Storage, 'getItem'> | null | undefined,
  key: string | null,
  settings: Settings | null | undefined,
): FundConfiguration | null {
  if (!storage || !key || !settings) return null;
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!isRecord(parsed) || parsed.version !== POLICY_PUBLISH_RECOVERY_VERSION) return null;
    if (parsed.fundScope !== getFundScope(settings)) return null;
    return normalizeFundConfig(parsed.fundConfig, settings);
  } catch {
    return null;
  }
}

export function savePolicyPublishRecovery(
  storage: Pick<Storage, 'setItem'> | null | undefined,
  key: string | null,
  settings: Settings | null | undefined,
  fundConfig: FundConfiguration,
): void {
  const fundScope = getFundScope(settings);
  if (!storage || !key || !fundScope) return;
  const stored: StoredPolicyPublishRecovery = {
    version: POLICY_PUBLISH_RECOVERY_VERSION,
    fundScope,
    fundConfig,
  };
  try {
    storage.setItem(key, JSON.stringify(stored));
  } catch {
    // Recovery remains available in memory when storage is unavailable/full.
  }
}

export function clearPolicyPublishRecovery(
  storage: Pick<Storage, 'removeItem'> | null | undefined,
  key: string | null,
): void {
  if (!storage || !key) return;
  try {
    storage.removeItem(key);
  } catch {
    // Successful publication is authoritative even if local cleanup is blocked.
  }
}

export function getPolicyPublishRecoveryStorage(): Storage | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}
