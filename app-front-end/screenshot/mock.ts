/**
 * Fabricated pipeline world for the screenshot harness — realistic VC content
 * across every state the UI renders (escalated, decided, reviewing, new).
 */
import type { SystemData } from '../src/hooks/useSystemData';
import type { Startup, SingleReview } from '../src/types/startup';

const NOW = Date.now();
const hoursAgo = (h: number) => new Date(NOW - h * 3600_000).toISOString();

function reviewers(scores: Array<[number, number, number, number, number, 'STRONG' | 'MEDIUM' | 'WEAK', string]>): SingleReview[] {
  const types = ['DefaultReviewer', 'SkepticalReviewer', 'OpportunistReviewer'] as const;
  return scores.map(([market, product, technical, execution, defensibility, verdict, summary], i) => ({
    reviewer_type: types[i],
    market_score: market,
    product_score: product,
    technical_score: technical,
    execution_score: execution,
    defensibility_score: defensibility,
    verdict,
    overall_summary: summary,
    key_risks: [],
    prompt_version: 'v1',
  }));
}

let n = 0;
function startup(partial: Record<string, unknown>): Startup {
  n += 1;
  return { id: `demo-${n}`, ...partial } as unknown as Startup;
}

export const STARTUPS: Startup[] = [
  startup({
    scout: {
      id: 's1', scout_type: 'PainPointScout', name: 'Hexigone Inhibitors Limited',
      one_line: 'Smart-release corrosion inhibitors replacing chromate coatings for industrial steel.',
      sector: 'Industrial chemicals & coatings', funding_stage: 'Seed', location: 'West Wales, United Kingdom',
      problem: 'Chromate-based anti-corrosion coatings are being banned across the EU, leaving heavy industry without a proven replacement.',
      solution: 'Patented smart-release inhibitor pigments that activate on corrosion onset, drop-in compatible with existing coating lines.',
      target_users: 'Industrial coating formulators and steel asset owners.',
      why_now: 'REACH restrictions force chromate phase-out by 2027; formulators are qualifying replacements now.',
      confidence: 0.58, est_tam: '$2.1B', primary_thesis: 'Regulatory forcing-function creates a rare wedge into a conservative supply chain.',
      biggest_unknown: 'Qualification cycles with tier-one formulators are 18–24 months; no public design win yet.',
      references: ['hexigone.com', 'Innovate UK grant record', 'European Coatings Journal coverage'],
    },
    review: {
      overall_score: 6.8, thesis_alignment_score: 0.72, reviewer_disagreement: true, consensus_verdict: 'MEDIUM',
      overall_summary: 'Credible chemistry with a regulatory tailwind, held back by long qualification cycles and thin commercial evidence.',
      reviews: reviewers([
        [7, 7, 8, 6, 7, 'STRONG', 'Regulatory deadline gives this a real wedge; IP position looks defensible.'],
        [5, 6, 7, 4, 6, 'WEAK', 'No design win after four years; industrial sales cycles will outlast the runway.'],
        [8, 7, 8, 6, 7, 'STRONG', 'If one tier-one formulator qualifies, the category flips fast.'],
      ]),
      investment_thesis: [
        'Chromate phase-out is a forced migration worth $2B+ in re-formulation spend.',
        'Smart-release chemistry is patent-protected and drop-in compatible — low switching friction.',
      ],
      key_risks: ['18–24 month qualification cycles against a 14-month runway', 'Single-product dependence'],
      diligence_red_flags: ['Missing: signed LOI or design win with a tier-one formulator'],
      team_analysis: ['Founder is ex-AkzoNobel formulation lead; commercial hire still open.'],
      competition_analysis: ['Incumbents reformulating in-house; two funded competitors at earlier TRL.'],
      business_model_analysis: ['Pigment supply at 38% gross margin, licensing upside on volume.'],
      improvement_to_9: ['A signed qualification agreement with a top-five formulator.'],
      risk_mitigation: ['Bridge through Innovate UK non-dilutive grants during qualification.'],
      aethria_view: {
        headline: 'A regulatory forcing-function bet with one decisive unknown.',
        focal_question: 'Does any tier-one formulator commit to qualification before the runway forces a raise?',
        thesis_fit_line: 'Fits the industrial-decarbonisation sleeve of the mandate.',
      },
    },
    partner: {
      recommendation: 'MONITOR', human_review_required: true, confidence: 0.62,
      decision_rationale: 'The regulatory wedge is real and the chemistry is differentiated, but conviction is capped by the absence of a single commercial proof point. Reviewers split on whether the runway survives the qualification cycle. Escalating: the mandate prizes industrial decarbonisation, and a pass here forecloses a position that may not be available post-design-win.',
      decision_drivers: ['Regulatory deadline (REACH 2027)', 'No tier-one design win', 'Reviewer split on runway risk'],
      thesis: 'Forced chromate migration creates a rare entry into conservative coating supply chains.',
      why_this_matters: 'Post-design-win, this round will be unavailable at seed pricing.',
      snapshot: { one_liner: 'Smart-release anti-corrosion pigments', key_signal: 'REACH phase-out hard deadline' },
      risks: ['Qualification timeline vs runway'],
    },
    timestamps: { discovered_at: hoursAgo(30), reviewed_at: hoursAgo(26), partnered_at: hoursAgo(24), first_seen_at: hoursAgo(30), unresolved_at: hoursAgo(24) },
  }),
  startup({
    scout: {
      id: 's2', scout_type: 'MarketDrivenScout', name: 'Lumen Grid',
      one_line: 'Grid-edge orchestration software for commercial battery fleets.',
      sector: 'Climate · Energy software', funding_stage: 'Seed', location: 'Amsterdam, Netherlands',
      why_now: 'Negative electricity pricing events tripled in 2025; batteries without orchestration lose money.',
      confidence: 0.81, est_tam: '$6.4B',
    },
    review: {
      overall_score: 8.2, thesis_alignment_score: 0.86, reviewer_disagreement: false, consensus_verdict: 'STRONG',
      overall_summary: 'Strong founder-market fit, live revenue, and a structural tailwind. Cleanest deal in the current cohort.',
      reviews: reviewers([
        [8, 8, 8, 9, 7, 'STRONG', 'Live with 11 fleet operators; net revenue retention already above 130%.'],
        [8, 7, 8, 8, 7, 'STRONG', 'Defensibility rests on data network effects that are real but early.'],
        [9, 8, 8, 9, 8, 'STRONG', 'The category winner profile: commercial pull, not push.'],
      ]),
      aethria_view: { headline: 'The cohort’s cleanest conviction.', focal_question: 'Can pricing power hold as utilities build in-house?' },
    },
    partner: {
      recommendation: 'INVEST', human_review_required: false, confidence: 0.84,
      decision_rationale: 'Meets every mandate gate with live commercial proof.',
      snapshot: { one_liner: 'Battery fleet orchestration', key_signal: '130% NRR at seed' },
    },
    timestamps: { discovered_at: hoursAgo(70), reviewed_at: hoursAgo(66), partnered_at: hoursAgo(60), first_seen_at: hoursAgo(70) },
  }),
  startup({
    scout: {
      id: 's3', scout_type: 'BuilderTechnicalScout', name: 'Biasol',
      one_line: 'Industrial HVAC heat-recovery retrofits financed as a service.',
      sector: 'Industrial equipment', funding_stage: 'Pre-seed', location: 'Copenhagen, Denmark',
      why_now: 'EU industrial energy-efficiency directive mandates audits from 2026.',
      confidence: 0.62,
    },
    review: {
      overall_score: 6.3, thesis_alignment_score: 0.64, reviewer_disagreement: false, consensus_verdict: 'MEDIUM',
      overall_summary: 'Sound unit economics, capital-heavy model that may not fit a seed fund profile.',
      reviews: reviewers([
        [6, 6, 7, 6, 6, 'MEDIUM', 'Works, but balance-sheet intensity caps venture upside.'],
        [6, 6, 6, 6, 5, 'MEDIUM', 'Service margin defensible; hardware is commodity.'],
        [7, 6, 7, 7, 6, 'MEDIUM', 'Regulatory pull is real; financing partner would change the math.'],
      ]),
      aethria_view: { focal_question: 'Does an infrastructure co-investor remove the balance-sheet drag?' },
    },
    partner: {
      recommendation: 'MONITOR', human_review_required: false, confidence: 0.66,
      decision_rationale: 'Watch for a financing partnership that converts this to an asset-light model.',
      snapshot: { one_liner: 'Heat-recovery-as-a-service', key_signal: 'EU audit mandate 2026' },
    },
    timestamps: { discovered_at: hoursAgo(13), reviewed_at: hoursAgo(12), partnered_at: hoursAgo(11), first_seen_at: hoursAgo(13) },
  }),
  startup({
    scout: {
      id: 's4', scout_type: 'ContrarianScout', name: 'Fergal',
      one_line: 'Agentic compliance filing for cross-border B2B SaaS.',
      sector: 'B2B SaaS · AI', funding_stage: 'Seed', location: 'Dublin, Ireland',
      why_now: 'E-invoicing mandates arrive in 14 EU states through 2027.',
      confidence: 0.49,
    },
    review: {
      overall_score: 5.0, thesis_alignment_score: 0.41, reviewer_disagreement: true, consensus_verdict: 'WEAK',
      overall_summary: 'Crowded wedge; incumbents bundle this for free.',
      reviews: reviewers([
        [5, 5, 6, 5, 4, 'WEAK', 'Avalara and the ERPs will bundle this.'],
        [4, 5, 5, 4, 4, 'WEAK', 'No moat visible beyond speed of shipping.'],
        [6, 6, 6, 6, 5, 'MEDIUM', 'Wedge could work if they win the mid-market ERP channel.'],
      ]),
    },
    partner: {
      recommendation: 'PASS', human_review_required: false, confidence: 0.71,
      decision_rationale: 'Mandate conflict: incumbent-bundled category with weak defensibility.',
      snapshot: { one_liner: 'Compliance filing agents', key_signal: 'Reviewer split on channel wedge' },
    },
    timestamps: { discovered_at: hoursAgo(50), reviewed_at: hoursAgo(48), partnered_at: hoursAgo(47), first_seen_at: hoursAgo(50) },
  }),
  startup({
    scout: {
      id: 's5', scout_type: 'MarketDrivenScout', name: 'Veeve',
      one_line: 'Realtime voice agents for field-service dispatch.',
      sector: 'AI · Vertical SaaS', funding_stage: 'Seed', location: 'Berlin, Germany',
      why_now: 'Field-service labour shortage meets sub-300ms voice latency.',
      confidence: 0.66,
    },
    review: {
      overall_score: 6.3, thesis_alignment_score: 0.69, reviewer_disagreement: false, consensus_verdict: 'MEDIUM',
      overall_summary: 'Strong early pull in HVAC dispatch; model-layer dependence is the open risk.',
      reviews: reviewers([
        [7, 6, 6, 7, 5, 'MEDIUM', 'Real usage, thin moat.'],
        [6, 6, 6, 6, 5, 'MEDIUM', 'Wrapper risk priced in; distribution is the bet.'],
        [7, 7, 6, 7, 6, 'STRONG', 'Vertical depth in dispatch workflows is underrated.'],
      ]),
    },
    partner: {
      recommendation: 'MONITOR', human_review_required: true, confidence: 0.58,
      decision_rationale: 'Escalated: mandate is overweight AI application layer this quarter — concentration call belongs to the principal.',
      snapshot: { one_liner: 'Voice agents for dispatch', key_signal: 'Concentration gate triggered' },
    },
    timestamps: { discovered_at: hoursAgo(20), reviewed_at: hoursAgo(18), partnered_at: hoursAgo(16), first_seen_at: hoursAgo(20), unresolved_at: hoursAgo(16) },
  }),
  startup({
    scout: {
      id: 's6', scout_type: 'PainPointScout', name: 'Northcache',
      one_line: 'Sovereign edge caching for regulated EU workloads.',
      sector: 'Infrastructure', funding_stage: 'Pre-seed', location: 'Helsinki, Finland',
      why_now: 'EU data-sovereignty rulings push regulated workloads off US CDNs.',
      confidence: 0.54,
    },
    is_new_to_user: true,
    timestamps: { discovered_at: hoursAgo(3), first_seen_at: hoursAgo(3) },
  }),
  startup({
    scout: {
      id: 's7', scout_type: 'BuilderTechnicalScout', name: 'Mighty Buildings',
      one_line: '3D-printed prefab panels for low-carbon housing.',
      sector: 'Climate · Construction', funding_stage: 'Series A', location: 'Oakland, United States',
      why_now: 'Housing shortage plus embodied-carbon rules in CA/EU.',
      confidence: 0.6,
    },
    review: {
      overall_score: 6.3, thesis_alignment_score: 0.55, reviewer_disagreement: false, consensus_verdict: 'MEDIUM',
      overall_summary: 'Impressive tech; capex profile outside mandate stage focus.',
      reviews: reviewers([
        [6, 7, 7, 5, 6, 'MEDIUM', 'Stage and capex outside sweet spot.'],
        [6, 6, 7, 5, 6, 'MEDIUM', 'Factory utilisation is the whole ballgame.'],
        [7, 7, 7, 6, 6, 'MEDIUM', 'Category will matter; entry point is wrong for us.'],
      ]),
    },
    partner: {
      recommendation: 'MONITOR', human_review_required: false, confidence: 0.6,
      decision_rationale: 'Outside stage focus; keep for thesis intelligence.',
      snapshot: { one_liner: '3D-printed prefab housing', key_signal: 'Stage misfit' },
    },
    timestamps: { discovered_at: hoursAgo(90), reviewed_at: hoursAgo(88), partnered_at: hoursAgo(86), first_seen_at: hoursAgo(90) },
  }),
  startup({
    scout: {
      id: 's8', scout_type: 'ContrarianScout', name: 'Pry Financials',
      one_line: 'CFO copilot for seed-stage startups.',
      sector: 'B2B SaaS · Fintech', funding_stage: 'Seed', location: 'London, United Kingdom',
      why_now: 'Fractional CFO costs rising; founders self-serve.',
      confidence: 0.45,
    },
    review: {
      overall_score: 5.3, thesis_alignment_score: 0.4, reviewer_disagreement: true, consensus_verdict: 'WEAK',
      overall_summary: 'Tarpit category — high churn, low willingness to pay.',
      reviews: reviewers([
        [5, 5, 5, 6, 4, 'WEAK', 'Graveyard category.'],
        [4, 5, 5, 5, 4, 'WEAK', 'Churns with every finance hire.'],
        [6, 6, 6, 6, 5, 'MEDIUM', 'Could work as a wedge into payments.'],
      ]),
    },
    partner: {
      recommendation: 'PASS', human_review_required: false, confidence: 0.74,
      decision_rationale: 'Churn structure conflicts with the mandate quality bar.',
      snapshot: { one_liner: 'CFO copilot', key_signal: 'Tarpit churn profile' },
    },
    human_resolution: { decision: 'NO', notes: 'Agree with pass — category churn is structural.', resolved_at: hoursAgo(40) },
    timestamps: { discovered_at: hoursAgo(55), reviewed_at: hoursAgo(52), partnered_at: hoursAgo(50), first_seen_at: hoursAgo(55) },
  }),
];

