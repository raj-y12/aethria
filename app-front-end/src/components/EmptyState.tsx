/**
 * Shared empty state: subtle mark, mono section title, Geist helper copy.
 * Used across WorkGrid, Judgements feed, System tabs — update here for global consistency.
 */

import type { ReactNode } from 'react';
import { productText } from '../design-system/productSystem';

/** The resting mark: a small verdigris triangle with softened corners (a filled
 *  path stroked in the same colour with round joins). */
export function EmptyMark() {
  return (
    <svg viewBox="0 0 10 10" className="block h-3 w-3 text-brand-mark" aria-hidden>
      <path
        d="M5 2.9 7.5 7.2H2.5Z"
        fill="currentColor"
        stroke="currentColor"
        strokeWidth={2.8}
        strokeLinejoin="round"
      />
    </svg>
  );
}

interface EmptyStateProps {
  label: string;
  body: ReactNode;
  icon?: ReactNode;
}

export default function EmptyState({ label, body, icon }: EmptyStateProps) {
  return (
    <div className="aethria-empty-state flex w-full flex-col items-start justify-center px-phi-6 py-phi-7 text-left sm:px-phi-7 empty-state-enter">
      <div className="aethria-empty-state__mark mb-phi-4 flex shrink-0 items-center">{icon ?? <EmptyMark />}</div>
      <p className={`aethria-empty-state__label ${productText.mutedLabel} mb-phi-3 max-w-xs`}>{label}</p>
      <div className={`aethria-empty-state__body ${productText.body} max-w-[28rem]`}>{body}</div>
    </div>
  );
}
