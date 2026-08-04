import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  resolveIdentityCase,
  type IdentityResolutionCase,
  type IdentityResolutionInput,
  type SourceObservation,
} from '../../api/identity';

interface IdentityResolutionDrawerProps {
  identityCase: IdentityResolutionCase;
  observation?: SourceObservation | null;
  onClose: () => void;
  onResolved?: (result: unknown) => void;
  linkedJobId?: string | null;
  onRetryJob?: (jobId: string) => void;
  /** When this case is one of several observations for the same company,
   * resolving it must transition every linked case to the same company at
   * once (see docs/known-issues.md "Duplicate companies in the identity
   * review queue") — the caller supplies the group-aware resolve call. */
  resolveCase?: (input: IdentityResolutionInput) => Promise<unknown>;
}

type DrawerMode = 'match' | 'create' | 'defer' | 'reject';

function confidenceLabel(value: number): string {
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
}

function reasonLabel(value: string): string {
  return value.replace(/_/g, ' ');
}

export default function IdentityResolutionDrawer({
  identityCase,
  observation,
  onClose,
  onResolved,
  linkedJobId,
  onRetryJob,
  resolveCase,
}: IdentityResolutionDrawerProps) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<DrawerMode>('match');
  const [selectedCompanyId, setSelectedCompanyId] = useState('');
  const [note, setNote] = useState('');
  // Creation is intentionally blank: observed values are evidence, not operator confirmation.
  const [canonicalName, setCanonicalName] = useState('');
  const [canonicalDomain, setCanonicalDomain] = useState('');

  const resolution = useMutation({
    mutationFn: (input: IdentityResolutionInput) =>
      (resolveCase ?? ((i: IdentityResolutionInput) => resolveIdentityCase(identityCase.identity_case_id, i)))(input),
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['identity', 'cases'] }),
        queryClient.invalidateQueries({ queryKey: ['identity', 'observations'] }),
        queryClient.invalidateQueries({ queryKey: ['startups', 'list'] }),
        queryClient.invalidateQueries({ queryKey: ['jobs'] }),
      ]);
      onResolved?.(result);
    },
  });

  const submitMatch = () => {
    if (!selectedCompanyId) return;
    resolution.mutate({
      action: 'match',
      selected_company_id: selectedCompanyId,
      ...(note.trim() ? { resolution_note: note.trim() } : {}),
    });
  };

  const submitCreate = () => {
    if (!canonicalName.trim() || !canonicalDomain.trim()) return;
    resolution.mutate({
      action: 'create',
      canonical_name: canonicalName.trim(),
      canonical_domain: canonicalDomain.trim().replace(/^https?:\/\//, '').replace(/\/$/, ''),
      ...(note.trim() ? { resolution_note: note.trim() } : {}),
    });
  };

  const submitDisposition = (action: 'defer' | 'reject') => {
    resolution.mutate({ action, ...(note.trim() ? { resolution_note: note.trim() } : {}) });
  };

  return (
    <aside className="flex h-full min-h-0 w-full max-w-2xl flex-col bg-paper" aria-label="Resolve company identity">
      <header className="flex items-start justify-between gap-phi-5 border-b border-oxford/10 px-phi-6 py-phi-5">
        <div>
          <p className="type-label-section">Identity review</p>
          <h2 className="mt-phi-2 font-display text-3xl font-medium leading-tight text-oxford">
            {observation?.observed_name || 'Observed company'}
          </h2>
          <p className="type-body mt-phi-2 text-oxford/60">
            {observation?.channel ? `${reasonLabel(observation.channel)} · ` : ''}
            {reasonLabel(identityCase.reason_code)}
          </p>
        </div>
        <button type="button" onClick={onClose} className="type-action border-b border-oxford/15 pb-1">
          Close
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-phi-6 py-phi-5">
        <div className="mb-phi-5 flex flex-wrap gap-phi-2" role="tablist" aria-label="Identity resolution method">
          {([
            ['match', 'Match existing'],
            ['create', 'Create new company'],
            ['defer', 'Defer'],
            ['reject', 'Reject observation'],
          ] as const).map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={mode === value}
              onClick={() => setMode(value)}
              className={`type-action border px-3 py-2 ${mode === value ? 'border-oxford bg-oxford text-paper' : 'border-oxford/15 text-oxford'}`}
            >
              {label}
            </button>
          ))}
        </div>

        {mode === 'match' ? (
          <fieldset>
            <legend className="type-label-section mb-phi-3">Candidate companies</legend>
            <div className="space-y-phi-3">
              {identityCase.candidates.map((candidate) => (
                <label
                  key={candidate.company_id}
                  className={`block cursor-pointer border p-phi-4 transition-colors ${
                    selectedCompanyId === candidate.company_id ? 'border-oxford bg-oxford/[0.04]' : 'border-oxford/10 hover:border-oxford/25'
                  }`}
                >
                  <div className="flex items-start gap-phi-3">
                    <input
                      type="radio"
                      name="identity-candidate"
                      value={candidate.company_id}
                      checked={selectedCompanyId === candidate.company_id}
                      onChange={() => setSelectedCompanyId(candidate.company_id)}
                      aria-label={`${candidate.canonical_name} — ${candidate.canonical_domain}`}
                      className="mt-1 accent-oxford"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-phi-4">
                        <div>
                          <h3 className="font-sans text-base font-semibold text-oxford">{candidate.canonical_name}</h3>
                          <p className="type-meta mt-1 text-oxford/60">{candidate.canonical_domain}</p>
                        </div>
                        <span className="type-status">{confidenceLabel(candidate.confidence)}</span>
                      </div>
                      {candidate.reason ? <p className="type-body mt-phi-2 text-oxford/60">{candidate.reason}</p> : null}
                      {candidate.evidence_urls.length ? (
                        <div className="mt-phi-2 flex flex-wrap gap-x-phi-3 gap-y-1">
                          {candidate.evidence_urls.map((url) => (
                            <a
                              key={url}
                              href={url}
                              target="_blank"
                              rel="noreferrer"
                              className="type-meta border-b border-oxford/20 text-oxford/65 hover:text-oxford"
                            >
                              Evidence source
                            </a>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </div>
                </label>
              ))}
              {identityCase.candidates.length === 0 ? (
                <p className="type-body border-y border-oxford/10 py-phi-4 text-oxford/60">
                  No credible existing match was returned. Create a canonical company or defer this observation.
                </p>
              ) : null}
            </div>
          </fieldset>
        ) : null}

        {mode === 'create' ? (
          <div className="space-y-phi-4">
            <div>
              <label htmlFor="identity-canonical-name" className="type-action">Canonical name</label>
              <input
                id="identity-canonical-name"
                value={canonicalName}
                onChange={(event) => setCanonicalName(event.target.value)}
                className="mt-phi-2 w-full border-0 border-b border-oxford/20 bg-transparent px-0 py-2 text-oxford outline-none focus:border-oxford"
              />
            </div>
            <div>
              <label htmlFor="identity-canonical-domain" className="type-action">Canonical domain</label>
              <input
                id="identity-canonical-domain"
                value={canonicalDomain}
                onChange={(event) => setCanonicalDomain(event.target.value)}
                placeholder="company.com"
                className="mt-phi-2 w-full border-0 border-b border-oxford/20 bg-transparent px-0 py-2 text-oxford outline-none focus:border-oxford"
              />
              <p className="type-meta mt-phi-2 text-oxford/55">Confirm this against an official source before creating the record.</p>
            </div>
          </div>
        ) : null}

        {mode === 'defer' || mode === 'reject' ? (
          <div className="border-y border-oxford/10 py-phi-4">
            <p className="type-body text-oxford/65">
              {mode === 'defer'
                ? 'Defer keeps this observation outside evaluation until an analyst returns with stronger identity evidence.'
                : 'Reject closes this observation as an invalid company record. This does not reject an investment opportunity.'}
            </p>
          </div>
        ) : null}

        <div className="mt-phi-5">
          <label htmlFor="identity-resolution-note" className="type-action">Resolution note</label>
          <textarea
            id="identity-resolution-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={3}
            maxLength={1000}
            placeholder="Evidence used, remaining uncertainty, or reason for disposition."
            className="mt-phi-2 w-full resize-none border border-oxford/15 bg-transparent p-3 text-sm leading-relaxed text-oxford outline-none focus:border-oxford"
          />
        </div>

        {resolution.isError ? (
          <p className="type-body mt-phi-3 text-signal" role="alert">The identity case changed or could not be resolved. Refresh the queue and try again.</p>
        ) : null}
      </div>

      <footer className="border-t border-oxford/10 px-phi-6 py-phi-4">
        {mode === 'match' ? (
          <button
            type="button"
            onClick={submitMatch}
            disabled={!selectedCompanyId || resolution.isPending}
            className="type-action w-full bg-oxford px-4 py-3 text-paper disabled:cursor-not-allowed disabled:opacity-35"
          >
            Match selected company
          </button>
        ) : mode === 'create' ? (
          <button
            type="button"
            onClick={submitCreate}
            disabled={!canonicalName.trim() || !canonicalDomain.trim() || resolution.isPending}
            className="type-action w-full bg-oxford px-4 py-3 text-paper disabled:cursor-not-allowed disabled:opacity-35"
          >
            Confirm new company
          </button>
        ) : (
          <button
            type="button"
            onClick={() => submitDisposition(mode)}
            disabled={resolution.isPending}
            className="type-action w-full border border-oxford/20 px-4 py-3 text-oxford disabled:opacity-35"
          >
            Confirm {mode === 'defer' ? 'deferral' : 'rejection'}
          </button>
        )}
        {resolution.isSuccess && linkedJobId && onRetryJob ? (
          <button
            type="button"
            onClick={() => onRetryJob(linkedJobId)}
            className="type-action mt-phi-2 w-full border border-oxford/20 px-4 py-3 text-oxford"
          >
            Retry blocked lookup
          </button>
        ) : null}
      </footer>
    </aside>
  );
}
