/**
 * Shared empty state: subtle mark, mono section title, Geist helper copy.
 * Used across WorkGrid, Judgements feed, System tabs — update here for global consistency.
 */

import type { ReactNode } from 'react';
import { productText } from '../design-system/productSystem';

/** The brand's punctuation as the resting mark — a small verdigris square. */
function DefaultMark() {
  return <span className="block h-2 w-2 rounded-none bg-brand-mark" aria-hidden />;
}

interface EmptyStateProps {
  label: string;
  body: ReactNode;
  icon?: ReactNode;
}

export default function EmptyState({ label, body, icon }: EmptyStateProps) {
  return (
    <div className="aethria-empty-state flex w-full flex-col items-start justify-center px-phi-6 py-phi-7 text-left sm:px-phi-7 empty-state-enter">
      <div className="aethria-empty-state__mark mb-phi-4 flex shrink-0 items-center">{icon ?? <DefaultMark />}</div>
      <p className={`aethria-empty-state__label ${productText.mutedLabel} mb-phi-3 max-w-xs`}>{label}</p>
      <div className={`aethria-empty-state__body ${productText.body} max-w-[28rem]`}>{body}</div>
    </div>
  );
}
