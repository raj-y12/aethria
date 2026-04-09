import { useCallback, forwardRef, useEffect, useImperativeHandle, useMemo, useState } from 'react';
import { fetchMemo, type MemoPartialPayload } from '../api/startups';
import { motion } from 'framer-motion';
import type { Startup, Review } from '../types/startup';
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
  QUALITY_LABELS,
  SCORE_DIMENSIONS,
  getReviewerQualityBand,
} from '../design-system/semantics';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';
import DecisionBadge from './DecisionBadge';
import VerdictBandBadge from './VerdictBandBadge';

function buildScoreJustification(startup: Startup): string | null {
  const r = startup.review;
  if (!r) return null;
  const scores: number[] = [];
  if (r.market_score != null) scores.push(r.market_score);
  if (r.product_score != null) scores.push(r.product_score);
  if (r.technical_score != null) scores.push(r.technical_score);
  if (r.execution_score != null) scores.push(r.execution_score);
  if (scores.length === 0) return null;
  const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
  const hasLow = scores.some((s) => s <= 5);
  const hasHigh = scores.some((s) => s >= 7);
  if (hasLow && hasHigh)
    return `Scores reflect mixed strength; execution and defensibility concerns offset market potential.`;
  if (hasLow) return `Scores reflect moderate opportunity offset by high execution risk and unproven defensibility.`;
  if (hasHigh) return `Scores support investment-grade opportunity across key dimensions.`;
  return `Average ${avg.toFixed(1)}/10. Scores reflect promising but incomplete validation.`;
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
  /** When true, used in side panel (no outer padding; panel provides it). */
  embedded?: boolean;
  /** After persisted memo becomes ready; use to refetch startup detail. */
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

/** Partner economic headline: ADVANCE / PASS / HOLD (display-only; stored codes unchanged). */
function partnerDecisionHeadline(startup: Startup): string {
  const d = startup.partner?.decision;
  if (d == null) return '—';
  const label = DECISION_LABELS[d] ?? String(d);
  return label.toUpperCase();
}

function toJudgmentReasoning(startup: Startup): string[] {
  const rationale = startup.partner?.rationale;
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

function getPartnerEconomicBadgeVariant(startup: Startup): 'YES' | 'NO' | 'MAYBE' | null {
  const d = startup.partner?.decision;
  if (d == null) return null;
  if (d === 'YES') return 'YES';
  if (d === 'NO' || d === 'PASS') return 'NO';
  return 'MAYBE';
}

function formatSectorAndCategory(startup: Startup): string {
  const sector = startup.scout.sector?.trim() || '—';
  const category = startup.scout.funding_stage?.trim() || startup.scout.scout_type?.trim() || '';
  return category ? `${sector} · ${category}` : sector;
}

const actionBtnCls = 'memoAction';

function pipelineReplayOneLiner(steps: PipelineReplayStep[]): string {
  if (!steps.length) return '';
  const flow = steps.map((s) => s.label).join(' → ');
  const last = [...steps].reverse().find((s) => s.atDisplay && s.atDisplay !== '—');
  const tail = last?.atDisplay;
  return tail ? `${flow} · ${tail}` : flow;
}

/**
 * Memo body only. Used in full-screen modal and in the right-side panel.
 * When embedded, ref can be used to call downloadPDF() from the parent (e.g. panel header).
 */
const InvestmentMemoContent = forwardRef<InvestmentMemoContentHandle, InvestmentMemoContentProps>(function InvestmentMemoContent(
  { startup, onClose, embedded = false, onMemoPipelineReady },
  ref
) {
  const reduceMotion = usePrefersReducedMotion();
  const wrapperCls = embedded ? 'memoPanel memoPanel--embedded' : 'memoPanel';
  const [selectedDimensionIdx, setSelectedDimensionIdx] = useState(0);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [pipelineLogOpen, setPipelineLogOpen] = useState(false);

  const [memoPartial, setMemoPartial] = useState<MemoPartialPayload | null>(null);
  const [memoPipeline, setMemoPipeline] = useState<'idle' | 'generating' | 'ready' | 'failed'>('idle');
  const [memoGateError, setMemoGateError] = useState<string | null>(null);

  const displayStartup = useMemo(
    () => (startup ? mergeMemoPartial(startup, memoPartial) : null),
    [startup, memoPartial]
  );

  const handleDownloadPDF = useCallback(() => {
    if (!displayStartup) return;
    const doc = buildMemoPDF(displayStartup);
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
    setMemoPipeline('idle');
    setMemoGateError(null);
    let cancelled = false;
    let t: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      try {
        const res = await fetchMemo(startup.id);
        if (cancelled) return;
        if (!res) {
          t = setTimeout(poll, 2000);
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
        t = setTimeout(poll, 2000);
      } catch {
        if (!cancelled) t = setTimeout(poll, 2000);
      }
    };
    void poll();
    return () => {
      cancelled = true;
      if (t) clearTimeout(t);
    };
  }, [startup?.id, onMemoPipelineReady]);

  const showJudgment = !!displayStartup?.review && !!displayStartup?.partner?.decision;
  const decisionHeadline = displayStartup && showJudgment ? partnerDecisionHeadline(displayStartup) : '';
  const dossierQualityBand = useMemo(
    () => (displayStartup && showJudgment ? getReviewerQualityBand(displayStartup.review) : null),
    [displayStartup, showJudgment]
  );
  const decisionBadgeVariant = useMemo(
    () => (displayStartup && showJudgment ? getPartnerEconomicBadgeVariant(displayStartup) : null),
    [displayStartup, showJudgment]
  );
  const showEscalationBadge = !!(displayStartup?.partner?.human_review_required && decisionBadgeVariant);
  const reasoningParagraphs = useMemo(
    () => (displayStartup && showJudgment ? toJudgmentReasoning(displayStartup) : []),
    [displayStartup, showJudgment]
  );

  useEffect(() => {
    setSelectedDimensionIdx(0);
    setSourcesOpen(false);
    setPipelineLogOpen(false);
  }, [startup?.id]);

  const scoreBlocks = useMemo(() => {
    if (!displayStartup?.review) return [];
    return SCORE_DIMENSIONS.map(({ id, name }) => {
      const score = displayStartup.review?.[id as keyof typeof displayStartup.review];
      const numeric = typeof score === 'number' ? score : null;
      const reasoning = displayStartup.review?.score_reasoning?.[id]?.trim() || '';
      return { id, name, score: numeric, reasoning };
    });
  }, [displayStartup]);

  const scoresSummary = useMemo(() => {
    if (!displayStartup?.review) return null;
    return buildScoreJustification(displayStartup);
  }, [displayStartup]);
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

  return (
    <div className={wrapperCls}>
      <style>{`
        .memoPanel{
          width: 60%;
          min-width: 0;
          flex: 0 0 60%;
          background: var(--color-paper);
          min-height: 0;
          height: 100%;
          overflow: hidden;
          display: flex;
          flex-direction: column;
        }
        .memoPanel--embedded{
          width: 100%;
          min-width: 0;
          flex: 1 1 auto;
          /* Let the parent panel own scrolling in embedded mode. */
          height: auto;
          overflow: visible;
        }
        .memoScroll{
          flex: 1 1 auto;
          min-height: 0;
          overflow-y: auto;
          overflow-x: hidden;
          padding-left: clamp(20px, 4vw, 48px);
          padding-right: clamp(20px, 4vw, 48px);
          padding-top: clamp(24px, 3vw, 40px);
          padding-bottom: clamp(28px, 4vw, 48px);
          color: #002147;
          background: var(--color-paper);
        }
        .memoPanel--embedded .memoScroll{
          /* PanelShell already applies content padding; avoid double-padding in embedded mode. */
          padding-left: 0px;
          padding-right: 0px;
          padding-top: 0px;
          padding-bottom: 0px;
          /* PanelShell already scrolls in embedded mode; avoid nested scrollbars. */
          overflow: visible;
          flex: 0 0 auto;
          min-height: auto;
        }
        .memoHeaderActions{
          display: flex;
          flex-wrap: wrap;
          justify-content: flex-end;
          align-items: center;
          gap: 10px 18px;
          margin-top: 0;
          margin-bottom: clamp(16px, 2.5vw, 22px);
        }
        .memoAction{
          appearance: none;
          border: none;
          background: transparent;
          padding: 4px 0;
          cursor: pointer;
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 12px;
          font-variant-caps: all-small-caps;
          letter-spacing: 0.12em;
          color: rgba(0,33,71,0.5);
          transition: color 150ms ease;
        }
        .memoAction:hover{ color: #002147; }
        .memoCompany{
          font-family: "Geist Sans", system-ui, sans-serif;
          font-weight: 600;
          font-size: clamp(1.375rem, 2.25vw + 0.35rem, 1.875rem);
          line-height: 1.22;
          letter-spacing: -0.02em;
          margin: 0;
          max-width: 40rem;
          color: #002147;
        }
        .memoHeaderDivider{
          margin-top: 14px;
          margin-bottom: clamp(22px, 3vw, 30px);
        }
        .memoBody{
          max-width: 42rem;
        }
        .memoPanel--embedded .memoBody{
          max-width: none;
          width: 100%;
        }
        .memoPanel--embedded .memoCompany{
          max-width: none;
        }
        .memoBody > section + section{
          margin-top: clamp(2rem, 4vw, 2.75rem);
        }
        .memoLeadSection{
          padding-top: 12px;
        }
        .memoMeta{
          margin-top: 8px;
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 12px;
          letter-spacing: 0.12em;
          color: rgba(0,33,71,0.48);
          text-transform: uppercase;
        }
        .memoDivider{
          height: 1px;
          width: 100%;
          background: rgba(0,33,71,0.08);
        }
        .memoDivider.memoHeaderDivider{
          background: linear-gradient(
            90deg,
            rgba(184, 151, 106, 0.45) 0%,
            rgba(0, 33, 71, 0.09) 32%,
            rgba(0, 33, 71, 0.07) 100%
          );
        }
        .memoLabel{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 12px;
          text-transform: uppercase;
          letter-spacing: 0.12em;
          line-height: 1.45;
          color: rgba(0,33,71,0.58);
          margin: 0 0 12px 0;
          padding-bottom: 8px;
          border-bottom: 1px solid rgba(0,33,71,0.07);
        }
        .memoLabel--thesis{
          font-size: 12px;
          font-weight: 400;
        }
        .memoJudgmentHead{
          margin: 0 0 12px 0;
        }
        .memoJudgmentHead--solo{
          margin-bottom: 0;
        }
        .memoVerdict{
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-weight: 600;
          font-size: clamp(1.5rem, 4.5vw, 2rem);
          line-height: 1.18;
          letter-spacing: -0.02em;
          text-transform: uppercase;
          margin: 0;
          padding-top: 0px;
          padding-bottom: 0px;
          color: #002147;
        }
        .memoJudgmentHead--solo .memoVerdict{
          margin: 0 0 12px 0;
        }
        .memoDossierRead{
          margin-top: 12px;
          padding-top: 12px;
          border-top: none;
        }
        .memoDossierReadKicker{
          display: block;
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 12px;
          font-weight: 400;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: rgba(0,33,71,0.42);
          margin: 0 0 8px 0;
        }
        .memoDossierReadLine{
          display: flex;
          flex-wrap: wrap;
          align-items: baseline;
          gap: 0 6px;
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 13px;
          line-height: 1.45;
          color: rgba(0,33,71,0.62);
          margin: 0;
        }
        .memoDossierReadBand{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 12px;
          font-weight: 400;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: rgba(0,33,71,0.72);
        }
        .memoDossierReadDot{
          color: rgba(0,33,71,0.28);
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 12px;
        }
        .memoDossierReadPhrase{
          font-weight: 400;
          color: rgba(0,33,71,0.58);
        }
        .memoReasoning{
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-weight: 400;
          font-size: 14px;
          line-height: 1.65;
          color: rgba(0,33,71,0.72);
        }
        .memoReasoning p{ margin: 0; }
        .memoReasoning p + p{ margin-top: 0.6rem; }
        .memoScoresRow{
          display: grid;
          grid-template-columns: repeat(5, minmax(0, 1fr));
          gap: clamp(12px, 2.5vw, 20px);
        }
        .memoScoreCol{
          appearance: none;
          border: none;
          background: transparent;
          padding: 0;
          text-align: center;
          cursor: pointer;
          min-width: 0;
        }
        .memoScoreCol:focus{ outline: none; }
        .memoScoreCol:focus-visible{
          outline: 2px solid rgba(0,33,71,0.25);
          outline-offset: 4px;
        }
        .memoScoreName{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 12px;
          font-variant-caps: all-small-caps;
          letter-spacing: 0.1em;
          color: rgba(0,33,71,0.52);
          margin: 0 0 10px 0;
        }
        .memoScoreValue{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-weight: 700;
          font-size: clamp(1.35rem, 3.5vw, 1.75rem);
          line-height: 1.35;
          margin: 0 0 8px 0;
          color: #002147;
        }
        .memoScoreValueRow{
          display: flex;
          align-items: baseline;
          justify-content: center;
          gap: 0;
        }
        .memoScoreBandLabel{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 12px;
          letter-spacing: 0.08em;
          color: rgba(0,33,71,0.4);
        }
        .memoScoreLegend{
          margin-top: 8px;
          margin-bottom: 16px;
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 10px;
          line-height: 1.55;
          letter-spacing: 0.06em;
          color: rgba(0,33,71,0.4);
        }
        .memoScoreUnderline{
          height: 2px;
          width: 100%;
          background: rgba(0,33,71,0.15);
          margin-top: 8px;
        }
        .memoScoreWhy{
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 12px;
          line-height: 1.6;
          color: rgba(0,33,71,0.6);
          margin: 0;
          overflow: hidden;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
        }
        .memoDimensionPanel{
          margin-top: 12px;
          padding: 0;
          background: transparent;
          border: none;
        }
        .memoDimensionPanelName{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 13px;
          font-variant-caps: all-small-caps;
          letter-spacing: 0.12em;
          color: rgba(0,33,71,0.48);
          margin: 0 0 10px 0;
        }
        .memoDimensionPanelText{
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 14px;
          line-height: 1.65;
          color: rgba(0,33,71,0.76);
          margin: 0;
          white-space: normal;
        }
        .memoList{
          margin: 0;
          padding: 0;
          list-style: none;
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 14px;
          line-height: 1.6;
          color: rgba(0,33,71,0.78);
        }
        .memoListItem{
          display: flex;
          gap: 10px;
        }
        .memoListItem + .memoListItem{ margin-top: 0.5rem; }
        .memoBullet{
          flex-shrink: 0;
          color: rgba(0,33,71,0.38);
          font-weight: 500;
        }
        .memoLink{
          color: #002147;
          text-decoration: none;
          border-bottom: 1px solid rgba(0,33,71,0.22);
          transition: border-color 120ms ease, color 120ms ease;
        }
        .memoLink:hover{
          border-bottom-color: rgba(0,33,71,0.45);
          color: rgba(0,33,71,0.88);
        }
        .memoSummaryCallout{
          background: transparent;
          padding: 0;
          margin: 0;
          border: none;
        }
        .memoSourcesToggle{
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: space-between;
          appearance: none;
          border: none;
          background: transparent;
          padding: 0;
          cursor: pointer;
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 12px;
          text-transform: uppercase;
          letter-spacing: 0.14em;
          color: rgba(0,33,71,0.5);
          padding-bottom: 8px;
          border-bottom: none;
        }
        .memoSourcesPlus{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 12px;
          color: rgba(0,33,71,0.5);
          line-height: 1.5;
        }
        .memoSourcesBody{
          padding-top: 14px;
        }
        .memoScoresSummary{
          margin: 14px 0 0 0;
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-style: italic;
          font-size: 13px;
          line-height: 1.6;
          color: rgba(0,33,71,0.5);
        }
        .memoOverviewRow{
          display: grid;
          grid-template-columns: minmax(7.25rem, 8.75rem) minmax(0, 1fr);
          column-gap: clamp(16px, 3vw, 28px);
          row-gap: 4px;
          align-items: start;
        }
        .memoOverviewRow + .memoOverviewRow{ margin-top: 1rem; }
        .memoOverviewKey{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 13px;
          font-variant-caps: all-small-caps;
          letter-spacing: 0.1em;
          color: rgba(0,33,71,0.52);
          margin: 0;
          padding-top: 2px;
        }
        .memoOverviewVal{
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 14px;
          line-height: 1.65;
          color: rgba(0,33,71,0.76);
          margin: 0;
        }
        .memoEmpty{
          height: 100%;
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--color-paper);
        }
        .memoEmptyInner{
          text-align: center;
          padding: 48px;
        }
        .memoEmptyWordmark{
          font-family: "Libre Baskerville", Georgia, serif;
          font-weight: 400;
          font-size: 24px;
          line-height: 1.4;
          color: rgba(0,33,71,0.25);
          margin: 0;
        }
        .memoEmptyHint{
          margin-top: 12px;
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 13px;
          line-height: 1.6;
          color: rgba(0,33,71,0.2);
        }

        .memoGateStrip{
          position: sticky;
          top: 0;
          z-index: 30;
          margin: 0 0 10px 0;
          padding: 8px 0 14px 0;
          background: var(--color-paper);
          border-bottom: 1px solid rgba(0,33,71,0.08);
          pointer-events: none;
        }
        .memoGateStripInner{
          pointer-events: auto;
          max-width: 100%;
        }
        .memoGateTitle{
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 14px;
          line-height: 1.5;
          color: rgba(0,33,71,0.78);
          margin: 8px 0 0 0;
        }
        .memoGateDetail{
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 12px;
          line-height: 1.45;
          color: rgba(0,33,71,0.48);
          margin: 5px 0 0 0;
          max-width: 38rem;
        }
        .memoGateStrip--error .memoGateTitle{
          color: rgba(125, 43, 58, 0.95);
        }
        .memoGateStrip--error .memoPipelineKicker{
          color: rgba(125, 43, 58, 0.72);
        }

        .memoPipelineSection{
          margin: 1.75rem 0 0 0;
        }
        .memoPipelineToggle{
          width: 100%;
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
          appearance: none;
          border: none;
          background: transparent;
          padding: 0 0 10px 0;
          cursor: pointer;
          text-align: left;
          border-bottom: 1px solid rgba(0,33,71,0.06);
        }
        .memoPipelineToggleTitle{
          display: flex;
          flex-direction: column;
          gap: 4px;
          min-width: 0;
          flex: 1;
        }
        .memoPipelineKicker{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 12px;
          font-weight: 400;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: rgba(0,33,71,0.42);
          margin: 0;
        }
        .memoPipelineOneLiner{
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 13px;
          line-height: 1.45;
          color: rgba(0,33,71,0.52);
          margin: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .memoPipelinePlus{
          flex-shrink: 0;
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 12px;
          color: rgba(0,33,71,0.45);
          line-height: 1.5;
          padding-top: 2px;
        }
        .memoReplayList{
          list-style: none;
          margin: 0;
          padding: 4px 0 2px 0;
        }
        .memoReplayItem{
          padding: 12px 0;
          border-top: 1px solid rgba(0,33,71,0.06);
        }
        .memoReplayItem:first-child{
          border-top: none;
          padding-top: 8px;
        }
        .memoReplayKicker{
          display: flex;
          flex-wrap: wrap;
          align-items: baseline;
          gap: 6px 10px;
          margin: 0 0 4px 0;
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 13px;
          font-weight: 600;
          line-height: 1.35;
          color: rgba(0,33,71,0.78);
        }
        .memoReplayBadge{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 12px;
          font-weight: 400;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: rgba(0,33,71,0.42);
        }
        .memoReplayBadge--pending{
          color: rgba(0,33,71,0.32);
        }
        .memoReplayWhen{
          font-family: "Space Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
          font-size: 12px;
          letter-spacing: 0.08em;
          color: rgba(0,33,71,0.4);
          margin: 0 0 6px 0;
        }
        .memoReplayDetail{
          font-family: "Geist Sans", system-ui, -apple-system, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
          font-size: 13px;
          line-height: 1.55;
          color: rgba(0,33,71,0.62);
          margin: 0;
        }

        .memoList--afterKey{
          margin-top: 6px;
        }
        .memoStackedVals .memoOverviewVal + .memoOverviewVal{
          margin-top: 0.5rem;
        }
        .memoThesisScoreBlock{
          margin: 0;
          padding: 0;
          width: 100%;
          box-sizing: border-box;
        }
        .memoThesisScoresRow{
          display: grid;
          width: 100%;
          align-items: stretch;
          gap: clamp(12px, 2.5vw, 20px);
          padding: 0;
          box-sizing: border-box;
        }
        .memoThesisScoresRow--n1{
          grid-template-columns: minmax(0, 1fr);
          justify-items: start;
        }
        .memoThesisScoresRow--n2{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .memoThesisScoresRow--n3{
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        .memoThesisScoresRow--n1 .memoThesisScoreTile{
          width: 100%;
          max-width: 11rem;
        }
        .memoThesisScoreTile{
          display: flex;
          flex-direction: column;
          align-items: center;
          min-width: 0;
          width: 100%;
          text-align: center;
          padding: 0;
          box-sizing: border-box;
        }
        .memoThesisScoreTile .memoScoreName{
          margin: 0 0 8px 0;
          width: 100%;
          padding: 0;
          box-sizing: border-box;
          font-size: 12px;
          font-weight: 400;
        }
        .memoThesisScoreTile .memoScoreValueRow{
          justify-content: center;
          width: 100%;
          flex: 0 0 auto;
        }
        .memoThesisScoreTile .memoScoreValue{
          margin: 0 0 10px 0;
          opacity: 1;
          font-size: clamp(1.35rem, 3.5vw, 1.75rem);
          font-weight: 700;
          line-height: 1.35;
        }
        .memoThesisScoreTile .memoScoreUnderline{
          margin-top: auto;
          align-self: stretch;
        }
        .memoScoreColSpacer{
          height: 2px;
          margin-top: 8px;
        }
        .memoGeneratingSection{
          margin-top: 2.25rem;
        }
        .memoSummaryCallout.memoGenCallout{
          background: var(--color-register-tint);
          padding: 14px 0 16px 0;
          border: none;
        }
        .memoGenCallout .memoPipelineKicker{
          margin-bottom: 8px;
        }
        .memoGenCallout .memoGateTitle{
          margin-top: 0;
        }
        .memoGenCallout .memoGateDetail{
          margin-bottom: 0;
        }
        @media (max-width: 1100px){
          .memoPanel{ width: 100%; flex-basis: auto; }
          .memoScoresRow{ grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        @media (max-width: 640px){
          .memoOverviewRow{
            grid-template-columns: 1fr;
            row-gap: 6px;
          }
          .memoOverviewKey{
            padding-top: 0;
          }
        }
      `}</style>

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
              <button type="button" onClick={handleDownloadPDF} className={actionBtnCls}>
                IC PACK (PDF)
              </button>
              <button type="button" onClick={handleDownloadMarkdown} className={actionBtnCls}>
                IC PACK (MD)
              </button>
              <button type="button" onClick={onClose} className={actionBtnCls}>
                CLOSE
              </button>
            </div>
          )}
          {memoPipeline === 'failed' && (
            <div className="memoGateStrip memoGateStrip--error">
                <motion.div
                  className="memoGateStripInner"
                  initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={transitionOrReduced(reduceMotion, {
                    duration: 0.28,
                    ease: [0.16, 1, 0.3, 1],
                  })}
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
            initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={transitionOrReduced(reduceMotion, {
              duration: 0.28,
              ease: [0.16, 1, 0.3, 1],
            })}
          >
            {/* Header block */}
            <h1 id="memo-title" className="memoCompany">
              {companyName || '—'}
            </h1>
            <div className="memoMeta">{sectorCategory}</div>
            <div className="memoDivider memoHeaderDivider" aria-hidden />

            {/* Investment Judgment block */}
            {showJudgment && (
              <section>
                  <p className="memoLabel">INVESTMENT JUDGMENT</p>
                  <div className="mb-4 flex flex-wrap items-center gap-2">
                    {dossierQualityBand ? <VerdictBandBadge band={dossierQualityBand} /> : null}
                    {decisionBadgeVariant ? <DecisionBadge variant={decisionBadgeVariant} /> : null}
                    {showEscalationBadge ? <DecisionBadge variant="escalation" /> : null}
                  </div>
                  <div
                    className={`memoJudgmentHead${dossierQualityBand == null ? ' memoJudgmentHead--solo' : ''}`}
                  >
                    <p className="memoVerdict">{decisionHeadline}</p>
                    {dossierQualityBand != null ? (
                      <div className="memoDossierRead">
                        <span className="memoDossierReadKicker">Dossier read</span>
                        <p className="memoDossierReadLine">
                          <span className="memoDossierReadBand">{dossierQualityBand}</span>
                          <span className="memoDossierReadDot" aria-hidden>
                            ·
                          </span>
                          <span className="memoDossierReadPhrase">
                            {QUALITY_LABELS[dossierQualityBand] ?? dossierQualityBand}
                          </span>
                        </p>
                      </div>
                    ) : null}
                  </div>
                  <div className="memoReasoning">
                    {reasoningParagraphs.filter((p) => String(p ?? '').trim().length > 0).map((p, i) => (
                      <p key={i}>{p}</p>
                    ))}
                  </div>
                </section>
            )}

            {displayStartup.review?.overall_summary && (
                <section>
                  <p className="memoLabel">SUMMARY</p>
                  <div className="memoSummaryCallout">
                    <p className="memoOverviewVal">{displayStartup.review.overall_summary}</p>
                  </div>
                </section>
            )}

            {/* Dimension Scores block */}
            <section className={showJudgment ? undefined : 'memoLeadSection'}>
              <p className="memoLabel">DIMENSION SCORES</p>
              <p className="memoScoreLegend">1-3: WEAK · 4-5: CONCERNING · 6-7: PROMISING · 8-10: STRONG</p>
              <div className="memoScoresRow">
                {scoreBlocks.map((b, idx) => {
                  const isSelected = idx === selectedDimensionIdx;
                  const displayScore = b.score != null ? `${Math.round(b.score)}/10` : '—';
                  return (
                    <button
                      key={b.id}
                      type="button"
                      className="memoScoreCol"
                      onClick={() => setSelectedDimensionIdx(idx)}
                      aria-pressed={isSelected}
                    >
                      <p className="memoScoreName">{b.name}</p>
                      <div className="memoScoreValueRow">
                        <p
                          className="memoScoreValue"
                          style={{
                            opacity: isSelected ? 1 : 0.5,
                            transition: reduceMotion ? 'opacity 0ms' : 'opacity 180ms ease',
                          }}
                        >
                          {displayScore}
                        </p>
                      </div>
                      {isSelected ? <div className="memoScoreUnderline" /> : <div className="memoScoreColSpacer" aria-hidden />}
                    </button>
                  );
                })}
              </div>

              {scoreBlocks.length > 0 && (
                <div className="memoDimensionPanel">
                  <motion.div
                    key={`${contentKey}:${selectedDimensionIdx}`}
                    initial={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={transitionOrReduced(reduceMotion, {
                      duration: 0.18,
                      ease: [0.16, 1, 0.3, 1],
                    })}
                  >
                    <p className="memoDimensionPanelName">
                      {scoreBlocks[selectedDimensionIdx]?.name ?? '—'}
                    </p>
                    <p className="memoDimensionPanelText">
                      {(() => {
                        const selected = scoreBlocks[selectedDimensionIdx];
                        if (!selected) return '—';
                        const reasoning = selected.reasoning?.trim();
                        if (reasoning) return reasoning;
                        if (selected.score != null) return getScoreBand(selected.score).meaning || '—';
                        return '—';
                      })()}
                    </p>
                  </motion.div>
                </div>
              )}

              {scoresSummary ? <div className="memoScoresSummary">{scoresSummary}</div> : null}
            </section>

            {reviewHasThesisAlignment(displayStartup.review) && (
              <section>
                <p className="memoLabel memoLabel--thesis">THESIS ALIGNMENT</p>
                {displayStartup.review &&
                (displayStartup.review.thesis_alignment_score != null ||
                  displayStartup.review.thesis_matches_fund != null ||
                  displayStartup.review.thesis_alignment_confidence != null) ? (
                  (() => {
                    const r = displayStartup.review!;
                    const rawAlign = r.thesis_alignment_score;
                    const ten =
                      rawAlign != null ? (rawAlign <= 1 ? rawAlign * 10 : rawAlign) : null;
                    const fund = r.thesis_matches_fund;
                    const confRaw = r.thesis_alignment_confidence;
                    const confPct =
                      confRaw != null ? `${(confRaw * 100).toFixed(0)}%` : null;
                    const thesisTileCount =
                      (ten != null ? 1 : 0) + (fund != null ? 1 : 0) + (confPct != null ? 1 : 0);
                    const thesisRowN = thesisTileCount >= 3 ? 3 : thesisTileCount >= 2 ? 2 : 1;
                    return (
                      <div className="memoThesisScoreBlock">
                        <div
                          className={`memoThesisScoresRow memoThesisScoresRow--n${thesisRowN}`}
                        >
                          {ten != null ? (
                            <div className="memoThesisScoreTile" aria-label="Thesis alignment score">
                              <p className="memoScoreName">Alignment</p>
                              <div className="memoScoreValueRow">
                                <p className="memoScoreValue">{`${ten.toFixed(0)}/10`}</p>
                              </div>
                              <div className="memoScoreUnderline" aria-hidden />
                            </div>
                          ) : null}
                          {fund != null ? (
                            <div
                              className="memoThesisScoreTile"
                              aria-label={fund ? 'Aligned with fund mandate' : 'Not aligned with fund mandate'}
                            >
                              <p className="memoScoreName">Mandate</p>
                              <div className="memoScoreValueRow">
                                <p className="memoScoreValue">{fund ? 'ALIGNED' : 'MISALIGNED'}</p>
                              </div>
                              <div className="memoScoreUnderline" aria-hidden />
                            </div>
                          ) : null}
                          {confPct != null ? (
                            <div className="memoThesisScoreTile" aria-label={`Confidence ${confPct}`}>
                              <p className="memoScoreName">Confidence</p>
                              <div className="memoScoreValueRow">
                                <p className="memoScoreValue">{confPct}</p>
                              </div>
                              <div className="memoScoreUnderline" aria-hidden />
                            </div>
                          ) : null}
                        </div>
                      </div>
                    );
                  })()
                ) : null}
                {(displayStartup.review?.thesis_fit_points?.length ?? 0) > 0 ? (
                  <div className="memoOverviewRow">
                    <p className="memoOverviewKey">FITS</p>
                    <div className="memoStackedVals memoList--afterKey min-w-0">
                      {(displayStartup.review?.thesis_fit_points ?? []).map((item, i) => (
                        <p key={i} className="memoOverviewVal">
                          {item}
                        </p>
                      ))}
                    </div>
                  </div>
                ) : null}
                {(displayStartup.review?.thesis_deviation_points?.length ?? 0) > 0 ? (
                  <div className="memoOverviewRow">
                    <p className="memoOverviewKey">GAPS</p>
                    <div className="memoStackedVals memoList--afterKey min-w-0">
                      {(displayStartup.review?.thesis_deviation_points ?? []).map((item, i) => (
                        <p key={i} className="memoOverviewVal">
                          {item}
                        </p>
                      ))}
                    </div>
                  </div>
                ) : null}
              </section>
            )}

            {/* Overview block */}
            <section>
              <p className="memoLabel">OVERVIEW</p>
              <div className="memoOverviewRow">
                <p className="memoOverviewKey">PROBLEM</p>
                <p className="memoOverviewVal">{displayStartup.scout.problem?.trim() || '—'}</p>
              </div>
              <div className="memoOverviewRow">
                <p className="memoOverviewKey">SOLUTION</p>
                <p className="memoOverviewVal">{displayStartup.scout.solution?.trim() || '—'}</p>
              </div>
              <div className="memoOverviewRow">
                <p className="memoOverviewKey">TARGET</p>
                <p className="memoOverviewVal">{displayStartup.scout.target_users?.trim() || '—'}</p>
              </div>
              <div className="memoOverviewRow">
                <p className="memoOverviewKey">WHY NOW</p>
                <p className="memoOverviewVal">{displayStartup.scout.why_now?.trim() || '—'}</p>
              </div>
            </section>

            {(displayStartup.scout.primary_thesis ||
              (displayStartup.scout.key_assumptions && displayStartup.scout.key_assumptions.length > 0) ||
              displayStartup.scout.biggest_unknown) && (
                <section>
                  <p className="memoLabel">HYPOTHESIS</p>
                  {displayStartup.scout.primary_thesis ? (
                    <div className="memoOverviewRow">
                      <p className="memoOverviewKey">THESIS</p>
                      <p className="memoOverviewVal">{displayStartup.scout.primary_thesis}</p>
                    </div>
                  ) : null}
                  {displayStartup.scout.key_assumptions && displayStartup.scout.key_assumptions.length > 0 ? (
                    <div className="memoOverviewRow">
                      <p className="memoOverviewKey">ASSUMPTIONS</p>
                      <div className="memoStackedVals memoList--afterKey min-w-0">
                        {displayStartup.scout.key_assumptions.map((item, i) => (
                          <p key={i} className="memoOverviewVal">
                            {item}
                          </p>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {displayStartup.scout.biggest_unknown ? (
                    <div className="memoOverviewRow">
                      <p className="memoOverviewKey">BIGGEST UNKNOWN</p>
                      <p className="memoOverviewVal">{displayStartup.scout.biggest_unknown}</p>
                    </div>
                  ) : null}
                </section>
            )}

            {(displayStartup.review?.diligence_red_flags?.length || displayStartup.review?.key_risks?.length) && (
                <section>
                  <p className="memoLabel">RED FLAGS</p>
                  <ul className="memoList">
                    {[...(displayStartup.review?.diligence_red_flags ?? []), ...(displayStartup.review?.key_risks ?? [])]
                      .map((r) => String(r ?? '').trim())
                      .filter(Boolean)
                      .map((r, i) => (
                        <li key={i} className="memoListItem">
                          <span className="memoBullet">·</span>
                          <span>{r}</span>
                        </li>
                      ))}
                  </ul>
                </section>
            )}

            {nextStepText ? (
                <section>
                  <p className="memoLabel">NEXT STEP</p>
                  {nextStepItems.length > 0 ? (
                    <ul className="memoList">
                      {nextStepItems.map((item, idx) => (
                        <li key={idx} className="memoListItem">
                          <span className="memoBullet">{idx + 1}.</span>
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="memoOverviewVal">{nextStepText}</p>
                  )}
                </section>
            ) : null}

            {(displayStartup.partner?.llm_fallback_reason || displayStartup.partner?.portfolio_context_at_decision) ? (
                <section>
                  <p className="memoLabel">DECISION CONTEXT</p>
                  {displayStartup.partner?.llm_fallback_reason ? (
                    <div className="memoOverviewRow">
                      <p className="memoOverviewKey">LLM FALLBACK</p>
                      <p className="memoOverviewVal">{displayStartup.partner.llm_fallback_reason}</p>
                    </div>
                  ) : null}
                  {displayStartup.partner?.portfolio_context_at_decision ? (
                    <div className="memoOverviewRow">
                      <p className="memoOverviewKey">PORTFOLIO SIZE</p>
                      <p className="memoOverviewVal">
                        {displayStartup.partner.portfolio_context_at_decision.total_portfolio_size}
                      </p>
                    </div>
                  ) : null}
                </section>
            ) : null}

            {displayStartup.scout.references && displayStartup.scout.references.length > 0 && (
                <section>
                  <button
                    type="button"
                    className="memoSourcesToggle"
                    onClick={() => setSourcesOpen((v) => !v)}
                    aria-expanded={sourcesOpen}
                  >
                    <span>SOURCES</span>
                    <span className="memoSourcesPlus">{sourcesOpen ? '−' : '+'}</span>
                  </button>
                  <motion.div
                    initial={false}
                    animate={
                      reduceMotion
                        ? { height: sourcesOpen ? 'auto' : 0, opacity: sourcesOpen ? 1 : 0 }
                        : sourcesOpen
                          ? { height: 'auto', opacity: 1 }
                          : { height: 0, opacity: 0 }
                    }
                    transition={transitionOrReduced(reduceMotion, {
                      duration: 0.2,
                      ease: [0.16, 1, 0.3, 1],
                    })}
                    style={{ overflow: 'hidden' }}
                  >
                    <div className="memoSourcesBody">
                      <ul className="memoList">
                        {displayStartup.scout.references
                          .map((r) => String(r ?? '').trim())
                          .filter(Boolean)
                          .map((ref, i) => {
                            const href = memoReferenceHref(ref);
                            const label = memoReferenceLabel(ref);
                            return (
                              <li key={i} className="memoListItem">
                                <span className="memoBullet">·</span>
                                {href ? (
                                  <a className="memoLink" href={href} target="_blank" rel="noreferrer">
                                    {label}
                                  </a>
                                ) : (
                                  <span className="memoOverviewVal">{label}</span>
                                )}
                              </li>
                            );
                          })}
                      </ul>
                    </div>
                  </motion.div>
                </section>
            )}

            {pipelineReplaySteps.length > 0 && (
              <section className="memoPipelineSection" aria-label="Run log">
                <button
                  type="button"
                  className="memoPipelineToggle"
                  onClick={() => setPipelineLogOpen((v) => !v)}
                  aria-expanded={pipelineLogOpen}
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
                  animate={
                    reduceMotion
                      ? { height: pipelineLogOpen ? 'auto' : 0, opacity: pipelineLogOpen ? 1 : 0 }
                      : pipelineLogOpen
                        ? { height: 'auto', opacity: 1 }
                        : { height: 0, opacity: 0 }
                  }
                  transition={transitionOrReduced(reduceMotion, {
                    duration: 0.2,
                    ease: [0.16, 1, 0.3, 1],
                  })}
                  style={{ overflow: 'hidden' }}
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
                </motion.div>
              </section>
            )}

            {memoPipeline === 'generating' && (
              <section className="memoGeneratingSection" aria-live="polite">
                <div className="memoSummaryCallout memoGenCallout">
                  <p className="memoPipelineKicker">Investment memo</p>
                  <motion.p
                    className="memoGateTitle"
                    animate={reduceMotion ? { opacity: 1 } : { opacity: [0.55, 1, 0.55] }}
                    transition={
                      reduceMotion ? { duration: 0 } : { duration: 2.2, repeat: Infinity, ease: 'easeInOut' }
                    }
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
