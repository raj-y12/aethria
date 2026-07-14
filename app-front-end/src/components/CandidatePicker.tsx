import { useState, type KeyboardEvent } from 'react';
import { motion } from 'framer-motion';
import type { LookupCandidate } from '../api/startups';
import { productInteraction } from '../design-system/productSystem';
import { domainLabel, evidenceLabels, identityConfidence, isBestIdentityMatch } from '../lib/candidateIdentity';

interface CandidatePickerProps {
  candidates: LookupCandidate[];
  onPick: (candidate: LookupCandidate) => void;
  onRefine: (websiteHint: string) => void;
  busy?: boolean;
  heading?: string;
}

export default function CandidatePicker({ candidates, onPick, onRefine, busy, heading }: CandidatePickerProps) {
  const [refineOpen, setRefineOpen] = useState(false);
  const [website, setWebsite] = useState('');

  const submitRefine = () => {
    const value = website.trim();
    if (value) onRefine(value);
  };
  const onWebsiteKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') submitRefine();
  };

  return (
    <motion.section
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className="candidate-identity mt-phi-3 grid gap-phi-4"
      aria-labelledby="candidate-identity-title"
    >
      <header className="candidate-identity__header flex items-end justify-between gap-phi-4 border-b border-oxford/[0.12] pb-phi-3">
        <div>
          <p className="type-label-section text-oxford/60">Confirm company identity</p>
          <h2 id="candidate-identity-title" className="mt-phi-1 font-serif text-[clamp(1.15rem,2vw,1.5rem)] text-oxford">
            Choose the company you meant
          </h2>
          <p className="mt-phi-1 max-w-prose type-meta text-oxford/60">
            {heading ?? 'These companies share a similar name. Compare their domains and verification evidence.'}
          </p>
        </div>
        <p className="type-meta shrink-0 text-oxford/60">
          {`${candidates.length} plausible ${candidates.length === 1 ? 'identity' : 'identities'}`}
        </p>
      </header>

      <ol className="candidate-identity__list grid gap-phi-2">
        {candidates.map((candidate, index) => {
          const domain = domainLabel(candidate.website);
          const confidence = identityConfidence(candidate.confidence);
          const evidence = evidenceLabels(candidate.source_badges, Boolean(domain));
          return (
            <li
              key={candidate.website}
              className="candidate-identity__row grid grid-cols-[minmax(3rem,.12fr)_minmax(0,1fr)_auto] items-center gap-phi-4 border-b border-oxford/[0.12] bg-oxford/[0.025] p-phi-3 transition-colors duration-150 hover:bg-oxford/[0.05]"
            >
              <div className="candidate-identity__rail flex flex-col gap-phi-2 font-mono text-[11px] text-oxford/50">
                <span>{String(index + 1).padStart(2, '0')}</span>
                <span>{confidence.percent}%</span>
              </div>
              <div className="candidate-identity__body min-w-0">
                {isBestIdentityMatch(candidate, index) ? <span className="type-label-section text-oxford/60">Best match</span> : null}
                <h3 className="mt-phi-1 font-sans text-[15px] font-medium text-oxford">{candidate.name}</h3>
                <p className="mt-0.5 truncate type-meta text-oxford/70">{domain}</p>
                <p className="mt-phi-1 type-meta text-oxford/60">{candidate.description || 'No description was confirmed for this domain.'}</p>
                <div className="mt-phi-2 flex flex-wrap items-center gap-x-phi-2 gap-y-phi-1 type-meta text-oxford/60" aria-label={`Verification evidence for ${candidate.name}`}>
                  <span>{confidence.label}</span>
                  <span>Verified by</span>
                  {evidence.map((label) => <span key={label}>{label}</span>)}
                </div>
              </div>
              <button
                type="button"
                onClick={() => onPick(candidate)}
                disabled={busy}
                aria-label={`Use ${candidate.name} at ${domain}`}
                className={`${productInteraction.action} candidate-identity__action whitespace-nowrap transition-transform duration-150 active:scale-[0.985] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oxford disabled:opacity-60`}
              >
                Use this company <span aria-hidden>→</span>
              </button>
            </li>
          );
        })}
      </ol>

      {refineOpen ? (
        <div className="candidate-identity__refinement grid gap-phi-2 border-t border-oxford/[0.12] pt-phi-3">
          <label htmlFor="candidate-website" className="type-label-section text-oxford/60">Company website</label>
          <p className="type-meta text-oxford/60">Add the company’s domain and we’ll resolve the identity directly.</p>
          <div className="flex items-center gap-phi-2 border-b border-oxford/[0.18]">
            <input
              id="candidate-website"
              type="text"
              autoFocus
              value={website}
              onChange={(event) => setWebsite(event.target.value)}
              onKeyDown={onWebsiteKeyDown}
              placeholder="Company website (e.g. example.ie)"
              autoComplete="off"
              disabled={busy}
              className="min-w-0 flex-1 bg-transparent px-0 py-phi-2 font-sans text-[13px] text-oxford placeholder:text-oxford/60 outline-none focus-visible:ring-1 focus-visible:ring-oxford/30"
            />
            <button type="button" onClick={submitRefine} disabled={busy || !website.trim()} className={`${productInteraction.action} transition-transform duration-150 active:scale-[0.985] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oxford`}>
              Resolve website
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setRefineOpen(true)}
          disabled={busy}
          className="justify-self-start type-meta cursor-pointer border-0 bg-transparent p-0 text-oxford/60 transition-colors hover:text-oxford focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oxford disabled:opacity-60"
        >
          None of these companies
        </button>
      )}
    </motion.section>
  );
}
