/**
 * Pure helpers for InvestmentMemoContent — data shaping, text normalization, and
 * memo-section derivation. Extracted verbatim from InvestmentMemoContent.tsx to
 * keep the component file focused on rendering. No React state here; these are
 * deterministic functions over a Startup (plus one tiny inline-number renderer).
 */
import { type ReactNode } from 'react';
import type { MemoPartialPayload } from '../../api/startups';
import type { DecisionHistoryDecision, Review, SingleReview, Startup } from '../../types/startup';
import { memoReferenceHref, memoReferenceLabel } from '../../lib/memoReferenceHref';
import { DECISION_LABELS } from '../../design-system/semantics';
import type { DecisionBadgeVariant } from '../../lib/decisionBadgeVariant';
import { type PipelineReplayStep } from '../../lib/memoIcPack';
import { type RulingDecision } from '../../lib/dealState';
import { type AdverseRegisterItem, type AdverseSeverity } from '../../lib/adverseRegister';

export function mergeMemoPartial(base: Startup, partial: MemoPartialPayload | null): Startup {
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

export function memoGeneratingDetailForVariant(variant: DecisionBadgeVariant): string {
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

export function memoSourceRows(startup: Startup) {
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

/**
 * The operator's typed re-review notes, without the fetched-link content blocks
 * the backend appends after them. Used to prefill the next re-review so context
 * carries forward instead of being silently overwritten.
 */
export function operatorTypedContext(startup: Startup | null | undefined): string {
  const raw = startup?.scout.operator_context ?? '';
  return raw.split('\n\n[Content of operator-provided link ')[0].trim();
}

export function analystContextSections(startup: Startup | null | undefined): Array<{ title: string; body: string }> {
  const raw = startup?.scout.operator_context?.trim();
  if (!raw) return [];
  const marker = /\n\n\[Content of operator-provided link ([^\]]+)\]\n/g;
  const sections: Array<{ title: string; body: string }> = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = marker.exec(raw)) !== null) {
    const previous = raw.slice(lastIndex, match.index).trim();
    if (previous) {
      sections.push({
        title: sections.length === 0 ? 'Submitted context' : 'Context note',
        body: previous,
      });
    }
    const url = match[1]?.trim() || 'Operator-provided link';
    const bodyStart = marker.lastIndex;
    const next = marker.exec(raw);
    const bodyEnd = next ? next.index : raw.length;
    marker.lastIndex = bodyEnd;
    const body = raw.slice(bodyStart, bodyEnd).trim();
    if (body) sections.push({ title: url, body });
    lastIndex = bodyEnd;
  }

  const tail = raw.slice(lastIndex).trim();
  if (tail) {
    sections.push({
      title: sections.length === 0 ? 'Submitted context' : 'Context note',
      body: tail,
    });
  }

  return sections;
}

export function reviewHasThesisAlignment(r: Review | null | undefined): boolean {
  if (!r) return false;
  return (
    r.thesis_alignment_score != null ||
    (r.thesis_fit_points?.length ?? 0) > 0 ||
    (r.thesis_deviation_points?.length ?? 0) > 0 ||
    r.thesis_matches_fund != null
  );
}

