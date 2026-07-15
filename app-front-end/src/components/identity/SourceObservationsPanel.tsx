import type { SourceObservation } from '../../api/identity';

export default function SourceObservationsPanel({ observations }: { observations: SourceObservation[] }) {
  return (
    <section aria-label="Source observations">
      <div className="flex items-baseline justify-between gap-phi-4">
        <p className="type-label-section">Source history</p>
        <span className="type-meta text-oxford/50">{observations.length} preserved observation{observations.length === 1 ? '' : 's'}</span>
      </div>
      {observations.length === 0 ? (
        <p className="type-body mt-phi-3 text-oxford/55">No source observations are available for this company.</p>
      ) : (
        <ol className="mt-phi-3 divide-y divide-oxford/10 border-y border-oxford/10">
          {observations.map((item) => (
            <li key={item.observation_id} className="grid gap-phi-2 py-phi-3 sm:grid-cols-[120px_1fr_auto] sm:items-baseline">
              <span className="type-status">{item.channel.replace(/_/g, ' ')}</span>
              <span className="type-body text-oxford/70">{item.observed_name}{item.observed_domain ? ` · ${item.observed_domain}` : ''}</span>
              <span className="type-meta text-oxford/50">{item.identity_status.replace(/_/g, ' ')}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
