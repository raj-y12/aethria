import type { Startup } from '../../types/startup';
import type { ReviewerQualityBand } from '../../design-system/semantics';
import type { DecisionBadgeVariant } from '../../lib/decisionBadgeVariant';
import type { QueueAttentionDriver, QueueRowContext } from '../../lib/queueAttentionDriver';

export interface DocketRowModel {
  startup: Startup;
  displayIndex: string;
  sourceBadge: 'LOOKUP' | 'SCOUT';
  reviewBand: ReviewerQualityBand | null;
  decisionVariant: DecisionBadgeVariant;
  queueContext: QueueRowContext;
  attentionDriver: QueueAttentionDriver;
  oneLiner: string | null;
  sectorStage: string;
  sortKeyValue: string;
  unresolvedAt: string | null;
  firstSeenAt: string;
  hasHighAdverse: boolean;
  isNewToUser: boolean;
}

export function formatRowDate(value: string): string {
  if (!value) return '';
  return new Date(value).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }).toUpperCase();
}

export function formatUnresolvedAgeDays(value: string): string {
  const time = new Date(value).getTime();
  if (!Number.isFinite(time)) return '';
  const days = Math.max(0, Math.floor((Date.now() - time) / (24 * 60 * 60 * 1000)));
  return `${days}d`;
}

export function buildRowAriaLabel(model: DocketRowModel, isSelected: boolean): string {
  const { startup, attentionDriver, queueContext } = model;
  const rec = queueContext.startup.partner?.recommendation ?? '';
  const parts = [
    startup.scout.name,
    startup.scout.location?.trim(),
    model.sectorStage || 'Unknown sector',
    attentionDriver.label,
    rec ? `Recommendation ${rec}` : '',
    isSelected ? 'Selected case' : '',
    'Press Enter to open memo',
  ].filter(Boolean);
  return parts.join('. ');
}
