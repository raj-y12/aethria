/**
 * Shared empty state: subtle mark, mono section title, Geist helper copy.
 * Used across WorkGrid, Judgements feed, System tabs — update here for global consistency.
 */

import type { ReactNode } from 'react';

const FONT_BODY = '"Geist Sans", system-ui, sans-serif' as const;

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
    <div className="w-full flex flex-col items-center justify-center py-10 px-4 sm:px-6 text-center">
      <div className="mb-3 flex h-7 w-7 shrink-0 items-center justify-center text-oxford/[0.22] [&_svg]:h-full [&_svg]:w-full">
        {icon ?? <DefaultMark />}
      </div>
      <p className="mb-2 max-w-xs font-mono text-[10px] font-normal uppercase leading-[1.5] tracking-[0.12em] text-oxford/50">
        {label}
      </p>
      <div
        className="max-w-sm text-[13px] font-normal leading-relaxed text-oxford/50"
        style={{ fontFamily: FONT_BODY }}
      >
        {body}
      </div>
    </div>
  );
}
