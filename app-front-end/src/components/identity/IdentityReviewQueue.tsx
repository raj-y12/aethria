import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchIdentityCaseGroups,
  fetchObservations,
  resolveIdentityCaseGroup,
  type IdentityCaseGroup,
} from '../../api/identity';
import { retryJob } from '../../api/jobs';
import IdentityResolutionDrawer from './IdentityResolutionDrawer';

export default function IdentityReviewQueue({
  compact = false,
  onClose,
  linkedJobId,
}: {
  compact?: boolean;
  onClose?: () => void;
  linkedJobId?: string | null;
}) {
  const [selected, setSelected] = useState<IdentityCaseGroup | null>(null);
  const queryClient = useQueryClient();
  const retryBlockedJob = useMutation({
    mutationFn: retryJob,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['jobs'] });
      setSelected(null);
    },
  });
  // Grouped by canonical identity (verified domain) so the same company
  // discovered via several observations shows as one review unit instead of
  // one row per duplicate. See docs/known-issues.md "Duplicate companies in
  // the identity review queue".
  const groups = useQuery({
    queryKey: ['identity', 'case-groups', 'open'],
    queryFn: () => fetchIdentityCaseGroups('open', compact ? 20 : 100),
    staleTime: 15_000,
  });
  const observations = useQuery({
    queryKey: ['identity', 'observations', 'needs_review'],
    queryFn: () => fetchObservations(undefined, compact ? 40 : 200),
    staleTime: 15_000,
  });
  const observationMap = useMemo(
    () => new Map((observations.data ?? []).map((item) => [item.observation_id, item])),
    [observations.data],
  );
  const rows = (groups.data ?? []).slice(0, compact ? 3 : 100);
  const totalObservations = (groups.data ?? []).reduce((sum, g) => sum + g.observation_count, 0);

  if (selected) {
    const primaryCase = selected.cases[0];
    return (
      <IdentityResolutionDrawer
        identityCase={primaryCase}
        observation={observationMap.get(primaryCase.observation_id)}
        linkedJobId={linkedJobId}
        onRetryJob={(jobId) => retryBlockedJob.mutate(jobId)}
        onClose={() => setSelected(null)}
        resolveCase={
          selected.cases.length > 1
            ? (input) => resolveIdentityCaseGroup(selected.group_key, input)
            : undefined
        }
        onResolved={() => {
          if (!linkedJobId) setSelected(null);
        }}
      />
    );
  }

  return (
    <section className="border-y border-oxford/10 bg-paper" aria-label="Identity review queue">
      <header className="flex items-start justify-between gap-phi-4 px-phi-5 py-phi-4">
        <div>
          <p className="type-label-section">Identity review</p>
          <p className="type-body mt-1 text-oxford/65">
            {groups.isLoading
              ? 'Loading unresolved observations…'
              : `${rows.length} identit${rows.length === 1 ? 'y' : 'ies'} to review (${totalObservations} observation${totalObservations === 1 ? '' : 's'})`}
          </p>
        </div>
        {onClose ? <button type="button" onClick={onClose} className="type-action border-b border-oxford/15">Close</button> : null}
      </header>

      {groups.isError ? (
        <p className="type-body border-t border-oxford/10 px-phi-5 py-phi-4 text-signal" role="alert">
          Identity review is unavailable. No case state was changed.
        </p>
      ) : rows.length === 0 && !groups.isLoading ? (
        <p className="type-body border-t border-oxford/10 px-phi-5 py-phi-4 text-oxford/65">No open identity cases.</p>
      ) : (
        <div className="divide-y divide-oxford/10 border-t border-oxford/10">
          {rows.map((group) => {
            const primaryCase = group.cases[0];
            const observation = observationMap.get(primaryCase.observation_id);
            const candidateCount = group.cases.reduce((sum, c) => sum + c.candidates.length, 0);
            return (
              <article key={group.group_key} className="flex items-center justify-between gap-phi-4 px-phi-5 py-phi-4">
                <div className="min-w-0">
                  <h3 className="truncate font-sans text-sm font-semibold text-oxford">
                    {group.observed_names[0] || observation?.observed_name || 'Observed company'}
                  </h3>
                  <p className="type-meta mt-1 truncate text-oxford/65">
                    {group.canonical_domain || observation?.observed_domain || 'Domain unconfirmed'} · {candidateCount} candidate{candidateCount === 1 ? '' : 's'}
                    {group.observation_count > 1 ? ` · ${group.observation_count} observations` : ''}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelected(group)}
                  className="type-action shrink-0 border border-oxford/15 px-3 py-2 text-oxford hover:bg-oxford hover:text-paper"
                >
                  Review identity
                </button>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
