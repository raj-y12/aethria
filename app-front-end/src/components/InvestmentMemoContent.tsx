import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { fetchMemo, type MemoPartialPayload } from '../api/startups';
import { motion } from 'framer-motion';
import './InvestmentMemoContent.css';
import type { ScoringDimensionKey, SignalItem, Startup } from '../types/startup';
import { normalizeStructuredScoring } from '../lib/reviewScoring';
import { canonicalCriteriaToStructuredScoring } from '../lib/canonicalScoring';
import { getPipelineReplaySteps } from '../lib/memoIcPack';
import { UI_DETAIL_EMPTY_HINT } from '../design-system/ui-text';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';
import AssessmentScorecard from './scoring/AssessmentScorecard';
import ReviewerPanel from './scoring/ReviewerPanel';
import MemoMasthead from './memo/MemoMasthead';
import MemoPrecedentStrip from './memo/MemoPrecedentStrip';
import MemoPortfolioContext from './memo/MemoPortfolioContext';
import MemoSectionTitle from './memo/MemoSectionTitle';
import {
  createDefaultFundConfiguration,
  type FundConfiguration,
} from '../lib/fundConfiguration';
import { findPrecedentCandidates } from '../lib/institutionalConviction';
import {
  buildFounderSectionModel,
  formatFounderBackground,
  formatMissingFounderFields,
} from '../lib/founderMemo';
import { formatDate } from '../lib/dates';
import { safeHref } from '../lib/memoReferenceHref';
import OpportunityIntelligence from './institutional/OpportunityIntelligence';
import { useMemoDecisionBrief } from '../hooks/useMemoDecisionBrief';
import { getTriageGateStatus } from '../lib/triageGate';
import TriageGateCard from './TriageGateCard';
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
  memoSourceRows,
  reviewHasThesisAlignment,
  normalizeListItemText,
  renderWithMonoNumbers,
  toJudgmentReasoning,
  firstNonEmpty,
  memoHeaderThesisLine,
  pipelineReplayOneLiner,
  decisionLabel,
  sourceSupportLine,
  collapseWhitespace,
  clipText,
  leadSentences,
  reviewerMeanScore,
  buildInvestmentCase,
  cleanFactValue,
  buildSnapshotRows,
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
    <section
      className="memoDocSection memoDisclosureSection"
      data-open={open}
      aria-labelledby={`${id}-title`}
    >
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
      <div
        id={`${id}-body`}
        className={`memoDisclosureReveal${open ? ' memoDisclosureReveal--open' : ''}`}
        aria-hidden={!open}
        inert={!open}
      >
        <div className="memoDisclosureBody">{children}</div>
      </div>
    </section>
  );
}

