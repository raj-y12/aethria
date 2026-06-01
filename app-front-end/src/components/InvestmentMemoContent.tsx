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
import ScoreOverview from './scoring/ScoreOverview';
import AssessmentDimensionStrip from './scoring/AssessmentDimensionStrip';
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
  };
}

const MEMO_GENERATING_DETAIL_AWAITING =
  'Reviewers are scoring this company against your fund thesis. Memo sections appear as outputs land.';
const MEMO_GENERATING_DETAIL_UNDECIDED =
  'Analyst review is complete; the partner engine is determining Invest, Pass, or Monitor. This page updates as the memo fills in.';
const MEMO_GENERATING_DETAIL_ESCALATION =
  'Partner flagged human review. Sections still populate from the pipeline where available.';
const MEMO_GENERATING_DETAIL_FORMATTING =
  'Formatting and persisting the IC memo. This page updates automatically when the document is ready.';

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

function getNextStepText(startup: Startup): string {
  return (startup.partner?.next_action ?? startup.partner?.next_step ?? '').trim();
}

function parseNextStepItems(raw: string): string[] {
  const text = raw.trim();
  if (!text) return [];

  const lines = text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.replace(/^[-*•]\s+/, '').replace(/^\d+[\)\.]\s+/, '').trim())
    .filter(Boolean);
  if (lines.length >= 2) return lines;

  const numberedMatches = [...text.matchAll(/(?:^|\s)\d+[\)\.]\s+/g)];
  if (numberedMatches.length >= 2) {
    const items: string[] = [];
    for (let i = 0; i < numberedMatches.length; i++) {
      const start = (numberedMatches[i].index ?? 0) + numberedMatches[i][0].length;
      const end = i + 1 < numberedMatches.length ? (numberedMatches[i + 1].index ?? text.length) : text.length;
      const item = text.slice(start, end).trim().replace(/\s+/g, ' ');
      if (item) items.push(item.replace(/[;,\s]+$/, ''));
    }
    if (items.length >= 2) return items;
  }

  if (text.includes(' - ')) {
    const parts = text.split(/\s-\s+/).map((p) => p.trim()).filter(Boolean);
    if (parts.length >= 2) return parts;
  }
  if (text.includes(';')) {
    const parts = text.split(';').map((p) => p.trim()).filter(Boolean);
    if (parts.length >= 2) return parts;
  }

  return [];
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

const SENTENCE_BOUNDARY = /(?<=[.!?])\s+/;

function collapseWhitespace(value: unknown): string {
  return String(value ?? '').replace(/\s+/g, ' ').trim();
}

function clipText(value: unknown, maxLen: number): string {
  const text = collapseWhitespace(value);
  if (text.length <= maxLen) return text;
  return `${text.slice(0, maxLen - 1).replace(/[\s,;:.]+$/, '')}…`;
}

