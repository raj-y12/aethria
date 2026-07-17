import { useState, type KeyboardEvent } from 'react';
import { motion } from 'framer-motion';
import type { LookupCandidate } from '../api/startups';
import { transitionOrReduced } from '../design-system/motion';
import { tokens } from '../design-system/tokens';
import { usePrefersReducedMotion } from '../hooks';
import { domainLabel, evidenceLabels, identityConfidence, isBestIdentityMatch } from '../lib/candidateIdentity';

const candidateAction =
  'type-action min-h-[44px] rounded-none border-0 bg-transparent p-0 transition-colors transition-transform duration-150 active:scale-[0.985] motion-reduce:transition-none motion-reduce:active:scale-100 disabled:cursor-not-allowed disabled:opacity-30 focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 [@media(hover:hover)_and_(pointer:fine)]:hover:text-oxford';

interface CandidatePickerProps {
  candidates: LookupCandidate[];
  onPick: (candidate: LookupCandidate) => void;
  onRefine: (websiteHint: string) => void;
  busy?: boolean;
  /** Override the prompt above the list (e.g. the no-match "add a website" case). */
  heading?: string;
}

/** How each candidate's identity is backed, in honest terms — a bare domain is not verification. */
function evidenceLine(candidate: LookupCandidate, domain: string): string {
  const evidence = evidenceLabels(candidate.source_badges);
  const tier = identityConfidence(candidate.confidence);
  if (evidence.length) return `${tier} · Verified by ${evidence.join(', ')}`;
  if (domain) return `${tier} · Domain found — not verified`;
  return `${tier} · No verification evidence`;
}

export default function CandidatePicker({ candidates, onPick, onRefine, busy, heading }: CandidatePickerProps) {
  const [refineOpen, setRefineOpen] = useState(false);
  const [website, setWebsite] = useState('');
  const reduceMotion = usePrefersReducedMotion();

  const submitRefine = () => {
    const value = website.trim();
    if (value) onRefine(value);
  };
  const onWebsiteKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') submitRefine();
  };

  return (
    <motion.section
      initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 4 }}
      animate={reduceMotion ? { opacity: 1 } : { opacity: 1, y: 0 }}
      transition={transitionOrReduced(reduceMotion, {
        duration: tokens.motion.duration.micro,
        ease: tokens.motion.ease,
      })}
      className="mt-phi-3 grid gap-phi-3"
      aria-label="Select the company you meant"
    >
      <p className="type-meta text-oxford/60">
        {heading ?? 'More than one company matches — choose the one you meant.'}
      </p>

      <ol className="grid gap-phi-1">
        {candidates.map((candidate, index) => {
          const domain = domainLabel(candidate.website);
          return (
            <li
              key={`${candidate.name}|${candidate.website}|${index}`}
              className="grid grid-cols-1 items-center gap-phi-3 border-b border-oxford/[0.12] py-phi-3 sm:grid-cols-[minmax(0,1fr)_auto]"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-baseline gap-x-phi-2">
                  <h3 className="font-sans text-[14px] font-medium text-oxford">{candidate.name}</h3>
                  <span className="truncate type-meta text-oxford/70">{domain || 'Website not verified'}</span>
                  {isBestIdentityMatch(candidate, index) ? (
                    <span className="type-label-section text-oxford/60">Best match</span>
                  ) : null}
                </div>
                {candidate.description ? (
                  <p className="mt-phi-1 type-meta text-oxford/60 line-clamp-2">{candidate.description}</p>
                ) : null}
                <p className="mt-phi-1 type-meta text-oxford/50">{evidenceLine(candidate, domain)}</p>
              </div>
              <button
                type="button"
                onClick={() => onPick(candidate)}
                disabled={busy}
                aria-label={`Use ${candidate.name} at ${domain || candidate.website}`}
                className={`${candidateAction} whitespace-nowrap disabled:opacity-60`}
              >
                Use this company <span aria-hidden>→</span>
              </button>
            </li>
          );
        })}
      </ol>

      {refineOpen ? (
        <div className="grid gap-phi-2 pt-phi-1">
          <label htmlFor="candidate-website" className="type-label-section text-oxford/60">Company website</label>
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
              className="min-w-0 flex-1 bg-transparent px-0 py-phi-2 font-sans text-[13px] text-oxford placeholder:text-oxford/60 outline-none"
            />
            <button type="button" onClick={submitRefine} disabled={busy || !website.trim()} className={candidateAction}>
              Resolve website
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setRefineOpen(true)}
          disabled={busy}
          className="justify-self-start type-meta cursor-pointer border-0 bg-transparent p-0 text-oxford/60 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 [@media(hover:hover)_and_(pointer:fine)]:hover:text-oxford disabled:opacity-60"
        >
          {candidates.length ? 'None of these — add a website' : 'Add a website'}
        </button>
      )}
    </motion.section>
  );
}
