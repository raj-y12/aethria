import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchPolicyProposal,
  previewPolicyProposal,
  publishGovernedPolicy,
  reviewPolicyProposal,
  type PolicyProposal,
  type ProposalReviewAction,
} from '../../api/fundIntelligence';

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? value as Record<string, unknown> : {};
}

function stringValue(value: unknown): string | null {
  return typeof value === 'string' && value ? value : null;
}

export default function ProposalReviewDrawer({
  proposal,
  fundConfig,
  onClose,
}: {
  proposal: PolicyProposal;
  fundConfig: Record<string, unknown>;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [action, setAction] = useState<ProposalReviewAction>('accept');
  const [rationale, setRationale] = useState('');
  const [editedPatch, setEditedPatch] = useState(JSON.stringify(proposal.proposed_policy_patch, null, 2));
  const [reviewResult, setReviewResult] = useState<Record<string, unknown> | null>(null);
  const detail = useQuery({
    queryKey: ['fund-intelligence', 'proposal', proposal.policy_proposal_id],
    queryFn: () => fetchPolicyProposal(proposal.policy_proposal_id),
    retry: false,
  });
  const preview = useMutation({ mutationFn: () => previewPolicyProposal(proposal.policy_proposal_id) });
  const patchError = useMemo(() => {
    if (action !== 'edit_and_accept') return null;
    try {
      const parsed = JSON.parse(editedPatch);
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? null : 'Policy patch must be a JSON object.';
    } catch {
      return 'Policy patch is not valid JSON.';
    }
  }, [action, editedPatch]);
  const review = useMutation({
    mutationFn: () => reviewPolicyProposal(proposal.policy_proposal_id, {
      action,
      rationale: rationale.trim(),
      ...(action === 'edit_and_accept' ? { edited_policy_patch: JSON.parse(editedPatch) as Record<string, unknown> } : {}),
    }),
    onSuccess: async (result) => {
      setReviewResult(record(result));
      await queryClient.invalidateQueries({ queryKey: ['fund-intelligence', 'proposals'] });
    },
  });
  const policyVersion = record(reviewResult?.policy_version);
  const policyVersionId = stringValue(policyVersion.governed_policy_version_id);
  const publish = useMutation({
    mutationFn: () => publishGovernedPolicy(policyVersionId!, fundConfig),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['fund-intelligence'] }),
        queryClient.invalidateQueries({ queryKey: ['fund-configuration'] }),
      ]);
    },
  });
  const acceptanceAction = action === 'accept' || action === 'edit_and_accept';
  const canReview = rationale.trim().length >= 3
    && !patchError
    && (!acceptanceAction || preview.isSuccess)
    && !review.isPending;
  const previewCount = Number(record(preview.data).affected_opportunity_count ?? 0);

  return (
    <section className="border-y border-oxford/10 bg-paper" aria-label="Policy proposal review">
      <header className="flex items-start justify-between gap-phi-5 px-phi-5 py-phi-4">
        <div>
          <p className="type-label-section">Proposal review</p>
          <h3 className="mt-phi-2 font-display text-2xl font-medium text-oxford">{proposal.pattern_summary}</h3>
          <p className="type-body mt-phi-2 text-oxford/55">
            {proposal.sample_size} attributed signals · {Math.round(proposal.confidence * 100)}% pattern confidence
          </p>
        </div>
        <button type="button" onClick={onClose} className="type-action border-b border-oxford/15">Close</button>
      </header>

      <div className="border-t border-oxford/10 px-phi-5 py-phi-5">
        {detail.data && 'signals' in detail.data ? (
          <p className="type-meta mb-phi-3 text-oxford/50">
            {Array.isArray((detail.data as unknown as { signals?: unknown[] }).signals)
              ? (detail.data as unknown as { signals: unknown[] }).signals.length
              : 0} linked learning signals
          </p>
        ) : null}
        <div className="grid gap-phi-5 lg:grid-cols-2">
          <div>
            <p className="type-label-section">Proposed policy patch</p>
            <pre className="mt-phi-2 max-h-64 overflow-auto border-l border-oxford/15 pl-phi-3 font-mono text-xs leading-relaxed text-oxford/60">{JSON.stringify(proposal.proposed_policy_patch, null, 2)}</pre>
          </div>
          <div>
            <p className="type-label-section">Limitations</p>
            {proposal.limitations.length ? <ul className="mt-phi-2 space-y-phi-2">{proposal.limitations.map((item) => <li key={item} className="type-body text-oxford/60">{item}</li>)}</ul> : <p className="type-body mt-phi-2 text-oxford/55">No limitations were recorded.</p>}
          </div>
        </div>

        <div className="mt-phi-6 border-y border-oxford/10 py-phi-4">
          <div className="flex flex-wrap items-center justify-between gap-phi-3">
            <div><p className="type-label-section">Impact preview</p><p className="type-body mt-1 text-oxford/55">Bounded replay only; it does not rescore or change production.</p></div>
            <button type="button" onClick={() => preview.mutate()} disabled={preview.isPending} className="type-action border border-oxford/15 px-3 py-2 text-oxford disabled:opacity-35">Run impact preview</button>
          </div>
          {preview.isSuccess ? <p role="status" className="type-body mt-phi-3 text-oxford/65">Preview complete · {previewCount} opportunities affected · automatic rescore disabled.</p> : null}
          {preview.isError ? <p role="alert" className="type-body mt-phi-3 text-signal">Impact preview failed. Acceptance remains disabled.</p> : null}
        </div>

        {!reviewResult ? (
          <div className="mt-phi-5">
            <div className="flex flex-wrap gap-phi-2" role="group" aria-label="Proposal disposition">
              {([['accept', 'Accept'], ['edit_and_accept', 'Edit + accept'], ['defer', 'Defer'], ['reject', 'Reject']] as const).map(([value, label]) => <button key={value} type="button" aria-pressed={action === value} onClick={() => setAction(value)} className={`type-action border px-3 py-2 ${action === value ? 'border-oxford bg-oxford text-paper' : 'border-oxford/15 text-oxford'}`}>{label}</button>)}
            </div>
            {action === 'edit_and_accept' ? <><textarea aria-label="Edited policy patch" value={editedPatch} onChange={(event) => setEditedPatch(event.target.value)} rows={8} className="mt-phi-3 w-full resize-y border border-oxford/15 bg-transparent p-3 font-mono text-xs leading-relaxed text-oxford" />{patchError ? <p role="alert" className="type-body mt-phi-2 text-signal">{patchError}</p> : null}</> : null}
            <textarea aria-label="Review rationale" value={rationale} onChange={(event) => setRationale(event.target.value)} rows={3} placeholder="Attribution, sample quality, limitations, and judgment" className="mt-phi-3 w-full resize-none border border-oxford/15 bg-transparent p-3 text-sm leading-relaxed text-oxford" />
            <button type="button" onClick={() => review.mutate()} disabled={!canReview} className="type-action mt-phi-3 bg-oxford px-4 py-3 text-paper disabled:cursor-not-allowed disabled:opacity-35">
              {action === 'accept' ? 'Accept proposal' : action === 'edit_and_accept' ? 'Accept edited proposal' : action === 'defer' ? 'Defer proposal' : 'Reject proposal'}
            </button>
          </div>
        ) : (
          <div className="mt-phi-5 border-l-2 border-oxford pl-phi-4">
            <p className="type-label-section">Review recorded</p>
            <p className="type-body mt-phi-2 text-oxford/65">Production policy is unchanged. Acceptance created a draft governed policy version; publication is a separate authenticated action.</p>
            {policyVersionId ? <button type="button" onClick={() => publish.mutate()} disabled={publish.isPending || publish.isSuccess} className="type-action mt-phi-3 border border-oxford/15 px-4 py-3 text-oxford disabled:opacity-40">{publish.isSuccess ? 'Policy published' : 'Publish policy version'}</button> : null}
            {publish.isError ? <p role="alert" className="type-body mt-phi-2 text-signal">Publication failed. The accepted draft remains unchanged and can be retried.</p> : null}
          </div>
        )}
      </div>
    </section>
  );
}

