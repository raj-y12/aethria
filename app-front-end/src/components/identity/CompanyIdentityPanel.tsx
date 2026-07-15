import type { Company, Opportunity } from '../../api/identity';

export default function CompanyIdentityPanel({ company, opportunity }: { company: Company; opportunity: Opportunity }) {
  const rows = [
    ['Canonical domain', company.canonical_domain],
    ['Identity confidence', `${Math.round(company.identity_confidence * 100)}%`],
    ['Decision state', opportunity.decision_state.replace(/_/g, ' ')],
    ['Service level', String(opportunity.service_level)],
    ['Legacy projection', opportunity.legacy_startup_id || 'None'],
  ];
  return (
    <section aria-label="Canonical company identity" className="border-y border-oxford/10 py-phi-4">
      <div className="flex items-baseline justify-between gap-phi-4">
        <div>
          <p className="type-label-section">Canonical identity</p>
          <h3 className="mt-1 font-display text-2xl font-medium text-oxford">{company.canonical_name}</h3>
        </div>
        <span className="type-status">{company.status}</span>
      </div>
      <dl className="mt-phi-4 grid gap-x-phi-5 gap-y-phi-3 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="type-meta text-oxford/50">{label}</dt>
            <dd className="type-body mt-1 break-all text-oxford/75">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
