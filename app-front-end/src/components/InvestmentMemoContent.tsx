import { useCallback, forwardRef, useEffect, useImperativeHandle, useMemo, useState, type ReactNode } from 'react';
import { fetchMemo, type MemoPartialPayload } from '../api/startups';
import { motion } from 'framer-motion';
import './InvestmentMemoContent.css';
import type { Review, ScoringDimensionKey, Startup, AethriaView } from '../types/startup';
import { normalizeStructuredScoring } from '../lib/reviewScoring';
import {
  buildMemoPDF,
  buildIcMarkdown,
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
import DimensionCard from './scoring/DimensionCard';
import { DECISION_BADGE_LABEL } from './DecisionBadge';
import { getDecisionBadgeVariant, type DecisionBadgeVariant } from '../lib/decisionBadgeVariant';
import { resolveEscalation } from '../api/escalations';
import {
  buildOptimisticResolution,
  isDealDecided,
  type RulingDecision,
} from '../lib/dealState';
import { extractAdverseRegister, type AdverseRegisterItem } from '../lib/adverseRegister';
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
  onMemoPipelineReady?: () => void;
  onDecisionResolved?: (startup: Startup) => void;
  fundConfiguration?: FundConfiguration;
  peerStartups?: Startup[];
}

export interface InvestmentMemoContentHandle {
  downloadPDF: () => void;
  downloadMarkdown: () => void;
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
  const scoutOneLine = startup.scout.one_line?.trim().toLowerCase();
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
    if (scoutOneLine && value.toLowerCase() === scoutOneLine) continue;
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

function MemoPlainSection({
  id,
  title,
  children,
  className = '',
}: {
  id: string;
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`memoDocSection ${className}`.trim()} aria-labelledby={`${id}-title`}>
      <h2 className="memoDocSectionHead" id={`${id}-title`}>{title}</h2>
      {children}
    </section>
  );
}

