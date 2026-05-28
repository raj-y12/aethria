/**
 * IC-style memo export: PDF pack sections and pipeline replay metadata.
 */
import type { jsPDF } from 'jspdf';
import type { Startup } from '../types/startup';
import {
  DECISION_LABELS,
  QUALITY_LABELS,
  getReviewerQualityBand,
  getScoreBand,
  SCORE_DIMENSIONS,
} from '../design-system/semantics';

const PDF_MARGIN = 20;
const PDF_LINE_HEIGHT = 5;
const PDF_FONT_SIZE_TITLE = 18;
const PDF_FONT_SIZE_HEADING = 11;
const PDF_FONT_SIZE_BODY = 10;
const PDF_FONT_SIZE_SMALL = 9;

export interface IcSection {
  title: string;
  lines: string[];
}

export interface PipelineReplayStep {
  id: string;
  label: string;
  atIso?: string;
  atDisplay: string;
  detail: string;
  done: boolean;
}

function fmtDate(iso?: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' });
  } catch {
    return String(iso);
  }
}

function shortPrompt(v?: string | null): string {
  if (!v || !String(v).trim()) return '';
  const s = String(v).trim();
  return s.length <= 10 ? s : `${s.slice(0, 8)}…`;
}

function judgmentToParagraphs(text: string): string[] {
  const trimmed = text.trim();
  if (!trimmed) return [];
  if (/\n\s*\n/.test(trimmed)) {
    return trimmed
      .split(/\n\s*\n/)
      .map((s) => s.trim())
      .filter(Boolean);
  }
  if (trimmed.includes('\n')) {
    return trimmed
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean);
  }
  const sentences = trimmed.split(/(?<=\.)\s+(?=[A-Z])/).map((s) => s.trim()).filter(Boolean);
  return sentences.length ? sentences : [trimmed];
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

function buildJudgmentLines(startup: Startup): string[] {
  if (!startup.partner) return [];
  const p = startup.partner;
  const decisionLabel = DECISION_LABELS[p.recommendation] ?? p.recommendation;
  const band = getReviewerQualityBand(startup.review);
  const dossier =
    band != null ? ` Dossier read: ${band} (${QUALITY_LABELS[band] ?? band}).` : '';
  const rationale = (p.decision_rationale ?? '').trim();
  const head = `${decisionLabel}.${dossier}`.replace(/\.\s*\./g, '.').trim();
  const combined = rationale ? `${head} ${rationale}` : head;
  return judgmentToParagraphs(combined);
}

export function getPipelineReplaySteps(startup: Startup): PipelineReplayStep[] {
  const scoutPv = shortPrompt(startup.scout.prompt_version);
  const steps: PipelineReplayStep[] = [
    {
      id: 'scout',
      label: 'Scout',
      atIso: startup.timestamps?.discovered_at,
      atDisplay: fmtDate(startup.timestamps?.discovered_at),
      detail: [
        startup.scout.scout_type || 'Scout',
        scoutPv ? `Prompt ${scoutPv}` : '',
      ]
        .filter(Boolean)
        .join(' · '),
      done: true,
    },
    {
      id: 'review',
      label: 'Review',
      atIso: startup.timestamps?.reviewed_at,
      atDisplay: fmtDate(startup.timestamps?.reviewed_at),
      detail: startup.review
        ? [
            `Verdict ${startup.review.consensus_verdict ?? startup.review.verdict ?? '—'}`,
            startup.review.reviews?.[0]?.prompt_version
              ? `Prompt ${shortPrompt(startup.review.reviews[0].prompt_version)}`
              : '',
          ]
            .filter(Boolean)
            .join(' · ')
        : 'Pending',
      done: !!startup.review,
},
    {
      id: 'partner',
      label: 'Partner',
      atIso: startup.timestamps?.partnered_at,
      atDisplay: fmtDate(startup.timestamps?.partnered_at),
      detail: startup.partner?.recommendation
        ? [
            DECISION_LABELS[startup.partner.recommendation] ?? startup.partner.recommendation,
            shortPrompt(startup.partner.prompt_version)
              ? `Prompt ${shortPrompt(startup.partner.prompt_version)}`
              : '',
          ]
            .filter(Boolean)
            .join(' · ')
        : 'Pending',
      done: !!startup.partner?.recommendation,
    },
  ];

  if (startup.human_resolution?.resolved_at) {
    steps.push({
      id: 'human',
      label: 'Human resolution',
      atIso: startup.human_resolution.resolved_at,
      atDisplay: fmtDate(startup.human_resolution.resolved_at),
      detail: [DECISION_LABELS[startup.human_resolution.decision] ?? startup.human_resolution.decision]
        .filter(Boolean)
        .join(' · '),
      done: true,
    });
  }

  return steps;
}

