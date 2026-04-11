import type { ReactNode } from 'react';

/**
 * Canonical signal/event row: same timestamp style, label, and body across
 * LiveIntelligenceFeed and SystemIntelligence. Compact = one line; stacked = label + body + meta.
 */
interface SignalEventRowProps {
  timestamp: string;
  label?: string;
  body: ReactNode;
  meta?: string;
  trailing?: ReactNode;
  /** Compact: timestamp + body (+ trailing) on one line. Stacked: timestamp+label line, then body, then meta. */
  layout?: 'compact' | 'stacked';
  className?: string;
}

export default function SignalEventRow({
  timestamp,
  label,
  body,
  meta,
  trailing,
  layout = 'stacked',
  className = '',
}: SignalEventRowProps) {
  const borderCls = 'border-b border-hairline';
  const tsCls = 'shrink-0 tabular-nums type-meta text-oxford/50';
  const bodyCls = 'type-body-sm text-oxford/70 leading-[1.6]';

  if (layout === 'compact') {
    return (
      <div className={`flex items-baseline gap-phi-3 py-phi-3 ${borderCls} ${className}`}>
        <span className={tsCls}>{timestamp}</span>
        <span className={`${bodyCls} min-w-0 truncate flex-1`}>{body}</span>
        {trailing != null && <span className="shrink-0">{trailing}</span>}
      </div>
    );
  }

  return (
    <div className={`flex flex-col gap-phi-2 py-phi-4 ${borderCls} ${className}`}>
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className={tsCls}>{timestamp}</span>
        {label != null && label !== '' && (
          <span className="type-label-section text-oxford/[0.58]">{label}</span>
        )}
        {trailing != null && <span className="ml-auto shrink-0">{trailing}</span>}
      </div>
      <div className={bodyCls}>{body}</div>
      {meta != null && meta !== '' && (
        <p className="type-meta text-oxford/40 mt-1">{meta}</p>
      )}
    </div>
  );
}
