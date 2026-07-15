import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchIdentityCases, fetchObservations, type IdentityResolutionCase } from '../../api/identity';
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
  const [selected, setSelected] = useState<IdentityResolutionCase | null>(null);
  const queryClient = useQueryClient();
  const retryBlockedJob = useMutation({
    mutationFn: retryJob,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['jobs'] });
      setSelected(null);
    },
  });
  const cases = useQuery({
    queryKey: ['identity', 'cases', 'open'],
    queryFn: () => fetchIdentityCases('open', compact ? 20 : 100),
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
  const rows = (cases.data ?? []).slice(0, compact ? 3 : 100);

  if (selected) {
    return (
      <IdentityResolutionDrawer
        identityCase={selected}
        observation={observationMap.get(selected.observation_id)}
        linkedJobId={linkedJobId}
        onRetryJob={(jobId) => retryBlockedJob.mutate(jobId)}
        onClose={() => setSelected(null)}
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
          <p className="type-body mt-1 text-oxford/60">
            {cases.isLoading ? 'Loading unresolved observations…' : `${cases.data?.length ?? 0} observations require an operator ruling`}
          </p>
        </div>
        {onClose ? <button type="button" onClick={onClose} className="type-action border-b border-oxford/15">Close</button> : null}
      </header>

      {cases.isError ? (
        <p className="type-body border-t border-oxford/10 px-phi-5 py-phi-4 text-signal" role="alert">
          Identity review is unavailable. No case state was changed.
        </p>
      ) : rows.length === 0 && !cases.isLoading ? (
        <p className="type-body border-t border-oxford/10 px-phi-5 py-phi-4 text-oxford/55">No open identity cases.</p>
      ) : (
        <div className="divide-y divide-oxford/10 border-t border-oxford/10">
          {rows.map((item) => {
            const observation = observationMap.get(item.observation_id);
            return (
              <article key={item.identity_case_id} className="flex items-center justify-between gap-phi-4 px-phi-5 py-phi-4">
                <div className="min-w-0">
                  <h3 className="truncate font-sans text-sm font-semibold text-oxford">{observation?.observed_name || 'Observed company'}</h3>
                  <p className="type-meta mt-1 truncate text-oxford/55">
                    {observation?.observed_domain || 'Domain unconfirmed'} · {item.candidates.length} candidate{item.candidates.length === 1 ? '' : 's'}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setSelected(item)}
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