export const MOCK_SYSTEM_DATA: SystemData = {
  startups: STARTUPS,
  escalations: [],
  signals: [
    { id: 'sig1', startup_id: 'demo-2', signal_type: 'funding_round', description: 'Lumen Grid named in Tech.eu as raising a competitive seed extension.', detected_at: hoursAgo(6), tracker_agent_id: 'PortfolioTracker' },
    { id: 'sig2', startup_id: 'demo-1', signal_type: 'regulatory', description: 'ECHA confirms chromate authorisation sunset date — accelerates Hexigone’s wedge.', detected_at: hoursAgo(11), tracker_agent_id: 'PortfolioTracker' },
    { id: 'sig3', startup_id: 'demo-5', signal_type: 'competitor', description: 'Salesloft announces field-service voice agent pilot.', detected_at: hoursAgo(28), tracker_agent_id: 'PortfolioTracker' },
  ],
  metaReports: [
    { cycle_number: 12, ran_at: hoursAgo(22), mutations_applied: [], weight_updates: [], calibration_changes: [], no_action_reasons: ['Guardrail: insufficient new resolutions since cycle 11.'], prompt_proposals: [] } as never,
  ],
  rejectionAnalytics: {
    most_common_red_flags: [
      { flag: 'no_commercial_proof', count: 9 },
      { flag: 'incumbent_bundling_risk', count: 7 },
      { flag: 'capex_intensity', count: 5 },
      { flag: 'single_product_dependence', count: 4 },
    ],
    rejection_by_sector: {},
    avg_scores_at_rejection: {},
    most_common_fail_dimensions: [],
  } as never,
  watchlistAnalytics: {
    total: 4, stale: 1, avg_days: 9,
    entries: [
      { startup_id: 'demo-1', startup_name: 'Hexigone Inhibitors Limited', days_on_watchlist: 4, stale_warning: false, signal_count: 1 },
      { startup_id: 'demo-3', startup_name: 'Biasol', days_on_watchlist: 2, stale_warning: false, signal_count: 0 },
      { startup_id: 'demo-5', startup_name: 'Veeve', days_on_watchlist: 6, stale_warning: false, signal_count: 1 },
      { startup_id: 'demo-7', startup_name: 'Mighty Buildings', days_on_watchlist: 16, stale_warning: true, signal_count: 0 },
    ],
  } as never,
  concentrationAnalytics: {
    by_sector: {
      'B2B SaaS': { count: 34, pct_of_total: 26 },
      'AI': { count: 28, pct_of_total: 22 },
      'Climate': { count: 21, pct_of_total: 16 },
      'Infrastructure': { count: 17, pct_of_total: 13 },
      'Fintech': { count: 12, pct_of_total: 9 },
      'Industrial': { count: 10, pct_of_total: 8 },
    },
    most_concentrated_sector: 'B2B SaaS',
    most_concentrated_theme: 'Agentic workflows',
    last_updated: hoursAgo(20),
  } as never,
  scoutWeights: { MarketDrivenScout: 0.31, BuilderTechnicalScout: 0.27, PainPointScout: 0.24, ContrarianScout: 0.18 },
  calibrationState: {
    confidence_threshold_override: null,
    reviewer_weak_threshold_override: null,
    reviewer_strong_threshold_override: null,
    last_calibrated_at: hoursAgo(46),
    last_calibrated_cycle: 11,
    calibration_history: [
      { parameter: 'reviewer_strong_threshold', direction: 'tightened', reasoning: 'STRONG verdicts over-issued vs human rulings in cycles 9–10.' },
    ] as never,
  },
  metaPromptState: { active: {}, active_detail: {}, pending: [] },
  metaEvalSet: { startup_ids: [], count: 0, max: 50 },
  systemHealth: {
    calibration_warning: null,
    pending_escalations: 2,
    queue_depths: { unreviewed: 1, undecided: 0, watchlist: 4 },
    budget_status: [],
  } as never,
  metaInsights: null,
  fundThesisRuntime: {
    mode: 'active', thesis_ready: true, active_version_number: 3, thesis_mode: 'embedding',
    parsed_json: {
      fund_name: "Aethria's Fund Thesis",
      sectors: ['B2B SaaS', 'AI', 'Climate'],
      stage_focus: ['Pre-seed', 'Seed'],
      geography: ['Europe', 'UK/Ireland'],
      exclusions: ['Crypto', 'Consumer social'],
      preferences: [
        'We back European founders applying applied AI to unglamorous B2B workflows — vertical software where the wedge is a measurable operational saving, not a platform promise.',
        'Recurring revenue or strong usage retention by seed',
        'Founder-led sales with at least two reference customers',
      ],
      risk_profile: 'balanced',
      check_size_min: 250_000,
      check_size_max: 2_000_000,
      ownership_target: 8,
    },
    alignment_stats: { pct_matching_thesis: 72, avg_alignment_score: 0.68, reviewed_with_thesis_count: 118, drift_vs_previous: 0.04 },
    version_timeline: [
      { id: 'v3', version_number: 3, is_active: true, created_at: hoursAgo(300) },
      { id: 'v2', version_number: 2, is_active: false, created_at: hoursAgo(1100) },
    ],
  } as never,
  fundThesisRuntimeLoading: false,
  fundThesisRuntimeError: null,
  settings: {
    fund_identity: { fund_name: "Aethria's Fund Thesis", stage_focus: 'Pre-seed', geographic_focus: 'Europe' },
    cost_budget: { enabled: false, max_tokens_per_run: 200000, daily_cost_ceiling: 10, weekly_cost_ceiling: 50, cooldown_seconds: 600 },
    agent_config: {
      scouts_enabled: true, reviewers_enabled: true, partners_enabled: true,
      max_agents_per_run: 4, confidence_threshold: 0.55, scout_region: 'europe',
    },
    portfolio: { auto_watchlist: true, signal_scan_frequency: 'daily', memo_verbosity: 'standard' },
    system_health: { calibration_warning: null, pending_escalations: 2, queue_depths: { unreviewed: 1, undecided: 0, watchlist: 4 }, budget_status: [] },
  } as never,
  pendingEscalationCount: 2,
  startupsError: null,
  liveGate: { tabVisible: true, userActive: true },
};