const InvestmentMemoContent = forwardRef<InvestmentMemoContentHandle, InvestmentMemoContentProps>(function InvestmentMemoContent(
  { startup, onClose, embedded = false, onMemoPipelineReady, onDecisionResolved, fundConfiguration, peerStartups = [] },
  ref
) {
  const config = fundConfiguration ?? createDefaultFundConfiguration();
  const reduceMotion = usePrefersReducedMotion();
  const wrapperCls = embedded ? 'memoPanel memoPanel--embedded' : 'memoPanel';
  const [selectedReviewerIdx, setSelectedReviewerIdx] = useState(0);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [pipelineLogOpen, setPipelineLogOpen] = useState(false);
  const [adverseOpen, setAdverseOpen] = useState(false);
  const [reasoningOpen, setReasoningOpen] = useState(false);
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

  const handleDownloadMarkdown = useCallback(() => {
    if (!displayStartup) return;
    const md = buildIcMarkdown(displayStartup);
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${icPackSafeBaseName(displayStartup)}-ic-pack.md`;
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }, [displayStartup]);

  useImperativeHandle(
    ref,
    () => ({ downloadPDF: handleDownloadPDF, downloadMarkdown: handleDownloadMarkdown }),
    [handleDownloadPDF, handleDownloadMarkdown]
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
    setSourcesOpen(!config.memo.deepDiveCollapsed);
    setPipelineLogOpen(false);
    setAdverseOpen(!config.memo.deepDiveCollapsed);
    setReasoningOpen(false);
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
  }, [displayStartup, onDecisionResolved, risksReviewed, rulingDecision, rulingNotes]);

  const structuredScoring = useMemo(
    () => normalizeStructuredScoring(displayStartup?.review ?? null),
    [displayStartup?.review]
  );
  const nextStepText = displayStartup ? getNextStepText(displayStartup) : '';
  const nextStepItems = useMemo(() => parseNextStepItems(nextStepText), [nextStepText]);
  const pipelineReplaySteps = useMemo(
    () => (displayStartup ? getPipelineReplaySteps(displayStartup) : []),
    [displayStartup]
  );
  const pipelineReplaySummary = useMemo(
    () => pipelineReplayOneLiner(pipelineReplaySteps),
    [pipelineReplaySteps]
  );

  const REVIEWER_LABELS: Record<string, string> = {
    DefaultReviewer: 'Default',
    SkepticalReviewer: 'Skeptical',
    OpportunistReviewer: 'Opportunist',
  };
  const rulingIntro =
    config.memo.tone === 'analyst'
      ? 'Record the fund view after reviewing the analyst read, material adverse items, and next action.'
      : 'Record the fund view after weighing the recommendation, material adverse items, and next action.';

  return (
    <div className={wrapperCls}>
      {/* Styles extracted to InvestmentMemoContent.css */}

      {!displayStartup ? (
        <div className="memoEmpty">
          <div className="memoEmptyInner">
            <p className="memoEmptyWordmark">Aethria</p>
            <div className="memoEmptyHint">{UI_DETAIL_EMPTY_HINT}</div>
          </div>
        </div>
      ) : (
        <div className="memoScroll relative" role="region" aria-label="Investment memo">
          {onClose && (
            <div className="memoHeaderActions">
              <button type="button" onClick={handleDownloadPDF} className={actionBtnCls}>IC Pack (PDF)</button>
              <button type="button" onClick={handleDownloadMarkdown} className={actionBtnCls}>IC Pack (MD)</button>
              <button type="button" onClick={onClose} className={actionBtnCls}>Close</button>
            </div>
          )}

          {memoPipeline === 'failed' && (
            <div className="memoGateStrip memoGateStrip--error">
              <motion.div
                className="memoGateStripInner"
                initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={transitionOrReduced(reduceMotion, { duration: 0.28, ease: [0.16, 1, 0.3, 1] })}
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
            initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={transitionOrReduced(reduceMotion, { duration: 0.26, ease: [0.16, 1, 0.3, 1] })}
          >

            {/* ── Document header ── */}
            <div className="memoDocHeader">
              <div className="memoDocHeaderMain">
                <p className="memoKicker">INVESTMENT MEMO</p>
                <div className="memoTitleRow">
                  <h1 className="memoCompany" id="memo-title">{companyName || '—'}</h1>
                  {headerMeta ? <p className="memoMeta">{renderWithMonoNumbers(headerMeta)}</p> : null}
                </div>
                {headerThesisLine ? (
                  <p className="memoThesisLine">{renderWithMonoNumbers(headerThesisLine)}</p>
                ) : null}
              </div>
            </div>

            <div className="memoDocDivider" aria-hidden />

            {/* ── Generating state ── */}
            {memoPipeline === 'generating' && (
              <section className="memoGeneratingSection" aria-live="polite">
                <div className="memoSummaryCallout memoGenCallout">
                  <p className="memoPipelineKicker">Investment memo</p>
                  <motion.p
                    className="memoGateTitle"
                    animate={reduceMotion ? { opacity: 1 } : { opacity: [0.55, 1, 0.55] }}
                    transition={reduceMotion ? { duration: 0 } : { duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
                  >
                    {memoGeneratingGateCopy.title}
                  </motion.p>
                  <p className="memoGateDetail">
                    {renderWithMonoNumbers(memoGeneratingGateCopy.detail)}
                  </p>
                </div>
              </section>
            )}

            <div className="memoDecisionCluster">
              {/* ── Decision surface ── */}
              <section className="memoDocSection memoDecisionSurface" aria-label="Judgment brief">
                {showRulingStatus && (
                <div
                  className={`memoRulingStatus${
                    showEscalationBadge && !isAlreadyDecided ? ' memoRulingStatus--escalation' : ''
                  }`}
                >
                  <div>
                    <div className="memoRulingLabelRow">
                      <p className="memoRulingLabel">
                        {isAlreadyDecided
                          ? 'Recorded human ruling'
                          : showEscalationBadge
                            ? 'Human ruling required'
                            : 'Pipeline assembling recommendation'}
                      </p>
                    </div>
                    {displayStartup.human_resolution?.resolved_at ? (
                      <p className="memoRulingValue">
                        {decisionLabel(displayStartup.human_resolution.decision)}
                      </p>
                    ) : showEscalationBadge ? null : (
                      <p className="memoRulingValue">Awaiting recommendation</p>
                    )}
                  </div>
                  {displayStartup.human_resolution?.notes ? (
                    <p className="memoRulingNote">{renderWithMonoNumbers(displayStartup.human_resolution.notes)}</p>
                  ) : null}
                </div>
                )}
                {showJudgment && (() => {
                  const paras = reasoningParagraphs.filter((p) => String(p ?? '').trim());
                  const primaryReason = paras[0];
                  const remainingReasons = paras.slice(1);
                  return (
                    <div
                      className={`memoRecommendationBlock${showRulingStatus ? '' : ' memoRecommendationBlock--lead'}`}
                      aria-labelledby="memo-investment-judgment"
                    >
                      <h2 className="memoDocSectionHead" id="memo-investment-judgment">Investment Judgement</h2>
                      {decisionBadgeVariant && (
                        <div className="memoDocJudgmentTop">
                          <p className={`memoDocRecommendation memoDocRecommendation--${decisionBadgeVariant.toLowerCase()}`}>
                            {decisionHeadline}.
                          </p>
                        </div>
                      )}
                      {primaryReason && (
                        <p className="memoDocProse memoDocPrimaryReason">{renderWithMonoNumbers(primaryReason)}</p>
                      )}
                      {remainingReasons.length > 0 && (
                        <div className="memoReasoningDisclosure">
                          <button
                            type="button"
                            className="memoInlineDisclosure"
                            onClick={() => setReasoningOpen((open) => !open)}
                            aria-expanded={reasoningOpen}
                            aria-controls={`${contentKey}-partner-rationale`}
                          >
                            {reasoningOpen ? 'Hide full rationale' : `Full rationale (${remainingReasons.length})`}
                          </button>
                          <div id={`${contentKey}-partner-rationale`} className={reasoningOpen ? 'memoReasoningBody' : 'hidden'}>
                            {remainingReasons.map((p, i) => (
                              <p key={i} className="memoDocProse">{renderWithMonoNumbers(p)}</p>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}
              </section>

            </div>

            {/* ── Executive summary ── */}
            {showJudgment && (() => {
              const summary = displayStartup.review?.overall_summary?.trim();
              if (!summary) return null;
              return (
                <section className="memoDocSection" aria-labelledby="memo-exec-summary">
                  <h2 className="memoDocSectionHead" id="memo-exec-summary">Executive Summary</h2>
                  {summary && <p className="memoDocProse">{renderWithMonoNumbers(summary)}</p>}
                </section>
              );
            })()}

            {/* ── Aethria view (thesis fit narrative) ── */}
            {(() => {
              const av = displayStartup.review?.aethria_view as AethriaView | undefined | null;
              if (!av?.headline?.trim()) return null;
              return (
                <section className="memoDocSection" aria-labelledby="memo-aethria-view">
                  <h2 className="memoDocSectionHead" id="memo-aethria-view">Aethria view</h2>
                  <p className="memoDocProse memoDocLead">{renderWithMonoNumbers(av.headline)}</p>
                  {av.thesis_fit_line?.trim() && (
                    <p className="memoDocProse">{renderWithMonoNumbers(av.thesis_fit_line)}</p>
                  )}
                  {av.tension_summary?.trim() && (
                    <p className="memoDocProse">{renderWithMonoNumbers(av.tension_summary)}</p>
                  )}
                  {av.focal_question?.trim() && (
                    <p className="memoDocProse memoDocFocalInset">
                      <span className="memoDocSubhead">Focal question</span>
                      {renderWithMonoNumbers(av.focal_question)}
                    </p>
                  )}
                </section>
              );
            })()}

            {/* ── Company Overview ── */}
            {(() => {
              const rows = [
                { key: 'Problem', val: displayStartup.scout.problem?.trim() },
                { key: 'Solution', val: displayStartup.scout.solution?.trim() },
                { key: 'Target Market', val: displayStartup.scout.target_users?.trim() },
              ].filter((r) => r.val);
              if (!rows.length) return null;
              return (
                <section className="memoDocSection" aria-labelledby="memo-overview">
                  <h2 className="memoDocSectionHead" id="memo-overview">Company Overview</h2>
                  <dl className="memoDocDL">
                    {rows.map((r) => (
                      <div key={r.key} className="memoDocDLRow">
                        <dt className="memoDocDT">{r.key}</dt>
                        <dd className="memoDocDD">{renderWithMonoNumbers(r.val)}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              );
            })()}

            {/* ── The Case ── */}
            {(() => {
              const rows = [
                { key: 'Why Now', val: (displayStartup.partner?.why_this_matters || displayStartup.scout.why_now)?.trim() },
                { key: 'Market', val: displayStartup.partner?.market_insight?.trim() },
                { key: 'Product Edge', val: displayStartup.partner?.product_edge?.trim() },
                { key: 'Traction', val: displayStartup.partner?.traction_signals?.trim() },
              ].filter((r) => r.val);
              if (!rows.length) return null;
              return (
                <section className="memoDocSection" aria-labelledby="memo-case">
                  <h2 className="memoDocSectionHead" id="memo-case">The Case</h2>
                  <dl className="memoDocDL">
                    {rows.map((r) => (
                      <div key={r.key} className="memoDocDLRow">
                        <dt className="memoDocDT">{r.key}</dt>
                        <dd className="memoDocDD">{renderWithMonoNumbers(r.val)}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              );
            })()}

            {/* ── Investment Thesis ── */}
            {(() => {
              const thesis = (displayStartup.partner?.thesis || displayStartup.scout.primary_thesis)?.trim();
              const assumptions = displayStartup.scout.key_assumptions?.filter((a) => String(a ?? '').trim());
              const biggest = displayStartup.scout.biggest_unknown?.trim();
              if (!thesis && !assumptions?.length && !biggest) return null;
              return (
                <section className="memoDocSection" aria-labelledby="memo-thesis">
                  <h2 className="memoDocSectionHead" id="memo-thesis">Investment Thesis</h2>
                  {thesis && <p className="memoDocProse memoDocThesis">{renderWithMonoNumbers(thesis)}</p>}
                  {assumptions && assumptions.length > 0 && (
                    <div className="memoDocSubsection">
                      <p className="memoDocSubhead">Key Assumptions</p>
                      <ul className="memoList">
                        {assumptions.map((item, i) => (
                          <li key={i} className="memoListItem">
                            <span className="memoBullet" aria-hidden>·</span>
                            <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {biggest && (
                    <div className="memoDocSubsection">
                      <p className="memoDocSubhead">Biggest Unknown</p>
                      <p className="memoDocProse">{renderWithMonoNumbers(biggest)}</p>
                    </div>
                  )}
                </section>
              );
            })()}

            {/* ── Assessment ── */}
            {(() => {
              const isMissing = (s: string) => /^\[MISSING/i.test(String(s ?? '').trim());
              const teamItems = (displayStartup.review?.team_analysis ?? []).filter((s) => String(s ?? '').trim() && !isMissing(String(s)));
              const compItems = (displayStartup.review?.competition_analysis ?? []).filter((s) => String(s ?? '').trim() && !isMissing(String(s)));
              const bizItems = (displayStartup.review?.business_model_analysis ?? []).filter((s) => String(s ?? '').trim() && !isMissing(String(s)));
              const hasScores = !!structuredScoring;
              if (
                !displayStartup.review &&
                !teamItems.length &&
                !compItems.length &&
                !bizItems.length &&
                !hasScores
              ) {
                return null;
              }
              return (
                <MemoPlainSection
                  id={`${contentKey}-assessment`}
                  title="Assessment"
                >

                  {config.memo.includeScoreReasoning && hasScores && (
                    <div className="memoDocScoreScope">
                      {structuredScoring && (
                        <>
                          <ScoreOverview scoring={structuredScoring} />
                          <div className="memoScoreDimensionStack">
                            {SCORING_DIMENSIONS.map((dimension) => (
                              <DimensionCard
                                key={dimension.key}
                                id={dimension.id}
                                title={dimension.label}
                                dimension={structuredScoring[dimension.key]}
                              />
                            ))}
                          </div>
                        </>
                      )}
                      {(displayStartup.review?.improvement_to_9?.length ?? 0) > 0 && (
                        <div className="memoDocSubsection">
                          <p className="memoDocSubhead">What would make this a 9?</p>
                          <ul className="memoList">
                            {(displayStartup.review?.improvement_to_9 ?? []).map((item, i) => (
                              <li key={i} className="memoListItem">
                                <span className="memoBullet" aria-hidden>·</span>
                                <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}

                  {teamItems.length > 0 && (
                    <div className="memoDocSubsection">
                      <p className="memoDocSubhead">Team</p>
                      <ul className="memoList">
                        {teamItems.map((item, i) => (
                          <li key={i} className="memoListItem">
                            <span className="memoBullet" aria-hidden>·</span>
                            <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {compItems.length > 0 && (
                    <div className="memoDocSubsection">
                      <p className="memoDocSubhead">Competitive Landscape</p>
                      <ul className="memoList">
                        {compItems.map((item, i) => (
                          <li key={i} className="memoListItem">
                            <span className="memoBullet" aria-hidden>·</span>
                            <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {bizItems.length > 0 && (
                    <div className="memoDocSubsection">
                      <p className="memoDocSubhead">Business Model</p>
                      <ul className="memoList">
                        {bizItems.map((item, i) => (
                          <li key={i} className="memoListItem">
                            <span className="memoBullet" aria-hidden>·</span>
                            <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </MemoPlainSection>
              );
            })()}

            {/* ── Thesis Alignment ── */}
            {reviewHasThesisAlignment(displayStartup.review) && (() => {
              const r = displayStartup.review!;
              const rawAlign = r.thesis_alignment_score;
              const ten = rawAlign != null ? (rawAlign <= 1 ? rawAlign * 10 : rawAlign) : null;
              const fund = r.thesis_matches_fund;
              const confRaw = r.thesis_alignment_confidence;
              const confPct = confRaw != null ? `${(confRaw * 100).toFixed(0)}%` : null;
              const tiles = [
                ten != null ? { label: 'Alignment', val: `${ten.toFixed(0)}/10` } : null,
                fund != null ? { label: 'Mandate', val: fund ? 'Aligned' : 'Misaligned' } : null,
                confPct != null ? { label: 'Confidence', val: confPct } : null,
              ].filter(Boolean) as { label: string; val: string }[];
              const fitPoints = r.thesis_fit_points ?? [];
              const gapPoints = r.thesis_deviation_points ?? [];
              return (
                <MemoPlainSection
                  id={`${contentKey}-thesis-alignment`}
                  title="Thesis Alignment"
                >
                  {tiles.length > 0 && (
                    <div className="memoDocAlignTiles">
                      {tiles.map((t) => (
                        <div key={t.label} className="memoDocAlignTile">
                          <p className="memoDocAlignTileLabel">{t.label}</p>
                          <p className="memoDocAlignTileVal">{renderWithMonoNumbers(t.val)}</p>
                        </div>
                      ))}
                    </div>
                  )}
                  {(fitPoints.length > 0 || gapPoints.length > 0) && (
                    <dl className="memoDocDL">
                      {fitPoints.length > 0 && (
                        <div className="memoDocDLRow">
                          <dt className="memoDocDT">Fits</dt>
                          <dd className="memoDocDD">
                            <ul className="memoList">
                              {fitPoints.map((item, i) => (
                                <li key={i} className="memoListItem">
                                  <span className="memoBullet" aria-hidden>·</span>
                                  <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                                </li>
                              ))}
                            </ul>
                          </dd>
                        </div>
                      )}
                      {gapPoints.length > 0 && (
                        <div className="memoDocDLRow">
                          <dt className="memoDocDT">Gaps</dt>
                          <dd className="memoDocDD">
                            <ul className="memoList">
                              {gapPoints.map((item, i) => (
                                <li key={i} className="memoListItem">
                                  <span className="memoBullet" aria-hidden>·</span>
                                  <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                                </li>
                              ))}
                            </ul>
                          </dd>
                        </div>
                      )}
                    </dl>
                  )}
                </MemoPlainSection>
              );
            })()}

            {/* ── Reviewer Panel ── */}
            {config.memo.style !== 'concise' && (displayStartup.review?.reviews?.length ?? 0) > 0 && (() => {
              const reviews = displayStartup.review!.reviews!;
              const isContested = displayStartup.review?.reviewer_disagreement === true;
              const selected = reviews[selectedReviewerIdx] ?? reviews[0];
              return (
                <MemoDisclosureSection
                  id={`${contentKey}-reviewer-panel`}
                  title="Reviewer Panel"
                  summary={isContested ? 'Contested reviewer read' : `${reviews.length} reviewer reads`}
                  initialOpen={isContested || !config.memo.deepDiveCollapsed}
                >
                  {isContested && (
                    <p className="memoDocProse">
                      Reviewer personas did not fully agree. The headline scores lean more conservative where their reads diverged.
                    </p>
                  )}
                  <div className="memoDocReviewerTable" role="group" aria-label="Per-reviewer scores and verdicts">
                    {reviews.map((rv, idx) => {
                      const isSelected = idx === selectedReviewerIdx;
                      const scoreRow = `Mkt ${rv.market_score}  ·  Prd ${rv.product_score}  ·  Tch ${rv.technical_score}  ·  Exc ${rv.execution_score}  ·  Def ${rv.defensibility_score}`;
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
              );
            })()}

            {/* ── Risks ── */}
            {(adverseRegister.length > 0 || riskFactors.risks.length > 0 || riskFactors.mitigation.length > 0 || missingEvidenceItems.length > 0) && (
              <section className="memoDocSection memoRiskCheckpoint" aria-labelledby="memo-risk-checkpoint">
                <h2 className="memoDocSectionHead" id="memo-risk-checkpoint">Risk Checkpoint</h2>
                {adverseRegister.length > 0 && (
                  <>
                    <button
                      type="button"
                      className="memoAdverseHeader"
                      onClick={() => setAdverseOpen((open) => !open)}
                      aria-expanded={adverseOpen}
                      aria-controls={`${contentKey}-adverse-register`}
                    >
                      <span className="memoAdverseToggleTitle">Material Adverse</span>
                      <span className="memoAdverseHeaderMeta">
                        <span className="memoAdverseCount" aria-label={`${highAdverseCount} high severity, ${adverseRegister.length} material adverse items`}>
                          <span className={highAdverseCount > 0 ? 'memoAdverseCountCritical' : undefined}>{highAdverseCount}</span>
                          {' high'}
                          <span aria-hidden> · </span>
                          <span>{adverseRegister.length}</span>
                          {' material'}
                        </span>
                        <span className="memoAdverseChevron" aria-hidden>{adverseOpen ? '−' : '+'}</span>
                      </span>
                    </button>
                    {adverseOpen && (
                      <div className="memoAdverseList" id={`${contentKey}-adverse-register`}>
                        {adverseRegister.map((item) => (
                          <article key={item.id} className={`memoAdverseItem memoAdverseItem--${item.severity}`}>
                            <div className="memoAdverseSeverity">
                              <span>{SEVERITY_LABEL[item.severity]}</span>
                            </div>
                            <div className="memoAdverseMain">
                              <p className="memoAdverseTitle">{renderWithMonoNumbers(item.title)}</p>
                              <p className="memoAdverseBody">{renderWithMonoNumbers(item.whyItMatters)}</p>
                            </div>
                            <div className="memoAdverseMeta">
                              <span>{item.basis}</span>
                              {item.missingData && <span>Missing data</span>}
                              {item.source && <span>{item.source}</span>}
                            </div>
                          </article>
                        ))}
                      </div>
                    )}
                  </>
                )}
                {config.memo.includeMissingData && missingEvidenceItems.length > 0 && (
                  <div className="memoDocSubsection">
                    <p className="memoDocSubhead">Missing Evidence</p>
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
                    <p className="memoDocSubhead">Other Risks</p>
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
                    <p className="memoDocSubhead">Mitigation Checklist</p>
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

            {/* ── Ruling ── */}
            {nextStepText && (
              <section className="memoDocSection memoNextActionSection" aria-labelledby="memo-next">
                <h2 className="memoDocSectionHead" id="memo-next">Next Steps</h2>
                {nextStepItems.length > 0 ? (
                  <ul className="memoList">
                    {nextStepItems.map((item, idx) => (
                      <li key={idx} className="memoListItem">
                        <span className="memoBullet"><span className="memoNum">{idx + 1}</span>.</span>
                        <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="memoDocProse">{renderWithMonoNumbers(nextStepText)}</p>
                )}
              </section>
            )}

            {!isAlreadyDecided && showJudgment && (
              <section className="memoDocSection memoRulingControls" aria-labelledby="memo-final-ruling">
                <h2 className="memoDocSectionHead" id="memo-final-ruling">Commit Ruling</h2>
                <p className="memoRulingIntro">{rulingIntro}</p>
                {needsRiskAcknowledgement && (
                  <div className="memoRiskAcknowledgement">
                    <p>High-severity risks present. Mark reviewed when satisfied.</p>
                    <button
                      type="button"
                      onClick={() => setRisksReviewed(true)}
                      className="memoRiskAckButton"
                      aria-pressed={risksReviewed}
                    >
                      {risksReviewed ? 'Risks reviewed' : 'Mark reviewed'}
                    </button>
                  </div>
                )}
                <div className="memoRulingPanel">
                  <div className="memoDecisionChoices" role="group" aria-label="Choose final ruling">
                    {([
                      ['YES', 'Invest'],
                      ['MAYBE', 'Monitor'],
                      ['NO', 'Pass'],
                    ] as const).map(([decision, label]) => (
                      <button
                        key={decision}
                        type="button"
                        onClick={() => setRulingDecision(decision)}
                        aria-pressed={rulingDecision === decision}
                        disabled={rulingSaving}
                        className="memoDecisionChoice"
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <textarea
                    value={rulingNotes}
                    onChange={(e) => setRulingNotes(e.target.value)}
                    disabled={rulingSaving}
                    rows={2}
                    className="memoRulingTextarea"
                    placeholder="Ruling rationale..."
                    aria-label="Final ruling rationale"
                  />
                  <div className="memoRulingSubmitRow">
                    <button
                      type="button"
                      onClick={handleRulingSubmit}
                      disabled={!rulingDecision || rulingNotes.trim().length < 5 || rulingSaving || riskReviewOutstanding}
                      className="memoRulingSubmit"
                    >
                      {rulingSaving ? 'Recording...' : 'Commit ruling'}
                    </button>
                    {riskReviewOutstanding && (
                      <span className="memoRulingHint">Mark risks reviewed to commit.</span>
                    )}
                    {rulingError && <span className="memoRulingError">{rulingError}</span>}
                  </div>
                </div>
              </section>
            )}

            {showJudgment && (convictionHistory.length > 0 || precedentCandidates.length > 0) && (
              <section className="memoDocSection memoDecisionLedger" aria-labelledby="memo-decision-ledger">
                <h2 className="memoDocSectionHead" id="memo-decision-ledger">Decision Ledger</h2>
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
              </section>
            )}

            {/* ── Decision Context (LLM trigger) ── */}
            {displayStartup.partner?.llm_fallback_reason && (
              <div className="memoDocSection">
                <dl className="memoDocDL">
                  <div className="memoDocDLRow">
                    <dt className="memoDocDT">Decision context</dt>
                    <dd className="memoDocDD">{renderWithMonoNumbers(displayStartup.partner.llm_fallback_reason)}</dd>
                  </div>
                </dl>
              </div>
            )}

            {/* ── Sources ── */}
            {config.memo.includeEvidenceExcerpts && memoSources.length > 0 && (
              <section className="memoSourcesSection">
                <button
                  type="button"
                  className="memoSourcesToggle"
                  onClick={() => setSourcesOpen((v) => !v)}
                  aria-expanded={sourcesOpen}
                  aria-controls={`${contentKey}-sources-panel`}
                >
                  <span>Sources</span>
                  <span className="memoSourcesPlus">{sourcesOpen ? '−' : '+'}</span>
                </button>
                <motion.div
                  initial={false}
                  animate={sourcesOpen ? { opacity: 1, y: 0 } : { opacity: 0, y: -6 }}
                  transition={transitionOrReduced(reduceMotion, { duration: 0.2, ease: [0.16, 1, 0.3, 1] })}
                >
                  <div
                    id={`${contentKey}-sources-panel`}
                    className={`min-h-0 overflow-hidden ${sourcesOpen ? '' : 'hidden'}`}
                  >
                    <div className="memoSourcesBody">
                      <ul className="memoList">
                        {memoSources
                          .map((source, i) => {
                            return (
                              <li key={i} className="memoListItem">
                                <span className="memoBullet">·</span>
                                <span className="min-w-0">
                                {source.href ? (
                                  <a className="memoLink" href={source.href} target="_blank" rel="noreferrer">{renderWithMonoNumbers(source.label)}</a>
                                ) : (
                                  <span>{renderWithMonoNumbers(source.label)}</span>
                                )}
                                  <span className="block type-meta normal-case tracking-normal text-oxford/42">
                                    {sourceSupportLine(source, config.memo.includeSourceConfidence)}
                                  </span>
                                </span>
                              </li>
                            );
                          })}
                      </ul>
                    </div>
                  </div>
                </motion.div>
              </section>
            )}

            {/* ── Run Log ── */}
            {pipelineReplaySteps.length > 0 && (
              <section
                className="memoPipelineSection"
                aria-label="Run log"
              >
                <button
                  type="button"
                  className="memoPipelineToggle"
                  onClick={() => setPipelineLogOpen((v) => !v)}
                  aria-expanded={pipelineLogOpen}
                  aria-controls={`${contentKey}-pipeline-panel`}
                >
                  <span className="memoPipelineToggleTitle">
                    <span className="memoPipelineKicker">Run log</span>
                    <span className="memoPipelineOneLiner" title={pipelineReplaySummary}>
                      {renderWithMonoNumbers(pipelineReplaySummary)}
                    </span>
                  </span>
                  <span className="memoPipelinePlus">{pipelineLogOpen ? '−' : '+'}</span>
                </button>
                <motion.div
                  initial={false}
                  animate={pipelineLogOpen ? { opacity: 1, y: 0 } : { opacity: 0, y: -6 }}
                  transition={transitionOrReduced(reduceMotion, { duration: 0.2, ease: [0.16, 1, 0.3, 1] })}
                >
                  <div
                    id={`${contentKey}-pipeline-panel`}
                    className={`min-h-0 overflow-hidden ${pipelineLogOpen ? '' : 'hidden'}`}
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
                  </div>
                </motion.div>
              </section>
            )}


          </motion.div>
        </div>
      )}
    </div>
  );
});

export default InvestmentMemoContent;
