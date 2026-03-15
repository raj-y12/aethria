/**
 * Deliberate empty state: minimal mark, section label, 1–2 lines of explanatory copy.
 * Consistent motif across WorkGrid, LiveIntelligenceFeed, SystemIntelligence, Settings.
 */

import type { ReactNode } from 'react';

/** Minimal mark: circle outline at currentColor (use with text-oxford/25) */
function DefaultMark() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <circle cx="12" cy="12" r="9" />
    </svg>
  );
}

interface EmptyStateProps {
  /** Section label (e.g. "Pipeline", "Judgements feed") */
  label: string;
  /** 1–2 lines body-sm Inter; explains what this panel is and when content will appear */
  body: ReactNode;
  /** Optional minimal mark/icon in oxford at low opacity; default is circle outline */
  icon?: ReactNode;
}

export default function EmptyState({ label, body, icon }: EmptyStateProps) {
  return (
    <div className="w-full flex flex-col items-center justify-center py-12 px-4 text-center">
      <div className="mb-3 text-oxford/25 flex items-center justify-center w-8 h-8 [&_svg]:w-full [&_svg]:h-full">
        {icon ?? <DefaultMark />}
      </div>
      <p className="type-label-section text-oxford/60 uppercase tracking-wider mb-2">
        {label}
      </p>
      <div className="type-body-sm text-oxford/60 max-w-sm leading-relaxed">
        {body}
      </div>
    </div>
  );
}
