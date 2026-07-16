import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { deriveOverridePatterns, fetchPolicyProposals, type PolicyProposal } from '../../api/fundIntelligence';
import ProposalReviewDrawer from './ProposalReviewDrawer';

function statusLabel(status: string): string {
  return status.replace(/_/g, ' ').replace(/^./, (value) => value.toUpperCase());
}

export default function ProposalInbox({ fundConfig }: { fundConfig: Record<string, unknown> }) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<PolicyProposal | null>(null);
  const proposals = useQuery({
    queryKey: ['fund-intelligence', 'proposals'],
    queryFn: () => fetchPolicyProposals(undefined, 100),
    staleTime: 15_000,
  });
  const derive = useMutation({
    mutationFn: deriveOverridePatterns,
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['fund-intelligence', 'proposals'] }),
  });

  if (selected) {
    return <ProposalReviewDrawer proposal={selected} fundConfig={fundConfig} onClose={() => setSelected(null)} />;
  }

  return (
    <section className="border-y border-oxford/10 bg-paper" aria-label="Fund Intelligence proposals">
      <header className="flex flex-wrap items-start justify-between gap-phi-4 px-phi-5 py-phi-4">
        <div>
          <p className="type-label-section">Fund Intelligence</p>
          <h3 className="mt-phi-2 font-display text-2xl font-medium text-oxford">Policy proposal inbox</h3>
          <p className="type-body mt-phi-2 max-w-2xl text-oxford/55">Override and outcome patterns produce attributed proposals. Analysis never changes the live policy.</p>
        </div>
        <button type="button" onClick={() => derive.mutate()} disabled={derive.isPending} className="type-action border border-oxford/15 px-3 py-2 text-oxford disabled:opacity-35">Derive override patterns</button>
      </header>
      {proposals.isLoading ? <p className="type-body border-t border-oxford/10 px-phi-5 py-phi-4 text-oxford/55">Loading proposals…</p>
        : proposals.isError ? <p role="alert" className="type-body border-t border-oxford/10 px-phi-5 py-phi-4 text-signal">Fund Intelligence is unavailable. No production policy was changed.</p>
          : (proposals.data?.length ?? 0) === 0 ? <p className="type-body border-t border-oxford/10 px-phi-5 py-phi-4 text-oxford/55">No policy proposals. More attributed human rulings and outcomes may be required.</p>
            : <div className="divide-y divide-oxford/10 border-t border-oxford/10">{proposals.data!.map((proposal) => (
              <article key={proposal.policy_proposal_id} className="grid gap-phi-4 px-phi-5 py-phi-4 lg:grid-cols-[1fr_auto] lg:items-center">
                <div><div className="flex flex-wrap items-center gap-phi-2"><span className="type-status">{statusLabel(proposal.status)}</span><span className="type-meta text-oxford/45">{proposal.sample_size} signals · {Math.round(proposal.confidence * 100)}%</span></div><p className="type-body mt-phi-2 font-medium text-oxford/75">{proposal.pattern_summary}</p><p className="type-meta mt-phi-2 text-oxford/45">Attribution: {proposal.attribution.replace(/_/g, ' ')}</p></div>
                <button type="button" onClick={() => setSelected(proposal)} className="type-action border border-oxford/15 px-3 py-2 text-oxford">Review proposal</button>
              </article>
            ))}</div>}
    </section>
  );
}

