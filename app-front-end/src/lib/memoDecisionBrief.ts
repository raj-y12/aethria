import type { HumanRuling, HumanRulingRecordDecision } from '../api/decisions';
import type { EvaluationRecord, RecommendationState } from '../api/evaluations';
import type {
  Claim,
  ClaimEvidenceLink,
  EvidenceArtifact,
  EvidenceItem,
  EvidenceLedger,
} from '../api/evidence';
import { formatDecisionDriver } from './decisionDrivers';
import type { DecisionBadgeVariant } from './decisionBadgeVariant';

export type MemoDecisionBriefStatus =
  | 'loading'
  | 'ready_for_ruling'
  | 'blocked'
  | 'recorded'
  | 'unavailable';
export type MemoDecisionBriefLean = 'advance' | 'monitor' | 'pass' | 'none';
export type MemoMandate = 'conflicted' | 'unknown';
export type MemoEvidenceCoverage = 'sufficient' | 'missing' | 'contradictory' | 'unknown';
export type MemoReviewerAgreement = 'consistent' | 'contested' | 'unknown';
export type MemoProvenance = 'verified' | 'reported' | 'model-derived' | 'rule-derived' | 'missing';
export type MemoRiskSeverity = 'high' | 'medium' | 'low';

export interface MemoDecisionBriefInput {
  evaluation?: EvaluationRecord | null;
  ledger?: EvidenceLedger | null;
  ruling?: HumanRuling | null;
  loading?: boolean;
  unavailable?: boolean;
}

export interface MemoSource {
  artifactId: string;
  title: string;
  href?: string;
}

export interface MemoClaimProvenance {
  claimId: string;
  claim: string;
  criterion: string;
  relationship: 'supports' | 'contradicts';
  provenance: Exclude<MemoProvenance, 'rule-derived'>;
  sources: MemoSource[];
}

export interface MemoDerivation {
  criterion: string;
  provenance: 'rule-derived';
}

export interface MemoRiskGap {
  key: string;
  text: string;
  kind: 'risk' | 'gap';
  severity: MemoRiskSeverity;
}

export interface MemoDecisionBrief {
  status: MemoDecisionBriefStatus;
  lean: MemoDecisionBriefLean;
  leanProvenance: 'rule-derived' | 'missing';
  mandate: MemoMandate;
  coverage: MemoEvidenceCoverage;
  agreement: MemoReviewerAgreement;
  ruling: Pick<HumanRuling, 'ruling_id' | 'decision' | 'rationale' | 'created_at'> | null;
  drivers: string[];
  claims: MemoClaimProvenance[];
  derivations: MemoDerivation[];
  risks: MemoRiskGap[];
}

type ClaimSource = {
  link: ClaimEvidenceLink;
  item?: EvidenceItem;
  artifact?: EvidenceArtifact;
};

type RiskCandidate = {
  text: string;
  kind: 'risk' | 'gap';
  severity: MemoRiskSeverity;
};

const DIAGNOSTIC_PATTERN = /\bgap\s*(?:>=|>|<=|<|=)\s*\d|\breviewer(?:\s+score)?\s*spread\b|\bdimension(?:\s+score)?\s*spread\b/i;
const CONTRADICTORY_CONDITION_PATTERN = /^\s*resolve\s+contradictory\s+evidence\s*:/i;
const REGULATORY_EXPANSION_PATTERN = /\b(regulat\w*|licen[cs]\w*|jurisdiction\w*|approval|authori[sz]\w*)\b/i;
const EXPANSION_PATTERN = /\b(expan\w*|new markets?|countries?|regions?)\b/i;
const SEVERITY_RANK: Record<MemoRiskSeverity, number> = { low: 1, medium: 2, high: 3 };

function emptyBrief(status: MemoDecisionBriefStatus): MemoDecisionBrief {
  return {
    status,
    lean: 'none',
    leanProvenance: 'missing',
    mandate: 'unknown',
    coverage: 'unknown',
    agreement: 'unknown',
    ruling: null,
    drivers: [],
    claims: [],
    derivations: [],
    risks: [],
  };
}

function coverageFor(evaluation: EvaluationRecord): MemoEvidenceCoverage {
  const criteria = evaluation.criteria ?? [];
  if (criteria.some((criterion) => criterion.contradicting_claim_ids.length > 0 || /contradict/i.test(criterion.evidence_sufficiency))) {
    return 'contradictory';
  }
  if (evaluation.recommendation?.change_conditions.some((condition) =>
    CONTRADICTORY_CONDITION_PATTERN.test(condition))) {
    return 'contradictory';
  }
  if (evaluation.recommendation?.recommended_state === 'insufficient_evidence') return 'missing';
  if (criteria.some((criterion) => criterion.supporting_claim_ids.length === 0 || criterion.missing_evidence.length > 0 || /missing|insufficient/i.test(criterion.evidence_sufficiency))) {
    return 'missing';
  }
  return criteria.length > 0 ? 'sufficient' : 'unknown';
}

