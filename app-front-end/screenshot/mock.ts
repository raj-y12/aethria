/**
 * Fabricated pipeline world for the screenshot harness — realistic VC content
 * across every state the UI renders (escalated, decided, reviewing, new).
 */
import type { SystemData } from '../src/hooks/useSystemData';
import type { Startup, SingleReview } from '../src/types/startup';

const NOW = Date.now();
const hoursAgo = (h: number) => new Date(NOW - h * 3600_000).toISOString();

function reviewers(
  scores: Array<[number, number, number, number, number, 'STRONG' | 'MEDIUM' | 'WEAK', string, string[]?]>,
): SingleReview[] {
  const types = ['DefaultReviewer', 'SkepticalReviewer', 'OpportunistReviewer'] as const;
  return scores.map(([market, product, technical, execution, defensibility, verdict, summary, risks], i) => ({
    reviewer_type: types[i],
    market_score: market,
    product_score: product,
    technical_score: technical,
    execution_score: execution,
    defensibility_score: defensibility,
    verdict,
    overall_summary: summary,
    key_risks: risks ?? DEFAULT_REVIEWER_RISKS[types[i]],
    prompt_version: 'v1',
  }));
}

/** Every reviewer states its own risks; an empty risk list reads as an unfinished review. */
const DEFAULT_REVIEWER_RISKS: Record<string, string[]> = {
  DefaultReviewer: ['Commercial evidence is thinner than the score implies', 'Concentration in a single design partner'],
  SkepticalReviewer: ['Sales cycle may outlast the current runway', 'No independent verification of the retention claim'],
  OpportunistReviewer: ['Entry price re-rates quickly if the category proves out', 'Round may be unavailable at this stage next quarter'],
};

let n = 0;
function startup(partial: Record<string, unknown>): Startup {
  n += 1;
  return { id: `demo-${n}`, ...partial } as unknown as Startup;
}


/** Fund intelligence — what the meta layer has observed, and what it will not yet claim. */
const FUND_OBSERVATIONS = [
  {
    observation_id: 'obs-1', observation_type: 'criterion_weight_drift', observation_family: 'scoring',
    segment: { sector: 'B2B SaaS', stage: 'Seed' },
    supporting_case_ids: ['demo-2', 'demo-4', 'demo-6', 'demo-8'], contradictory_case_ids: ['demo-7'],
    sample_size: 31, time_window: { from: hoursAgo(24 * 180), to: hoursAgo(12) },
    thesis_versions: ['v2', 'v3'], mandate_versions: ['v3'], policy_versions: ['partner_rules_v1'],
    metric: { mean_execution_at_invest: 7.4, mean_execution_at_pass: 5.1, separation: 2.3 },
    sufficiency: 'moderate', descriptive_confidence: 0.71,
    limitations: ['Descriptive only — no causal claim', 'Single mandate version dominates the window'],
    direction: 'execution weighted above stated mandate weight',
    involved_criteria: ['execution', 'defensibility'], involved_factors: ['founder-led sales', 'reference customers'],
    interpretation_as_of: 'latest_retrospective', interpretation_provenance: [],
  },
  {
    observation_id: 'obs-2', observation_type: 'segment_conversion', observation_family: 'coverage',
    segment: { geography: 'UK/Ireland', stage: 'Pre-seed' },
    supporting_case_ids: ['demo-1', 'demo-4'], contradictory_case_ids: [],
    sample_size: 14, time_window: { from: hoursAgo(24 * 120), to: hoursAgo(30) },
    thesis_versions: ['v3'], mandate_versions: ['v3'], policy_versions: ['partner_rules_v1'],
    metric: { escalation_rate: 0.36, fund_wide_escalation_rate: 0.19 },
    sufficiency: 'emerging', descriptive_confidence: 0.54,
    limitations: ['Sample below the threshold for a stable rate', 'Window overlaps a single sourcing push'],
    direction: 'escalates roughly twice as often as the fund average',
    involved_criteria: ['thesis_alignment'], involved_factors: ['geography', 'stage'],
    interpretation_as_of: 'latest_retrospective', interpretation_provenance: [],
  },
  {
    observation_id: 'obs-3', observation_type: 'reviewer_disagreement', observation_family: 'process',
    segment: { sector: 'Climate · Energy software' },
    supporting_case_ids: ['demo-2', 'demo-3'], contradictory_case_ids: ['demo-5'],
    sample_size: 22, time_window: { from: hoursAgo(24 * 150), to: hoursAgo(18) },
    thesis_versions: ['v2', 'v3'], mandate_versions: ['v3'], policy_versions: ['partner_rules_v1'],
    metric: { disagreement_rate: 0.48, mean_spread: 2.1 },
    sufficiency: 'moderate', descriptive_confidence: 0.66,
    limitations: ['Disagreement is measured on verdict, not on reasoning'],
    direction: 'skeptical and opportunist reviewers split most often here',
    involved_criteria: ['market', 'defensibility'], involved_factors: ['regulatory timing'],
    interpretation_as_of: 'latest_retrospective', interpretation_provenance: [],
  },
];

