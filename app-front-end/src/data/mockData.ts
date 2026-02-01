import type { Startup } from '../types/startup';

// Using the actual data from discoveries.json - GridPulse, PhotonEdge AI, TraceLeaf ESG
export const mockStartups: Startup[] = [
  {
    id: "2a1f3c9e-5b6d-4a9e-8f3a-1e2c5b7d9a0e",
    scout: {
      id: "2a1f3c9e-5b6d-4a9e-8f3a-1e2c5b7d9a0e",
      scout_type: "market_driven",
      name: "GridPulse",
      one_line: "AI-driven microgrid optimizer coordinating solar, storage, and demand response to cut costs, emissions, and outages for commercial and industrial sites.",
      sector: "Energy",
      problem: "DER proliferation and electrification are increasing grid complexity, volatility in energy prices, and outage risk for commercial/industrial sites due to inefficient coordination of solar, storage, and flexible loads.",
      solution: "A SaaS platform with AI-based forecasting, optimal dispatch, and real-time control that integrates with existing EMS/SCADA via vendor-agnostic APIs to minimize energy spend (15-40%), increase reliability, and simplify DER orchestration.",
      target_users: "Mid-market commercial buildings, campuses, data centers, and manufacturing facilities with on-site generation and storage, plus microgrid developers and operators.",
      why_now: "Surging deployment of DER and storage, energy price volatility, and grid modernization policies are driving demand for intelligent, scalable DER orchestration at scale; AI-enabled optimization has matured to produce reliable ROI.",
      confidence: 0.78
    },
    review: {
      market_score: 7,
      product_score: 6,
      technical_score: 6,
      execution_score: 6,
      overall_summary: "GridPulse addresses a large, growing segment (mid-market commercial/industrial sites with on-site generation and storage) with an AI-driven platform for forecasting, optimal dispatch, and real-time control, plus vendor-agnostic EMS/SCADA integration. The opportunity is credible and ROI-driven (15-40% energy spend reduction) if deployments achieve reliable control and data-quality. Moat is moderate, hinging on AI model performance, integration network effects, and deep partnerships with operators and OEMs. Key challenges include complex, multi-vendor integration, safety and reliability requirements for real-time control, cybersecurity, and the long enterprise sales cycle. Success depends on strong pilots, scalable integrations, and strategic partnerships; without those, competition from established EMS vendors and optimization startups could erode differentiation.",
      key_risks: [
        "Integration complexity with diverse EMS/SCADA ecosystems and vendor APIs",
        "Cybersecurity and safety-critical control requirements for real-time dispatch",
        "Reliability and latency constraints under variable DER/grid conditions",
        "Data quality, privacy, and model accuracy driving ROI variability",
        "Long sales cycles and need for strategic partnerships (OEMs, system integrators)",
        "Competition from incumbent EMS providers expanding optimization capabilities",
        "Regulatory and tariff policy changes affecting DER programs and incentives",
        "Dependency on stable API ecosystems; potential vendor lock-in or API deprecation",
        "Required trust and safety assurances to customers for automated control actions"
      ],
      verdict: "MEDIUM"
    },
    timestamps: {
      discovered_at: "2026-01-25T12:31:32.715686",
      reviewed_at: "2026-01-25T12:32:18.254896",
      partnered_at: "2026-01-25T13:24:40.574399"
    },
    partner: {
      decision: "PASS",
      confidence: 8,
      rationale: "Critical risks identified (regulatory or execution impossibility). Average score: 6.2/10. Risk too high for investment.",
      next_action: "Reject due to critical risks",
      human_review_required: false
    }
  },
  {
    id: "e2f1a4b3-9c7e-4d2a-8b6f-1c2d3e4f5a6b",
    scout: {
      id: "e2f1a4b3-9c7e-4d2a-8b6f-1c2d3e4f5a6b",
      scout_type: "builder_technical",
      name: "PhotonEdge AI",
      one_line: "Programmable silicon photonic accelerator delivering ultra-low-power edge AI with on-chip memory and optical interconnect.",
      sector: "AI hardware / edge computing",
      problem: "Running modern neural networks at the edge is power-hungry and bandwidth-limited; sending data to the cloud adds latency, privacy risk, and unreliable connectivity for autonomous and remote devices.",
      solution: "A modular silicon-photonics-based accelerator that uses on-chip optical matrix-multiplication cores coupled to a CMOS backend, with a unified compiler to map models to photonic tensor cores, a scalable optical interconnect to memory, and chiplet-based packaging for OEMs. It delivers order-of-magnitude energy efficiency improvements and predictable latency for real-time inference. Includes firmware/software stack that supports TensorFlow, PyTorch via XLA-like compiler.",
      target_users: "Automotive and drone OEMs, smart camera manufacturers, industrial IoT providers, mobile device makers that require on-device AI inference.",
      why_now: "Advances in silicon photonics, CMOS-compatible fabrication, and optical interconnect density make optical accelerators feasible; increasing demand for on-device AI due to privacy, latency, and 5G/edge compute shift; rising energy costs drive need for ultra-low-power inference.",
      confidence: 0.63
    },
    review: {
      market_score: 6,
      product_score: 6,
      technical_score: 5,
      execution_score: 4,
      overall_summary: "PhotonEdge AI targets a significant but nascent market by leveraging silicon photonics for energy-efficient edge AI. The concept of on-chip optical matrix multiplication with a CMOS backend and chiplet packaging could offer meaningful advantages if technical hurdles are overcome. However, the plan rests on unproven manufacturing maturity, system integration, and a software stack that can run mainstream ML frameworks. Market adoption depends on reliable fabrication, unit economics, and proven performance in automotive and industrial IoT contexts, which remain uncertain. Execution risk is high due to long OEM validation cycles, need for partnerships, and competition from optimized electronic accelerators.",
      key_risks: [
        "Feasibility and manufacturability of dense on-chip photonic tensor cores with CMOS-compatible fabrication and reliable optical interconnects.",
        "System integration risk: memory, optics, CMOS backend, packaging (chiplets) and thermal management.",
        "Cost and yield of photonic silicon process; capital expenditure for fab tooling; supply chain dependency.",
        "Software stack viability: compiler mapping, ML framework support, toolchain maturity, debugging and performance profiling.",
        "Customer adoption risk: long sales cycles in automotive/industrial IoT; certification, reliability, and safety requirements.",
        "Competitive landscape: improvements in electronic accelerators and software optimizations could reduce relative advantage.",
        "IP moat and timing: uncertain patent protection and potential rapid replication by incumbents.",
        "Regulatory, safety, and cybersecurity considerations for autonomous edge devices."
      ],
      verdict: "MEDIUM"
    },
    timestamps: {
      discovered_at: "2026-01-25T12:31:32.718142",
      reviewed_at: "2026-01-25T13:24:52.288133",
      partnered_at: "2026-01-25T13:25:10.577866"
    },
    partner: {
      decision: "PASS",
      confidence: 8,
      rationale: "Critical risks identified (regulatory or execution impossibility). Average score: 5.2/10. Risk too high for investment.",
      next_action: "Reject due to critical risks",
      human_review_required: false
    }
  },
  {
    id: "e4a9d8f0-7c4a-4a2f-9b2d-3f19e7a3f7b9",
    scout: {
      id: "e4a9d8f0-7c4a-4a2f-9b2d-3f19e7a3f7b9",
      scout_type: "market_driven",
      name: "TraceLeaf ESG",
      one_line: "AI-driven ESG data platform for mid-market companies to measure, verify, and report Scope 1-3 emissions with supplier data and a carbon credits marketplace.",
      sector: "Climate tech / ESG data / SaaS",
      problem: "Mid-market companies lack affordable, accurate, end-to-end tools to calculate and report their carbon emissions across scopes, with supplier data and regulatory alignment; current solutions are expensive or incomplete.",
      solution: "An AI-powered platform that ingests ERP/billing data, utility records, and satellite insights to model Scope 1-3 emissions, ties to established frameworks, auto-verifies supplier data, and offers a marketplace for high-quality carbon offsets with API access to ERP systems.",
      target_users: "Mid-market manufacturers, retailers, property managers, and supply-chain-intensive SMEs seeking regulatory compliance and sustainability reporting.",
      why_now: "Regulatory tightening (TCFD, CSRD/EU, SEC climate disclosure rules), growing investor and customer demand for ESG transparency, plus affordable data and AI enable scalable solutions in a large addressable market.",
      confidence: 0.75
    },
    review: {
      market_score: 6,
      product_score: 5,
      technical_score: 6,
      execution_score: 5,
      overall_summary: "TraceLeaf ESG targets a sizable mid-market ESG data and disclosure market driven by regulatory tightening and demand for transparency. The opportunity is credible, but the product's success hinges on delivering credible Scope 1-3 emissions estimation, robust supplier data verification, and a trustworthy carbon offsets marketplace, all while integrating with diverse ERP systems. Technical execution is complex due to data heterogeneity and regulatory alignment across regions, and GTM risk is non-trivial in a crowded competitive space. Without strong data moats, proven accuracy, and strategic partnerships (ERP, utilities, offset providers), the path to scalable adoption remains uncertain. Overall, a moderate-risk opportunity with meaningful upside if key execution risks are mitigated.",
      key_risks: [
        "Data quality and verification of supplier data for accurate Scope 3 accounting",
        "Credibility and audibility of AI-based emission models across Scope 1-3",
        "Regulatory risk and cross-jurisdictional compliance (CSRD, SEC, TCFD alignment)",
        "Integrity, additionality, and verification of carbon offsets in the marketplace",
        "Technical integration complexity with multiple ERPs, utilities, and data sources",
        "Competitive landscape and pricing pressure from established ESG vendors",
        "Go-to-market challenges in mid-market with longer sales cycles and ROI demonstrations"
      ],
      verdict: "MEDIUM"
    },
    timestamps: {
      discovered_at: "2026-01-25T13:25:08.567160",
      reviewed_at: "2026-01-25T14:08:07.609612",
      partnered_at: "2026-01-25T14:08:20.807511"
    },
    partner: {
      decision: "PASS",
      confidence: 8,
      rationale: "Critical risks identified (regulatory or execution impossibility). Average score: 5.5/10. Risk too high for investment.",
      next_action: "Reject due to critical risks",
      human_review_required: false
    }
  }
];
