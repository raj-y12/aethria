import { useCallback, forwardRef, useEffect, useImperativeHandle, useMemo, useState, type ReactNode } from 'react';
import { fetchMemo, type MemoPartialPayload } from '../api/startups';
import { motion } from 'framer-motion';
import './InvestmentMemoContent.css';
import type { Review, ScoringDimensionKey, SignalItem, SingleReview, Startup } from '../types/startup';
import { normalizeStructuredScoring } from '../lib/reviewScoring';
import {
  buildMemoPDF,
  icPackSafeBaseName,
  getPipelineReplaySteps,
  type PipelineReplayStep,
} from '../lib/memoIcPack';
import { memoReferenceHref, memoReferenceLabel } from '../lib/memoReferenceHref';
import { DECISION_LABELS } from '../design-system/semantics';
import { UI_DETAIL_EMPTY_HINT } from '../design-system/ui-text';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';
import AssessmentScorecard from './scoring/AssessmentScorecard';
import MemoRulingSection from './memo/MemoRulingSection';
import MemoPrecedentStrip from './memo/MemoPrecedentStrip';
import MemoPortfolioContext from './memo/MemoPortfolioContext';
import { DECISION_BADGE_LABEL } from './DecisionBadge';
import { getDecisionBadgeVariant, type DecisionBadgeVariant } from '../lib/decisionBadgeVariant';
import { resolveEscalation } from '../api/escalations';
import {
  buildOptimisticResolution,
  isDealDecided,
  type RulingDecision,
} from '../lib/dealState';
import { extractAdverseRegister, type AdverseRegisterItem, type AdverseSeverity } from '../lib/adverseRegister';
import {
  createDefaultFundConfiguration,
  shouldGateRisk,
  type FundConfiguration,
} from '../lib/fundConfiguration';
import { findPrecedentCandidates } from '../lib/institutionalConviction';
import { getNextStepText, parseNextStepItems } from '../lib/memoText';
const MEMO_POLL_INITIAL_MS = 2000;
const MEMO_POLL_MAX_MS = 15000;
const MEMO_POLL_MAX_ATTEMPTS = 60;

const SCORING_DIMENSIONS: Array<{ key: ScoringDimensionKey; label: string; id: string }> = [
  { key: 'market', label: 'Market', id: 'memo-score-market' },
  { key: 'execution', label: 'Execution', id: 'memo-score-execution' },
  { key: 'product', label: 'Product', id: 'memo-score-product' },
  { key: 'technical', label: 'Technical', id: 'memo-score-technical' },
  { key: 'defensibility', label: 'Defensibility', id: 'memo-score-defensibility' },
];

function mergeMemoPartial(base: Startup, partial: MemoPartialPayload | null): Startup {
  if (!partial) return base;
  return {
    ...base,
    scout: partial.scout ?? base.scout,
    review: partial.review ?? base.review,
    partner: partial.partner ?? base.partner,
    financials: partial.financials ?? base.financials,
  };
}

const MEMO_GENERATING_DETAIL_AWAITING = 'Reviewers scoring against your thesis.';
const MEMO_GENERATING_DETAIL_UNDECIDED = 'Partner engine determining the call.';
const MEMO_GENERATING_DETAIL_ESCALATION = 'Partner flagged this for human review.';
const MEMO_GENERATING_DETAIL_FORMATTING = 'Finalising the memo.';

function memoGeneratingDetailForVariant(variant: DecisionBadgeVariant): string {
  switch (variant) {
    case 'awaiting':
      return MEMO_GENERATING_DETAIL_AWAITING;
    case 'undecided':
      return MEMO_GENERATING_DETAIL_UNDECIDED;
    case 'escalation':
      return MEMO_GENERATING_DETAIL_ESCALATION;
    default:
      return MEMO_GENERATING_DETAIL_FORMATTING;
  }
}

function memoSourceRows(startup: Startup) {
  const structured = startup.scout.source_evidence ?? [];
  if (structured.length > 0) {
    return structured.map((item) => ({
      reference: item.reference,
      supports: item.supports || 'Company evidence',
      href: item.url || memoReferenceHref(item.reference),
      label: memoReferenceLabel(item.reference),
    }));
  }
  return (startup.scout.references ?? [])
    .map((r) => String(r ?? '').trim())
    .filter(Boolean)
    .map((ref) => ({
      reference: ref,
      supports: 'Company evidence',
      href: memoReferenceHref(ref),
      label: memoReferenceLabel(ref),
    }));
}

function reviewHasThesisAlignment(r: Review | null | undefined): boolean {
  if (!r) return false;
  return (
    r.thesis_alignment_score != null ||
    (r.thesis_fit_points?.length ?? 0) > 0 ||
    (r.thesis_deviation_points?.length ?? 0) > 0 ||
    r.thesis_matches_fund != null
  );
}

export interface InvestmentMemoContentProps {
  startup: Startup | null;
  onClose?: () => void;
  embedded?: boolean;
  /** Share link / co-GP view: memo readable, ruling controls hidden. */
  readOnly?: boolean;
  onMemoPipelineReady?: () => void;
  onDecisionResolved?: (startup: Startup) => void;
  fundConfiguration?: FundConfiguration;
  peerStartups?: Startup[];
  portfolioSignals?: SignalItem[];
}

export interface InvestmentMemoContentHandle {
  downloadPDF: () => void;
}

function normalizeParagraphs(value: unknown): string[] {
  if (value == null) return [];
  if (Array.isArray(value)) {
    return value
      .map((v) => String(v ?? '').replace(/\s*\n+\s*/g, ' ').trim())
      .filter(Boolean)
      .flatMap((v) => [v]);
  }
  if (typeof value === 'string') return [value.replace(/\s*\n+\s*/g, ' ').trim()].filter(Boolean);
  return [];
}

function normalizeListItemText(value: unknown): string {
  return String(value ?? "")
    .replace(/^\s*[•·*-]\s+/, "")
    .trim();
}