const FUND_HYPOTHESES = [
  {
    hypothesis_id: 'hyp-1', hypothesis_family: 'scoring',
    statement: 'The fund rules on execution evidence more heavily than the published mandate weighting implies.',
    source_observation_ids: ['obs-1'], source_observation_types: ['criterion_weight_drift'],
    segment: { sector: 'B2B SaaS', stage: 'Seed' },
    supporting_case_ids: ['demo-2', 'demo-4', 'demo-6', 'demo-8'], contradictory_case_ids: ['demo-7'],
    sample_size: 31, sufficiency: 'moderate', descriptive_confidence: 0.71,
    mandate_versions: ['v3'], thesis_versions: ['v2', 'v3'], policy_versions: ['partner_rules_v1'],
    time_window: { from: hoursAgo(24 * 180), to: hoursAgo(12) },
    limitations: ['Descriptive pattern, not a demonstrated cause of outcome quality'],
    status: 'open',
  },
  {
    hypothesis_id: 'hyp-2', hypothesis_family: 'coverage',
    statement: 'Pre-seed UK/Ireland cases reach the human more often than the mandate intends.',
    source_observation_ids: ['obs-2'], source_observation_types: ['segment_conversion'],
    segment: { geography: 'UK/Ireland', stage: 'Pre-seed' },
    supporting_case_ids: ['demo-1', 'demo-4'], contradictory_case_ids: [],
    sample_size: 14, sufficiency: 'emerging', descriptive_confidence: 0.54,
    mandate_versions: ['v3'], thesis_versions: ['v3'], policy_versions: ['partner_rules_v1'],
    time_window: { from: hoursAgo(24 * 120), to: hoursAgo(30) },
    limitations: ['Sample size below the fund threshold for acting on this'],
    status: 'insufficient_basis',
  },
];

