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
  return category ? `${sector} · ${category}` : sector;
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

const InvestmentMemoContent = forwardRef<InvestmentMemoContentHandle, InvestmentMemoContentProps>(function InvestmentMemoContent(
  { startup, onClose, embedded = false, onMemoPipelineReady },
  ref
) {
  const reduceMotion = usePrefersReducedMotion();
  const wrapperCls = embedded ? 'memoPanel memoPanel--embedded' : 'memoPanel';
  const [selectedReviewerIdx, setSelectedReviewerIdx] = useState(0);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [pipelineLogOpen, setPipelineLogOpen] = useState(false);

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
  const reasoningParagraphs = useMemo(
    () => (displayStartup && showJudgment ? toJudgmentReasoning(displayStartup) : []),
    [displayStartup, showJudgment]
  );

  useEffect(() => {
    setSelectedReviewerIdx(0);
    setSourcesOpen(false);
    setPipelineLogOpen(false);
  }, [startup?.id]);

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
                <h1 className="memoCompany" id="memo-title">{companyName || '—'}</h1>
                {displayStartup.scout.one_line?.trim() && (
                  <p className="memoDocTagline">{renderWithMonoNumbers(displayStartup.scout.one_line)}</p>
                )}
                <p className="memoMeta">
                  {sectorCategory.trim() ? renderWithMonoNumbers(sectorCategory) : null}
                  {showLookupBadge && (
                    <>
                      {sectorCategory.trim() ? (
                        <span className="memoMetaSep" aria-hidden>
                          {' · '}
                        </span>
                      ) : null}
                      <span className="text-lookup">Lookup</span>
                    </>
                  )}
                </p>
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

            {/* ── Verdict (partner recommendation — published conclusion) ── */}
            {showJudgment && (() => {
              const paras = reasoningParagraphs.filter((p) => String(p ?? '').trim());
              return (
                <section className="memoDocSection memoDocVerdictSection" aria-labelledby="memo-verdict">
                  <h2 className="memoDocSectionHead" id="memo-verdict">Verdict</h2>
                  {decisionBadgeVariant && (
                    <div className="memoDocJudgmentTop">
                      <p className={`memoDocRecommendation memoDocRecommendation--${decisionBadgeVariant.toLowerCase()}`}>
                        {decisionHeadline}.
                      </p>
                      <div className="memoDocStatusLine">
                        {displayStartup.partner?.confidence != null && (
                          <p className="memoDocConfidence">
                            <span className="memoNum">{Math.round(displayStartup.partner.confidence * 100)}%</span> confidence
                          </p>
                        )}
                        {showEscalationBadge && (
                          <p className="memoDocEscalation">Escalation required</p>
                        )}
                      </div>
                      {displayStartup.partner?.decision_drivers &&
                        displayStartup.partner.decision_drivers.length > 0 && (
                          <p className="memoDocDrivers">
                            {displayStartup.partner.decision_drivers.join(' · ')}
                          </p>
                        )}
                    </div>
                  )}
                  {paras.map((p, i) => (
                    <p key={i} className="memoDocProse">{renderWithMonoNumbers(p)}</p>
                  ))}
                </section>
              );
            })()}

            {/* ── Executive Summary (synthesis after verdict) ── */}
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
                  <p className="memoDocProse font-semibold text-oxford">{renderWithMonoNumbers(av.headline)}</p>
                  {av.thesis_fit_line?.trim() && (
                    <p className="memoDocProse mt-2">{renderWithMonoNumbers(av.thesis_fit_line)}</p>
                  )}
                  {av.tension_summary?.trim() && (
                    <p className="memoDocProse mt-2 text-oxford/90">{renderWithMonoNumbers(av.tension_summary)}</p>
                  )}
                  {av.focal_question?.trim() && (
                    <p className="memoDocProse memoDocFocalInset mt-3">
                      <span className="memoDocSubhead block mb-1">Focal question</span>
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
              const rawSig = displayStartup.review?.structured_signals as Record<string, unknown> | undefined;
              const hasSignalsAudit =
                !!(rawSig && Object.keys(rawSig).length > 0) ||
                !!displayStartup.review?.disagreement_summary?.trim() ||
                (displayStartup.review?.resolution_notes?.filter(Boolean) ?? []).length > 0;
              if (
                !displayStartup.review &&
                !teamItems.length &&
                !compItems.length &&
                !bizItems.length &&
                !hasSignalsAudit &&
                !hasScores
              ) {
                return null;
              }
              return (
                <section className="memoDocSection" aria-labelledby="memo-assessment">
                  <h2 className="memoDocSectionHead" id="memo-assessment">Assessment</h2>

                  {(hasScores || hasSignalsAudit) && (
                    <div className="memoDocScoreScope">
                      {(() => {
                        const sig = rawSig;
                        const dsum = displayStartup.review?.disagreement_summary?.trim();
                        const rnotes = displayStartup.review?.resolution_notes?.filter(Boolean) ?? [];
                        if (!sig && !dsum && rnotes.length === 0) return null;
                        const sigPreview =
                          sig && Object.keys(sig).length > 0
                            ? JSON.stringify(sig, null, 2).slice(0, 6000)
                            : null;
                        return (
                          <div className="memoDocSubsection mb-4 bg-registerTint px-3 py-3">
                            <p className="memoDocSubhead">Signals &amp; reviewer alignment</p>
                            {dsum && (
                              <p className="memoDocProse text-sm text-oxford/90">{renderWithMonoNumbers(dsum)}</p>
                            )}
                            {rnotes.length > 0 && (
                              <ul className="memoList mt-2">
                                {rnotes.map((note, i) => (
                                  <li key={i} className="memoListItem text-sm">
                                    <span className="memoBullet" aria-hidden>
                                      ·
                                    </span>
                                    <span>{renderWithMonoNumbers(String(note))}</span>
                                  </li>
                                ))}
                              </ul>
                            )}
                            {sigPreview && (
                              <pre className="mt-2 max-h-48 overflow-auto rounded bg-oxford/[0.04] p-2 font-mono text-[11px] leading-snug text-oxford/85">
                                {sigPreview}
                                {sigPreview.length >= 6000 ? '\n…' : ''}
                              </pre>
                            )}
                          </div>
                        );
                      })()}
                      {structuredScoring && (
                        <>
                          <ScoreOverview scoring={structuredScoring} />
                          <div className="mt-3 space-y-3">
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
                      {hasScores && !structuredScoring && (
                        <div className="mt-2 border border-oxford/10 bg-oxford/[0.02] px-3 py-3">
                          <p className="type-meta text-oxford/75">
                            Structured scoring is not present in this memo payload yet.
                          </p>
                        </div>
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
                </section>
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
                <section className="memoDocSection" aria-labelledby="memo-align">
                  <h2 className="memoDocSectionHead" id="memo-align">Thesis Alignment</h2>
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
                </section>
              );
            })()}

            {/* ── Reviewer Panel ── */}
            {(displayStartup.review?.reviews?.length ?? 0) > 0 && (() => {
              const reviews = displayStartup.review!.reviews!;
              const isContested = displayStartup.review?.reviewer_disagreement === true;
              const selected = reviews[selectedReviewerIdx] ?? reviews[0];
              return (
                <section className="memoDocSection" aria-labelledby="memo-reviewers">
                  <h2 className="memoDocSectionHead" id="memo-reviewers">
                    Reviewer Panel
                    {isContested && (
                      <span className="memoDocContestedKicker">Contested</span>
                    )}
                  </h2>
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
                </section>
              );
            })()}

            {/* ── Risk Factors ── */}
            {(() => {
              const combined = [
                ...(displayStartup.review?.diligence_red_flags ?? []),
                ...(displayStartup.review?.key_risks ?? []),
                ...(displayStartup.partner?.risks ?? []),
              ].map((r) => String(r ?? '').trim()).filter(Boolean);
              const seen = new Set<string>();
              const uniqueRisks = combined.filter((r) => {
                if (seen.has(r)) return false;
                seen.add(r);
                return true;
              });
              const mitigation = (displayStartup.review?.risk_mitigation ?? []).filter((s) => String(s ?? '').trim());
              if (!uniqueRisks.length && !mitigation.length) return null;
              return (
                <section className="memoDocSection" aria-labelledby="memo-risks">
                  <h2 className="memoDocSectionHead" id="memo-risks">Risk Factors</h2>
                  {uniqueRisks.length > 0 && (
                    <ul className="memoList">
                      {uniqueRisks.map((r, i) => (
                        <li key={i} className="memoListItem">
                          <span className="memoBullet">·</span>
                          <span>{renderWithMonoNumbers(normalizeListItemText(r))}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {mitigation.length > 0 && (
                    <div className="memoDocSubsection">
                      <p className="memoDocSubhead">Mitigation Checklist</p>
                      <ul className="memoList">
                        {mitigation.map((item, i) => (
                          <li key={i} className="memoListItem">
                            <span className="memoBullet">·</span>
                            <span>{renderWithMonoNumbers(normalizeListItemText(item))}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </section>
              );
            })()}

            {/* ── Next Steps ── */}
            {nextStepText && (
              <section className="memoDocSection" aria-labelledby="memo-next">
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
            {(displayStartup.scout.references?.length ?? 0) > 0 && (
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
                        {(displayStartup.scout.references ?? [])
                          .map((r) => String(r ?? '').trim())
                          .filter(Boolean)
                          .map((ref, i) => {
                            const href = memoReferenceHref(ref);
                            const label = memoReferenceLabel(ref);
                            return (
                              <li key={i} className="memoListItem">
                                <span className="memoBullet">·</span>
                                {href ? (
                                  <a className="memoLink" href={href} target="_blank" rel="noreferrer">{renderWithMonoNumbers(label)}</a>
                                ) : (
                                  <span>{renderWithMonoNumbers(label)}</span>
                                )}
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
