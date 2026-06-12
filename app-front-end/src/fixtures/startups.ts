import type { Partner, Review, Startup } from '../types/startup';

/**
 * Hand-built dev fixtures covering every docket row state.
 * Served by src/api/startups.ts when VITE_USE_FIXTURES=1 (dev only —
 * the flag is statically false in production builds, so this module
 * is dead-code-eliminated).
 */

function review(overall: number, extra: Partial<Review> = {}): Review {
  return {
    market_score: overall,
    product_score: overall,
    technical_score: overall,
    execution_score: overall,
    defensibility_score: overall,
    overall_summary: 'Fixture review summary.',
    key_risks: ['Fixture risk one', 'Fixture risk two'],
    verdict: overall >= 7 ? 'STRONG' : overall >= 5 ? 'MEDIUM' : 'WEAK',
    ...extra,
  };
}

function partner(rec: Partner['recommendation'], extra: Partial<Partner> = {}): Partner {
  return {
    recommendation: rec,
    confidence: 0.8,
    decision_rationale: 'Fixture rationale.',
    next_action: 'Fixture next action.',
    ...extra,
  };
}

function fx(
  id: string,
  name: string,
  oneLine: string,
  sector: string,
  overrides: Partial<Startup> = {},
): Startup {
  return {
    id,
    scout: {
      id,
      scout_type: 'market_driven',
      name,
      one_line: oneLine,
      sector,
      why_now: 'Fixture timing thesis.',
      confidence: 0.7,
      funding_stage: 'Seed',
      location: 'Berlin',
      origin_type: 'scout',
    },
    timestamps: { discovered_at: '2026-06-01T09:00:00Z', first_seen_at: '2026-06-01T09:00:00Z' },
    ...overrides,
  };
}

export const fixtureStartups: Startup[] = [
  fx('fx-esc-vantor', 'Vantor Systems', 'Autonomous procurement agents for mid-market manufacturers', 'Industrial AI', {
    review: review(7.4, { reviewer_disagreement: true }),
    partner: partner('INVEST', { human_review_required: true }),
    unresolved_at: '2026-06-08T10:00:00Z',
    queue_reason: 'Reviewers split on defensibility — your ruling resolves it.',
  }),
  fx('fx-esc-brightloom', 'Brightloom AI', 'Demand forecasting copilot for grocery chains', 'Retail ML', {
    review: review(6.8, { reviewer_disagreement: true }),
    partner: partner('MONITOR', { human_review_required: true }),
    unresolved_at: '2026-06-10T10:00:00Z',
    queue_reason: 'Partner confidence below threshold.',
  }),
  fx('fx-invest-cobalt', 'Cobalt Health', 'Claims pre-adjudication for regional payers', 'Health fintech', {
    review: review(8.1),
    partner: partner('INVEST'),
  }),
  fx('fx-invest-helio', 'Heliograph', 'Grid-scale battery telemetry and warranty analytics', 'Energy', {
    review: review(7.9),
    partner: partner('INVEST', { human_review_required: true }),
    human_resolution: { decision: 'YES', resolved_at: '2026-06-09T12:00:00Z' },
  }),
  fx('fx-pass-ferrostack', 'Ferrostack', 'Edge GPU orchestration for robotics fleets', 'Infrastructure', {
    review: review(4.2),
    partner: partner('PASS'),
  }),
  fx('fx-pass-human', 'Quillwright', 'AI contract drafting for boutique law firms', 'Legal tech', {
    review: review(5.5),
    partner: partner('MONITOR', { human_review_required: true }),
    human_resolution: { decision: 'NO', resolved_at: '2026-06-07T12:00:00Z' },
  }),
  fx('fx-monitor-quill', 'Saltmarsh Robotics', 'Autonomous dredging for inland waterways', 'Climate robotics', {
    review: review(6.2),
    partner: partner('MONITOR'),
  }),
  fx('fx-awaiting-northbeam', 'Northbeam Optics', 'Photonic interconnects for AI datacenters', 'Semiconductors', {}),
  fx('fx-awaiting-lookup', 'Mistral Forge', 'On-prem fine-tuning appliances for banks', 'Enterprise AI', {
    scout: {
      id: 'fx-awaiting-lookup',
      scout_type: 'lookup',
      name: 'Mistral Forge',
      one_line: 'On-prem fine-tuning appliances for banks',
      sector: 'Enterprise AI',
      why_now: 'Fixture timing thesis.',
      confidence: 0.4,
      origin_type: 'lookup',
      lookup_id: 'fx-lookup-1',
      resolution_status: 'PARTIAL',
    },
  }),
  fx('fx-undecided-arcfin', 'Arcfin Labs', 'Real-time treasury hedging for marketplaces', 'Fintech', {
    review: review(7.0),
  }),
  fx(
    'fx-undecided-longname',
    'Extraordinarily Long Company Name Industries International Holdings',
    'A deliberately verbose one-line description engineered to overflow and verify truncation behaviour in narrow docket columns',
    'Stress testing',
    { review: review(6.5) },
  ),
  fx('fx-monitor-bare', 'Tidemill', '', 'Maritime SaaS', {
    review: review(6.0),
    partner: partner('MONITOR'),
  }),
];
