/**
 * Shared empty state: subtle mark, mono section title, Geist helper copy.
 * Used across WorkGrid, Judgements feed, System tabs — update here for global consistency.
 */

import type { ReactNode } from 'react';
import { productText } from '../design-system/productSystem';

function DefaultMark() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" aria-hidden>
      <circle cx="12" cy="12" r="9" />
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
    <div className="flex w-full flex-col items-start justify-center px-phi-6 py-phi-7 text-left sm:px-phi-7 empty-state-enter">
      <div className="mb-phi-4 flex h-6 w-6 shrink-0 items-center justify-center text-oxford/22 [&_svg]:h-full [&_svg]:w-full">
        {icon ?? <DefaultMark />}
      </div>
      <p className={`${productText.mutedLabel} mb-phi-3 max-w-xs`}>{label}</p>
      <div className={`${productText.body} max-w-[28rem]`}>{body}</div>
    </div>
  );
}
