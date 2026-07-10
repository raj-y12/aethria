import { useCallback, forwardRef, useEffect, useImperativeHandle, useMemo, useState, type ReactNode } from 'react';
import { fetchMemo, type MemoPartialPayload } from '../api/startups';
import { motion } from 'framer-motion';
import './InvestmentMemoContent.css';
import type { ScoringDimensionKey, SignalItem, Startup } from '../types/startup';
import { normalizeStructuredScoring } from '../lib/reviewScoring';
import {
  buildMemoPDF,
  icPackSafeBaseName,
  getPipelineReplaySteps,
} from '../lib/memoIcPack';
import { UI_DETAIL_EMPTY_HINT } from '../design-system/ui-text';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';
import AssessmentScorecard from './scoring/AssessmentScorecard';
import MemoMasthead from './memo/MemoMasthead';
import MemoRulingSection from './memo/MemoRulingSection';
import MemoPrecedentStrip from './memo/MemoPrecedentStrip';
import MemoPortfolioContext from './memo/MemoPortfolioContext';
import MemoSectionTitle from './memo/MemoSectionTitle';
import MemoDossierOpening from './memo/MemoDossierOpening';
import { DECISION_BADGE_LABEL } from './DecisionBadge';
import { getDecisionBadgeVariant } from '../lib/decisionBadgeVariant';
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
import { getNextStepText, parseNextStepItems } from '../lib/memoText';
import { formatDate } from '../lib/dates';
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

import {
  mergeMemoPartial,
  analystContextSections,
  memoGeneratingDetailForVariant,
  memoSourceRows,
  reviewHasThesisAlignment,
  normalizeListItemText,
  normalizeMemoKey,
  renderWithMonoNumbers,
  partnerDecisionHeadline,
  toJudgmentReasoning,
  firstNonEmpty,
  getPartnerEconomicBadgeVariant,
  memoHeaderThesisLine,
  pipelineReplayOneLiner,
  decisionLabel,
  uniqueRiskItems,
  missingDataItems,
  sourceSupportLine,
  collapseWhitespace,
  clipText,
  leadSentences,
  reviewerMeanScore,
  buildInvestmentCase,
  cleanFactValue,
  buildSnapshotRows,
  buildKillers,
} from './memo/memoContentHelpers';

const RESOLUTION_SECTION_LABELS: Record<string, string> = {
  FOUND: 'Identity confirmed',
  PARTIAL: 'Partial evidence',
  LOW_CONFIDENCE: 'Low-confidence match',
  NEEDS_REVIEW: 'Needs review',
  NOT_FOUND: 'Not found',
};

const RESOLUTION_MISSING_FIELD_LABELS: Record<string, string> = {
  website: 'website',
  linkedin_url: 'LinkedIn company page',
  funding_profile: 'funding profile (Crunchbase/Dealroom/YC)',
  founder_names: 'founder names',
  description: 'company description',
  news_mentions: 'news mentions',
};