export const STARTUPS: Startup[] = [
  startup({
    scout: {
      id: 's1', scout_type: 'PainPointScout', name: 'Calderwell Materials',
      company_resolution: {
        query: 'Calderwell Materials', canonical_name: 'Calderwell Materials',
        website: 'https://calderwellmaterials.com', linkedin_url: 'https://www.linkedin.com/company/calderwell-materials',
        crunchbase_url: 'https://www.crunchbase.com/organization/calderwell-materials',
        founder_names: ['Elin Vaughan'],
        confidence: 0.94, resolution_status: 'FOUND', missing_fields: [],
        queries_used: ['Calderwell Materials funding', 'Calderwell Materials founders'],
        evidence_sources: [
          { url: 'https://calderwellmaterials.com', title: 'Calderwell Materials — company site', source_type: 'company_site', match_score: 0.97, supports: 'identity' },
          { url: 'https://www.crunchbase.com/organization/calderwell-materials', title: 'Calderwell Materials — funding profile', source_type: 'funding_db', match_score: 0.91, supports: 'funding' },
        ],
      },
      founder_resolution: {
        company: 'Calderwell Materials', website: 'https://calderwellmaterials.com',
        resolution_status: 'FOUND', confidence: 0.9, missing_fields: [],
        founders: [
        {
          name: 'Elin Vaughan', role: 'Founder & CSO', location: 'West Wales, United Kingdom',
          previous_employment: ['Coatings formulation lead, industrial chemicals'], education: ['PhD Materials Chemistry, Swansea'], confidence: 0.9,
          evidence: [{ url: 'https://calderwellmaterials.com/team', title: 'Calderwell Materials — team', source_type: 'company_site', supports: 'role' }],
        },
        ],
      },
      one_line: 'Smart-release corrosion inhibitors replacing chromate coatings for industrial steel.',
      sector: 'Industrial chemicals & coatings', funding_stage: 'Seed', location: 'West Wales, United Kingdom',
      problem: 'Chromate-based anti-corrosion coatings are being banned across the EU, leaving heavy industry without a proven replacement.',
      solution: 'Patented smart-release inhibitor pigments that activate on corrosion onset, drop-in compatible with existing coating lines.',
      target_users: 'Industrial coating formulators and steel asset owners.',
      why_now: 'REACH restrictions force chromate phase-out by 2027; formulators are qualifying replacements now.',
      confidence: 0.58, est_tam: '$2.1B', primary_thesis: 'Regulatory forcing-function creates a rare wedge into a conservative supply chain.',
      biggest_unknown: 'Qualification cycles with tier-one formulators are 18–24 months; no public design win yet.',
      references: ['calderwellmaterials.com', 'Innovate UK grant record', 'European Coatings Journal coverage'],
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
      id: 's2', scout_type: 'MarketDrivenScout', name: 'Wickfield Grid',
      company_resolution: {
        query: 'Wickfield Grid', canonical_name: 'Wickfield Grid',
        website: 'https://wickfieldgrid.com', linkedin_url: 'https://www.linkedin.com/company/wickfield-grid',
        crunchbase_url: 'https://www.crunchbase.com/organization/wickfield-grid',
        founder_names: ['Sanne de Vries', 'Thomas Bakker'],
        confidence: 0.94, resolution_status: 'FOUND', missing_fields: [],
        queries_used: ['Wickfield Grid funding', 'Wickfield Grid founders'],
        evidence_sources: [
          { url: 'https://wickfieldgrid.com', title: 'Wickfield Grid — company site', source_type: 'company_site', match_score: 0.97, supports: 'identity' },
          { url: 'https://www.crunchbase.com/organization/wickfield-grid', title: 'Wickfield Grid — funding profile', source_type: 'funding_db', match_score: 0.91, supports: 'funding' },
        ],
      },
      founder_resolution: {
        company: 'Wickfield Grid', website: 'https://wickfieldgrid.com',
        resolution_status: 'FOUND', confidence: 0.9, missing_fields: [],
        founders: [
        {
          name: 'Sanne de Vries', role: 'Co-founder & CEO', location: 'Amsterdam, Netherlands',
          previous_employment: ['Grid flexibility trading'], education: ['MSc Energy Systems, TU Delft'], confidence: 0.9,
          evidence: [{ url: 'https://wickfieldgrid.com/team', title: 'Wickfield Grid — team', source_type: 'company_site', supports: 'role' }],
        },
        {
          name: 'Thomas Bakker', role: 'Co-founder & CTO', location: 'Amsterdam, Netherlands',
          previous_employment: ['Distributed systems, energy markets'], education: ['BSc Computer Science, Utrecht'], confidence: 0.9,
          evidence: [{ url: 'https://wickfieldgrid.com/team', title: 'Wickfield Grid — team', source_type: 'company_site', supports: 'role' }],
        },
        ],
      },
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
    human_resolution: { decision: 'YES', notes: 'Ruled in. Retention evidence held up under reference checks; entered at seed.', resolved_at: hoursAgo(52) },
  }),
  startup({
    scout: {
      id: 's3', scout_type: 'BuilderTechnicalScout', name: 'Kilbride Systems',
      company_resolution: {
        query: 'Kilbride Systems', canonical_name: 'Kilbride Systems',
        website: 'https://kilbridesystems.dk', linkedin_url: 'https://www.linkedin.com/company/kilbride-systems',
        crunchbase_url: 'https://www.crunchbase.com/organization/kilbride-systems',
        founder_names: ['Mads Lindqvist'],
        confidence: 0.94, resolution_status: 'FOUND', missing_fields: [],
        queries_used: ['Kilbride Systems funding', 'Kilbride Systems founders'],
        evidence_sources: [
          { url: 'https://kilbridesystems.dk', title: 'Kilbride Systems — company site', source_type: 'company_site', match_score: 0.97, supports: 'identity' },
          { url: 'https://www.crunchbase.com/organization/kilbride-systems', title: 'Kilbride Systems — funding profile', source_type: 'funding_db', match_score: 0.91, supports: 'funding' },
        ],
      },
      founder_resolution: {
        company: 'Kilbride Systems', website: 'https://kilbridesystems.dk',
        resolution_status: 'FOUND', confidence: 0.9, missing_fields: [],
        founders: [
        {
          name: 'Mads Lindqvist', role: 'Founder & CEO', location: 'Copenhagen, Denmark',
          previous_employment: ['Process automation, food manufacturing'], education: ['MEng Mechanical, DTU'], confidence: 0.9,
          evidence: [{ url: 'https://kilbridesystems.dk/team', title: 'Kilbride Systems — team', source_type: 'company_site', supports: 'role' }],
        },
        ],
      },
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
      id: 's4', scout_type: 'ContrarianScout', name: 'Corrib Analytics',
      company_resolution: {
        query: 'Corrib Analytics', canonical_name: 'Corrib Analytics',
        website: 'https://corribanalytics.ie', linkedin_url: 'https://www.linkedin.com/company/corrib-analytics',
        crunchbase_url: 'https://www.crunchbase.com/organization/corrib-analytics',
        founder_names: ['Aoife Brennan'],
        confidence: 0.94, resolution_status: 'FOUND', missing_fields: [],
        queries_used: ['Corrib Analytics funding', 'Corrib Analytics founders'],
        evidence_sources: [
          { url: 'https://corribanalytics.ie', title: 'Corrib Analytics — company site', source_type: 'company_site', match_score: 0.97, supports: 'identity' },
          { url: 'https://www.crunchbase.com/organization/corrib-analytics', title: 'Corrib Analytics — funding profile', source_type: 'funding_db', match_score: 0.91, supports: 'funding' },
        ],
      },
      founder_resolution: {
        company: 'Corrib Analytics', website: 'https://corribanalytics.ie',
        resolution_status: 'FOUND', confidence: 0.9, missing_fields: [],
        founders: [
        {
          name: 'Aoife Brennan', role: 'Co-founder & CEO', location: 'Dublin, Ireland',
          previous_employment: ['Payments infrastructure'], education: ['BA Computer Science, Trinity College Dublin'], confidence: 0.9,
          evidence: [{ url: 'https://corribanalytics.ie/team', title: 'Corrib Analytics — team', source_type: 'company_site', supports: 'role' }],
        },
        ],
      },
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
      id: 's5', scout_type: 'MarketDrivenScout', name: 'Rheinlab',
      company_resolution: {
        query: 'Rheinlab', canonical_name: 'Rheinlab',
        website: 'https://rheinlab.de', linkedin_url: 'https://www.linkedin.com/company/rheinlab',
        crunchbase_url: 'https://www.crunchbase.com/organization/rheinlab',
        founder_names: ['Jonas Feldmann', 'Lena Hoffmann'],
        confidence: 0.94, resolution_status: 'FOUND', missing_fields: [],
        queries_used: ['Rheinlab funding', 'Rheinlab founders'],
        evidence_sources: [
          { url: 'https://rheinlab.de', title: 'Rheinlab — company site', source_type: 'company_site', match_score: 0.97, supports: 'identity' },
          { url: 'https://www.crunchbase.com/organization/rheinlab', title: 'Rheinlab — funding profile', source_type: 'funding_db', match_score: 0.91, supports: 'funding' },
        ],
      },
      founder_resolution: {
        company: 'Rheinlab', website: 'https://rheinlab.de',
        resolution_status: 'FOUND', confidence: 0.9, missing_fields: [],
        founders: [
        {
          name: 'Jonas Feldmann', role: 'Co-founder & CEO', location: 'Berlin, Germany',
          previous_employment: ['Field-service operations software'], education: ['MSc Informatik, TU Berlin'], confidence: 0.9,
          evidence: [{ url: 'https://rheinlab.de/team', title: 'Rheinlab — team', source_type: 'company_site', supports: 'role' }],
        },
        {
          name: 'Lena Hoffmann', role: 'Co-founder & CTO', location: 'Berlin, Germany',
          previous_employment: ['Speech systems research'], education: ['PhD Computational Linguistics, Heidelberg'], confidence: 0.9,
          evidence: [{ url: 'https://rheinlab.de/team', title: 'Rheinlab — team', source_type: 'company_site', supports: 'role' }],
        },
        ],
      },
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
      id: 's6', scout_type: 'PainPointScout', name: 'Boreal Cache',
      company_resolution: {
        query: 'Boreal Cache', canonical_name: 'Boreal Cache',
        website: 'https://borealcache.fi', linkedin_url: 'https://www.linkedin.com/company/boreal-cache',
        crunchbase_url: 'https://www.crunchbase.com/organization/boreal-cache',
        founder_names: ['Aino Virtanen'],
        confidence: 0.94, resolution_status: 'FOUND', missing_fields: [],
        queries_used: ['Boreal Cache funding', 'Boreal Cache founders'],
        evidence_sources: [
          { url: 'https://borealcache.fi', title: 'Boreal Cache — company site', source_type: 'company_site', match_score: 0.97, supports: 'identity' },
          { url: 'https://www.crunchbase.com/organization/boreal-cache', title: 'Boreal Cache — funding profile', source_type: 'funding_db', match_score: 0.91, supports: 'funding' },
        ],
      },
      founder_resolution: {
        company: 'Boreal Cache', website: 'https://borealcache.fi',
        resolution_status: 'FOUND', confidence: 0.9, missing_fields: [],
        founders: [
        {
          name: 'Aino Virtanen', role: 'Founder & CTO', location: 'Helsinki, Finland',
          previous_employment: ['Edge caching, CDN infrastructure'], education: ['MSc Computer Science, Aalto'], confidence: 0.9,
          evidence: [{ url: 'https://borealcache.fi/team', title: 'Boreal Cache — team', source_type: 'company_site', supports: 'role' }],
        },
        ],
      },
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
      id: 's7', scout_type: 'BuilderTechnicalScout', name: 'Claybourne Build',
      company_resolution: {
        query: 'Claybourne Build', canonical_name: 'Claybourne Build',
        website: 'https://claybournebuild.com', linkedin_url: 'https://www.linkedin.com/company/claybourne-build',
        crunchbase_url: 'https://www.crunchbase.com/organization/claybourne-build',
        founder_names: ['Marcus Reyes'],
        confidence: 0.94, resolution_status: 'FOUND', missing_fields: [],
        queries_used: ['Claybourne Build funding', 'Claybourne Build founders'],
        evidence_sources: [
          { url: 'https://claybournebuild.com', title: 'Claybourne Build — company site', source_type: 'company_site', match_score: 0.97, supports: 'identity' },
          { url: 'https://www.crunchbase.com/organization/claybourne-build', title: 'Claybourne Build — funding profile', source_type: 'funding_db', match_score: 0.91, supports: 'funding' },
        ],
      },
      founder_resolution: {
        company: 'Claybourne Build', website: 'https://claybournebuild.com',
        resolution_status: 'FOUND', confidence: 0.9, missing_fields: [],
        founders: [
        {
          name: 'Marcus Reyes', role: 'Co-founder & CEO', location: 'Oakland, United States',
          previous_employment: ['Modular construction delivery'], education: ['BArch, California Polytechnic'], confidence: 0.9,
          evidence: [{ url: 'https://claybournebuild.com/team', title: 'Claybourne Build — team', source_type: 'company_site', supports: 'role' }],
        },
        ],
      },
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
      id: 's8', scout_type: 'ContrarianScout', name: 'Sablefield Financial',
      company_resolution: {
        query: 'Sablefield Financial', canonical_name: 'Sablefield Financial',
        website: 'https://sablefield.co', linkedin_url: 'https://www.linkedin.com/company/sablefield-financial',
        crunchbase_url: 'https://www.crunchbase.com/organization/sablefield-financial',
        founder_names: ['Priya Raman'],
        confidence: 0.94, resolution_status: 'FOUND', missing_fields: [],
        queries_used: ['Sablefield Financial funding', 'Sablefield Financial founders'],
        evidence_sources: [
          { url: 'https://sablefield.co', title: 'Sablefield Financial — company site', source_type: 'company_site', match_score: 0.97, supports: 'identity' },
          { url: 'https://www.crunchbase.com/organization/sablefield-financial', title: 'Sablefield Financial — funding profile', source_type: 'funding_db', match_score: 0.91, supports: 'funding' },
        ],
      },
      founder_resolution: {
        company: 'Sablefield Financial', website: 'https://sablefield.co',
        resolution_status: 'FOUND', confidence: 0.9, missing_fields: [],
        founders: [
        {
          name: 'Priya Raman', role: 'Founder & CEO', location: 'London, United Kingdom',
          previous_employment: ['Treasury operations, commercial banking'], education: ['MSc Finance, LSE'], confidence: 0.9,
          evidence: [{ url: 'https://sablefield.co/team', title: 'Sablefield Financial — team', source_type: 'company_site', supports: 'role' }],
        },
        ],
      },
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
  escalations: [
    {
      startup_id: 'demo-1', startup_name: 'Calderwell Materials',
      reason: 'Reviewer disagreement above threshold on a mandate-aligned case',
      recommendation: 'MONITOR', confidence: 0.62, escalated_at: hoursAgo(6),
    },
    {
      startup_id: 'demo-5', startup_name: 'Rheinlab',
      reason: 'Conviction sits inside the partner review band',
      recommendation: 'MONITOR', confidence: 0.58, escalated_at: hoursAgo(20),
    },
  ] as never,
  signals: [
    { id: 'sig1', startup_id: 'demo-2', signal_type: 'funding_round', description: 'Wickfield Grid named in Tech.eu as raising a competitive seed extension.', detected_at: hoursAgo(6), tracker_agent_id: 'PortfolioTracker' },
    { id: 'sig2', startup_id: 'demo-1', signal_type: 'regulatory', description: 'ECHA confirms chromate authorisation sunset date — accelerates Calderwell’s wedge.', detected_at: hoursAgo(11), tracker_agent_id: 'PortfolioTracker' },
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
    rejection_by_sector: { 'B2B SaaS': 34, 'AI · Vertical SaaS': 21, 'Climate · Energy software': 18, Infrastructure: 12, 'B2B SaaS · Fintech': 9 },
    avg_scores_at_rejection: { market: 5.4, product: 5.1, technical: 5.8, execution: 4.6, defensibility: 4.9 },
    most_common_fail_dimensions: ['execution', 'defensibility', 'product'],
  } as never,
  watchlistAnalytics: {
    total: 4, stale: 1, avg_days: 9,
    entries: [
      { startup_id: 'demo-1', startup_name: 'Calderwell Materials', days_on_watchlist: 4, stale_warning: false, signal_count: 1 },
      { startup_id: 'demo-3', startup_name: 'Kilbride Systems', days_on_watchlist: 2, stale_warning: false, signal_count: 0 },
      { startup_id: 'demo-5', startup_name: 'Rheinlab', days_on_watchlist: 6, stale_warning: false, signal_count: 1 },
      { startup_id: 'demo-7', startup_name: 'Claybourne Build', days_on_watchlist: 16, stale_warning: true, signal_count: 0 },
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
    budget_status: [
    { name: 'LLM spend', used: 41.28, limit: 120, unit: 'USD', window: 'month' },
    { name: 'Retrieval calls', used: 1840, limit: 5000, unit: 'calls', window: 'month' },
  ] as never,
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
    if (url.includes('/api/escalations')) return json(MOCK_SYSTEM_DATA.escalations);
    if (/\/api\/startups\/[^/]+\/memo/.test(url)) return json({ status: 'ready' });
    const legacyOpportunity = url.match(/\/api\/startups\/([^/?]+)\/opportunity$/);
    if (legacyOpportunity) {
      const legacyId = decodeURIComponent(legacyOpportunity[1]);
      const fixture = STARTUPS.find((item) => item.id === legacyId);
      return json({
        opportunity_id: `opp-${legacyId}`,
        company_id: `company-${legacyId}`,
        context_key: 'default',
        decision_state: fixture?.partner ? 'needs_ruling' : 'awaiting_review',
        service_level: 1,
        legacy_startup_id: legacyId,
        current_evaluation_id: `eval-${legacyId}`,
        current_recommendation_id: `rec-${legacyId}`,
        created_at: hoursAgo(48),
        updated_at: hoursAgo(2),
      });
    }
    const evaluationMatch = url.match(/\/api\/opportunities\/([^/?]+)\/evaluation(?:\?|$)/);
    if (evaluationMatch) {
      const opportunityId = decodeURIComponent(evaluationMatch[1]);
      const legacyId = opportunityId.replace(/^opp-/, '');
      const fixture = STARTUPS.find((item) => item.id === legacyId);
      const recommendation = String(fixture?.partner?.recommendation ?? 'monitor').toLowerCase();
      return json({
        evaluation: {
          evaluation_id: `eval-${legacyId}`,
          evidence_snapshot_hash: 'fixture-snapshot',
          rubric_version: 'fixture-rubric-v1',
          status: 'completed',
          created_at: hoursAgo(3),
        },
        criteria: [
          {
            criterion_assessment_id: `criterion-${legacyId}`,
            criterion: 'thesis_alignment',
            score: 7,
            confidence: 0.78,
            evidence_sufficiency: 'sufficient',
            reasoning: 'Fixture evidence supports the current recommendation.',
            supporting_claim_ids: [`claim-${legacyId}`],
            contradicting_claim_ids: [],
            missing_evidence: [],
            quality_flags: [],
          },
        ],
        recommendation: {
          recommendation_id: `rec-${legacyId}`,
          recommended_state: recommendation === 'pass' || recommendation === 'advance' ? recommendation : 'monitor',
          attention_priority: 2,
          confidence: 0.72,
          decision_drivers: [fixture?.partner?.decision_rationale ?? 'Review the current evidence before advancing.'],
          principal_risks: ['Fixture risk remains subject to diligence.'],
          mandate_conflicts: [],
          missing_information: [],
          change_conditions: [],
          human_review_required: true,
        },
        provenance: { recommendation_origin: 'PARTNER_ANALYSIS' },
      });
    }
    const evidenceMatch = url.match(/\/api\/opportunities\/([^/?]+)\/evidence/);
    if (evidenceMatch) {
      const opportunityId = decodeURIComponent(evidenceMatch[1]);
      const legacyId = opportunityId.replace(/^opp-/, '');
      return json({
        artifacts: [{
          artifact_id: `artifact-${legacyId}`,
          artifact_type: 'company_website',
          source_uri: 'https://example.com/fixture-source',
          title: 'Fixture source',
          trust_class: 'public',
          access_class: 'public',
        }],
        evidence_items: [{
          evidence_item_id: `item-${legacyId}`,
          artifact_id: `artifact-${legacyId}`,
          item_type: 'web_excerpt',
          display_excerpt: 'Fixture source excerpt.',
          verification_state: 'verified',
          source_quality: 0.8,
          extraction_confidence: 0.9,
        }],
        claims: [{
          claim_id: `claim-${legacyId}`,
          company_id: `company-${legacyId}`,
          claim_type: 'company_fact',
          display_text: 'Fixture evidence supports the company overview.',
          assertion_class: 'externally_verified',
          confidence: 0.8,
          material: true,
          status: 'current',
        }],
        claim_evidence_links: [{
          link_id: `link-${legacyId}`,
          claim_id: `claim-${legacyId}`,
          evidence_item_id: `item-${legacyId}`,
          relationship: 'supports',
          support_strength: 0.8,
          rationale: 'Fixture source support.',
        }],
        evidence_plans: [],
      });
    }
    if (/\/api\/opportunities\/[^/?]+\/rulings/.test(url)) return json({ rulings: [] });
    const detail = url.match(/\/api\/startups\/([^/?]+)$/);
    if (detail) {
      const found = STARTUPS.find((s) => s.id === decodeURIComponent(detail[1]));
      if (found) return json(found);
    }
    if (url.includes('/api/outcomes/coverage')) {
      return json({
        eligible_opportunity_count: 18, observed_opportunity_count: 11, coverage_ratio: 0.61,
        outcomes_by_valence: { positive: 5, neutral: 4, negative: 2 },
        causal_inference_supported: false,
        limitations: ['Coverage is descriptive; outcomes are not attributed to the decision that preceded them.'],
      });
    }
    if (url.includes('/api/portfolio/positions')) {
      return json({
        positions: [
          {
            position_id: 'pos-1', opportunity_id: 'opp-2', company_id: 'co-2', ruling_id: 'rul-2',
            status: 'active', legacy_startup_id: 'demo-2',
            canonical_name: 'Wickfield Grid', canonical_domain: 'wickfieldgrid.com',
            entry_rationale: 'Grid-flexibility software with contracted revenue and a defensible data position.',
            investor_confidence: 0.78, entered_at: hoursAgo(52),
          },
        ],
      });
    }
    if (url.includes('/api/fund-intelligence/observations')) return json({ observations: FUND_OBSERVATIONS });
    if (url.includes('/api/fund-intelligence/hypotheses')) return json({ hypotheses: FUND_HYPOTHESES });
    if (url.includes('/api/fund-intelligence/counterfactual-proposals')) return json({ proposals: [] });
    if (url.includes('/api/settings')) return json(MOCK_SYSTEM_DATA.settings);
    if (url.includes('/api/')) return json({});
    return realFetch(input as RequestInfo, init);
  };
}