function firstSentence(value: unknown, maxLen = 180): string {
  const text = collapseWhitespace(value);
  if (!text) return '';
  const first = text.split(SENTENCE_BOUNDARY)[0]?.trim() || text;
  return clipText(first, maxLen);
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
        <span className="memoDisclosurePlus" aria-hidden>{open ? '−' : '+'}</span>
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
  const [selectedReviewerIdx, setSelectedReviewerIdx] = useState(0);
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

  const memoGeneratingGateCopy = useMemo(() => {
    if (!displayStartup) return { title: '', detail: '' };
    const variant = getDecisionBadgeVariant(displayStartup);
    return {
      title: DECISION_BADGE_LABEL[variant],
      detail: memoGeneratingDetailForVariant(variant),
    };
  }, [displayStartup]);

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
  const showRulingStatus =
    memoPipeline !== 'generating'
    && Boolean(
      isAlreadyDecided
      || (showEscalationBadge && !isAlreadyDecided)
      || !showJudgment
    );
  const riskReviewOutstanding = needsRiskAcknowledgement && !risksReviewed;
  const convictionHistory = displayStartup?.conviction_state?.decision_history ?? [];
  const precedentCandidates = useMemo(
    () => (displayStartup ? findPrecedentCandidates(displayStartup, peerStartups) : []),
    [displayStartup, peerStartups]
  );

  useEffect(() => {
    setSelectedReviewerIdx(0);
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
    ? firstSentence(
        firstNonEmpty(
          displayStartup.partner?.thesis,
          displayStartup.review?.aethria_view?.headline,
          displayStartup.partner?.why_this_matters,
          headerThesisLine,
          displayStartup.review?.overall_summary,
        ),
        220,
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
        take: firstSentence(rv.overall_summary, 150),
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

  const rulingIntro =
    config.memo.tone === 'analyst'
      ? 'Record the fund view after reviewing the analyst read, material adverse items, and next action.'
      : 'Record the fund view after weighing the recommendation, material adverse items, and next action.';

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
                <h1 className="type-title font-semibold text-oxford-ink-emphasis m-0" id="memo-title">
                  {companyName || '—'}
                </h1>
                {headerMeta ? <p className="memoMeta">{renderWithMonoNumbers(headerMeta)}</p> : null}
              </div>

              {coverStandfirst ? (
                <p className="memoCoverStandfirst">{renderWithMonoNumbers(coverStandfirst)}</p>
              ) : null}

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
                <p
                  className={`memoCoverRulingWord memoCoverRulingWord--${(decisionBadgeVariant ?? 'pending').toLowerCase()}`}
                >
                  {showJudgment ? renderWithMonoNumbers(decisionHeadline) : 'Pending'}
                </p>
                <p className="memoCoverRulingSupport">
                  {displayStartup.review?.overall_score != null
                    ? renderWithMonoNumbers(`${displayStartup.review.overall_score}/10 conviction`)
                    : thesisAlignmentBrief
                      ? renderWithMonoNumbers(thesisAlignmentBrief)
                      : 'Conviction forming'}
                  {reviewerConsensus.verdict ? (
                    <span className="memoCoverRulingMeta">
                      {' · '}
                      {reviewerConsensus.split ? 'reviewers split' : 'reviewers aligned'}
                    </span>
                  ) : null}
                </p>
                {showRulingStatus ? (
                  <p
                    className={`memoCoverStatus${
                      showEscalationBadge && !isAlreadyDecided ? ' memoCoverStatus--escalation' : ''
                    }`}
                  >
                    {isAlreadyDecided && displayStartup.human_resolution?.resolved_at
                      ? `Recorded ruling — ${decisionLabel(displayStartup.human_resolution.decision)}`
                      : showEscalationBadge
                        ? 'Human ruling required'
                        : 'Pipeline assembling recommendation'}
                  </p>
                ) : null}
              </div>

              {(coverBlocker || coverAction) && (
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
              )}
            </header>

            {/* ── Generating state ── */}
            {memoPipeline === 'generating' && (
              <section className="memoGeneratingSection" aria-live="polite">
                <div className="memoSummaryCallout memoGenCallout">
                  <p className="memoPipelineKicker">Investment memo</p>
                  <motion.p
                    className="memoGateTitle"
                    animate={reduceMotion ? { opacity: 1 } : { opacity: [0.58, 1, 0.58] }}
                    transition={
                      reduceMotion
                        ? { duration: 0 }
                        : { duration: 2.4, repeat: Infinity, ease: [0.77, 0, 0.175, 1] }
                    }
                  >
                    {memoGeneratingGateCopy.title}
                  </motion.p>
                  <p className="memoGateDetail">
                    {renderWithMonoNumbers(memoGeneratingGateCopy.detail)}
                  </p>
                </div>
              </section>
            )}


            {/* ── Company snapshot ── */}
            {snapshotRows.length > 0 && (
              <section className="memoDocSection memoSnapshotSection" aria-labelledby="memo-snapshot">
                <h2 className="memoDocSectionHead" id="memo-snapshot">Snapshot</h2>
                <dl className="memoSnapshot">
                  {snapshotRows.map((row) => (
                    <div key={row.label} className="memoSnapshotRow">
                      <dt className="memoSnapshotLabel">{row.label}</dt>
                      <dd className="memoSnapshotText">{renderWithMonoNumbers(row.text)}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            )}

            {/* ── Investment case ── */}
            {investmentCasePoints.length > 0 && (
              <section className="memoDocSection memoCaseSection" aria-labelledby="memo-case">
                <h2 className="memoDocSectionHead" id="memo-case">The Case</h2>
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

            {/* ── Scoring ── */}
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
              if (!showScores && assessmentReadouts.length === 0 && improvements.length === 0 && !hasThesis) {
                return null;
              }
              const r = displayStartup.review;
              const rawAlign = r?.thesis_alignment_score;
              const ten = rawAlign != null ? (rawAlign <= 1 ? rawAlign * 10 : rawAlign) : null;
              const fund = r?.thesis_matches_fund;
              const confRaw = r?.thesis_alignment_confidence;
              const confPct = confRaw != null ? `${(confRaw * 100).toFixed(0)}%` : null;
              const statLine = [
                ten != null ? `${ten.toFixed(0)}/10 alignment` : null,
                fund != null ? (fund ? 'Mandate aligned' : 'Mandate misaligned') : null,
                confPct != null ? `${confPct} confidence` : null,
              ].filter(Boolean).join('   ·   ');
              const fitPoints = (r?.thesis_fit_points ?? []).filter((s) => String(s ?? '').trim());
              const gapPoints = (r?.thesis_deviation_points ?? []).filter((s) => String(s ?? '').trim());
              return (
                <section className="memoDocSection memoScoringSection" aria-labelledby="memo-scoring">
                  <h2 className="memoDocSectionHead" id="memo-scoring">Scoring</h2>
                  {showScores && (
                    <div className="memoDocScoreScope">
                      {structuredScoring && (
                        <>
                          <ScoreOverview scoring={structuredScoring} presentation={scoringPresentation} />
                          <AssessmentDimensionStrip
                            dimensions={SCORING_DIMENSIONS}
                            scoring={structuredScoring}
                            presentation={scoringPresentation}
                            contentKey={contentKey}
                          />
                        </>
                      )}
                    </div>
                  )}
                  {(improvements.length > 0 || assessmentReadouts.length > 0) && (
                    <div className="memoDiscGroup memoScoringMore">
                      <MemoDisclosureSection
                        id={`${contentKey}-scoring-reads`}
                        title="Analyst reads"
                        summary={`${improvements.length + assessmentReadouts.length} note${improvements.length + assessmentReadouts.length === 1 ? '' : 's'}`}
                        initialOpen={false}
                      >
                        {improvements.length > 0 && (
                          <div className="memoDocSubsection">
                            <p className="memoDocSubhead">Path to a 9</p>
                            <ul className="memoList">
                              {improvements.slice(0, 4).map((item, i) => (
                                <li key={i} className="memoListItem">
                                  <span className="memoBullet" aria-hidden>·</span>
                                  <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {assessmentReadouts.map((section) => (
                          <div key={section.label} className="memoDocSubsection">
                            <p className="memoDocSubhead">{section.label}</p>
                            <ul className="memoList">
                              {section.items.slice(0, 3).map((item, i) => (
                                <li key={i} className="memoListItem">
                                  <span className="memoBullet" aria-hidden>·</span>
                                  <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </MemoDisclosureSection>
                    </div>
                  )}
                  {hasThesis && (
                    <div className="memoDiscGroup">
                      <MemoDisclosureSection
                        id={`${contentKey}-thesis-alignment`}
                        title="Thesis alignment"
                        summary={ten != null ? `${ten.toFixed(0)}/10` : fund != null ? (fund ? 'Aligned' : 'Misaligned') : undefined}
                        initialOpen={!config.memo.deepDiveCollapsed}
                      >
                        {statLine && <p className="memoEvStatLine">{renderWithMonoNumbers(statLine)}</p>}
                        {fitPoints.length > 0 && (
                          <div className="memoDocSubsection">
                            <p className="memoDocSubhead">Fits</p>
                            <ul className="memoList">
                              {fitPoints.map((item, i) => (
                                <li key={i} className="memoListItem">
                                  <span className="memoBullet" aria-hidden>·</span>
                                  <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {gapPoints.length > 0 && (
                          <div className="memoDocSubsection">
                            <p className="memoDocSubhead">Gaps</p>
                            <ul className="memoList">
                              {gapPoints.map((item, i) => (
                                <li key={i} className="memoListItem">
                                  <span className="memoBullet" aria-hidden>·</span>
                                  <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </MemoDisclosureSection>
                    </div>
                  )}
                </section>
              );
            })()}

            {/* ── Reviewer consensus ── */}
            {reviewerConsensusRows.length > 0 && (
              <section className="memoDocSection memoConsensusSection" aria-labelledby="memo-consensus">
                <h2 className="memoDocSectionHead" id="memo-consensus">Reviewer Consensus</h2>
                <div className="memoConsensusHead">
                  <p className="memoConsensusVerdict">
                    {reviewerConsensus.split ? 'Split' : 'Aligned'}
                    {reviewerConsensus.verdict ? (
                      <span className="memoConsensusVerdictTag">{` · ${reviewerConsensus.verdict}`}</span>
                    ) : null}
                  </p>
                  {reviewerConsensus.min != null && reviewerConsensus.max != null ? (
                    <p className="memoConsensusSpread">
                      {renderWithMonoNumbers(
                        reviewerConsensus.min === reviewerConsensus.max
                          ? `${reviewerConsensus.min.toFixed(1)}/10 across the panel`
                          : `${reviewerConsensus.min.toFixed(1)}–${reviewerConsensus.max.toFixed(1)}/10 spread`
                      )}
                    </p>
                  ) : null}
                </div>
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
              </section>
            )}

            {/* ── Reviewer detail ── */}
            {config.memo.style !== 'concise' && (displayStartup.review?.reviews?.length ?? 0) > 0 && (() => {
              const reviews = displayStartup.review!.reviews!;
              const isContested = displayStartup.review?.reviewer_disagreement === true;
              const selected = reviews[selectedReviewerIdx] ?? reviews[0];
              return (
                <div className="memoDiscGroup">
                  <MemoDisclosureSection
                    id={`${contentKey}-reviewer-panel`}
                    title="Reviewer detail"
                    summary={isContested ? 'Where conviction diverges' : `${reviews.length} internal reads`}
                    initialOpen={isContested || !config.memo.deepDiveCollapsed}
                  >
                    {isContested && (
                      <p className="memoDocProse">
                        The reviewer read is not unanimous. The useful signal is the shape of disagreement: which part of the case is carrying conviction, and which part is still soft.
                      </p>
                    )}
                    <div className="memoDocReviewerTable" role="group" aria-label="Reviewer conviction and disagreement">
                      {reviews.map((rv, idx) => {
                        const isSelected = idx === selectedReviewerIdx;
                        const scoreRow = `M ${rv.market_score} · P ${rv.product_score} · T ${rv.technical_score} · E ${rv.execution_score} · D ${rv.defensibility_score}`;
                        return (
                          <button
                            key={rv.reviewer_type}
                            type="button"
                            className="memoDocReviewerRow"
                            aria-pressed={isSelected}
                            onClick={() => setSelectedReviewerIdx(idx)}
                          >
                            <span className="memoDocReviewerRowLabel">
                              {REVIEWER_LABELS[rv.reviewer_type] ?? rv.reviewer_type}
                            </span>
                            <span className="memoDocReviewerRowVerdict">{rv.verdict}</span>
                            <span className="memoDocReviewerRowScores">{renderWithMonoNumbers(scoreRow)}</span>
                          </button>
                        );
                      })}
                    </div>
                    {selected?.overall_summary && (
                      <motion.div
                        key={`${contentKey}:reviewer:${selectedReviewerIdx}`}
                        className="memoDocReviewerDetail"
                        initial={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={transitionOrReduced(reduceMotion, { duration: 0.18, ease: [0.16, 1, 0.3, 1] })}
                      >
                        <p className="memoDocReviewerDetailText">{renderWithMonoNumbers(selected.overall_summary)}</p>
                      </motion.div>
                    )}
                  </MemoDisclosureSection>
                </div>
              );
            })()}

            {/* ── Risk register ── */}
            {(adverseRegister.length > 0 || riskFactors.risks.length > 0 || riskFactors.mitigation.length > 0 || missingEvidenceItems.length > 0) && (
              <section className="memoDocSection memoRiskRegisterSection" aria-labelledby="memo-risk-register">
                <h2 className="memoDocSectionHead" id="memo-risk-register">Risk Register</h2>
                {adverseRegister.length > 0 && (
                  <p className="memoEvStatLine">
                    {renderWithMonoNumbers(`${highAdverseCount} high · ${adverseRegister.length} material`)}
                  </p>
                )}
                {adverseRegister.length > 0 && (
                  <div className="memoEvRiskList">
                    {adverseRegister.map((item) => (
                      <article key={item.id} className={`memoEvRisk memoEvRisk--${item.severity}`}>
                        <p className="memoEvRiskHead">
                          <span className="memoEvRiskSeverity">{SEVERITY_LABEL[item.severity]}</span>
                          <span className="memoEvRiskTitle">{renderWithMonoNumbers(item.title)}</span>
                        </p>
                        <p className="memoEvRiskWhy">{renderWithMonoNumbers(item.whyItMatters)}</p>
                        {(item.basis || item.missingData || item.source) && (
                          <p className="memoEvRiskMeta">
                            {[item.basis, item.missingData ? 'Missing data' : null, item.source].filter(Boolean).join('  ·  ')}
                          </p>
                        )}
                      </article>
                    ))}
                  </div>
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
                rulingIntro={rulingIntro}
                nextStepItems={nextStepItems}
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
                renderWithMonoNumbers={renderWithMonoNumbers}
                normalizeListItemText={normalizeListItemText}
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
                    {[...convictionHistory].reverse().slice(0, 5).map((entry, index) => (
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