export interface InvestmentMemoContentProps {
  startup: Startup | null;
  onClose?: () => void;
  /** Mobile/modal entry point for the add-context re-review takeover. */
  onAddContext?: () => void;
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

const SEVERITY_LABEL: Record<AdverseRegisterItem['severity'], string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

const REVIEWER_LABELS: Record<string, string> = {
  DefaultReviewer: 'Default',
  SkepticalReviewer: 'Skeptical',
  OpportunistReviewer: 'Opportunist',
};


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
    onAddContext,
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
  const analystContext = useMemo(
    () => analystContextSections(displayStartup),
    [displayStartup]
  );
  const companyResolution = displayStartup?.scout.company_resolution ?? null;
  const resolutionStatus = (
    displayStartup?.scout.resolution_status ??
    companyResolution?.resolution_status ??
    ''
  )
    .toString()
    .toUpperCase();
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
  const thesisSection = useMemo(() => {
    const review = displayStartup?.review;
    if (!review) {
      return { visible: false, score: null, headlineTag: '', fitPoints: [], gapPoints: [] };
    }
    const rawScore = review.thesis_alignment_score;
    const score = rawScore != null ? (rawScore <= 1 ? rawScore * 10 : rawScore) : null;
    const confidence = review.thesis_alignment_confidence;
    const headlineTag = [
      review.thesis_matches_fund != null
        ? (review.thesis_matches_fund ? 'Mandate aligned' : 'Mandate misaligned')
        : null,
      confidence != null ? `${(confidence * 100).toFixed(0)}% confidence` : null,
    ].filter(Boolean).join('  ·  ');
    const fitPoints = (review.thesis_fit_points ?? []).filter((item) => String(item ?? '').trim());
    const gapPoints = (review.thesis_deviation_points ?? []).filter((item) => String(item ?? '').trim());
    const visible = reviewHasThesisAlignment(review) && (
      score != null || Boolean(headlineTag) || fitPoints.length > 0 || gapPoints.length > 0
    );
    return { visible, score, headlineTag, fitPoints, gapPoints };
  }, [displayStartup?.review]);
  const openingRiskItems = useMemo(() => {
    const items = [
      ...adverseRegister.map((item) => item.whyItMatters || item.title),
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
    () => (displayStartup ? buildSnapshotRows(displayStartup, coverBlocker, false) : []),
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
  const reviewerState = reviewerConsensusRows.length > 0
    ? `${reviewerConsensusRows.length} · ${reviewerConsensus.split ? 'Split' : 'Aligned'}`
    : 'Pending';
  const mandateFit = displayStartup?.review?.thesis_matches_fund == null
    ? thesisAlignmentBrief || undefined
    : displayStartup.review.thesis_matches_fund
      ? 'Strong'
      : 'Outside mandate';
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
          <MemoMasthead
            startup={displayStartup}
            onAddContext={onAddContext}
            onDownloadPDF={handleDownloadPDF}
            onClose={onClose}
            readOnly={readOnly}
          />

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
            // Single opacity fade for the whole document — no per-section stagger.
            initial={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={transitionOrReduced(reduceMotion, { duration: 0.2, ease: [0.23, 1, 0.32, 1] })}
          >

            {readOnly ? (
              <p className="memoShareBanner" role="status">
                Read-only view — share this link with a co-GP. Rulings and edits are disabled.
              </p>
            ) : null}

            <MemoDossierOpening
              recommendation={coverRulingHeadline}
              recommendationTone={coverRulingVariantClass}
              standfirst={coverStandfirst}
              conviction={convictionLine}
              reviewerState={reviewerState}
              mandateFit={mandateFit}
              status={coverStatusText}
              focalQuestion={focalQuestion}
              blocker={coverBlocker}
              nextMove={coverAction}
            />

            {(showJudgment && precedentCandidates.length > 0) || portfolioSignals.length > 0 ? (
              <div className="memoDossierContext">
                {showJudgment && precedentCandidates.length > 0 ? (
                  <MemoPrecedentStrip
                    candidates={precedentCandidates}
                    renderWithMonoNumbers={renderWithMonoNumbers}
                  />
                ) : null}
                <MemoPortfolioContext startupId={displayStartup.id} signals={portfolioSignals} />
              </div>
            ) : null}

            {/* ── Company snapshot — one definition grid: verified vitals first, then narrative rows ── */}
            {(snapshotRows.length > 0 || hasVitals) && (
              <section className="memoDocSection memoSnapshotSection" aria-labelledby="memo-snapshot">
                <MemoSectionTitle number="01" id="memo-snapshot">Snapshot</MemoSectionTitle>
                <dl className="memoSnapshot">
                  {[
                    ...vitalsStrip.map((v) => ({ label: v.label, text: v.value })),
                    ...(fundingLine ? [{ label: 'Funding', text: fundingLine }] : []),
                    ...(tractionLine ? [{ label: 'Traction', text: tractionLine }] : []),
                    ...(modelLine ? [{ label: 'Model', text: modelLine }] : []),
                    ...(ipLine ? [{ label: 'IP', text: ipLine }] : []),
                    ...snapshotRows,
                  ].map((row) => (
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
                <MemoSectionTitle number="02" id="memo-case">Why Now</MemoSectionTitle>
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
                <MemoSectionTitle number="03" id="memo-killers">What Limits Conviction</MemoSectionTitle>
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
              const hasScorecard = showScores && !!structuredScoring;
              const hasPanel = reviewerConsensusRows.length > 0;
              const hasDeepDive = improvements.length > 0 || assessmentReadouts.length > 0;
              if (!hasScorecard && !hasPanel && !hasDeepDive) {
                return null;
              }
              return (
                <section className="memoDocSection memoScoringSection" aria-labelledby="memo-scoring">
                  <MemoSectionTitle number="04" id="memo-scoring">Assessment</MemoSectionTitle>
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
                    </div>
                  )}
                </section>
              );
            })()}

            {/* ── Fund thesis alignment ── */}
            {thesisSection.visible && (
              <section className="memoDocSection memoThesisSection" aria-labelledby="memo-thesis-alignment">
                <MemoSectionTitle number="05" id="memo-thesis-alignment">Thesis alignment</MemoSectionTitle>
                <div className="memoThesisBody">
                  {(thesisSection.score != null || thesisSection.headlineTag) && (
                    <p className="memoScoreHeadline">
                      {thesisSection.score != null && (
                        <>
                          <span className="memoScoreHeadlineValue">
                            {renderWithMonoNumbers(thesisSection.score.toFixed(0))}
                          </span>
                          <span className="memoScoreHeadlineMax">/ 10</span>
                        </>
                      )}
                      {thesisSection.headlineTag && (
                        <span className="memoScoreHeadlineTag">
                          {renderWithMonoNumbers(thesisSection.headlineTag)}
                        </span>
                      )}
                    </p>
                  )}
                  {thesisSection.fitPoints.length > 0 && (
                    <ul className="memoList">
                      {thesisSection.fitPoints.map((item, i) => (
                        <li key={`fit-${i}`} className="memoListItem">
                          <span className="memoBullet" aria-hidden>+</span>
                          <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {thesisSection.gapPoints.length > 0 && (
                    <ul className="memoList memoThesisGapList">
                      {thesisSection.gapPoints.map((item, i) => (
                        <li key={`gap-${i}`} className="memoListItem">
                          <span className="memoBullet" aria-hidden>·</span>
                          <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </section>
            )}

            {/* ── Risk register ── */}
            {(adverseRegister.length > 0 || riskFactors.risks.length > 0 || riskFactors.mitigation.length > 0 || missingEvidenceItems.length > 0) && (
              <section className="memoDocSection memoRiskRegisterSection" aria-labelledby="memo-risk-register">
                <MemoSectionTitle number="06" id="memo-risk-register">Risks</MemoSectionTitle>
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

            {/* ── Appendix (sits under the ruling) ── */}
            <div className="memoDiscGroup">
            {/* Hidden via :only-child when every disclosure fails its render condition. */}
            <p className="memoAppendixLabel" aria-hidden>Appendix</p>
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
                          <span>{formatDate(entry.timestamp)}</span>
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
            {analystContext.length > 0 && (
              <MemoDisclosureSection
                id={`${contentKey}-analyst-context`}
                title="Analyst context"
                summary={`${analystContext.length} added item${analystContext.length === 1 ? '' : 's'}`}
                initialOpen
              >
                <ol className="memoAnalystContextList">
                  {analystContext.map((section, i) => {
                    const isUrl = /^https?:\/\//i.test(section.title);
                    const clipped = clipText(collapseWhitespace(section.body), 900);
                    return (
                      <li key={`${section.title}-${i}`} className="memoAnalystContextItem">
                        <p className="memoReplayKicker">
                          {isUrl ? (
                            <a className="memoLink" href={section.title} target="_blank" rel="noreferrer">
                              {renderWithMonoNumbers(section.title)}
                            </a>
                          ) : (
                            <span>{section.title}</span>
                          )}
                        </p>
                        <p className="memoReplayDetail">{renderWithMonoNumbers(clipped)}</p>
                      </li>
                    );
                  })}
                </ol>
              </MemoDisclosureSection>
            )}
            {/* ── Company resolution (lookup stage 1) ── */}
            {(companyResolution || resolutionStatus) && (
              <MemoDisclosureSection
                id={`${contentKey}-resolution`}
                title="Company resolution"
                summary={RESOLUTION_SECTION_LABELS[resolutionStatus] ?? resolutionStatus ?? 'Resolved'}
                initialOpen={false}
              >
                <ul className="memoList">
                  <li className="memoListItem">
                    <span className="memoBullet">·</span>
                    <span>
                      Status: {RESOLUTION_SECTION_LABELS[resolutionStatus] ?? resolutionStatus ?? 'Unknown'}
                      {typeof companyResolution?.confidence === 'number'
                        ? ` (${Math.round(companyResolution.confidence * 100)}% identity confidence)`
                        : ''}
                    </span>
                  </li>
                  {companyResolution?.website ? (
                    <li className="memoListItem">
                      <span className="memoBullet">·</span>
                      <span>
                        Website:{' '}
                        <a className="memoLink" href={companyResolution.website} target="_blank" rel="noreferrer">
                          {companyResolution.website}
                        </a>
                      </span>
                    </li>
                  ) : null}
                  {companyResolution?.linkedin_url ? (
                    <li className="memoListItem">
                      <span className="memoBullet">·</span>
                      <span>
                        LinkedIn:{' '}
                        <a className="memoLink" href={companyResolution.linkedin_url} target="_blank" rel="noreferrer">
                          {companyResolution.linkedin_url}
                        </a>
                      </span>
                    </li>
                  ) : null}
                  {companyResolution?.crunchbase_url || companyResolution?.dealroom_url || companyResolution?.yc_url ? (
                    <li className="memoListItem">
                      <span className="memoBullet">·</span>
                      <span>
                        Funding profile:{' '}
                        <a
                          className="memoLink"
                          href={companyResolution.crunchbase_url || companyResolution.dealroom_url || companyResolution.yc_url || undefined}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {companyResolution.crunchbase_url || companyResolution.dealroom_url || companyResolution.yc_url}
                        </a>
                      </span>
                    </li>
                  ) : null}
                  {(companyResolution?.founder_names?.length ?? 0) > 0 ? (
                    <li className="memoListItem">
                      <span className="memoBullet">·</span>
                      <span>Founders: {companyResolution!.founder_names!.join(', ')}</span>
                    </li>
                  ) : null}
                  {(companyResolution?.missing_fields?.length ?? 0) > 0 ? (
                    <li className="memoListItem">
                      <span className="memoBullet">·</span>
                      <span>
                        Missing evidence:{' '}
                        {companyResolution!.missing_fields!
                          .map((f) => RESOLUTION_MISSING_FIELD_LABELS[f] ?? f)
                          .join(', ')}
                      </span>
                    </li>
                  ) : null}
                  {(companyResolution?.alternative_matches?.length ?? 0) > 0 ? (
                    <li className="memoListItem">
                      <span className="memoBullet">·</span>
                      <span>
                        Alternative matches:{' '}
                        {companyResolution!.alternative_matches!
                          .map((a) => a.website || a.name)
                          .filter(Boolean)
                          .join(', ')}
                      </span>
                    </li>
                  ) : null}
                  {(companyResolution?.notes ?? []).map((note, i) => (
                    <li key={`note-${i}`} className="memoListItem">
                      <span className="memoBullet">·</span>
                      <span>{note}</span>
                    </li>
                  ))}
                </ul>
                {(companyResolution?.stage_log?.length ?? 0) > 0 ? (
                  <ol className="memoReplayList">
                    {companyResolution!.stage_log!.map((step, i) => (
                      <li key={`res-step-${i}`} className="memoReplayItem">
                        <p className="memoReplayKicker">
                          <span>{step.stage}</span>
                          <span className="memoReplayBadge">{step.decision || '—'}</span>
                        </p>
                        {step.queries && step.queries.length > 0 ? (
                          <p className="memoReplayWhen">Queries: {step.queries.join(' · ')}</p>
                        ) : null}
                        <p className="memoReplayDetail">
                          {step.reason || ''}
                          {typeof step.sources_found === 'number' ? ` (${step.sources_found} sources)` : ''}
                        </p>
                      </li>
                    ))}
                  </ol>
                ) : null}
              </MemoDisclosureSection>
            )}

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