/**
 * Ordered sections for investment committee PDF pack.
 */
export function buildIcPackSections(startup: Startup): IcSection[] {
  const sections: IcSection[] = [];

  const exec: string[] = [];
  if (startup.scout.one_line?.trim()) exec.push(`One line: ${startup.scout.one_line.trim()}`);
  if (startup.scout.primary_thesis?.trim()) exec.push(`Thesis: ${startup.scout.primary_thesis.trim()}`);
  if (startup.scout.funding_stage?.trim()) exec.push(`Stage: ${startup.scout.funding_stage.trim()}`);
  if (startup.scout.est_tam?.trim()) exec.push(`TAM (scout est.): ${startup.scout.est_tam.trim()}`);
  if (startup.scout.biggest_unknown?.trim()) exec.push(`Biggest unknown: ${startup.scout.biggest_unknown.trim()}`);
  if (exec.length) sections.push({ title: 'Executive summary', lines: exec });

  const origin: string[] = [];
  const ot = (startup.scout.origin_type ?? '').toLowerCase();
  if (ot === 'on_demand_lookup') {
    origin.push('Channel: On-demand lookup');
    if (startup.scout.lookup_query) origin.push(`Lookup input: ${startup.scout.lookup_query}`);
    if (startup.scout.lookup_website) origin.push(`Website: ${startup.scout.lookup_website}`);
    if (startup.scout.lookup_input_type) origin.push(`Input type: ${startup.scout.lookup_input_type}`);
  } else {
    origin.push(`Channel: Scout pipeline (${startup.scout.scout_type || 'scout'})`);
  }
  origin.push(`Company ID: ${startup.id}`);
  sections.push({ title: 'Deal origin', lines: origin });

  const timelineLines = getPipelineReplaySteps(startup).map(
    (s) => `${s.label}: ${s.atDisplay} — ${s.detail}`
  );
  sections.push({ title: 'Pipeline replay (timeline)', lines: timelineLines });

  const judgment = buildJudgmentLines(startup);
  if (judgment.length) sections.push({ title: 'Investment judgment', lines: judgment });

  const overview: string[] = [];
  if (startup.scout.problem) overview.push(`Problem: ${startup.scout.problem}`);
  if (startup.scout.solution) overview.push(`Solution: ${startup.scout.solution}`);
  if (startup.scout.target_users) overview.push(`Target customers: ${startup.scout.target_users}`);
  if (startup.scout.why_now) overview.push(`Why now: ${startup.scout.why_now}`);
  if (overview.length) sections.push({ title: 'Business overview', lines: overview });

  if (startup.scout.key_assumptions?.length) {
    sections.push({
      title: 'Key assumptions',
      lines: startup.scout.key_assumptions.map((a) => `• ${a}`),
    });
  }

  if (startup.review) {
    const primary = SCORE_DIMENSIONS.slice(0, 2);
    const scoreLines = primary
      .map(({ id, name }) => {
        const score = startup.review?.[id as keyof typeof startup.review];
        if (score == null || typeof score !== 'number') return null;
        const band = getScoreBand(score);
        return `${name}: ${score}/10 (${band.label})`;
      })
      .filter(Boolean) as string[];
    const supporting = SCORE_DIMENSIONS.slice(2);
    const scoreLines2 = supporting
      .map(({ id, name }) => {
        const score = startup.review?.[id as keyof typeof startup.review];
        if (score == null || typeof score !== 'number') return null;
        const band = getScoreBand(score);
        return `${name}: ${score}/10 (${band.label})`;
      })
      .filter(Boolean) as string[];
    const allScores = [...scoreLines, ...scoreLines2];
    if (allScores.length) sections.push({ title: 'Dimension scores', lines: allScores });
  }

  const primaryRisks = startup.review?.diligence_red_flags ?? [];
  const secondaryRisks = (startup.review?.key_risks ?? []).filter(
    (r) => !primaryRisks.some((p) => r.includes(p) || p.includes(r))
  );
  if (primaryRisks.length || secondaryRisks.length) {
    sections.push({
      title: 'Risks & red flags',
      lines: [
        ...(primaryRisks.length ? [`Primary diligence: ${primaryRisks.join('; ')}`] : []),
        ...(secondaryRisks.length ? [`Additional risks: ${secondaryRisks.join('; ')}`] : []),
      ],
    });
  }

  if (startup.review?.overall_summary?.trim()) {
    sections.push({ title: 'Reviewer summary', lines: [startup.review.overall_summary.trim()] });
  }

  const dissent: string[] = [];
  if (startup.review?.reviewer_disagreement) {
    dissent.push('Multiple reviewers reported disagreement; treat verdicts with extra scrutiny.');
  }
  if (startup.review?.reviews && startup.review.reviews.length > 1) {
    const verdicts = startup.review.reviews.map((r) => r.verdict).filter(Boolean);
    if (verdicts.length) dissent.push(`Per-reviewer verdicts: ${verdicts.join(', ')}`);
  }
  if (startup.review?.assumption_feedback?.length) {
    dissent.push(
      ...startup.review.assumption_feedback.map((a) => `Assumption note: ${a}`)
    );
  }
  if (dissent.length) sections.push({ title: 'Open questions & dissent notes', lines: dissent });

  if (startup.human_resolution) {
    const hr = startup.human_resolution;
    const lines = [
      `Resolution: ${DECISION_LABELS[hr.decision] ?? hr.decision}`,
      ...(hr.notes?.trim() ? [`Notes: ${hr.notes.trim()}`] : []),
      ...(hr.resolved_at ? [`Resolved at: ${fmtDate(hr.resolved_at)}`] : []),
    ];
    sections.push({ title: 'Human resolution (escalation)', lines });
  }

  if (startup.partner) {
    const p = startup.partner;
    const nextRaw = getNextStepText(startup);
    const nextItems = parseNextStepItems(nextRaw);
    const rec: string[] = [
      `Recommendation: ${DECISION_LABELS[p.recommendation] ?? p.recommendation} (${p.recommendation})`,
    ];
    if (startup.review?.verdict) rec.push(`Reviewer quality band: ${startup.review.verdict}`);
    if (p.confidence != null) rec.push(`Partner confidence: ${Math.round(p.confidence * 100)}%`);
    if (p.human_review_required) rec.push('Flag: Human review was required before resolution.');
    if (p.decision_rationale?.trim()) rec.push(`Rationale: ${p.decision_rationale.trim()}`);
    if (nextItems.length) {
      nextItems.forEach((item, idx) => rec.push(`Next step ${idx + 1}: ${item}`));
    } else if (nextRaw) rec.push(`Next step: ${nextRaw}`);
    if (p.llm_fallback_reason) rec.push(`Engine note: ${p.llm_fallback_reason}`);
    sections.push({ title: 'Formal recommendation', lines: rec });
  }

  const appendix: string[] = [
    `Generated: ${fmtDate(new Date().toISOString())}`,
    `Discovered: ${fmtDate(startup.timestamps?.discovered_at)}`,
    `Reviewed: ${fmtDate(startup.timestamps?.reviewed_at)}`,
    `Partner decision recorded: ${fmtDate(startup.timestamps?.partnered_at)}`,
  ];
  const scoutH = startup.scout.prompt_version?.trim();
  if (scoutH) appendix.push(`Scout prompt hash: ${scoutH}`);
  const revH =
    startup.review?.reviews?.[0]?.prompt_version?.trim() ?? undefined;
  if (revH) appendix.push(`Reviewer prompt hash (primary): ${revH}`);
  const pH = startup.partner?.prompt_version?.trim();
  if (pH) appendix.push(`Partner prompt hash: ${pH}`);
  appendix.push(
    'This document was generated by Aethria for internal decision support. It is not investment advice.'
  );
  sections.push({ title: 'Appendix & data lineage', lines: appendix });

  if (startup.scout.references?.length) {
    sections.push({
      title: 'Sources',
      lines: startup.scout.references.map((r) => String(r).trim()).filter(Boolean),
    });
  }

  return sections;
}

