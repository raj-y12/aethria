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
  SCORE_DIMENSIONS,
} from '../design-system/semantics';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';

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
  const [selectedDimensionIdx, setSelectedDimensionIdx] = useState(0);
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
    setMemoGateError(null);

    if (startup.partner?.recommendation) {
      setMemoPipeline('ready');
      return;
    }

    setMemoPipeline('idle');
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
    setSelectedDimensionIdx(0);
    setSelectedReviewerIdx(0);
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

  const REVIEWER_LABELS: Record<string, string> = {
    DefaultReviewer: 'Default',
    SkepticalReviewer: 'Skeptical',
    OpportunistReviewer: 'Opportunist',
  };

  return (
    <div className={wrapperCls}>
      <style>{`
        /* === Layout === */
        .memoPanel{
          --memo-body-size: 14px;
          --memo-label-size: 11px;
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
          height: auto;
          overflow: visible;
        }
        .memoScroll{
          flex: 1 1 auto;
          min-height: 0;
          overflow-y: auto;
          overflow-x: hidden;
          padding: clamp(34px, 4vw, 55px) clamp(34px, 5vw, 55px);
          color: #002147;
          background: var(--color-paper);
        }
        .memoPanel--embedded .memoScroll{
          padding: 0;
          overflow: visible;
          flex: 0 0 auto;
          min-height: auto;
        }

        /* === Action buttons === */
        .memoHeaderActions{
          display: flex;
          flex-wrap: wrap;
          justify-content: flex-end;
          align-items: center;
          gap: 10px 18px;
          margin-bottom: 10px;
        }
        .memoAction{
          appearance: none;
          border: none;
          background: transparent;
          padding: 4px 0;
          cursor: pointer;
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 11px;
          font-variant-caps: all-small-caps;
          letter-spacing: 0.12em;
          color: rgba(0,33,71,0.45);
          transition: color 150ms ease;
        }
        .memoAction:hover{ color: #002147; }

        /* === Gate strip (error/generating) === */
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
        .memoGateStripInner{ pointer-events: auto; }
        .memoGateTitle{
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-size: 14px;
          line-height: 1.5;
          color: rgba(0,33,71,0.78);
          margin: 8px 0 0 0;
        }
        .memoGateDetail{
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-size: 13px;
          line-height: 1.6;
          color: rgba(0,33,71,0.55);
          margin: 5px 0 0 0;
          max-width: 38rem;
        }
        .memoPipelineKicker{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: var(--memo-label-size);
          letter-spacing: 0.11em;
          text-transform: uppercase;
          color: rgba(0,33,71,0.50);
          margin: 0;
        }
        .memoGateStrip--error .memoGateTitle{ color: rgba(125,43,58,0.95); }
        .memoGateStrip--error .memoPipelineKicker{ color: rgba(125,43,58,0.72); }

        /* === Document body === */
        .memoBody{
          max-width: 42rem;
        }
        .memoPanel--embedded .memoBody{
          max-width: none;
          width: 100%;
        }
        .memoDocSection{
          margin-top: clamp(32px, 4.5vw, 48px);
        }

        /* === Empty state === */
        .memoEmpty{
          height: 100%;
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--color-paper);
        }
        .memoEmptyInner{ text-align: center; padding: 48px; }
        .memoEmptyWordmark{
          font-family: "Libre Baskerville", Georgia, serif;
          font-weight: 400;
          font-size: 24px;
          line-height: 1.4;
          color: rgba(0,33,71,0.22);
          margin: 0;
        }
        .memoEmptyHint{
          margin-top: 12px;
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-size: 13px;
          color: rgba(0,33,71,0.18);
        }

        /* === Document header === */
        .memoDocHeader{
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 10px;
        }
        .memoDocHeaderMain{ flex: 1 1 auto; min-width: 0; }
        .memoCompany{
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-weight: 600;
          font-size: clamp(1.375rem, 2.2vw, 1.625rem);
          line-height: 1.2;
          letter-spacing: -0.01em;
          margin: 0 0 6px 0;
          color: #002147;
        }
        .memoDocTagline{
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-size: 14px;
          line-height: 1.55;
          color: rgba(0,33,71,0.55);
          margin: 0 0 8px 0;
          font-style: italic;
        }
        .memoMeta{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 11px;
          letter-spacing: 0.08em;
          color: rgba(0,33,71,0.40);
          text-transform: uppercase;
        }
        .memoDocHeaderRight{
          width: 100%;
          text-align: left;
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 4px;
        }
        .memoDocRecommendation{
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-size: clamp(1.375rem, 5vw, 2rem);
          font-weight: 600;
          letter-spacing: -0.03em;
          text-transform: uppercase;
          margin: 0;
          line-height: 1;
        }
        .memoDocRecommendation--invest{ color: rgba(14, 88, 44, 0.88); }
        .memoDocRecommendation--monitor{ color: rgba(115, 76, 0, 0.85); }
        .memoDocRecommendation--pass{ color: rgba(125, 43, 58, 0.88); }
        .memoDocConfidence{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 11px;
          letter-spacing: 0.10em;
          text-transform: uppercase;
          color: rgba(0,33,71,0.38);
          margin: 0;
        }
        .memoDocEscalation{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 10px;
          letter-spacing: 0.10em;
          text-transform: uppercase;
          color: rgba(125,43,58,0.60);
          margin: 0;
        }
        .memoDocStatusLine{
          display: flex;
          align-items: baseline;
          gap: 12px;
          flex-wrap: wrap;
        }
        .memoDocJudgmentTop{
          margin-bottom: 12px;
        }
        .memoDocLookupBadge{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 10px;
          letter-spacing: 0.10em;
          text-transform: uppercase;
          color: rgba(0,33,71,0.30);
          margin: 0;
        }

        /* === Header divider === */
        .memoDocDivider{
          height: 1px;
          background: rgba(0,33,71,0.08);
          margin: clamp(20px, 3vw, 30px) 0 0 0;
        }

        /* === Section heading === */
        .memoDocSectionHead{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: var(--memo-label-size);
          text-transform: uppercase;
          letter-spacing: 0.14em;
          color: rgba(0,33,71,0.40);
          margin: 0 0 20px 0;
          display: flex;
          align-items: center;
          gap: 12px;
          font-weight: 400;
        }
        .memoDocContestedKicker{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 10px;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: rgba(125,43,58,0.65);
        }
        .memoDocSubsection{ margin-top: 22px; }
        .memoDocSubhead{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 0.12em;
          color: rgba(0,33,71,0.35);
          margin: 0 0 10px 0;
        }

        /* === Prose text === */
        .memoDocProse{
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-size: var(--memo-body-size);
          line-height: 1.72;
          color: rgba(0,33,71,0.72);
          margin: 0 0 14px 0;
        }
        .memoDocProse:last-child{ margin-bottom: 0; }
        .memoDocThesis{
          font-style: italic;
          color: rgba(0,33,71,0.80);
          font-size: 14.5px;
        }

        /* === Definition list (key-value rows) === */
        .memoDocDL{ display: flex; flex-direction: column; }
        .memoDocDLRow{
          display: grid;
          grid-template-columns: minmax(7.5rem, 9rem) minmax(0, 1fr);
          column-gap: clamp(18px, 2.5vw, 28px);
          align-items: start;
          padding: 9px 0;
        }
        .memoDocDLRow + .memoDocDLRow{ margin-top: 2px; }
        .memoDocDT{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 0.10em;
          color: rgba(0,33,71,0.36);
          margin: 0;
          padding-top: 2px;
        }
        .memoDocDD{
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-size: var(--memo-body-size);
          line-height: 1.65;
          color: rgba(0,33,71,0.75);
          margin: 0;
        }

        /* === Assessment scorecard === */
        .memoDocScoreLegend{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 10px;
          letter-spacing: 0.06em;
          color: rgba(0,33,71,0.30);
          margin: 0 0 16px 0;
        }
        .memoDocScorecardRow{
          display: grid;
          grid-template-columns: repeat(5, minmax(0, 1fr));
          gap: clamp(10px, 1.8vw, 18px);
          margin-bottom: 4px;
        }
        .memoDocScoreBtn{
          appearance: none;
          border: none;
          background: transparent;
          padding: 0;
          cursor: pointer;
          text-align: center;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 5px;
          min-width: 0;
        }
        .memoDocScoreBtn:focus{ outline: none; }
        .memoDocScoreBtn:focus-visible{
          outline: 2px solid rgba(0,33,71,0.22);
          outline-offset: 4px;
        }
        .memoDocScoreDim{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 9px;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: rgba(0,33,71,0.30);
          transition: color 150ms ease;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 100%;
        }
        .memoDocScoreVal{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: clamp(0.9375rem, 1.5vw, 1.1875rem);
          font-weight: 700;
          color: rgba(0,33,71,0.42);
          transition: color 150ms ease;
          line-height: 1.1;
        }
        .memoDocScoreBtn[aria-pressed="true"] .memoDocScoreDim{ color: rgba(0,33,71,0.55); }
        .memoDocScoreBtn[aria-pressed="true"] .memoDocScoreVal{ color: #002147; }
        .memoDocScoreUnderline{
          height: 2px;
          width: 100%;
          background: rgba(0,33,71,0.18);
        }
        .memoDocScoreColSpacer{ height: 2px; }
        .memoDocDimDetail{
          padding: 14px 0 2px 0;
          margin-top: 8px;
          display: flex;
          flex-direction: column;
          gap: 5px;
        }
        .memoDocDimName{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 0.10em;
          color: rgba(0,33,71,0.42);
        }
        .memoDocDimText{
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-size: 13px;
          line-height: 1.62;
          color: rgba(0,33,71,0.68);
        }
        .memoDocScoreNote{
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-style: italic;
          font-size: 13px;
          line-height: 1.6;
          color: rgba(0,33,71,0.40);
          margin: 14px 0 0 0;
        }

        /* === Thesis alignment tiles === */
        .memoDocAlignTiles{
          display: flex;
          flex-wrap: wrap;
          gap: clamp(20px, 3vw, 36px);
          margin-bottom: 20px;
        }
        .memoDocAlignTile{
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .memoDocAlignTileLabel{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 0.10em;
          color: rgba(0,33,71,0.36);
          margin: 0;
        }
        .memoDocAlignTileVal{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: clamp(1rem, 1.6vw, 1.25rem);
          font-weight: 600;
          color: #002147;
          margin: 0;
          line-height: 1.2;
        }

        /* === Reviewer comparison table === */
        .memoDocReviewerTable{
          border-top: 1px solid rgba(0,33,71,0.08);
        }
        .memoDocReviewerRow{
          display: grid;
          grid-template-columns: 6.5rem 5rem minmax(0, 1fr);
          gap: 0 clamp(12px, 2vw, 20px);
          align-items: center;
          padding: 13px 0;
          border-bottom: 1px solid rgba(0,33,71,0.06);
          appearance: none;
          border-left: none;
          border-right: none;
          background: transparent;
          width: 100%;
          cursor: pointer;
          text-align: left;
          transition: background 120ms ease;
        }
        .memoDocReviewerRow:hover{ background: rgba(0,33,71,0.025); }
        .memoDocReviewerRow:focus{ outline: none; }
        .memoDocReviewerRow:focus-visible{
          outline: 2px solid rgba(0,33,71,0.22);
          outline-offset: 2px;
        }
        .memoDocReviewerRowLabel{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: rgba(0,33,71,0.42);
          transition: color 150ms ease;
        }
        .memoDocReviewerRow[aria-pressed="true"] .memoDocReviewerRowLabel{ color: rgba(0,33,71,0.72); }
        .memoDocReviewerRowVerdict{
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-size: 13px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.02em;
          color: rgba(0,33,71,0.45);
          transition: color 150ms ease;
        }
        .memoDocReviewerRow[aria-pressed="true"] .memoDocReviewerRowVerdict{ color: #002147; }
        .memoDocReviewerRowScores{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 10px;
          letter-spacing: 0.04em;
          color: rgba(0,33,71,0.32);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          transition: color 150ms ease;
        }
        .memoDocReviewerRow[aria-pressed="true"] .memoDocReviewerRowScores{ color: rgba(0,33,71,0.50); }
        .memoDocReviewerDetail{
          padding: 16px 0 4px 0;
        }
        .memoDocReviewerDetailText{
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-size: 13px;
          line-height: 1.65;
          color: rgba(0,33,71,0.65);
          margin: 0;
        }

        /* === Shared list === */
        .memoList{
          margin: 0;
          padding: 0;
          list-style: none;
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-size: var(--memo-body-size);
          line-height: 1.65;
          color: rgba(0,33,71,0.72);
        }
        .memoListItem{
          display: flex;
          gap: 12px;
        }
        .memoListItem + .memoListItem{ margin-top: 0.625rem; }
        .memoBullet{
          flex-shrink: 0;
          color: rgba(0,33,71,0.25);
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 12px;
          margin-top: 0.12em;
        }
        .memoLink{
          color: #002147;
          text-decoration: none;
          border-bottom: 1px solid rgba(0,33,71,0.20);
          transition: border-color 120ms ease;
        }
        .memoLink:hover{ border-bottom-color: rgba(0,33,71,0.45); }

        /* === Sources toggle === */
        .memoSourcesToggle{
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: space-between;
          appearance: none;
          border: none;
          border-top: 1px solid rgba(0,33,71,0.08);
          background: transparent;
          padding: 13px 0 0 0;
          cursor: pointer;
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: var(--memo-label-size);
          text-transform: uppercase;
          letter-spacing: 0.12em;
          color: rgba(0,33,71,0.36);
          transition: color 120ms ease;
        }
        .memoSourcesToggle:hover{ color: rgba(0,33,71,0.60); }
        .memoSourcesPlus{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 13px;
          color: rgba(0,33,71,0.30);
          line-height: 1;
        }
        .memoSourcesBody{ padding-top: 14px; padding-bottom: 4px; }

        /* === Pipeline run log === */
        .memoPipelineSection{ margin: 0; }
        .memoPipelineToggle{
          width: 100%;
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
          appearance: none;
          border: none;
          background: transparent;
          padding: 0 0 12px 0;
          cursor: pointer;
          text-align: left;
          border-bottom: 1px solid rgba(0,33,71,0.06);
          transition: opacity 120ms ease;
        }
        .memoPipelineToggle:hover{ opacity: 0.72; }
        .memoPipelineToggleTitle{
          display: flex;
          flex-direction: column;
          gap: 4px;
          min-width: 0;
          flex: 1;
        }
        .memoPipelineOneLiner{
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-size: var(--memo-body-size);
          line-height: 1.45;
          color: rgba(0,33,71,0.48);
          margin: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .memoPipelinePlus{
          flex-shrink: 0;
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: 12px;
          color: rgba(0,33,71,0.40);
          line-height: 1.5;
          padding-top: 2px;
        }
        .memoReplayList{ list-style: none; margin: 0; padding: 4px 0 2px 0; }
        .memoReplayItem{
          padding: 16px 0;
          border-top: 1px solid rgba(0,33,71,0.06);
        }
        .memoReplayItem:first-child{ border-top: none; padding-top: 12px; }
        .memoReplayKicker{
          display: flex;
          flex-wrap: wrap;
          align-items: baseline;
          gap: 6px 10px;
          margin: 0 0 4px 0;
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-size: var(--memo-body-size);
          font-weight: 600;
          line-height: 1.35;
          color: rgba(0,33,71,0.75);
        }
        .memoReplayBadge{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: var(--memo-label-size);
          font-weight: 400;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: rgba(0,33,71,0.38);
        }
        .memoReplayBadge--pending{ color: rgba(0,33,71,0.28); }
        .memoReplayWhen{
          font-family: "Space Mono", ui-monospace, monospace;
          font-size: var(--memo-label-size);
          letter-spacing: 0.08em;
          color: rgba(0,33,71,0.36);
          margin: 0 0 6px 0;
        }
        .memoReplayDetail{
          font-family: "Instrument Sans", system-ui, sans-serif;
          font-size: var(--memo-body-size);
          line-height: 1.55;
          color: rgba(0,33,71,0.58);
          margin: 0;
        }

        /* === Generating state === */
        .memoGeneratingSection{ margin-top: 2.25rem; }
        .memoSummaryCallout{ background: transparent; padding: 0; margin: 0; border: none; }
        .memoSummaryCallout.memoGenCallout{
          background: var(--color-register-tint);
          padding: 14px 0 16px 0;
        }
        .memoGenCallout .memoPipelineKicker{ margin-bottom: 8px; }
        .memoGenCallout .memoGateTitle{ margin-top: 0; }
        .memoGenCallout .memoGateDetail{ margin-bottom: 0; }

        @media (max-width: 1100px){
          .memoPanel{ width: 100%; flex-basis: auto; }
          .memoDocScorecardRow{ grid-template-columns: repeat(3, minmax(0,1fr)); }
        }
        @media (max-width: 640px){
          .memoDocHeader{ flex-direction: column; gap: 10px; }
          .memoDocHeaderRight{ text-align: left; align-items: flex-start; }
          .memoDocDLRow{ grid-template-columns: 1fr; row-gap: 5px; }
          .memoDocDT{ padding-top: 0; }
          .memoDocReviewerRow{ grid-template-columns: 1fr 1fr; }
          .memoDocReviewerRowScores{ display: none; }
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
                      <>
                        <p className="memoDocScoreLegend">1–3 Weak · 4–5 Concerning · 6–7 Promising · 8–10 Strong</p>
                        <div className="memoDocScorecardRow">
                          {scoreBlocks.map((b, idx) => {
                            const isSelected = idx === selectedDimensionIdx;
                            return (
                              <button
                                key={b.id}
                                type="button"
                                className="memoDocScoreBtn"
                                onClick={() => setSelectedDimensionIdx(idx)}
                                aria-pressed={isSelected}
                              >
                                <span className="memoDocScoreDim">{b.name}</span>
                                <span className="memoDocScoreVal">{b.score != null ? `${b.score}/10` : '—'}</span>
                                {isSelected ? <div className="memoDocScoreUnderline" /> : <div className="memoDocScoreColSpacer" aria-hidden />}
                              </button>
                            );
                          })}
                        </div>
                        <motion.div
                          key={`${contentKey}:dim:${selectedDimensionIdx}`}
                          className="memoDocDimDetail"
                          initial={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={transitionOrReduced(reduceMotion, { duration: 0.18, ease: [0.16, 1, 0.3, 1] })}
                        >
                          <span className="memoDocDimName">{scoreBlocks[selectedDimensionIdx]?.name}</span>
                          <span className="memoDocDimText">
                            {(() => {
                              const sel = scoreBlocks[selectedDimensionIdx];
                              if (!sel) return '—';
                              if (sel.reasoning?.trim()) return sel.reasoning;
                              if (sel.score != null) return getScoreBand(sel.score).meaning || '—';
                              return '—';
                            })()}
                          </span>
                        </motion.div>
                        {scoresSummary && <p className="memoDocScoreNote">{scoresSummary}</p>}
                      </>
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
                    <div className="memoDocReviewerTable" role="table" aria-label="Per-reviewer scores and verdicts">
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
              <section style={{ marginTop: 'clamp(24px, 3.5vw, 36px)' }}>
                <button
                  type="button"
                  className="memoSourcesToggle"
                  onClick={() => setSourcesOpen((v) => !v)}
                  aria-expanded={sourcesOpen}
                >
                  <span>Sources</span>
                  <span className="memoSourcesPlus">{sourcesOpen ? '−' : '+'}</span>
                </button>
                <motion.div
                  initial={false}
                  animate={
                    reduceMotion
                      ? { height: sourcesOpen ? 'auto' : 0, opacity: sourcesOpen ? 1 : 0 }
                      : sourcesOpen ? { height: 'auto', opacity: 1 } : { height: 0, opacity: 0 }
                  }
                  transition={transitionOrReduced(reduceMotion, { duration: 0.2, ease: [0.16, 1, 0.3, 1] })}
                  style={{ overflow: 'hidden' }}
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
                </motion.div>
              </section>
            )}

            {/* ── Run Log ── */}
            {pipelineReplaySteps.length > 0 && (
              <section
                className="memoPipelineSection"
                aria-label="Run log"
                style={{ marginTop: 'clamp(18px, 2.5vw, 28px)' }}
              >
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
                      : pipelineLogOpen ? { height: 'auto', opacity: 1 } : { height: 0, opacity: 0 }
                  }
                  transition={transitionOrReduced(reduceMotion, { duration: 0.2, ease: [0.16, 1, 0.3, 1] })}
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
