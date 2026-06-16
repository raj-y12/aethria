import { useState, type KeyboardEvent } from 'react';
import { motion } from 'framer-motion';
import type { LookupCandidate } from '../api/startups';
import { productInteraction } from '../design-system/productSystem';

interface CandidatePickerProps {
  candidates: LookupCandidate[];
  onPick: (candidate: LookupCandidate) => void;
  onRefine: (websiteHint: string) => void;
  busy?: boolean;
  /** Override the prompt above the list (e.g. the no-match "add a website" case). */
  heading?: string;
}

/** Strip protocol so the registrable domain (and its .ie/.com/.co extension) reads cleanly. */
function domainLabel(website: string): string {
  return website.replace(/^https?:\/\//, '').replace(/\/.*$/, '');
}

export default function CandidatePicker({ candidates, onPick, onRefine, busy, heading }: CandidatePickerProps) {
  const [refineOpen, setRefineOpen] = useState(false);
  const [website, setWebsite] = useState('');

  const submitRefine = () => {
    const value = website.trim();
    if (value) onRefine(value);
  };
  const onWebsiteKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') submitRefine();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className="mt-phi-3 grid gap-phi-2"
      aria-label="Select the company you meant"
    >
      <p className="type-meta text-oxford/[0.45]">
        {heading ?? 'More than one company matches — select the one you meant.'}
      </p>

      {candidates.map((c) => (
        <button
          key={c.website}
          type="button"
          disabled={busy}
          onClick={() => onPick(c)}
          aria-label={`Select ${c.name}`}
          className="group w-full text-left border border-oxford/[0.10] hover:border-oxford/[0.30] bg-paper px-phi-3 py-phi-3 transition-colors disabled:opacity-60 btn-interaction"
        >
          <div className="flex items-baseline justify-between gap-phi-2">
            <span className="min-w-0 truncate font-sans font-medium text-[13px] text-oxford">{c.name}</span>
            <span className="type-meta shrink-0 max-w-[45%] truncate text-oxford/[0.50]">{domainLabel(c.website)}</span>
          </div>
          {c.description ? (
            <p className="mt-phi-1 type-meta text-oxford/[0.55] line-clamp-2">{c.description}</p>
          ) : null}
          {c.source_badges.length ? (
            <div className="mt-phi-2 flex flex-wrap gap-phi-1">
              {c.source_badges.map((b, i) => (
                <span
                  key={`${b}-${i}`}
                  className="type-meta text-oxford/[0.40] border border-oxford/[0.10] px-phi-1 leading-[1.6]"
                >
                  {b}
                </span>
              ))}
            </div>
          ) : null}
        </button>
      ))}

      {refineOpen ? (
        <div className="flex items-center gap-phi-2 border-b border-oxford/[0.18] pt-phi-1">
          <input
            type="text"
            autoFocus
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
            onKeyDown={onWebsiteKeyDown}
            placeholder="Company website (e.g. example.ie)"
            autoComplete="off"
            disabled={busy}
            className="min-w-0 flex-1 bg-transparent border-0 px-0 py-phi-2 font-sans text-[13px] text-oxford placeholder:text-oxford/[0.28] outline-none"
          />
          <button type="button" onClick={submitRefine} disabled={busy || !website.trim()} className={productInteraction.action}>
            Resolve →
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setRefineOpen(true)}
          disabled={busy}
          className="justify-self-start type-meta text-oxford/[0.40] hover:text-oxford/[0.70] bg-transparent border-0 p-0 cursor-pointer transition-colors btn-interaction"
        >
          {candidates.length ? 'None of these — add a website' : 'Add a website'}
        </button>
      )}
    </motion.div>
  );
}