function addPDFSection(
  doc: jsPDF,
  opts: { title?: string; lines: string[]; startY: number }
): number {
  let y = opts.startY;
  const pageH = doc.internal.pageSize.getHeight();
  const maxW = doc.internal.pageSize.getWidth() - PDF_MARGIN * 2;
  if (opts.title) {
    doc.setFontSize(PDF_FONT_SIZE_HEADING);
    doc.setTextColor(80, 80, 100);
    doc.text(opts.title.toUpperCase(), PDF_MARGIN, y);
    y += PDF_LINE_HEIGHT + 1;
  }
  doc.setFontSize(PDF_FONT_SIZE_BODY);
  doc.setTextColor(0, 20, 51);
  for (const line of opts.lines) {
    const split = doc.splitTextToSize(line, maxW);
    for (const s of split) {
      if (y > pageH - 20) {
        doc.addPage();
        y = PDF_MARGIN;
      }
      doc.text(s, PDF_MARGIN, y);
      y += PDF_LINE_HEIGHT;
    }
  }
  return y + PDF_LINE_HEIGHT;
}

export async function buildMemoPDF(startup: Startup): Promise<jsPDF> {
  const { jsPDF: JsPDF } = await import('jspdf');
  const doc = new JsPDF({ unit: 'mm', format: 'a4' });
  let y = PDF_MARGIN;

  doc.setFontSize(PDF_FONT_SIZE_SMALL);
  doc.setTextColor(100, 100, 120);
  doc.text('CONFIDENTIAL — FOR INVESTMENT COMMITTEE USE ONLY', PDF_MARGIN, y);
  y += PDF_LINE_HEIGHT + 2;
  doc.setFontSize(PDF_FONT_SIZE_TITLE);
  doc.setTextColor(0, 20, 51);
  doc.text('Investment committee memorandum', PDF_MARGIN, y);
  y += PDF_LINE_HEIGHT + 4;
  doc.setFontSize(14);
  doc.text(startup.scout.name ?? '—', PDF_MARGIN, y);
  y += PDF_LINE_HEIGHT + 2;
  doc.setFontSize(PDF_FONT_SIZE_SMALL);
  doc.setTextColor(80, 80, 100);
  const sector = startup.scout.sector?.trim() || '—';
  const stage = startup.scout.funding_stage?.trim() || '';
  doc.text(stage ? `${sector} · ${stage}` : sector, PDF_MARGIN, y);
  y += PDF_LINE_HEIGHT;
  doc.text(`Prepared: ${fmtDate(new Date().toISOString())}`, PDF_MARGIN, y);
  y += PDF_LINE_HEIGHT * 2;

  const sections = buildIcPackSections(startup);
  for (const sec of sections) {
    y = addPDFSection(doc, { title: sec.title, lines: sec.lines, startY: y });
  }

  return doc;
}

export function icPackSafeBaseName(startup: Startup): string {
  return (startup.scout.name ?? 'memo').replace(/[^a-zA-Z0-9-_]/g, '_').slice(0, 60);
}
