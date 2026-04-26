import { useCallback, forwardRef, useEffect, useImperativeHandle, useMemo, useState } from 'react';
import { fetchMemo, type MemoPartialPayload } from '../api/startups';
import { motion } from 'framer-motion';
import './InvestmentMemoContent.css';
import type { Startup, Review, SingleReview } from '../types/startup';
import {
  buildMemoPDF,
  buildIcMarkdown,
  icPackSafeBaseName,
  getPipelineReplaySteps,
  type PipelineReplayStep,
} from '../lib/memoIcPack';
import { memoReferenceHref, memoReferenceLabel } from '../lib/memoReferenceHref';
import {
  getScoreBand,
  DECISION_LABELS,
  SCORE_DIMENSIONS,
} from '../design-system/semantics';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';
const SCORE_DERIVATION_FALLBACK =
  'Score derived from multiple reviewer perspectives (optimistic, neutral, skeptical) and aggregated.';
const MEMO_POLL_INITIAL_MS = 2000;
const MEMO_POLL_MAX_MS = 15000;
const MEMO_POLL_MAX_ATTEMPTS = 60;

function computeOverallScore(review: Review | null | undefined): number | null {
  if (!review) return null;
  if (typeof review.overall_score === 'number') return review.overall_score;
  if (typeof review.aggregate_score === 'number') return review.aggregate_score;
  const scores = [
    review.market_score,
    review.product_score,
    review.technical_score,
    review.execution_score,
  ];
  if (!scores.every((s) => typeof s === 'number')) return null;
  const vals = scores as number[];
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

function scoreLabelFor(review: Review | null | undefined, dimension: string, score: number | null): string | null {
  const key = `${dimension}_label` as keyof Review;
  const fromReview = review?.[key];
  if (typeof fromReview === 'string' && fromReview.trim()) return fromReview;
  if (score == null) return null;
  return getScoreBand(score).label;
}

function mergeMemoPartial(base: Startup, partial: MemoPartialPayload | null): Startup {
  if (!partial) return base;
  return {
    ...base,
    scout: partial.scout ?? base.scout,
    review: partial.review ?? base.review,
    partner: partial.partner ?? base.partner,
  };
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

function normalizeMemoStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => normalizeListItemText(item))
    .filter((item) => item && !/^\[MISSING/i.test(item));
}

function uniqueMemoItems(items: string[]): string[] {
  return [...new Set(items.map((item) => normalizeListItemText(item)).filter(Boolean))];
}

function deriveWeaknessesFromReasoning(items: string[]): string[] {
  const caveatPattern = /\b(but|however|risk|risks|gap|gaps|weak|weakness|unknown|unproven|replication|constraint|depends|relies)\b/i;
  return uniqueMemoItems(
    items.flatMap((item) =>
      normalizeListItemText(item)
        .split(/;|\.\s+/)
        .map((part) => part.replace(/^(but|however)\s+/i, '').trim())
        .filter((part) => part.length > 12 && caveatPattern.test(part))
    )
  );
}

function partnerDecisionHeadline(startup: Startup): string {
  const rec = startup.partner?.recommendation;
  if (rec == null) return '—';
  const label = DECISION_LABELS[rec] ?? String(rec);
  return label.toUpperCase();
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
  const [activeDimensionId, setActiveDimensionId] = useState<string | null>(null);
  const [selectedReviewerIdx, setSelectedReviewerIdx] = useState(0);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [pipelineLogOpen, setPipelineLogOpen] = useState(false);
  const [scoreTooltipOpen, setScoreTooltipOpen] = useState(false);

  const [memoPartial, setMemoPartial] = useState<MemoPartialPayload | null>(null);
  const [memoPipeline, setMemoPipeline] = useState<'idle' | 'generating' | 'ready' | 'failed'>('idle');
  const [memoGateError, setMemoGateError] = useState<string | null>(null);

  const displayStartup = useMemo(
    () => (startup ? mergeMemoPartial(startup, memoPartial) : null),
    [startup, memoPartial]
  );

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
    setActiveDimensionId(null);
    setSelectedReviewerIdx(0);
    setSourcesOpen(false);
    setPipelineLogOpen(false);
    setScoreTooltipOpen(false);
  }, [startup?.id]);

  const scoreBlocks = useMemo(() => {
    if (!displayStartup?.review) return [];
    return SCORE_DIMENSIONS.map(({ id, name }) => {
      const score = displayStartup.review?.[id as keyof typeof displayStartup.review];
      const numeric = typeof score === 'number' ? score : null;
      const reasoning = displayStartup.review?.score_reasoning?.[id]?.trim() || '';
      const dimBase = id.replace('_score', '');
      const structuredReasoning = displayStartup.review?.[`${dimBase}_reasoning` as keyof Review];
      const normalizedReasoning = normalizeMemoStringList(structuredReasoning);
      const weaknessKey = `${dimBase}_weaknesses` as keyof Review & keyof SingleReview;
      const topLevelWeaknesses = normalizeMemoStringList(displayStartup.review?.[weaknessKey]);
      const reviewerWeaknesses = (displayStartup.review?.reviews ?? []).flatMap((review) =>
        normalizeMemoStringList(review[weaknessKey])
      );
      const caveatWeaknesses = deriveWeaknessesFromReasoning([
        ...normalizedReasoning,
        ...(reasoning ? [reasoning] : []),
      ]);
      const broadRiskWeaknesses = normalizeMemoStringList([
        ...(displayStartup.review?.key_risks ?? []),
        ...(displayStartup.review?.diligence_red_flags ?? []),
      ]);
      const confidence = displayStartup.review?.[`${dimBase}_confidence` as keyof Review];
      return {
        id,
        name,
        score: numeric,
        label: scoreLabelFor(displayStartup.review, id, numeric),
        reasoning,
        structuredReasoning: normalizedReasoning,
        weaknesses: uniqueMemoItems([
          ...topLevelWeaknesses,
          ...reviewerWeaknesses,
          ...caveatWeaknesses,
          ...(topLevelWeaknesses.length || reviewerWeaknesses.length || caveatWeaknesses.length
            ? []
            : broadRiskWeaknesses.slice(0, 2)),
        ]),
        confidence: typeof confidence === 'string' ? confidence : null,
      };
    });
  }, [displayStartup]);

  const overallScore = useMemo(() => computeOverallScore(displayStartup?.review), [displayStartup?.review]);
  const overallLabel = useMemo(() => {
    if (!displayStartup?.review) return null;
    if (typeof displayStartup.review.overall_label === 'string' && displayStartup.review.overall_label.trim()) {
      return displayStartup.review.overall_label.trim();
    }
    return overallScore != null ? getScoreBand(overallScore).label : null;
  }, [displayStartup?.review, overallScore]);
  const scoreSourceText = useMemo(() => {
    const raw = displayStartup?.review?.score_source;
    return typeof raw === 'string' && raw.trim() ? raw.trim() : SCORE_DERIVATION_FALLBACK;
  }, [displayStartup?.review?.score_source]);
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
            <div className="memoEmptyHint">Select a company to view the investment memo.</div>
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
                <p className="memoGateDetail">{memoGateError}</p>
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
                  <p className="memoDocTagline">{displayStartup.scout.one_line}</p>
                )}
                <p className="memoMeta">{sectorCategory}</p>
              </div>
            </div>

            <div className="memoDocDivider" aria-hidden />

            {/* ── Investment Judgment ── */}
            {showJudgment && (() => {
              const paras = reasoningParagraphs.filter((p) => String(p ?? '').trim());
              if (!paras.length) return null;
              return (
                <section className="memoDocSection" aria-labelledby="memo-judgment">
                  <h2 className="memoDocSectionHead" id="memo-judgment">Investment Judgment</h2>
                  {decisionBadgeVariant && (
                    <div className="memoDocJudgmentTop">
                      {showLookupBadge && <span className="memoDocLookupBadge">ON-DEMAND LOOKUP</span>}
                      <p className={`memoDocRecommendation memoDocRecommendation--${decisionBadgeVariant.toLowerCase()}`}>
                        {decisionHeadline}.
                      </p>
                      <div className="memoDocStatusLine">
                        {displayStartup.partner?.confidence != null && (
                          <p className="memoDocConfidence">
                            {Math.round(displayStartup.partner.confidence * 100)}% confidence
                          </p>
                        )}
                        {showEscalationBadge && (
                          <p className="memoDocEscalation">Escalation required</p>
                        )}
                      </div>
                    </div>
                  )}
                  {paras.map((p, i) => <p key={i} className="memoDocProse">{p}</p>)}
                </section>
              );
            })()}

            {/* ── Executive Summary ── */}
            {showJudgment && (() => {
              const summary = displayStartup.review?.overall_summary?.trim();
              if (!summary) return null;
              return (
                <section className="memoDocSection" aria-labelledby="memo-exec-summary">
                  <h2 className="memoDocSectionHead" id="memo-exec-summary">Executive Summary</h2>
                  {summary && <p className="memoDocProse">{summary}</p>}
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
                        <dd className="memoDocDD">{r.val}</dd>
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
                        <dd className="memoDocDD">{r.val}</dd>
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
                  {thesis && <p className="memoDocProse memoDocThesis">{thesis}</p>}
                  {assumptions && assumptions.length > 0 && (
                    <div className="memoDocSubsection">
                      <p className="memoDocSubhead">Key Assumptions</p>
                      <ul className="memoList">
                        {assumptions.map((item, i) => (
                          <li key={i} className="memoListItem">
                            <span className="memoBullet" aria-hidden>·</span>
                            <span>{normalizeListItemText(item)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {biggest && (
                    <div className="memoDocSubsection">
                      <p className="memoDocSubhead">Biggest Unknown</p>
                      <p className="memoDocProse">{biggest}</p>
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
              const hasScores = displayStartup.review && scoreBlocks.length > 0;
              if (!hasScores && !teamItems.length && !compItems.length && !bizItems.length) return null;
              return (
                <section className="memoDocSection" aria-labelledby="memo-assessment">
                  <h2 className="memoDocSectionHead" id="memo-assessment">Assessment</h2>

                  {hasScores && (
                    <div className="memoDocScoreScope">
                      <div className="memoDocOverallScoreRow">
                        <div className="memoDocOverallScoreMain">
                          <p className="memoDocOverallScoreValue">
                            {overallScore != null ? overallScore.toFixed(1) : '—'}
                          </p>
                          <p className="memoDocOverallScoreLabel">
                            {overallLabel ?? 'Unscored'}
                          </p>
                        </div>
                        <button
                          type="button"
                          className="memoDocTooltipBtn"
                          aria-label="How this score is derived"
                          aria-expanded={scoreTooltipOpen}
                          aria-controls={`${contentKey}-score-tooltip`}
                          onClick={() => setScoreTooltipOpen((v) => !v)}
                        >
                          Method
                        </button>
                      </div>
                      {scoreTooltipOpen && (
                        <p id={`${contentKey}-score-tooltip`} className="memoDocTooltipPanel" role="note">
                          {scoreSourceText}
                        </p>
                      )}
                      <div className="memoDocScoreLegend" aria-label="Score scale">
                        <span><strong>1–3</strong> Weak</span>
                        <span><strong>4–5</strong> Concerning</span>
                        <span><strong>6–7</strong> Promising</span>
                        <span><strong>8–10</strong> Strong</span>
                      </div>
                      <div className="memoDocScoreStack">
                        {scoreBlocks.map((b) => {
                          const expanded = activeDimensionId === b.id;
                          const panelId = `${contentKey}-${b.id}-details`;
                          const reasoningItems = b.structuredReasoning.length
                            ? b.structuredReasoning
                            : [b.reasoning || (b.score != null ? getScoreBand(b.score).meaning : 'No rationale available.')];
                          const weaknessItems = b.weaknesses.length ? b.weaknesses : null;
                          return (
                            <article key={b.id} className="memoDocScorePanel">
                              <button
                                type="button"
                                className="memoDocScorePanelToggle"
                                onClick={() => setActiveDimensionId((prev) => (prev === b.id ? null : b.id))}
                                aria-expanded={expanded}
                                aria-controls={panelId}
                              >
                                <span className="memoDocScorePanelTitle">{b.name}</span>
                                <span className="memoDocScorePanelValue" aria-label={`${b.name} score`}>
                                  <span className="memoDocScorePanelNumber">
                                    {b.score != null ? b.score.toFixed(1) : '—'}
                                  </span>
                                  <span className="memoDocScorePanelBand">
                                    {b.score != null ? b.label ?? getScoreBand(b.score).label : 'Unscored'}
                                  </span>
                                </span>
                                <span className="memoDocScorePanelMeta">
                                  <span>{(b.confidence ?? 'medium').toUpperCase()} confidence</span>
                                  <span className="memoDocScorePanelToggleGlyph" aria-hidden>
                                    {expanded ? '−' : '+'}
                                  </span>
                                </span>
                              </button>
                              {expanded && (
                                <div
                                  id={panelId}
                                  className="memoDocExpandedBody"
                                  role="region"
                                >
                                  <p className="memoDocExpandedLabel">Reasoning</p>
                                  <ul className="memoList">
                                    {reasoningItems.map((item, i) => (
                                      <li key={i} className="memoListItem">
                                        <span className="memoBullet" aria-hidden>·</span>
                                        <span>{normalizeListItemText(item)}</span>
                                      </li>
                                    ))}
                                  </ul>
                                  {weaknessItems && (
                                    <>
                                      <p className="memoDocExpandedLabel memoDocExpandedLabel--weaknesses">Weaknesses / risks</p>
                                      <ul className="memoList">
                                        {weaknessItems.map((item, i) => (
                                          <li key={i} className="memoListItem">
                                            <span className="memoBullet" aria-hidden>·</span>
                                            <span>{normalizeListItemText(item)}</span>
                                          </li>
                                        ))}
                                      </ul>
                                    </>
                                  )}
                                </div>
                              )}
                            </article>
                          );
                        })}
                      </div>
                      {(displayStartup.review?.improvement_to_9?.length ?? 0) > 0 && (
                        <div className="memoDocSubsection">
                          <p className="memoDocSubhead">What would make this a 9?</p>
                          <ul className="memoList">
                            {(displayStartup.review?.improvement_to_9 ?? []).map((item, i) => (
                              <li key={i} className="memoListItem">
                                <span className="memoBullet" aria-hidden>·</span>
                                <span>{normalizeListItemText(item)}</span>
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
                            <span>{normalizeListItemText(item)}</span>
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
                            <span>{normalizeListItemText(item)}</span>
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
                            <span>{normalizeListItemText(item)}</span>
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
                          <p className="memoDocAlignTileVal">{t.val}</p>
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
                                  <span>{normalizeListItemText(item)}</span>
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
                                  <span>{normalizeListItemText(item)}</span>
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
                          <span className="memoDocReviewerRowScores">{scoreRow}</span>
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
                      <p className="memoDocReviewerDetailText">{selected.overall_summary}</p>
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
                          <span>{normalizeListItemText(r)}</span>
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
                            <span>{normalizeListItemText(item)}</span>
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
                        <span className="memoBullet">{idx + 1}.</span>
                        <span>{normalizeListItemText(item)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="memoDocProse">{nextStepText}</p>
                )}
              </section>
            )}

            {/* ── Decision Context (LLM trigger) ── */}
            {displayStartup.partner?.llm_fallback_reason && (
              <div className="memoDocSection">
                <dl className="memoDocDL">
                  <div className="memoDocDLRow">
                    <dt className="memoDocDT">Decision context</dt>
                    <dd className="memoDocDD">{displayStartup.partner.llm_fallback_reason}</dd>
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
                                  <a className="memoLink" href={href} target="_blank" rel="noreferrer">{label}</a>
                                ) : (
                                  <span>{label}</span>
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
                      {pipelineReplaySummary}
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
                          <p className="memoReplayWhen">{step.atDisplay}</p>
                          <p className="memoReplayDetail">{step.detail}</p>
                        </li>
                      ))}
                    </ol>
                  </div>
                </motion.div>
              </section>
            )}

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
                    Generating full investment memo…
                  </motion.p>
                  <p className="memoGateDetail">
                    This page updates automatically when the formatted memo is persisted.
                  </p>
                </div>
              </section>
            )}

          </motion.div>
        </div>
      )}
    </div>
  );
});

export default InvestmentMemoContent;