const json = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });

/** Intercept the API the components call directly (queries not fed via SystemData). */
export function installMockApi() {
  const realFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    if (url.includes('/api/agents/status')) {
      return json({ worker_ready: true, supabase_configured: true, openai_configured: true, agents_will_run: true, thesis_ready: true, mandate_published: true });
    }
    if (url.includes('/api/agents/loop-status')) return json({ loop_alive: true, agents_enabled: true });
    if (url.includes('/api/fund-thesis/summary') || url.includes('/api/fund-thesis/active')) {
      return json({
        active_version_id: 'v3', active_version_number: 3,
        parsed_json: { fund_name: "Aethria's Fund Thesis", sectors: ['B2B SaaS', 'AI', 'Climate'], stage_focus: ['Pre-seed', 'Seed'], geography: ['Europe', 'UK/Ireland'] },
      });
    }
    if (url.includes('/api/fund-thesis/runtime')) return json(MOCK_SYSTEM_DATA.fundThesisRuntime);
    if (/\/api\/fund-thesis\/?($|\?)/.test(url)) {
      return json({
        active_version_id: 'v3', active_version_number: 3,
        parsed_json: { fund_name: "Aethria's Fund Thesis", sectors: ['B2B SaaS', 'AI', 'Climate'], stage_focus: ['Pre-seed', 'Seed'], geography: ['Europe', 'UK/Ireland'] },
      });
    }
    if (url.includes('/api/activity/summary')) {
      return json({ found: 12, reviewed: 8, decided: 5, agent_decided: 5, human_reviewed: 1, escalations: 2 });
    }
    if (url.includes('/api/activity/seen')) return json({});
    if (url.includes('/api/escalations')) return json([]);
    if (/\/api\/startups\/[^/]+\/memo/.test(url)) return json({ status: 'ready' });
    const detail = url.match(/\/api\/startups\/([^/?]+)$/);
    if (detail) {
      const found = STARTUPS.find((s) => s.id === decodeURIComponent(detail[1]));
      if (found) return json(found);
    }
    if (url.includes('/api/settings')) return json(MOCK_SYSTEM_DATA.settings);
    if (url.includes('/api/')) return json({});
    return realFetch(input as RequestInfo, init);
  };
}