function leanFor(recommendation?: RecommendationState): MemoDecisionBriefLean {
  return recommendation && recommendation !== 'insufficient_evidence' ? recommendation : 'none';
}

function claimSources(ledger: EvidenceLedger): Map<string, ClaimSource[]> {
  const items = ledger.items ?? ledger.evidence_items ?? [];
  const itemById = new Map(items.map((item) => [item.evidence_item_id, item]));
  const artifactById = new Map(ledger.artifacts.map((artifact) => [artifact.artifact_id, artifact]));
  const sources = new Map<string, ClaimSource[]>();
  for (const link of ledger.links) {
    const item = itemById.get(link.evidence_item_id);
    const source = { link, item, artifact: item ? artifactById.get(item.artifact_id) : undefined };
    const existing = sources.get(link.claim_id) ?? [];
    existing.push(source);
    sources.set(link.claim_id, existing);
  }
  return sources;
}

function toMemoSources(sources: ClaimSource[]): MemoSource[] {
  const unique = new Map<string, MemoSource>();
  for (const source of sources) {
    if (!source.artifact) continue;
    unique.set(source.artifact.artifact_id, {
      artifactId: source.artifact.artifact_id,
      title: source.artifact.title?.trim() || source.artifact.artifact_type.replace(/_/g, ' '),
      ...(source.artifact.source_uri ? { href: source.artifact.source_uri } : {}),
    });
  }
  return [...unique.values()].sort((left, right) =>
    left.title.localeCompare(right.title) || left.artifactId.localeCompare(right.artifactId),
  );
}

function provenanceFor(claim: Claim, sources: ClaimSource[]): Exclude<MemoProvenance, 'rule-derived'> {
  if (claim.assertion_class === 'founder_asserted' || claim.assertion_class === 'operator_asserted') return 'reported';
  if (claim.assertion_class === 'model_inferred') return 'model-derived';
  if (
    claim.assertion_class === 'externally_verified'
    && sources.some((source) => source.item?.verification_state === 'verified' && source.artifact)
  ) return 'verified';
  return 'missing';
}

function isDiagnostic(value: string): boolean {
  return DIAGNOSTIC_PATTERN.test(value.trim()) || value.trim() === 'reviewer_spread';
}

function riskKey(text: string): string {
  const subject = text.replace(/^resolve\s+(?:missing|contradictory)\s+evidence\s*:\s*/i, '').trim();
  if (REGULATORY_EXPANSION_PATTERN.test(subject) && EXPANSION_PATTERN.test(subject)) return 'regulatory-expansion';
  return subject.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().replace(/\s+/g, '-');
}

function riskGaps(evaluation: EvaluationRecord): MemoRiskGap[] {
  const candidates: RiskCandidate[] = [];
  const recommendation = evaluation.recommendation;
  for (const text of recommendation?.principal_risks ?? []) {
    if (!isDiagnostic(text) && text.trim()) {
      candidates.push({ text: text.trim(), kind: 'risk', severity: 'high' });
    }
  }
  for (const text of recommendation?.missing_information ?? []) {
    if (!isDiagnostic(text) && text.trim()) candidates.push({ text: text.trim(), kind: 'gap', severity: 'medium' });
  }
  for (const text of recommendation?.change_conditions ?? []) {
    if (!isDiagnostic(text) && text.trim()) candidates.push({ text: text.trim(), kind: 'gap', severity: 'medium' });
  }
  for (const criterion of evaluation.criteria ?? []) {
    for (const text of criterion.missing_evidence) {
      if (!isDiagnostic(text) && text.trim()) {
        candidates.push({ text: text.trim(), kind: 'gap', severity: 'medium' });
      }
    }
  }
  const grouped = new Map<string, RiskCandidate[]>();
  for (const candidate of candidates) {
    const key = riskKey(candidate.text);
    if (!key) continue;
    const existing = grouped.get(key) ?? [];
    existing.push(candidate);
    grouped.set(key, existing);
  }
  return [...grouped.entries()]
    .map(([key, group]) => {
      const richest = [...group].sort((left, right) =>
        right.text.length - left.text.length || left.text.localeCompare(right.text),
      )[0];
      const severity = [...group].sort((left, right) => SEVERITY_RANK[right.severity] - SEVERITY_RANK[left.severity])[0].severity;
      return {
        key,
        text: richest.text,
        kind: group.some((item) => item.kind === 'risk') ? 'risk' as const : 'gap' as const,
        severity,
      };
    })
    .sort((left, right) => left.key.localeCompare(right.key) || left.text.localeCompare(right.text));
}

function visibleDrivers(values: string[]): string[] {
  const seen = new Set<string>();
  const drivers: string[] = [];
  for (const value of values) {
    if (isDiagnostic(value)) continue;
    const formatted = formatDecisionDriver(value);
    const key = formatted.toLocaleLowerCase();
    if (!formatted || seen.has(key)) continue;
    seen.add(key);
    drivers.push(formatted);
    if (drivers.length === 3) break;
  }
  return drivers;
}

