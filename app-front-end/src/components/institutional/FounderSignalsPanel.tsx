import type { Claim, ClaimEvidenceLink, EvidenceItem } from '../../api/evidence';

const FOUNDER_SIGNAL_TERMS = [
  'founder', 'team', 'domain', 'insight', 'execution', 'speed', 'customer', 'project', 'interview', 'operator',
];

function isFounderSignal(claim: Claim): boolean {
  const haystack = `${claim.claim_type} ${claim.display_text}`.toLowerCase();
  return FOUNDER_SIGNAL_TERMS.some((term) => haystack.includes(term));
}

export default function FounderSignalsPanel({
  claims,
  links,
  items,
}: {
  claims: Claim[];
  links: ClaimEvidenceLink[];
  items: EvidenceItem[];
}) {
  const itemMap = new Map(items.map((item) => [item.evidence_item_id, item]));
  const signals = claims.filter((claim) => claim.status === 'current' && isFounderSignal(claim));

  return (
    <section className="border-y border-oxford/10 py-phi-4" aria-label="Evidence-backed founder signals">
      <div className="flex items-baseline justify-between gap-phi-4">
        <p className="type-label-section">Founder evidence</p>
        <span className="type-meta text-oxford/65">Only claims tied to a recorded source</span>
      </div>
      {signals.length === 0 ? (
        <p className="type-body mt-phi-3 text-oxford/65">
          No founder-specific claim has enough recorded evidence to display.
        </p>
      ) : (
        <ul className="mt-phi-3 space-y-phi-4">
          {signals.map((claim) => {
            const evidence = links
              .filter((link) => link.claim_id === claim.claim_id)
              .map((link) => itemMap.get(link.evidence_item_id))
              .filter((item): item is EvidenceItem => Boolean(item));
            return (
              <li key={claim.claim_id} className="grid gap-phi-2 sm:grid-cols-[132px_1fr]">
                <div>
                  <p className="type-status">{claim.claim_type.replace(/_/g, ' ')}</p>
                </div>
                <div>
                  <p className="type-body font-medium text-oxford/80">{claim.display_text}</p>
                  {evidence.map((item) => (
                    <blockquote key={item.evidence_item_id} className="mt-phi-2 border-l border-oxford/20 pl-phi-3 type-body text-oxford/65">
                      {item.display_excerpt}
                    </blockquote>
                  ))}
                  {evidence.length === 0 ? (
                    <p className="type-meta mt-phi-2 text-signal">No linked evidence item. Treat as unverified.</p>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