function InvestmentMemoContent(
  {
    startup,
    onClose,
    onAddContext,
    embedded = false,
    readOnly = false,
    onMemoPipelineReady,
    fundConfiguration,
    peerStartups = [],
    portfolioSignals = [],
  }: InvestmentMemoContentProps
) {
  const config = fundConfiguration ?? createDefaultFundConfiguration();
  const reduceMotion = usePrefersReducedMotion();
  const wrapperCls = embedded ? 'memoPanel memoPanel--embedded' : 'memoPanel';
  const [memoPartial, setMemoPartial] = useState<MemoPartialPayload | null>(null);
  const [memoPipeline, setMemoPipeline] = useState<'idle' | 'generating' | 'ready' | 'failed'>('idle');
  const [memoGateError, setMemoGateError] = useState<string | null>(null);

  const displayStartup = useMemo(
    () => (startup ? mergeMemoPartial(startup, memoPartial) : null),
    [startup, memoPartial]
  );

  // Triage funnel (product direction, 2026-08-18): a startup the periodic
  // pipeline never reviewed or decided (see getTriageGateStatus) shows this
  // gate instead of the memo -- no memo content is fetched or rendered.
  const gateStatus = useMemo(
    () => (startup ? getTriageGateStatus(startup) : { gated: false as const }),
    [startup]
  );

  // Shared with OpportunityIntelligence below — same React Query keys, so this
  // is one fetch, not two, and the masthead verdict can never drift from the
  // decision workspace's canonical state.
  const { brief: mastheadBrief, evaluation: canonicalEvaluation } = useMemoDecisionBrief(displayStartup?.id ?? '');

  const contentKey = displayStartup?.id ?? startup?.id ?? 'empty';

  useEffect(() => {
    if (!startup?.id || gateStatus.gated) {
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
  }, [startup?.id, startup?.partner?.recommendation, gateStatus.gated, onMemoPipelineReady]);

  const showJudgment = !!displayStartup?.partner?.recommendation;
  const headerThesisLine = displayStartup ? memoHeaderThesisLine(displayStartup) : '';
  const reasoningParagraphs = useMemo(
    () => (displayStartup && showJudgment ? toJudgmentReasoning(displayStartup) : []),
    [displayStartup, showJudgment]
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
  const {
    candidates: founderCandidates,
    names: founderNames,
    missing: founderMissing,
    emptyMessage: founderEmptyMessage,
  } = useMemo(
    () =>
      buildFounderSectionModel({
        founderResolution: displayStartup?.scout.founder_resolution ?? null,
        companyResolution,
        scoutFounderNames: displayStartup?.scout.founder_names ?? null,
      }),
    [displayStartup, companyResolution],
  );
  const founderTeamItems = (displayStartup?.review?.team_analysis ?? []).filter(
    (s) => String(s ?? '').trim() && !/^\[MISSING/i.test(String(s ?? '').trim()),
  );
  // Investment read (reviewer_rules v2+). Narrative only; the backend has
  // already dropped anything that failed the evidence bar, so anything present
  // here is renderable as-is.
  const founderFluency = displayStartup?.review?.founder_fluency ?? [];
  const founderSignal = (displayStartup?.scout.founder_signal ?? '').trim();
  const founderQuote = (displayStartup?.scout.founder_quote ?? '').trim();
  const resolutionStatus = (
    displayStartup?.scout.resolution_status ??
    companyResolution?.resolution_status ??
    ''
  )
    .toString()
    .toUpperCase();
  const convictionHistory = displayStartup?.conviction_state?.decision_history ?? [];
  const precedentCandidates = useMemo(
    () => (displayStartup ? findPrecedentCandidates(displayStartup, peerStartups) : []),
    [displayStartup, peerStartups]
  );

  // Canonical evaluate_snapshot() criteria are the score authority when present;
  // legacy reviewer structured_scoring is the fallback for opportunities without
  // one yet (see docs/archive/plans/2026-08-17-reviewer-scoring-collapse.md).
  const canonicalStructuredScoring = useMemo(
    () => canonicalCriteriaToStructuredScoring(canonicalEvaluation),
    [canonicalEvaluation]
  );
  const structuredScoring = useMemo(
    () => canonicalStructuredScoring ?? normalizeStructuredScoring(displayStartup?.review ?? null),
    [canonicalStructuredScoring, displayStartup?.review]
  );

  // scoring_presentation is a legacy narrative layer built from reviewer's own
  // dimension values — only valid alongside the legacy scoring, never canonical's.
  const scoringPresentation = useMemo(
    () => (canonicalStructuredScoring ? null : (displayStartup?.review?.scoring_presentation ?? null)),
    [canonicalStructuredScoring, displayStartup?.review]
  );
  const thesisSection = useMemo(() => {
    const review = displayStartup?.review;
    if (!review) {
      return { visible: false, score: null, headlineTag: '', fitPoints: [], gapPoints: [] };
    }
    const rawScore = review.thesis_alignment_score;
    const score = rawScore != null ? (rawScore <= 1 ? rawScore * 10 : rawScore) : null;
    const headlineTag = review.thesis_matches_fund != null
      ? (review.thesis_matches_fund ? 'Mandate aligned' : 'Mandate misaligned')
      : '';
    const fitPoints = (review.thesis_fit_points ?? []).filter((item) => String(item ?? '').trim());
    const gapPoints = (review.thesis_deviation_points ?? []).filter((item) => String(item ?? '').trim());
    const visible = reviewHasThesisAlignment(review) && (
      score != null || Boolean(headlineTag) || fitPoints.length > 0 || gapPoints.length > 0
    );
    return { visible, score, headlineTag, fitPoints, gapPoints };
  }, [displayStartup?.review]);
  const pipelineReplaySteps = useMemo(
    () => (displayStartup ? getPipelineReplaySteps(displayStartup) : []),
    [displayStartup]
  );
  const pipelineReplaySummary = useMemo(
    () => pipelineReplayOneLiner(pipelineReplaySteps),
    [pipelineReplaySteps]
  );
  // ── Editorial derivations ──
  // On a decided deal the standfirst sits directly under the recommendation, so
  // it must be the REASON. Leading with partner.thesis put the bull case under
  // a PASS ("startups are underserved by traditional insurers" beneath a Pass on
  // an insurtech), which reads as self-contradiction; the actual rationale was
  // buried in the appendix.
  const coverStandfirst = displayStartup
    ? leadSentences(
        firstNonEmpty(
          ...(displayStartup.partner?.recommendation
            ? [displayStartup.partner?.decision_rationale]
            : []),
          displayStartup.partner?.thesis,
          displayStartup.review?.aethria_view?.headline,
          displayStartup.partner?.why_this_matters,
          headerThesisLine,
          displayStartup.review?.overall_summary,
        ),
        260,
      )
    : '';
  const investmentCasePoints = useMemo(
    () => (displayStartup ? buildInvestmentCase(displayStartup, coverStandfirst) : []),
    [displayStartup, coverStandfirst]
  );
  const snapshotRows = useMemo(
    () => (displayStartup ? buildSnapshotRows(displayStartup, '', false) : []),
    [displayStartup]
  );
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
        // A low score on thin data is a measurement, not a verdict. Without this
        // the panel showed a bare "2.0" beside an upbeat sentence and the two read
        // as a contradiction. Despite its backend name, evidence_coverage is the
        // fraction of rubric sub-criteria that had ANY extractable signal (not
        // missing_data_applied) -- it says nothing about whether that signal was
        // independently verified. Labelled "data coverage" below, not "evidenced",
        // so it never reads as a verification claim.
        coverage: typeof rv.evidence_coverage === 'number' ? rv.evidence_coverage : null,
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
  // The house upward reveal (see Reveal.tsx), fired as each document section scrolls
  // into view. Shared by every numbered section so the motion stays uniform.
  const sectionReveal = {
    initial: reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 12 },
    whileInView: { opacity: 1, y: 0 },
    viewport: { once: true, margin: '0px 0px -10% 0px' },
    transition: transitionOrReduced(reduceMotion, { duration: 0.5, ease: [0.16, 1, 0.3, 1] }),
  };
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
      ) : gateStatus.gated ? (
        <TriageGateCard startup={displayStartup} status={gateStatus} onClose={onClose} />
      ) : (
        <div
          className={`memoScroll relative${embedded ? '' : ' memo-scroll-root'}`}
          role="region"
          aria-label="Investment memo"
        >
          <MemoMasthead
            startup={displayStartup}
            brief={mastheadBrief}
            onAddContext={onAddContext}
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
            // Opening the memo lands the document with the house upward reveal;
            // numbered sections add their own in-view reveal (sectionReveal) as
            // the reader scrolls.
            initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={transitionOrReduced(reduceMotion, { duration: 0.55, ease: [0.16, 1, 0.3, 1] })}
          >

            {readOnly ? (
              <p className="memoShareBanner" role="status">
                Read-only view — share this link with a co-GP. Rulings and edits are disabled.
              </p>
            ) : null}

            <div className="memoSupportingAnalysis">
              <div className="memoSupportingAnalysisBody">
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
              <motion.section {...sectionReveal} className="memoDocSection memoSnapshotSection" aria-labelledby="memo-snapshot">
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
              </motion.section>
            )}

            {/* ── Founder ──
                Always rendered. A memo that silently omits the founder section
                reads as "no team risk" when it actually means "we did not look"
                or "we could not find them" — so the empty state is explicit. */}
            <motion.section {...sectionReveal} className="memoDocSection memoFounderSection" aria-labelledby="memo-founder">
                <MemoSectionTitle number="02" id="memo-founder">Founder</MemoSectionTitle>
                {founderCandidates.length > 0 ? (
                  <ul className="memoFounderList">
                    {founderCandidates.map((f, i) => (
                      <li key={`${f.name}-${i}`} className="memoFounderItem">
                        <p className="memoDocSubhead">
                          {f.name}
                          {f.role ? <span className="memoFounderRole">{f.role}</span> : null}
                        </p>
                        {formatFounderBackground(f) ? (
                          <p className="memoDocProse memoFounderBackground">
                            {formatFounderBackground(f)}
                          </p>
                        ) : null}
                        {(f.linkedin_url || f.x_url || f.github_url) ? (
                          <p className="memoFounderLinks">
                            {f.linkedin_url ? (
                              <a href={safeHref(f.linkedin_url)} target="_blank" rel="noopener noreferrer">LinkedIn</a>
                            ) : null}
                            {f.x_url ? (
                              <a href={safeHref(f.x_url)} target="_blank" rel="noopener noreferrer">X</a>
                            ) : null}
                            {f.github_url ? (
                              <a href={safeHref(f.github_url)} target="_blank" rel="noopener noreferrer">GitHub</a>
                            ) : null}
                          </p>
                        ) : null}
                        {f.conflicts?.length ? (
                          <p className="memoFounderConflict">
                            Sources disagree on {f.conflicts.map((c) => c.field).join(', ')} — verify before relying on this.
                          </p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : founderNames.length > 0 ? (
                  // Names with no resolved candidate used to render as a mono
                  // caption, so the founders read as a field label rather than
                  // as people. They are the section's subject; set them as such.
                  <p className="memoFounderBareNames">{founderNames.join(', ')}</p>
                ) : (
                  <p className="memoDocProse memoFounderEmpty">{founderEmptyMessage}</p>
                )}
                {founderNames.length > 0 && founderMissing.length > 0 ? (
                  <p className="memoDocProse memoFounderEmpty">
                    {founderMissing.includes('previous_employment')
                      ? 'No founder history was retrieved. Team execution is therefore unevidenced rather than judged weak, and no founder read could be produced. '
                      : ''}
                    Not confirmed: {formatMissingFounderFields(founderMissing)}.
                  </p>
                ) : null}
                {founderSignal ? (
                  <div className="memoDocSubsection">
                    <p className="memoDocSubhead">The read</p>
                    <p className="memoDocProse">{renderWithMonoNumbers(founderSignal)}</p>
                  </div>
                ) : null}
                {founderQuote ? (
                  <div className="memoDocSubsection">
                    <p className="memoDocSubhead">In their words</p>
                    <p className="memoDocProse">{'“'}{founderQuote}{'”'}</p>
                  </div>
                ) : null}
                {founderFluency.length > 0 ? (
                  <div className="memoDocSubsection memoFluency">
                    <p className="memoDocSubhead">Fluency</p>
                    {founderFluency.map((f, i) => (
                      <div key={`${f.founder}-${i}`} className="memoFluencyEntry">
                        <p className="memoDocProse">
                          <span className="memoFluencyName">{f.founder}</span>
                          {' — '}{renderWithMonoNumbers(f.prior_domain)}
                          {f.fluent_in?.length ? ` Fluent in ${f.fluent_in.join('; ')}.` : ''}
                          {f.unlocks?.length ? ` Unlocks ${f.unlocks.join('; ')}.` : ''}
                        </p>
                        <p className="memoFluencyEvidence">{f.evidence}</p>
                      </div>
                    ))}
                  </div>
                ) : null}
                {founderTeamItems.length > 0 ? (
                  <div className="memoDocSubsection">
                    <p className="memoDocSubhead">Team assessment</p>
                    <ExpandableList
                      items={founderTeamItems}
                      cap={3}
                      renderItem={(item, i) => (
                        <li key={i} className="memoListItem">
                          <span className="memoBullet" aria-hidden>·</span>
                          <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                        </li>
                      )}
                    />
                  </div>
                ) : null}
            </motion.section>

            {/* ── Investment case ── */}
            {investmentCasePoints.length > 0 && (
              <motion.section {...sectionReveal} className="memoDocSection memoCaseSection" aria-labelledby="memo-case">
                <MemoSectionTitle number="03" id="memo-case">Why Now</MemoSectionTitle>
                <ol className="memoCaseList">
                  {investmentCasePoints.map((point, i) => (
                    <li key={i} className={`memoCasePoint${i === 0 ? ' memoCasePoint--lead' : ''}`}>
                      {renderWithMonoNumbers(point)}
                    </li>
                  ))}
                </ol>
              </motion.section>
            )}

            {/* ── Assessment ── */}
            {(() => {
              const isMissing = (s: string) => /^\[MISSING/i.test(String(s ?? '').trim());
              const compItems = (displayStartup.review?.competition_analysis ?? []).filter((s) => String(s ?? '').trim() && !isMissing(String(s)));
              const bizItems = (displayStartup.review?.business_model_analysis ?? []).filter((s) => String(s ?? '').trim() && !isMissing(String(s)));
              const hasScores = !!structuredScoring;
              const showScores = config.memo.includeScoreReasoning && hasScores;
              const assessmentReadouts = [
                { label: 'Competitive Landscape', items: compItems },
                { label: 'Business Model', items: bizItems },
              ].filter((section) => section.items.length > 0);
              const hasScorecard = showScores && !!structuredScoring;
              const hasPanel = reviewerConsensusRows.length > 0;
              const hasDeepDive = assessmentReadouts.length > 0;
              if (!hasScorecard && !hasPanel && !hasDeepDive) {
                return null;
              }
              return (
                <motion.section {...sectionReveal} className="memoDocSection memoScoringSection" aria-labelledby="memo-scoring">
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
                    <ReviewerPanel
                      rows={reviewerConsensusRows}
                      consensus={reviewerConsensus}
                      renderNumbers={renderWithMonoNumbers}
                    />
                  ) : null}
                  {hasDeepDive && (
                    <div className="memoScoringMore">
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
                  {mastheadBrief.drivers.length > 0 && (
                    <div className="memoDocSubsection memoAssessmentDrivers">
                      <p className="memoDocSubhead">Why the system leans this way</p>
                      <ul className="memoList">
                        {mastheadBrief.drivers.map((driver) => (
                          <li key={driver} className="memoListItem">
                            <span className="memoBullet" aria-hidden>·</span>
                            <span>{renderWithMonoNumbers(driver)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </motion.section>
              );
            })()}

            {/* ── Fund thesis alignment ── */}
            {thesisSection.visible && (
              <motion.section {...sectionReveal} className="memoDocSection memoThesisSection" aria-labelledby="memo-thesis-alignment">
                <MemoSectionTitle number="05" id="memo-thesis-alignment">Thesis alignment</MemoSectionTitle>
                <div className="memoThesisBody">
                  {mastheadBrief.mandate === 'conflicted' && (
                    <p className="memoThesisMandateConflict" role="alert">Mandate conflict — this opportunity falls outside the fund's stated mandate.</p>
                  )}
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
              </motion.section>
            )}

            {/* ── Before you rule: evidence coverage, deduplicated risks, and the ruling itself ── */}
            <OpportunityIntelligence
              startupId={displayStartup.id}
              companyName={displayStartup.scout.name}
              onRulingRecorded={onClose}
              readOnly={readOnly}
            />

            {/* ── Appendix ── */}
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
                    const href = safeHref(section.title);
                    const clipped = clipText(collapseWhitespace(section.body), 900);
                    return (
                      <li key={`${section.title}-${i}`} className="memoAnalystContextItem">
                        <p className="memoReplayKicker">
                          {href ? (
                            <a className="memoLink" href={href} target="_blank" rel="noreferrer">
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
                    </span>
                  </li>
                  {companyResolution?.website ? (
                    <li className="memoListItem">
                      <span className="memoBullet">·</span>
                      <span>
                        Website:{' '}
                        <a className="memoLink" href={safeHref(companyResolution.website)} target="_blank" rel="noreferrer">
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
                        <a className="memoLink" href={safeHref(companyResolution.linkedin_url)} target="_blank" rel="noreferrer">
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
                          href={safeHref(companyResolution.crunchbase_url || companyResolution.dealroom_url || companyResolution.yc_url)}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {companyResolution.crunchbase_url || companyResolution.dealroom_url || companyResolution.yc_url}
                        </a>
                      </span>
                    </li>
                  ) : null}
                  {founderNames.length > 0 ? (
                    <li className="memoListItem">
                      <span className="memoBullet">·</span>
                      <span>Founders: {founderNames.join(', ')}</span>
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
                          <a className="memoLink" href={safeHref(source.href)} target="_blank" rel="noreferrer">{renderWithMonoNumbers(source.label)}</a>
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
              </div>
            </div>

          </motion.div>
        </div>
      )}
    </article>
  );
}

export default InvestmentMemoContent;