export function buildMemoDecisionBrief(input: MemoDecisionBriefInput): MemoDecisionBrief {
  if (input.loading) return emptyBrief('loading');
  if (input.unavailable || !input.evaluation) return emptyBrief('unavailable');

  const evaluation = input.evaluation;
  const ledger = input.ledger ?? { artifacts: [], claims: [], links: [], plans: [] };
  const sourcesByClaim = claimSources(ledger);
  const claimById = new Map(ledger.claims.map((claim) => [claim.claim_id, claim]));
  const claims: MemoClaimProvenance[] = [];
  const derivations: MemoDerivation[] = [];

  for (const criterion of [...(evaluation.criteria ?? [])].sort((left, right) => left.criterion.localeCompare(right.criterion))) {
    const ids = [
      ...criterion.supporting_claim_ids.map((claimId) => ({ claimId, relationship: 'supports' as const })),
      ...criterion.contradicting_claim_ids.map((claimId) => ({ claimId, relationship: 'contradicts' as const })),
    ];
    // A criterion with no linked claims already surfaces as a "missing evidence"
    // gap below — don't also report it here as an empty rule-derived provenance
    // row. Only unclaimed criteria that aren't already a named gap belong here.
    if (ids.length === 0 && criterion.missing_evidence.length === 0) {
      derivations.push({ criterion: criterion.criterion, provenance: 'rule-derived' });
    }
    for (const { claimId, relationship } of ids.sort((left, right) =>
      left.relationship.localeCompare(right.relationship) || left.claimId.localeCompare(right.claimId),
    )) {
      const claim = claimById.get(claimId);
      if (!claim) continue;
      const sources = (sourcesByClaim.get(claimId) ?? [])
        .filter((source) => source.link.relationship === relationship);
      const memoSources = toMemoSources(sources);
      claims.push({
        claimId,
        claim: claim.display_text,
        criterion: criterion.criterion,
        relationship,
        provenance: provenanceFor(claim, sources),
        sources: memoSources,
      });
    }
  }

  claims.sort((left, right) =>
    left.criterion.localeCompare(right.criterion)
    || left.relationship.localeCompare(right.relationship)
    || left.claimId.localeCompare(right.claimId),
  );
  derivations.sort((left, right) => left.criterion.localeCompare(right.criterion));

  const coverage = coverageFor(evaluation);
  const recommendation = evaluation.recommendation;
  const lean = leanFor(recommendation?.recommended_state);
  const blocked = coverage === 'missing' || coverage === 'contradictory';
  const ruling = input.ruling
    ? {
      ruling_id: input.ruling.ruling_id,
      decision: input.ruling.decision as HumanRulingRecordDecision,
      rationale: input.ruling.rationale,
      created_at: input.ruling.created_at,
    }
    : null;

  return {
    status: blocked ? 'blocked' : ruling ? 'recorded' : 'ready_for_ruling',
    lean,
    leanProvenance: recommendation ? 'rule-derived' : 'missing',
    mandate: recommendation?.mandate_conflicts.length ? 'conflicted' : 'unknown',
    coverage,
    agreement: 'unknown',
    ruling,
    drivers: visibleDrivers(recommendation?.decision_drivers ?? []),
    claims,
    derivations,
    risks: riskGaps(evaluation),
  };
}

export const MEMO_STATUS_LABELS: Record<MemoDecisionBriefStatus, string> = {
  loading: 'Decision data loading',
  ready_for_ruling: 'Ready for ruling',
  blocked: 'Blocked by evidence',
  recorded: 'Ruling recorded',
  unavailable: 'Decision data unavailable',
};

export const MEMO_LEAN_LABELS: Record<MemoDecisionBriefLean, string> = {
  advance: 'Advance',
  monitor: 'Monitor',
  pass: 'Pass',
  none: 'No system lean',
};

/**
 * The masthead's verdict badge is a first read, before the reader has seen any
 * evidence — it must never assert more than the honest state model does.
 * `blocked` always wins (missing/contradictory evidence pre-empts a lean, per
 * ADR-0013); a recorded human ruling is what actually happened; otherwise the
 * badge reflects the system's rule-derived lean, clearly not a human decision.
 */
export function memoVerdictVariant(brief: MemoDecisionBrief): DecisionBadgeVariant {
  if (brief.status === 'loading' || brief.status === 'unavailable') return 'undecided';
  if (brief.status === 'blocked') return 'escalation';
  if (brief.status === 'recorded' && brief.ruling) {
    if (brief.ruling.decision === 'advance' || brief.ruling.decision === 'invest') return 'INVEST';
    if (brief.ruling.decision === 'pass') return 'PASS';
    return 'MONITOR';
  }
  if (brief.lean === 'advance') return 'INVEST';
  if (brief.lean === 'pass') return 'PASS';
  if (brief.lean === 'monitor') return 'MONITOR';
  return 'awaiting';
}