export function normalizeParagraphs(value: unknown): string[] {
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

export function normalizeListItemText(value: unknown): string {
  return String(value ?? "")
    .replace(/^\s*[•·*-]\s+/, "")
    .trim();
}

export function normalizeMemoKey(value: unknown): string {
  return String(value ?? '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

const MEMO_NUMBER_TOKEN_REGEX = /(?:[$€£¥]\s*)?\d[\d,]*(?:\.\d+)?(?:%|x|X|k|K|m|M|b|B)?(?:\/\d+(?:\.\d+)?)?/g;

export function renderWithMonoNumbers(value: unknown): ReactNode {
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

export function partnerDecisionHeadline(startup: Startup): string {
  const rec = startup.partner?.recommendation;
  if (rec == null) return '—';
  return DECISION_LABELS[rec] ?? String(rec);
}

export function toJudgmentReasoning(startup: Startup): string[] {
  const rationale = startup.partner?.decision_rationale;
  if (!rationale) return [];
  return normalizeParagraphs(rationale);
}

export function firstNonEmpty(...values: Array<unknown>): string {
  for (const value of values) {
    const text = String(value ?? '').trim();
    if (text) return text;
  }
  return '';
}

export function getPartnerEconomicBadgeVariant(startup: Startup): 'INVEST' | 'PASS' | 'MONITOR' | null {
  const rec = startup.partner?.recommendation;
  if (rec == null) return null;
  if (rec === 'INVEST') return 'INVEST';
  if (rec === 'PASS') return 'PASS';
  return 'MONITOR';
}

export { buildMemoTags, type MemoTag } from '../../lib/memoTags';

export function memoHeaderThesisLine(startup: Startup): string {
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

export function isLookupStartup(startup: Startup): boolean {
  return (startup.scout.origin_type ?? '').toLowerCase() === 'on_demand_lookup';
}

export function pipelineReplayOneLiner(steps: PipelineReplayStep[]): string {
  if (!steps.length) return '';
  const flow = steps.map((s) => s.label).join(' → ');
  const last = [...steps].reverse().find((s) => s.atDisplay && s.atDisplay !== '—');
  const tail = last?.atDisplay;
  return tail ? `${flow} · ${tail}` : flow;
}

export function decisionLabel(decision: RulingDecision | DecisionHistoryDecision): string {
  if (decision === 'YES') return 'Invest';
  if (decision === 'NO') return 'Pass';
  if (decision === 'ADVANCE') return 'Advance';
  return 'Monitor';
}

export function uniqueRiskItems(startup: Startup | null): { risks: string[]; mitigation: string[] } {
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

export function adverseCoverageKeys(adverseItems: AdverseRegisterItem[]): Set<string> {
  const keys = new Set<string>();
  for (const item of adverseItems) {
    keys.add(item.whyItMatters.toLowerCase());
    keys.add(item.title.toLowerCase());
  }
  return keys;
}

export function isAdverseCovered(text: string, adverseItems: AdverseRegisterItem[]): boolean {
  const key = text.toLowerCase();
  const keys = adverseCoverageKeys(adverseItems);
  if (keys.has(key)) return true;
  return adverseItems.some((item) => {
    const why = item.whyItMatters.toLowerCase();
    return why.includes(key) || key.includes(why);
  });
}

export function missingDataItems(startup: Startup | null, adverseItems: AdverseRegisterItem[]): string[] {
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

export function sourceSupportLine(source: ReturnType<typeof memoSourceRows>[number], showConfidence: boolean): string {
  if (!showConfidence) return source.supports;
  return `${source.supports} · Scout confidence signal`;
}

export function collapseWhitespace(value: unknown): string {
  return String(value ?? '').replace(/\s+/g, ' ').trim();
}

// Truncation is intentionally disabled across the memo — full text is shown everywhere,
// nothing is cut mid-thought. Both helpers keep their signatures (so the many call sites
// stay unchanged) but now just normalize whitespace and return the complete string.
export function clipText(value: unknown, _maxLen?: number): string {
  return collapseWhitespace(value);
}

// A short lede made of WHOLE sentences (never cut mid-thought, never an ellipsis). Used for
// the cover standfirst so it stays a lede, not the full multi-paragraph thesis — the complete
// text still appears in the body sections, so nothing is lost.
export function leadSentences(value: unknown, maxChars = 260): string {
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

export function reviewerMeanScore(rv: SingleReview): number | null {
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
export function buildInvestmentCase(startup: Startup, exclude: string): string[] {
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
export function cleanFactValue(value: unknown): string | null {
  const s = String(value ?? '').trim();
  if (!s) return null;
  if (/^\[?\s*missing/i.test(s)) return null;
  if (['unknown', 'n/a', 'na', 'tbd', 'none', '—', '-'].includes(s.toLowerCase())) return null;
  return s;
}

export function buildSnapshotRows(
  startup: Startup,
  blocker: string,
  omitStandfirst = false,
): Array<{ label: string; text: string }> {
  const whatItDoes = firstNonEmpty(
    startup.scout.solution,
    startup.scout.one_line,
    startup.partner?.snapshot?.one_liner,
  );
  // Under a Decision Stage cover the standfirst already says this — once is enough.
  const standfirst = (startup.scout.one_line ?? '').toString().replace(/\s+/g, ' ').trim();
  const dropWhatItDoes =
    omitStandfirst && whatItDoes.replace(/\s+/g, ' ').trim() === standfirst && standfirst !== '';
  return [
    {
      label: 'What it does',
      text: dropWhatItDoes ? '' : whatItDoes,
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

export interface MemoKiller {
  statement: string;
  severity: AdverseSeverity;
}

/** Ranked, deduped, compressed conviction-limiters. One strong statement beats three similar warnings. */
export function buildKillers(adverse: AdverseRegisterItem[], fallbackRisks: string[]): MemoKiller[] {
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
