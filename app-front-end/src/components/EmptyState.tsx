/**
 * Shared empty state: subtle mark, mono section title, Geist helper copy.
 * Used across WorkGrid, Judgements feed, System tabs — update here for global consistency.
 */

import type { ReactNode } from 'react';

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
    <div className="flex w-full flex-col items-center justify-center px-4 py-10 text-center sm:px-6">
      <div className="mb-3 flex h-7 w-7 shrink-0 items-center justify-center text-oxford/[0.22] [&_svg]:h-full [&_svg]:w-full">
        {icon ?? <DefaultMark />}
      </div>
      <p className="type-meta mb-2 max-w-xs uppercase text-oxford/50">{label}</p>
      <div className="type-body-sm max-w-sm leading-relaxed text-oxford/50">{body}</div>
    </div>
  );
}
