import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { correctClaim, type Claim, type EvidenceLedger } from '../../api/evidence';
import FounderSignalsPanel from './FounderSignalsPanel';

function sourceForClaim(ledger: EvidenceLedger, claim: Claim) {
  const items = ledger.items ?? ledger.evidence_items ?? [];
  const itemMap = new Map(items.map((item) => [item.evidence_item_id, item]));
  const artifactMap = new Map(ledger.artifacts.map((artifact) => [artifact.artifact_id, artifact]));
  return ledger.links
    .filter((link) => link.claim_id === claim.claim_id)
    .map((link) => {
      const item = itemMap.get(link.evidence_item_id);
      const artifact = item ? artifactMap.get(item.artifact_id) : undefined;
      return { link, item, artifact };
    });
}

function ClaimCorrection({ claim, onDone }: { claim: Claim; onDone: () => void }) {
  const [action, setAction] = useState<'withdraw' | 'contradict' | 'mark_stale' | 'supersede'>('mark_stale');
  const [rationale, setRationale] = useState('');
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => correctClaim(claim.claim_id, { action, rationale: rationale.trim() }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['institutional', 'evidence'] });
      onDone();
    },
  });
  return (
    <div className="mt-phi-3 border-t border-oxford/10 pt-phi-3">
      <div className="grid gap-phi-3 sm:grid-cols-[150px_1fr]">
        <select aria-label="Correction action" value={action} onChange={(event) => setAction(event.target.value as typeof action)} className="border border-oxford/15 bg-paper px-2 py-2 type-action">
          <option value="mark_stale">Mark stale</option>
          <option value="contradict">Contradict</option>
          <option value="withdraw">Withdraw</option>
          <option value="supersede">Supersede</option>
        </select>
        <input aria-label="Correction rationale" value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Why this claim changed" className="border border-oxford/15 bg-transparent px-3 py-2 text-sm text-oxford" />
      </div>
      <div className="mt-phi-2 flex gap-phi-2">
        <button type="button" onClick={() => mutation.mutate()} disabled={rationale.trim().length < 3 || mutation.isPending} className="type-action bg-oxford px-3 py-2 text-paper disabled:opacity-35">Record correction</button>
        <button type="button" onClick={onDone} className="type-action border-b border-oxford/15">Cancel</button>
      </div>
    </div>
  );
}

export default function ClaimEvidenceLedger({ ledger, readOnly = false }: { ledger: EvidenceLedger; readOnly?: boolean }) {
  const [correctingClaimId, setCorrectingClaimId] = useState<string | null>(null);
  const items = ledger.items ?? ledger.evidence_items ?? [];
  const currentClaims = ledger.claims.filter((claim) => claim.status === 'current');
  return (
    <div className="space-y-phi-6">
      <FounderSignalsPanel claims={ledger.claims} links={ledger.links} items={items} />
      <section aria-label="Claim evidence ledger">
        <div className="flex items-baseline justify-between gap-phi-4">
          <p className="type-label-section">Claim ledger</p>
          <span className="type-meta text-oxford/50">{currentClaims.length} current · {ledger.artifacts.length} artifacts</span>
        </div>
        {ledger.claims.length === 0 ? (
          <p className="type-body mt-phi-3 text-oxford/55">No structured claims have been recorded for this opportunity.</p>
        ) : (
          <div className="mt-phi-3 divide-y divide-oxford/10 border-y border-oxford/10">
            {ledger.claims.map((claim) => {
              const sources = sourceForClaim(ledger, claim);
              return (
                <article key={claim.claim_id} className="py-phi-4">
                  <div className="flex flex-wrap items-start justify-between gap-phi-3">
                    <div className="max-w-2xl">
                      <p className="type-status">{claim.claim_type.replace(/_/g, ' ')} · {claim.status}</p>
                      <p className="type-body mt-1 font-medium text-oxford/80">{claim.display_text}</p>
                    </div>
                    {!readOnly && claim.status === 'current' ? (
                      <button type="button" onClick={() => setCorrectingClaimId(claim.claim_id)} className="type-action border-b border-oxford/15">Correct</button>
                    ) : null}
                  </div>
                  <div className="mt-phi-3 space-y-phi-2">
                    {sources.map(({ link, item, artifact }) => (
                      <div key={link.link_id} className="grid gap-phi-2 border-l border-oxford/15 pl-phi-3 sm:grid-cols-[110px_1fr]">
                        <span className="type-meta text-oxford/50">{link.relationship.replace(/_/g, ' ')}</span>
                        <div>
                          <p className="type-body text-oxford/65">{item?.display_excerpt || link.rationale}</p>
                          <p className="type-meta mt-1 text-oxford/45">
                            {artifact?.title || artifact?.artifact_type?.replace(/_/g, ' ') || 'Source unavailable'}
                            {artifact?.trust_class ? ` · ${artifact.trust_class}` : ''}
                          </p>
                        </div>
                      </div>
                    ))}
                    {sources.length === 0 ? <p className="type-meta text-signal">No evidence link recorded.</p> : null}
                  </div>
                  {correctingClaimId === claim.claim_id ? <ClaimCorrection claim={claim} onDone={() => setCorrectingClaimId(null)} /> : null}
                </article>
              );
            })}
          </div>
        )}
        {ledger.plans.length ? (
          <div className="mt-phi-5">
            <p className="type-label-section">Open evidence plans</p>
            <ul className="mt-phi-2 space-y-phi-2">
              {ledger.plans.map((plan) => (
                <li key={plan.evidence_plan_id} className="type-body text-oxford/60">
                  {plan.trigger_type.replace(/_/g, ' ')} · {plan.missing_evidence.join(', ') || 'No named gap'} · {plan.status}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>
    </div>
  );
}