function normalizeMemoKey(value: unknown): string {
  return String(value ?? '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

const MEMO_NUMBER_TOKEN_REGEX = /(?:[$€£¥]\s*)?\d[\d,]*(?:\.\d+)?(?:%|x|X|k|K|m|M|b|B)?(?:\/\d+(?:\.\d+)?)?/g;

function renderWithMonoNumbers(value: unknown): ReactNode {
  const text = String(value ?? '');
  if (!text) return text;
  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let tokenIndex = 0;
  for (const match of text.matchAll(MEMO_NUMBER_TOKEN_REGEX)) {
    const token = match[0];
    const start = match.index ?? 0;
    if (start > lastIndex) {
      parts.push(text.slice(lastIndex, start));
    }
    parts.push(
      <span key={`memo-num-${start}-${tokenIndex}`} className="memoNum">
        {token}
      </span>
    );
    lastIndex = start + token.length;
    tokenIndex += 1;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts.length ? <>{parts}</> : text;
}

function partnerDecisionHeadline(startup: Startup): string {
  const rec = startup.partner?.recommendation;
  if (rec == null) return '—';
  return DECISION_LABELS[rec] ?? String(rec);
}

function toJudgmentReasoning(startup: Startup): string[] {
  const rationale = startup.partner?.decision_rationale;
  if (!rationale) return [];
  return normalizeParagraphs(rationale);
}

function firstNonEmpty(...values: Array<unknown>): string {
  for (const value of values) {
    const text = String(value ?? '').trim();
    if (text) return text;
  }
  return '';
}

function getPartnerEconomicBadgeVariant(startup: Startup): 'INVEST' | 'PASS' | 'MONITOR' | null {
  const rec = startup.partner?.recommendation;
  if (rec == null) return null;
  if (rec === 'INVEST') return 'INVEST';
  if (rec === 'PASS') return 'PASS';
  return 'MONITOR';
}

function formatSectorAndCategory(startup: Startup): string {
  const sector = startup.scout.sector?.trim() || '—';
  const category = startup.scout.funding_stage?.trim() || startup.scout.scout_type?.trim() || '';
  return (category ? `${sector} · ${category}` : sector).toUpperCase();
}

function memoHeaderThesisLine(startup: Startup): string {
  const scoutOneLine = startup.scout.one_line?.trim();
  if (scoutOneLine) return scoutOneLine;
  const candidates = [
    startup.partner?.snapshot?.key_signal,
    startup.partner?.decision_drivers?.[0],
    startup.review?.aethria_view?.thesis_fit_line,
    startup.review?.investment_thesis?.[0],
    startup.partner?.thesis,
    startup.partner?.why_this_matters,
    startup.partner?.snapshot?.one_liner,
    startup.review?.overall_summary,
    startup.scout.primary_thesis,
  ];

  for (const candidate of candidates) {
    const value = String(candidate ?? '').trim();
    if (!value) continue;
    return value;
  }

  return '';
}

function isLookupStartup(startup: Startup): boolean {
  return (startup.scout.origin_type ?? '').toLowerCase() === 'on_demand_lookup';
}

const actionBtnCls = 'memoAction';

function pipelineReplayOneLiner(steps: PipelineReplayStep[]): string {
  if (!steps.length) return '';
  const flow = steps.map((s) => s.label).join(' → ');
  const last = [...steps].reverse().find((s) => s.atDisplay && s.atDisplay !== '—');
  const tail = last?.atDisplay;
  return tail ? `${flow} · ${tail}` : flow;
}

const SEVERITY_LABEL: Record<AdverseRegisterItem['severity'], string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

function decisionLabel(decision: RulingDecision): string {
  if (decision === 'YES') return 'Invest';
  if (decision === 'NO') return 'Pass';
  return 'Monitor';
}

function uniqueRiskItems(startup: Startup | null): { risks: string[]; mitigation: string[] } {
  if (!startup) return { risks: [], mitigation: [] };
  const combined = [
    ...(startup.review?.diligence_red_flags ?? []),
    ...(startup.review?.key_risks ?? []),
    ...(startup.partner?.risks ?? []),
  ].map((r) => String(r ?? '').trim()).filter(Boolean);
  const seen = new Set<string>();
  const risks = combined.filter((r) => {
    const key = r.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const mitigation = (startup.review?.risk_mitigation ?? []).filter((s) => String(s ?? '').trim());
  return { risks, mitigation };
}

function adverseCoverageKeys(adverseItems: AdverseRegisterItem[]): Set<string> {
  const keys = new Set<string>();
  for (const item of adverseItems) {
    keys.add(item.whyItMatters.toLowerCase());
    keys.add(item.title.toLowerCase());
  }
  return keys;
}

function isAdverseCovered(text: string, adverseItems: AdverseRegisterItem[]): boolean {
  const key = text.toLowerCase();
  const keys = adverseCoverageKeys(adverseItems);
  if (keys.has(key)) return true;
  return adverseItems.some((item) => {
    const why = item.whyItMatters.toLowerCase();
    return why.includes(key) || key.includes(why);
  });
}

function missingDataItems(startup: Startup | null, adverseItems: AdverseRegisterItem[]): string[] {
  if (!startup) return [];
  const items = [
    startup.scout.biggest_unknown?.trim(),
    ...(startup.review?.diligence_red_flags ?? []).filter((item) => /missing|unknown|unclear/i.test(String(item))),
  ].map((item) => String(item ?? '').trim()).filter(Boolean);
  const seen = new Set<string>();
  const skipAdverseOverlap = adverseItems.length > 0;
  return items.filter((item) => {
    const key = item.toLowerCase();
    if (seen.has(key)) return false;
    if (skipAdverseOverlap && isAdverseCovered(item, adverseItems)) return false;
    seen.add(key);
    return true;
  }).slice(0, 5);
}

function sourceSupportLine(source: ReturnType<typeof memoSourceRows>[number], showConfidence: boolean): string {
  if (!showConfidence) return source.supports;
  return `${source.supports} · Scout confidence signal`;
}

const REVIEWER_LABELS: Record<string, string> = {
  DefaultReviewer: 'Default',
  SkepticalReviewer: 'Skeptical',
  OpportunistReviewer: 'Opportunist',
};

function collapseWhitespace(value: unknown): string {
  return String(value ?? '').replace(/\s+/g, ' ').trim();
}

// Truncation is intentionally disabled across the memo — full text is shown everywhere,
// nothing is cut mid-thought. Both helpers keep their signatures (so the many call sites
// stay unchanged) but now just normalize whitespace and return the complete string.
function clipText(value: unknown, _maxLen?: number): string {
  return collapseWhitespace(value);
}

// A short lede made of WHOLE sentences (never cut mid-thought, never an ellipsis). Used for
// the cover standfirst so it stays a lede, not the full multi-paragraph thesis — the complete
// text still appears in the body sections, so nothing is lost.
function leadSentences(value: unknown, maxChars = 260): string {
  const text = collapseWhitespace(value);
  if (!text) return '';
  const sentences = text.split(/(?<=[.!?])\s+/);
  let out = sentences[0] ?? text;
  for (let i = 1; i < sentences.length; i += 1) {
    if (`${out} ${sentences[i]}`.length > maxChars) break;
    out = `${out} ${sentences[i]}`;
  }
  return out;
}

function reviewerMeanScore(rv: SingleReview): number | null {
  const vals = [
    rv.market_score,
    rv.product_score,
    rv.technical_score,
    rv.execution_score,
    rv.defensibility_score,
  ]
    .map((v) => Number(v))
    .filter((v) => Number.isFinite(v));
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

/**
 * Investment case observations — partner-voiced reasons this might matter, drawn from
 * narrative fields only (no scoring terms or system metadata). Deduped, capped at five.
 */
function buildInvestmentCase(startup: Startup, exclude: string): string[] {
  const candidates = [
    startup.partner?.why_this_matters,
    startup.partner?.market_insight,
    startup.partner?.product_edge,
    startup.partner?.traction_signals,
    startup.review?.aethria_view?.thesis_fit_line,
    ...(startup.review?.investment_thesis ?? []),
    ...(startup.partner?.decision_drivers ?? []),
    startup.scout.why_now,
    startup.scout.primary_thesis,
  ];
  const seen = new Set<string>();
  const excludeKey = normalizeMemoKey(exclude);
  if (excludeKey) seen.add(excludeKey);
  const points: string[] = [];
  for (const candidate of candidates) {
    const text = collapseWhitespace(candidate);
    if (!text) continue;
    const key = normalizeMemoKey(text);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    points.push(clipText(text, 240));
    if (points.length >= 5) break;
  }
  return points;
}

/** A fact is shown only when it carries real signal — empty, [MISSING], and
 *  non-answers ("unknown"/"n/a"/"tbd") collapse to null so the memo never renders
 *  a hollow "Stage: Unknown" row. Honest absence beats filler. */
function cleanFactValue(value: unknown): string | null {
  const s = String(value ?? '').trim();
  if (!s) return null;
  if (/^\[?\s*missing/i.test(s)) return null;
  if (['unknown', 'n/a', 'na', 'tbd', 'none', '—', '-'].includes(s.toLowerCase())) return null;
  return s;
}

function buildSnapshotRows(startup: Startup, blocker: string): Array<{ label: string; text: string }> {
  return [
    {
      label: 'What it does',
      text: firstNonEmpty(startup.scout.solution, startup.scout.one_line, startup.partner?.snapshot?.one_liner),
    },
    {
      label: 'Who it serves',
      text: firstNonEmpty(startup.scout.target_users, startup.scout.problem),
    },
    {
      label: 'Why Aethria flagged it',
      text: firstNonEmpty(
        startup.partner?.snapshot?.key_signal,
        startup.partner?.decision_drivers?.[0],
        startup.scout.why_now,
        startup.partner?.why_this_matters,
      ),
    },
    { label: 'What limits conviction', text: blocker },
  ]
    .map((row) => ({ label: row.label, text: clipText(row.text, 220) }))
    .filter((row) => row.text);
}

interface MemoKiller {
  statement: string;
  severity: AdverseSeverity;
}

/** Ranked, deduped, compressed conviction-limiters. One strong statement beats three similar warnings. */
function buildKillers(adverse: AdverseRegisterItem[], fallbackRisks: string[]): MemoKiller[] {
  const seen = new Set<string>();
  const killers: MemoKiller[] = [];
  for (const item of adverse) {
    const statement = clipText(item.whyItMatters || item.title, 220);
    const key = normalizeMemoKey(statement);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    killers.push({ statement, severity: item.severity });
    if (killers.length >= 4) break;
  }
  if (!killers.length) {
    for (const risk of fallbackRisks) {
      const statement = clipText(risk, 220);
      const key = normalizeMemoKey(statement);
      if (!key || seen.has(key)) continue;
      seen.add(key);
      killers.push({ statement, severity: 'medium' });
      if (killers.length >= 3) break;
    }
  }
  return killers;
}

/** A list that shows the first `cap` items and reveals the rest in place via "Show N more".
 *  Used for long memo lists so the collapsed view stays tight without ever truncating content. */
function ExpandableList<T>({
  items,
  cap = 4,
  className = 'memoList',
  as: Tag = 'ul',
  renderItem,
}: {
  items: T[];
  cap?: number;
  className?: string;
  as?: 'ul' | 'div';
  renderItem: (item: T, index: number) => ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  const shown = expanded ? items : items.slice(0, cap);
  const rest = items.length - cap;
  return (
    <>
      <Tag className={className}>{shown.map(renderItem)}</Tag>
      {rest > 0 && (
        <button type="button" className="memoShowMore" onClick={() => setExpanded((v) => !v)}>
          {expanded ? 'Show less' : `Show ${rest} more`}
        </button>
      )}
    </>
  );
}

function MemoDisclosureSection({
  id,
  title,
  summary,
  initialOpen = false,
  children,
}: {
  id: string;
  title: string;
  summary?: ReactNode;
  initialOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(initialOpen);
  useEffect(() => {
    setOpen(initialOpen);
  }, [id, initialOpen]);
  return (
    <section className="memoDocSection memoDisclosureSection" aria-labelledby={`${id}-title`}>
      <button
        type="button"
        className="memoDisclosureToggle"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls={`${id}-body`}
      >
        <span className="memoDisclosureTitle" id={`${id}-title`}>{title}</span>
        <span className="memoDisclosureMeta">{summary}</span>
        <span
          aria-hidden
          className={open ? 'memoScoreChevron memoDisclosurePlus memoScoreChevron--open' : 'memoScoreChevron memoDisclosurePlus'}
        >
          ›
        </span>
      </button>
      <div id={`${id}-body`} className={open ? 'memoDisclosureBody' : 'hidden'}>
        {children}
      </div>
    </section>
  );
}

const InvestmentMemoContent = forwardRef<InvestmentMemoContentHandle, InvestmentMemoContentProps>(function InvestmentMemoContent(
  {
    startup,
    onClose,
    embedded = false,
    readOnly = false,
    onMemoPipelineReady,
    onDecisionResolved,
    fundConfiguration,
    peerStartups = [],
    portfolioSignals = [],
  },
  ref
) {
  const config = fundConfiguration ?? createDefaultFundConfiguration();
  const reduceMotion = usePrefersReducedMotion();
  const wrapperCls = embedded ? 'memoPanel memoPanel--embedded' : 'memoPanel';
  const [risksReviewed, setRisksReviewed] = useState(false);
  const [rulingDecision, setRulingDecision] = useState<RulingDecision | null>(null);
  const [rulingNotes, setRulingNotes] = useState('');
  const [rulingSaving, setRulingSaving] = useState(false);
  const [rulingError, setRulingError] = useState<string | null>(null);
  const [memoPartial, setMemoPartial] = useState<MemoPartialPayload | null>(null);
  const [memoPipeline, setMemoPipeline] = useState<'idle' | 'generating' | 'ready' | 'failed'>('idle');
  const [memoGateError, setMemoGateError] = useState<string | null>(null);

  const displayStartup = useMemo(
    () => (startup ? mergeMemoPartial(startup, memoPartial) : null),
    [startup, memoPartial]
  );

  const pipelineBadgeVariant = useMemo(
    () => (displayStartup ? getDecisionBadgeVariant(displayStartup) : null),
    [displayStartup]
  );
  const pipelineStatusDetail = useMemo(
    () =>
      pipelineBadgeVariant
        ? memoGeneratingDetailForVariant(pipelineBadgeVariant)
        : '',
    [pipelineBadgeVariant]
  );

  const handleDownloadPDF = useCallback(async () => {
    if (!displayStartup) return;
    const doc = await buildMemoPDF(displayStartup);
    doc.save(`${icPackSafeBaseName(displayStartup)}-ic-pack.pdf`);
  }, [displayStartup]);

  useImperativeHandle(
    ref,
    () => ({ downloadPDF: handleDownloadPDF }),
    [handleDownloadPDF]
  );

  const contentKey = displayStartup?.id ?? startup?.id ?? 'empty';
  const companyName = displayStartup?.scout.name?.trim() || '';
  const sectorCategory = displayStartup ? formatSectorAndCategory(displayStartup) : '';

  useEffect(() => {
    if (!startup?.id) {
      setMemoPipeline('idle');
      setMemoPartial(null);
      setMemoGateError(null);
      return;
    }
    setMemoPartial(null);
    setMemoGateError(null);

    if (startup.partner?.recommendation) {
      setMemoPipeline('ready');
      return;
    }

    setMemoPipeline('idle');
    let cancelled = false;
    let t: ReturnType<typeof setTimeout> | undefined;

    let attempt = 0;
    const scheduleNextPoll = () => {
      attempt += 1;
      if (attempt >= MEMO_POLL_MAX_ATTEMPTS) {
        setMemoPipeline('failed');
        setMemoGateError('Memo generation timed out. Please retry in a moment.');
        return;
      }
      const backoff = Math.min(
        MEMO_POLL_INITIAL_MS * 2 ** Math.max(0, attempt - 1),
        MEMO_POLL_MAX_MS
      );
      t = setTimeout(poll, backoff);
    };

    const poll = async () => {
      try {
        const res = await fetchMemo(startup.id);
        if (cancelled) return;
        if (!res) {
          scheduleNextPoll();
          return;
        }
        if (res.status === 'ready') {
          setMemoPipeline('ready');
          setMemoPartial(null);
          onMemoPipelineReady?.();
          return;
        }
        if (res.status === 'failed') {
          setMemoPipeline('failed');
          setMemoGateError(res.error ?? 'Investment memo pipeline failed.');
          if (res.partial) setMemoPartial(res.partial);
          return;
        }
        setMemoPipeline('generating');
        if (res.partial) setMemoPartial(res.partial);
        scheduleNextPoll();
      } catch {
        if (!cancelled) scheduleNextPoll();
      }
    };
    void poll();
    return () => {
      cancelled = true;
      if (t) clearTimeout(t);
    };
  }, [startup?.id, startup?.partner?.recommendation, onMemoPipelineReady]);

  const showJudgment = !!displayStartup?.partner?.recommendation;
  const decisionHeadline = displayStartup && showJudgment ? partnerDecisionHeadline(displayStartup) : '';
  const decisionBadgeVariant = useMemo(
    () => (displayStartup && showJudgment ? getPartnerEconomicBadgeVariant(displayStartup) : null),
    [displayStartup, showJudgment]
  );
  const showEscalationBadge = !!(displayStartup?.partner?.human_review_required && decisionBadgeVariant);
  const showLookupBadge = !!(displayStartup && isLookupStartup(displayStartup));
  const headerLocation = displayStartup?.scout.location?.trim() || '';
  const headerMeta = [sectorCategory.trim(), showLookupBadge ? 'LOOKUP' : ''].filter(Boolean).join(' · ');
  const headerThesisLine = displayStartup ? memoHeaderThesisLine(displayStartup) : '';
  const reasoningParagraphs = useMemo(
    () => (displayStartup && showJudgment ? toJudgmentReasoning(displayStartup) : []),
    [displayStartup, showJudgment]
  );
  const adverseRegister = useMemo(
    () => extractAdverseRegister(displayStartup),
    [displayStartup]
  );
  const missingEvidenceItems = useMemo(
    () => missingDataItems(displayStartup, adverseRegister),
    [adverseRegister, displayStartup]
  );
  const memoSources = useMemo(
    () => (displayStartup ? memoSourceRows(displayStartup) : []),
    [displayStartup]
  );
  const highAdverseCount = adverseRegister.filter((item) => item.severity === 'high').length;
  const riskFactors = useMemo(
    () => uniqueRiskItems(displayStartup),
    [displayStartup]
  );
  const hasHighAdverse = adverseRegister.some((item) => item.severity === 'high');
  const isAlreadyDecided = displayStartup ? isDealDecided(displayStartup) : false;
  const needsRiskAcknowledgement = Boolean(
    displayStartup && shouldGateRisk(config, hasHighAdverse, adverseRegister.length > 0, isAlreadyDecided)
  );
  const coverRulingHeadline = showJudgment
    ? decisionHeadline
    : pipelineBadgeVariant
      ? DECISION_BADGE_LABEL[pipelineBadgeVariant]
      : 'Pending';
  const coverRulingVariantClass = (
    (showJudgment ? decisionBadgeVariant : pipelineBadgeVariant) ?? 'pending'
  )
    .toString()
    .toLowerCase();
  const coverStatusText = isAlreadyDecided && displayStartup?.human_resolution?.resolved_at
    ? `Recorded ruling — ${decisionLabel(displayStartup.human_resolution.decision)}`
    : showEscalationBadge && !isAlreadyDecided
      ? 'Human ruling required'
      : memoPipeline === 'generating' && !showJudgment
        ? pipelineStatusDetail
        : !showJudgment
          ? 'Pipeline assembling recommendation'
          : null;
  const showCoverPipelineDetail = memoPipeline === 'generating' && !showJudgment && !!coverStatusText;
  const riskReviewOutstanding = needsRiskAcknowledgement && !risksReviewed;
  const convictionHistory = displayStartup?.conviction_state?.decision_history ?? [];
  const precedentCandidates = useMemo(
    () => (displayStartup ? findPrecedentCandidates(displayStartup, peerStartups) : []),
    [displayStartup, peerStartups]
  );

  useEffect(() => {
    setRisksReviewed(false);
    setRulingDecision(null);
    setRulingNotes('');
    setRulingError(null);
  }, [config.memo.deepDiveCollapsed, startup?.id]);

  useEffect(() => {
    if (!displayStartup || rulingDecision) return;
    const rec = displayStartup.partner?.recommendation;
    if (rec === 'INVEST') setRulingDecision('YES');
    else if (rec === 'PASS') setRulingDecision('NO');
    else if (rec === 'MONITOR') setRulingDecision('MAYBE');
  }, [displayStartup, rulingDecision]);

  const handleRulingSubmit = useCallback(async () => {
    if (!displayStartup || !rulingDecision || rulingNotes.trim().length < 5) return;
    const previous = displayStartup;
    const optimistic = buildOptimisticResolution(displayStartup, rulingDecision, rulingNotes.trim());
    setRulingSaving(true);
    setRulingError(null);
    onDecisionResolved?.(optimistic);
    try {
      await resolveEscalation(displayStartup.id, rulingDecision, rulingNotes.trim(), risksReviewed);
      setRulingSaving(false);
    } catch {
      onDecisionResolved?.(previous);
      setRulingSaving(false);
      setRulingError('Ruling did not save. Retry once the API is reachable.');
    }
  }, [
    displayStartup,
    onDecisionResolved,
    risksReviewed,
    rulingDecision,
    rulingNotes,
  ]);

  const structuredScoring = useMemo(
    () => normalizeStructuredScoring(displayStartup?.review ?? null),
    [displayStartup?.review]
  );

  const scoringPresentation = useMemo(
    () => displayStartup?.review?.scoring_presentation ?? null,
    [displayStartup?.review]
  );
  const nextStepText = displayStartup ? getNextStepText(displayStartup) : '';
  const nextStepItems = useMemo(() => parseNextStepItems(nextStepText), [nextStepText]);
  const thesisAlignmentBrief = useMemo(() => {
    const review = displayStartup?.review;
    if (!review) return '';
    const score = review.thesis_alignment_score;
    if (score != null) {
      const ten = score <= 1 ? score * 10 : score;
      return `${ten.toFixed(0)}/10 thesis alignment`;
    }
    if (review.thesis_matches_fund != null) return review.thesis_matches_fund ? 'Mandate aligned' : 'Mandate conflict';
    return firstNonEmpty(review.aethria_view?.thesis_fit_line, review.thesis_fit_points?.[0], review.thesis_deviation_points?.[0]);
  }, [displayStartup?.review]);
  const openingRiskItems = useMemo(() => {
    const items = [
      ...adverseRegister.map((item) => item.title),
      ...missingEvidenceItems,
      ...riskFactors.risks,
    ].map((item) => normalizeListItemText(item)).filter(Boolean);
    const seen = new Set<string>();
    return items.filter((item) => {
      const key = normalizeMemoKey(item);
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    }).slice(0, 2);
  }, [adverseRegister, missingEvidenceItems, riskFactors.risks]);
  const pipelineReplaySteps = useMemo(
    () => (displayStartup ? getPipelineReplaySteps(displayStartup) : []),
    [displayStartup]
  );
  const pipelineReplaySummary = useMemo(
    () => pipelineReplayOneLiner(pipelineReplaySteps),
    [pipelineReplaySteps]
  );
  // ── Editorial derivations ──
  const coverStandfirst = displayStartup
    ? leadSentences(
        firstNonEmpty(
          displayStartup.partner?.thesis,
          displayStartup.review?.aethria_view?.headline,
          displayStartup.partner?.why_this_matters,
          headerThesisLine,
          displayStartup.review?.overall_summary,
        ),
        260,
      )
    : '';
  const coverBlocker = displayStartup
    ? (openingRiskItems[0] ?? collapseWhitespace(displayStartup.scout.biggest_unknown))
    : '';
  const coverAction = displayStartup ? (nextStepItems[0] ?? collapseWhitespace(nextStepText)) : '';
  const investmentCasePoints = useMemo(
    () => (displayStartup ? buildInvestmentCase(displayStartup, coverStandfirst) : []),
    [displayStartup, coverStandfirst]
  );
  const snapshotRows = useMemo(
    () => (displayStartup ? buildSnapshotRows(displayStartup, coverBlocker) : []),
    [displayStartup, coverBlocker]
  );
  // Decision confidence — surfaced on the verdict so the recommendation is honest
  // about how sure it is, not just what it concludes.
  const partnerConfidencePct =
    typeof displayStartup?.partner?.confidence === 'number'
      ? Math.round(Math.max(0, Math.min(1, displayStartup.partner.confidence)) * 100)
      : null;
  const convictionLine = useMemo(() => {
    const parts: string[] = [];
    if (displayStartup?.review?.overall_score != null) {
      const sc = Number(displayStartup.review.overall_score);
      const scText = Number.isFinite(sc) ? sc.toFixed(1) : String(displayStartup.review.overall_score);
      parts.push(`${scText}/10 conviction`);
    } else if (thesisAlignmentBrief) {
      parts.push(thesisAlignmentBrief);
    }
    if (partnerConfidencePct != null) parts.push(`${partnerConfidencePct}% partner confidence`);
    return parts.length ? parts.join('   ·   ') : 'Conviction forming';
  }, [displayStartup?.review?.overall_score, thesisAlignmentBrief, partnerConfidencePct]);
  // The single question the deal hinges on (AethriaView synthesis) — previously unused.
  const focalQuestion = cleanFactValue(displayStartup?.review?.aethria_view?.focal_question);
  // Vitals: the quantitative facts. Stage/TAM come from the scout; funding, valuation,
  // traction, and IP come from the backend Financials grounding gate — every value there
  // is verified against a cited source, so anything present is safe to show verbatim.
  const fin = displayStartup?.financials;
  const vitalsStrip = useMemo(
    () =>
      [
        { label: 'Location', value: cleanFactValue(displayStartup?.scout?.location) },
        { label: 'Stage', value: cleanFactValue(displayStartup?.scout?.funding_stage) },
        { label: 'Market (TAM)', value: cleanFactValue(displayStartup?.scout?.est_tam) },
        { label: 'Valuation', value: cleanFactValue(fin?.valuation_est) },
      ].filter((v): v is { label: string; value: string } => !!v.value),
    [displayStartup?.scout?.location, displayStartup?.scout?.funding_stage, displayStartup?.scout?.est_tam, fin?.valuation_est]
  );
  const fundingLine = cleanFactValue(fin?.funding_history);
  // Prefer the source-verified traction metric; fall back to the partner's narrative signal.
  const tractionLine =
    cleanFactValue(fin?.traction_metrics) ?? cleanFactValue(displayStartup?.partner?.traction_signals);
  const ipLine = cleanFactValue(fin?.ip_status);
  const modelLine = useMemo(() => {
    for (const item of displayStartup?.review?.business_model_analysis ?? []) {
      const cleaned = cleanFactValue(item);
      if (cleaned) return clipText(cleaned, 160);
    }
    return null;
  }, [displayStartup?.review?.business_model_analysis]);
  const hasVitals =
    vitalsStrip.length > 0 || !!fundingLine || !!tractionLine || !!ipLine || !!modelLine;
  const memoKillers = useMemo(
    () => buildKillers(adverseRegister, riskFactors.risks),
    [adverseRegister, riskFactors.risks]
  );
  const reviewerConsensusRows = useMemo(() => {
    const reviews = displayStartup?.review?.reviews ?? [];
    return reviews
      .map((rv) => ({
        key: rv.reviewer_type,
        name: REVIEWER_LABELS[rv.reviewer_type] ?? rv.reviewer_type,
        score: reviewerMeanScore(rv),
        verdict: rv.verdict,
        // Lead sentence only — the reviewer's full read lives in Reviewer detail. Keeps the
        // consensus panel compact instead of stacking a full paragraph per reviewer.
        take: leadSentences(rv.overall_summary, 140),
      }))
      .filter((row) => row.score != null || row.take);
  }, [displayStartup?.review?.reviews]);
  const reviewerConsensus = useMemo(() => {
    const scores = reviewerConsensusRows
      .map((row) => row.score)
      .filter((score): score is number => score != null);
    const min = scores.length ? Math.min(...scores) : null;
    const max = scores.length ? Math.max(...scores) : null;
    const spread = min != null && max != null ? max - min : null;
    const split =
      displayStartup?.review?.reviewer_disagreement === true || (spread != null && spread >= 2);
    const verdict =
      displayStartup?.review?.consensus_verdict ?? displayStartup?.review?.derived_verdict ?? null;
    return { min, max, spread, split, verdict };
  }, [
    reviewerConsensusRows,
    displayStartup?.review?.reviewer_disagreement,
    displayStartup?.review?.consensus_verdict,
    displayStartup?.review?.derived_verdict,
  ]);
  return (
    <article className={wrapperCls} aria-labelledby="memo-title">
      {/* Styles extracted to InvestmentMemoContent.css */}

      {!displayStartup ? (
        <div className="memoEmpty">
          <div className="memoEmptyInner">
            <p className="memoEmptyWordmark">Aethria</p>
            <div className="memoEmptyHint">{UI_DETAIL_EMPTY_HINT}</div>
          </div>
        </div>
      ) : (
        <div
          className={`memoScroll relative${embedded ? '' : ' memo-scroll-root'}`}
          role="region"
          aria-label="Investment memo"
        >
          {onClose && (
            <div className="memoHeaderActions">
              <button type="button" onClick={handleDownloadPDF} className={actionBtnCls}>IC Pack (PDF)</button>
              <button type="button" onClick={onClose} className={actionBtnCls}>Close</button>
            </div>
          )}

          {memoPipeline === 'failed' && (
            <div className="memoGateStrip memoGateStrip--error">
              <motion.div
                className="memoGateStripInner"
                initial={
                  reduceMotion
                    ? { opacity: 1, transform: 'translateY(0px)' }
                    : { opacity: 0, transform: 'translateY(8px)' }
                }
                animate={{ opacity: 1, transform: 'translateY(0px)' }}
                transition={transitionOrReduced(reduceMotion, { duration: 0.28, ease: [0.23, 1, 0.32, 1] })}
                role="alert"
              >
                <p className="memoPipelineKicker">Pipeline</p>
                <p className="memoGateTitle">Memo unavailable</p>
                <p className="memoGateDetail">{renderWithMonoNumbers(memoGateError)}</p>
              </motion.div>
            </div>
          )}

          <motion.div
            className="memoBody"
            key={contentKey}
            initial={
              reduceMotion
                ? { opacity: 1, transform: 'translateY(0px)' }
                : { opacity: 0, transform: 'translateY(16px)' }
            }
            animate={{ opacity: 1, transform: 'translateY(0px)' }}
            transition={transitionOrReduced(reduceMotion, { duration: 0.24, ease: [0.23, 1, 0.32, 1] })}
          >

            {/* ── Executive cover ── */}
            <header className="memoCover">
              {!embedded ? <p className="memoKicker">Investment Memo</p> : null}
              <div className="memoCoverTitleRow">
                {headerLocation ? (
                  <p className="memoMeta memoCoverLocation">{renderWithMonoNumbers(headerLocation)}</p>
                ) : null}
                <h1 className="type-title font-semibold text-oxford-ink-emphasis m-0" id="memo-title">
                  {companyName || '—'}
                </h1>
                {headerMeta ? <p className="memoMeta">{renderWithMonoNumbers(headerMeta)}</p> : null}
              </div>

              {readOnly ? (
                <p className="memoShareBanner" role="status">
                  Read-only view — share this link with a co-GP. Rulings and edits are disabled.
                </p>
              ) : null}

              {showJudgment && precedentCandidates.length > 0 ? (
                <MemoPrecedentStrip
                  candidates={precedentCandidates}
                  renderWithMonoNumbers={renderWithMonoNumbers}
                />
              ) : null}

              <MemoPortfolioContext startupId={displayStartup.id} signals={portfolioSignals} />

              <div className="memoCoverRuling">
                <p className="memoCoverRulingLabel">Recommendation</p>
                {/* Static verdict set in plain ink — the word itself carries the call, no
                    colour-coding. Pending states stay faint (and pulse) to read as "still
                    working"; decided verdicts are perfectly static. */}
                <p
                  className={`memoCoverRulingWord memoCoverRulingWord--${coverRulingVariantClass}`}
                  {...(showCoverPipelineDetail ? { 'aria-live': 'polite' as const } : {})}
                >
                  {renderWithMonoNumbers(coverRulingHeadline)}
                </p>
                {coverStandfirst ? (
                  <p className="memoCoverStandfirst">{renderWithMonoNumbers(coverStandfirst)}</p>
                ) : null}
                <div className="memoCoverRulingSupport">
                  <span className="memoCoverRulingConviction">
                    {renderWithMonoNumbers(convictionLine)}
                  </span>
                  {/* Only flag the exception. "Aligned" is the expected state — badging it is noise. */}
                  {reviewerConsensus.split ? (
                    <span className="memoCoverRulingConsensus">Reviewers split</span>
                  ) : null}
                </div>
                {coverStatusText ? (
                  <p
                    className={`memoCoverStatus${
                      showEscalationBadge && !isAlreadyDecided ? ' memoCoverStatus--escalation' : ''
                    }${showCoverPipelineDetail ? ' memoCoverStatus--detail' : ''}`}
                    {...(showCoverPipelineDetail ? { 'aria-live': 'polite' as const } : {})}
                  >
                    {renderWithMonoNumbers(coverStatusText)}
                  </p>
                ) : null}
              </div>

              {focalQuestion ? (
                <div className="memoCoverDecider">
                  <p className="memoCoverDeciderLabel">What decides it</p>
                  <p className="memoCoverDeciderText">{renderWithMonoNumbers(focalQuestion)}</p>
                </div>
              ) : null}

              {!embedded && (coverBlocker || coverAction) ? (
                <dl className="memoCoverBrief">
                  {coverBlocker ? (
                    <div className="memoCoverBriefItem">
                      <dt>Blocker</dt>
                      <dd>{renderWithMonoNumbers(coverBlocker)}</dd>
                    </div>
                  ) : null}
                  {coverAction ? (
                    <div className="memoCoverBriefItem">
                      <dt>Next move</dt>
                      <dd>{renderWithMonoNumbers(coverAction)}</dd>
                    </div>
                  ) : null}
                </dl>
              ) : null}
            </header>

            {/* ── Company snapshot ── */}
            {(snapshotRows.length > 0 || hasVitals) && (
              <section className="memoDocSection memoSnapshotSection" aria-labelledby="memo-snapshot">
                <h2 className="memoDocSectionHead" id="memo-snapshot">Snapshot</h2>
                {hasVitals && (
                  <div className={`memoVitals${snapshotRows.length > 0 ? ' mb-4 border-b border-oxford/8 pb-4' : ''}`}>
                    {vitalsStrip.length > 0 && (
                      <dl className="flex flex-wrap gap-x-8 gap-y-1.5">
                        {vitalsStrip.map((v) => (
                          <div key={v.label} className="flex items-baseline gap-2">
                            <dt className="type-label uppercase tracking-[0.06em] text-oxford/45">{v.label}</dt>
                            <dd className="type-data text-oxford/82 tabular-nums">{renderWithMonoNumbers(v.value)}</dd>
                          </div>
                        ))}
                      </dl>
                    )}
                    {(fundingLine || tractionLine || ipLine || modelLine) && (
                      <div className={`${vitalsStrip.length > 0 ? 'mt-2.5 ' : ''}space-y-1.5`}>
                        {fundingLine && (
                          <p className="type-body-sm leading-snug text-oxford/75">
                            <span className="type-label uppercase tracking-[0.06em] text-oxford/45 mr-2">Funding</span>
                            {renderWithMonoNumbers(fundingLine)}
                          </p>
                        )}
                        {tractionLine && (
                          <p className="type-body-sm leading-snug text-oxford/75">
                            <span className="type-label uppercase tracking-[0.06em] text-oxford/45 mr-2">Traction</span>
                            {renderWithMonoNumbers(tractionLine)}
                          </p>
                        )}
                        {modelLine && (
                          <p className="type-body-sm leading-snug text-oxford/70">
                            <span className="type-label uppercase tracking-[0.06em] text-oxford/45 mr-2">Model</span>
                            {renderWithMonoNumbers(modelLine)}
                          </p>
                        )}
                        {ipLine && (
                          <p className="type-body-sm leading-snug text-oxford/70">
                            <span className="type-label uppercase tracking-[0.06em] text-oxford/45 mr-2">IP</span>
                            {renderWithMonoNumbers(ipLine)}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                )}
                {snapshotRows.length > 0 && (
                  <dl className="memoSnapshot">
                    {snapshotRows.map((row) => (
                      <div key={row.label} className="memoSnapshotRow">
                        <dt className="memoSnapshotLabel">{row.label}</dt>
                        <dd className="memoSnapshotText">{renderWithMonoNumbers(row.text)}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </section>
            )}

            {embedded && coverAction && !(showEscalationBadge && !isAlreadyDecided) ? (
              <div className="memoCoverNextMove" aria-label="Next move">
                <p className="memoCoverNextMoveLabel">Next move</p>
                <p className="memoCoverNextMoveText">{renderWithMonoNumbers(coverAction)}</p>
              </div>
            ) : null}

            {/* ── Investment case ── */}
            {investmentCasePoints.length > 0 && (
              <section className="memoDocSection memoCaseSection" aria-labelledby="memo-case">
                <h2 className="memoDocSectionHead" id="memo-case">Why Now</h2>
                <ol className="memoCaseList">
                  {investmentCasePoints.map((point, i) => (
                    <li key={i} className={`memoCasePoint${i === 0 ? ' memoCasePoint--lead' : ''}`}>
                      {renderWithMonoNumbers(point)}
                    </li>
                  ))}
                </ol>
              </section>
            )}

            {/* ── Investment killers ── */}
            {memoKillers.length > 0 && (
              <section className="memoDocSection memoKillerSection" aria-labelledby="memo-killers">
                <h2 className="memoDocSectionHead" id="memo-killers">What Limits Conviction</h2>
                <ol className="memoKillerList">
                  {memoKillers.map((killer, i) => (
                    <li key={i} className={`memoKiller memoKiller--${killer.severity}`}>
                      <span className="memoKillerRank" aria-hidden>{String(i + 1).padStart(2, '0')}</span>
                      <p className="memoKillerStatement">{renderWithMonoNumbers(killer.statement)}</p>
                    </li>
                  ))}
                </ol>
              </section>
            )}

            {/* ── Assessment ── */}
            {(() => {
              const isMissing = (s: string) => /^\[MISSING/i.test(String(s ?? '').trim());
              const teamItems = (displayStartup.review?.team_analysis ?? []).filter((s) => String(s ?? '').trim() && !isMissing(String(s)));
              const compItems = (displayStartup.review?.competition_analysis ?? []).filter((s) => String(s ?? '').trim() && !isMissing(String(s)));
              const bizItems = (displayStartup.review?.business_model_analysis ?? []).filter((s) => String(s ?? '').trim() && !isMissing(String(s)));
              const hasScores = !!structuredScoring;
              const showScores = config.memo.includeScoreReasoning && hasScores;
              const improvements = (displayStartup.review?.improvement_to_9 ?? []).filter((s) => String(s ?? '').trim());
              const assessmentReadouts = [
                { label: 'Team', items: teamItems },
                { label: 'Competitive Landscape', items: compItems },
                { label: 'Business Model', items: bizItems },
              ].filter((section) => section.items.length > 0);
              const hasThesis = reviewHasThesisAlignment(displayStartup.review);
              const hasScorecard = showScores && !!structuredScoring;
              const hasPanel = reviewerConsensusRows.length > 0;
              const hasDeepDive = improvements.length > 0 || assessmentReadouts.length > 0 || hasThesis;
              if (!hasScorecard && !hasPanel && !hasDeepDive) {
                return null;
              }
              const r = displayStartup.review;
              const rawAlign = r?.thesis_alignment_score;
              const ten = rawAlign != null ? (rawAlign <= 1 ? rawAlign * 10 : rawAlign) : null;
              const fund = r?.thesis_matches_fund;
              const confRaw = r?.thesis_alignment_confidence;
              const confPct = confRaw != null ? `${(confRaw * 100).toFixed(0)}%` : null;
              const thesisHeadlineTag = [
                fund != null ? (fund ? 'Mandate aligned' : 'Mandate misaligned') : null,
                confPct != null ? `${confPct} confidence` : null,
              ].filter(Boolean).join('  ·  ');
              const fitPoints = (r?.thesis_fit_points ?? []).filter((s) => String(s ?? '').trim());
              const gapPoints = (r?.thesis_deviation_points ?? []).filter((s) => String(s ?? '').trim());
              return (
                <section className="memoDocSection memoScoringSection" aria-labelledby="memo-scoring">
                  <h2 className="memoDocSectionHead" id="memo-scoring">Assessment</h2>
                  {hasScorecard ? (
                    <div className="memoDocScoreScope">
                      <AssessmentScorecard
                        dimensions={SCORING_DIMENSIONS}
                        scoring={structuredScoring}
                        presentation={scoringPresentation}
                        reviewerRows={reviewerConsensusRows}
                        reviewerConsensus={reviewerConsensus}
                        renderNumbers={renderWithMonoNumbers}
                        reduceMotion={reduceMotion}
                      />
                    </div>
                  ) : hasPanel ? (
                    <div className="memoConsensusHead">
                      <p className="memoConsensusVerdict">
                        {reviewerConsensus.split ? 'Split' : 'Aligned'}
                        {reviewerConsensus.verdict ? (
                          <span className="memoConsensusVerdictTag">{` · ${reviewerConsensus.verdict}`}</span>
                        ) : null}
                      </p>
                      <ul className="memoConsensusList">
                        {reviewerConsensusRows.map((row) => (
                          <li key={row.key} className="memoConsensusRow">
                            <span className="memoConsensusName">{row.name}</span>
                            <span className="memoConsensusScore">
                              {row.score != null ? renderWithMonoNumbers(row.score.toFixed(1)) : '—'}
                            </span>
                            <span className="memoConsensusTake">
                              {renderWithMonoNumbers(row.take || row.verdict || '—')}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {hasDeepDive && (
                    <div className="memoScoringMore">
                        {improvements.length > 0 && (
                          <div className="memoDocSubsection">
                            <p className="memoDocSubhead">Path to a 9</p>
                            <ExpandableList
                              items={improvements}
                              cap={4}
                              renderItem={(item, i) => (
                                <li key={i} className="memoListItem">
                                  <span className="memoBullet" aria-hidden>·</span>
                                  <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                                </li>
                              )}
                            />
                          </div>
                        )}
                        {assessmentReadouts.map((section) => (
                          <div key={section.label} className="memoDocSubsection">
                            <p className="memoDocSubhead">{section.label}</p>
                            <ExpandableList
                              items={section.items}
                              cap={3}
                              renderItem={(item, i) => (
                                <li key={i} className="memoListItem">
                                  <span className="memoBullet" aria-hidden>·</span>
                                  <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                                </li>
                              )}
                            />
                          </div>
                        ))}
                        {hasThesis && (
                          <div className="memoDocSubsection">
                            <h3 className="memoDocSectionHead">Thesis alignment</h3>
                            {(ten != null || thesisHeadlineTag) && (
                              <p className="memoScoreHeadline">
                                {ten != null && (
                                  <>
                                    <span className="memoScoreHeadlineValue">{renderWithMonoNumbers(ten.toFixed(0))}</span>
                                    <span className="memoScoreHeadlineMax">/ 10</span>
                                  </>
                                )}
                                {thesisHeadlineTag && (
                                  <span className="memoScoreHeadlineTag">{renderWithMonoNumbers(thesisHeadlineTag)}</span>
                                )}
                              </p>
                            )}
                            {fitPoints.length > 0 && (
                              <ul className="memoList">
                                {fitPoints.map((item, i) => (
                                  <li key={`fit-${i}`} className="memoListItem">
                                    <span className="memoBullet" aria-hidden>+</span>
                                    <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                                  </li>
                                ))}
                              </ul>
                            )}
                            {gapPoints.length > 0 && (
                              <ul className="memoList">
                                {gapPoints.map((item, i) => (
                                  <li key={`gap-${i}`} className="memoListItem">
                                    <span className="memoBullet" aria-hidden>·</span>
                                    <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        )}
                    </div>
                  )}
                </section>
              );
            })()}

            {/* ── Risk register ── */}
            {(adverseRegister.length > 0 || riskFactors.risks.length > 0 || riskFactors.mitigation.length > 0 || missingEvidenceItems.length > 0) && (
              <section className="memoDocSection memoRiskRegisterSection" aria-labelledby="memo-risk-register">
                <h2 className="memoDocSectionHead" id="memo-risk-register">Risks</h2>
                {adverseRegister.length > 0 && (
                  <p className="memoEvStatLine">
                    {renderWithMonoNumbers(`${highAdverseCount} high · ${adverseRegister.length} material`)}
                  </p>
                )}
                {adverseRegister.length > 0 && (
                  <ExpandableList
                    items={adverseRegister}
                    cap={4}
                    as="div"
                    className="memoEvRiskList"
                    renderItem={(item) => {
                      // The engine often sets whyItMatters == title; don't print the same line twice.
                      const why = collapseWhitespace(item.whyItMatters);
                      const showWhy = !!why && why.toLowerCase() !== collapseWhitespace(item.title).toLowerCase();
                      return (
                        <article key={item.id} className={`memoEvRisk memoEvRisk--${item.severity}`}>
                          <span className="memoEvRiskSeverity">{SEVERITY_LABEL[item.severity]}</span>
                          <div className="memoEvRiskBody">
                            <p className="memoEvRiskTitle">{renderWithMonoNumbers(item.title)}</p>
                            {showWhy && <p className="memoEvRiskWhy">{renderWithMonoNumbers(item.whyItMatters)}</p>}
                            {(item.basis || item.missingData || item.source) && (
                              <p className="memoEvRiskMeta">
                                {[item.basis, item.missingData ? 'Missing data' : null, item.source].filter(Boolean).join('  ·  ')}
                              </p>
                            )}
                          </div>
                        </article>
                      );
                    }}
                  />
                )}
                {config.memo.includeMissingData && missingEvidenceItems.length > 0 && (
                  <div className="memoDocSubsection">
                    <p className="memoDocSubhead">Missing evidence</p>
                    <ul className="memoList">
                      {missingEvidenceItems.map((item, i) => (
                        <li key={i} className="memoListItem">
                          <span className="memoBullet">·</span>
                          <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {adverseRegister.length === 0 && riskFactors.risks.length > 0 && (
                  <div className="memoDocSubsection">
                    <p className="memoDocSubhead">Other risks</p>
                    <ul className="memoList">
                      {riskFactors.risks.map((r, i) => (
                        <li key={i} className="memoListItem">
                          <span className="memoBullet">·</span>
                          <span>{renderWithMonoNumbers(normalizeListItemText(r))}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {riskFactors.mitigation.length > 0 && (
                  <div className="memoDocSubsection">
                    <p className="memoDocSubhead">Mitigation</p>
                    <ul className="memoList">
                      {riskFactors.mitigation.map((item, i) => (
                        <li key={i} className="memoListItem">
                          <span className="memoBullet">·</span>
                          <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </section>
            )}

            {/* ── Your ruling ── */}
            {!readOnly && !isAlreadyDecided && showJudgment && (
              <MemoRulingSection
                rulingDecision={rulingDecision}
                rulingNotes={rulingNotes}
                rulingSaving={rulingSaving}
                rulingError={rulingError}
                needsRiskAcknowledgement={needsRiskAcknowledgement}
                risksReviewed={risksReviewed}
                riskReviewOutstanding={riskReviewOutstanding}
                onSelectDecision={setRulingDecision}
                onNotesChange={setRulingNotes}
                onAcknowledgeRisks={() => setRisksReviewed(true)}
                onSubmit={() => void handleRulingSubmit()}
              />
            )}

            {/* ── Supporting detail (sits under the ruling) ── */}
            <div className="memoDiscGroup">
            {/* ── Partner rationale ── */}
            {showJudgment && reasoningParagraphs.length > 0 && (
              <MemoDisclosureSection
                id={`${contentKey}-rationale`}
                title="Partner rationale"
                summary={`${reasoningParagraphs.length} note${reasoningParagraphs.length === 1 ? '' : 's'}`}
                initialOpen={!config.memo.deepDiveCollapsed}
              >
                {reasoningParagraphs.map((p, i) => (
                  <p key={i} className="memoDocProse">{renderWithMonoNumbers(p)}</p>
                ))}
              </MemoDisclosureSection>
            )}

            {showJudgment && (convictionHistory.length > 0 || precedentCandidates.length > 0) && (
              <MemoDisclosureSection
                id={`${contentKey}-ledger`}
                title="Decision ledger"
                summary={
                  convictionHistory.length > 0
                    ? `${convictionHistory.length} change${convictionHistory.length === 1 ? '' : 's'}`
                    : `${precedentCandidates.length} precedent${precedentCandidates.length === 1 ? '' : 's'}`
                }
                initialOpen={false}
              >
                {convictionHistory.length > 0 && (
                  <ol className="memoLedgerList">
                    {[...convictionHistory].reverse().map((entry, index) => (
                      <li key={`${entry.timestamp}-${index}`} className="memoLedgerItem">
                        <div className="memoLedgerMeta">
                          <span>{decisionLabel(entry.new_decision)}</span>
                          <span>{entry.timestamp ? new Date(entry.timestamp).toLocaleDateString('en-GB') : '—'}</span>
                        </div>
                        {entry.rationale && (
                          <p className="memoLedgerText">{renderWithMonoNumbers(entry.rationale)}</p>
                        )}
                        <p className="memoLedgerSub">
                          {entry.previous_decision ? `From ${decisionLabel(entry.previous_decision)} · ` : ''}
                          {entry.config_version ? renderWithMonoNumbers(entry.config_version) : 'Current configuration'}
                        </p>
                      </li>
                    ))}
                  </ol>
                )}
                {precedentCandidates.length > 0 && (
                  <div className="memoPrecedentBlock">
                    <p className="memoDocSubhead">Precedents</p>
                    <ul className="memoList">
                      {precedentCandidates.map((candidate) => (
                        <li key={candidate.startupId} className="memoListItem">
                          <span className="memoBullet" aria-hidden>·</span>
                          <span>
                            {candidate.name}: {decisionLabel(candidate.decision)}
                            {candidate.matchReasons.length ? ` (${candidate.matchReasons.join(', ')})` : ''}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </MemoDisclosureSection>
            )}

            {/* ── Decision context (LLM trigger) ── */}
            {displayStartup.partner?.llm_fallback_reason && (
              <MemoDisclosureSection
                id={`${contentKey}-context`}
                title="Decision context"
                summary="Why this needed judgement"
                initialOpen={false}
              >
                <p className="memoDocProse">{renderWithMonoNumbers(displayStartup.partner.llm_fallback_reason)}</p>
              </MemoDisclosureSection>
            )}
            </div>

            {/* ── Footer detail ── */}
            <div className="memoDiscGroup">
            {/* ── Sources ── */}
            {config.memo.includeEvidenceExcerpts && memoSources.length > 0 && (
              <MemoDisclosureSection
                id={`${contentKey}-sources`}
                title="Sources"
                summary={`${memoSources.length} reference${memoSources.length === 1 ? '' : 's'}`}
                initialOpen={!config.memo.deepDiveCollapsed}
              >
                <ul className="memoList">
                  {memoSources.map((source, i) => (
                    <li key={i} className="memoListItem">
                      <span className="memoBullet">·</span>
                      <span className="min-w-0">
                        {source.href ? (
                          <a className="memoLink" href={source.href} target="_blank" rel="noreferrer">{renderWithMonoNumbers(source.label)}</a>
                        ) : (
                          <span>{renderWithMonoNumbers(source.label)}</span>
                        )}
                        <span className="memoSourceSupport">
                          {sourceSupportLine(source, config.memo.includeSourceConfidence)}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </MemoDisclosureSection>
            )}

            {/* ── Run log ── */}
            {pipelineReplaySteps.length > 0 && (
              <MemoDisclosureSection
                id={`${contentKey}-run-log`}
                title="Run log"
                summary={pipelineReplaySummary}
                initialOpen={false}
              >
                <ol className="memoReplayList">
                  {pipelineReplaySteps.map((step) => (
                    <li key={step.id} className="memoReplayItem">
                      <p className="memoReplayKicker">
                        <span>{step.label}</span>
                        <span className={step.done ? 'memoReplayBadge' : 'memoReplayBadge memoReplayBadge--pending'}>
                          {step.done ? 'Done' : 'Pending'}
                        </span>
                      </p>
                      <p className="memoReplayWhen">{renderWithMonoNumbers(step.atDisplay)}</p>
                      <p className="memoReplayDetail">{renderWithMonoNumbers(step.detail)}</p>
                    </li>
                  ))}
                </ol>
              </MemoDisclosureSection>
            )}
            </div>


          </motion.div>
        </div>
      )}
    </article>
  );
});

export default InvestmentMemoContent;
