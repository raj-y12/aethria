import type { LookupCommandBarProps } from './types';

function cx(...parts: Array<string | false | undefined>) {
  return parts.filter(Boolean).join(' ');
}

export default function LookupCommandBar({ query, trailing = 'run', className }: LookupCommandBarProps) {
  const trailingLabel = trailing === 'result' ? 'Result' : '↵ run';

  return (
    <div
      className={cx(
        'flex items-center gap-3 border border-solid border-oxford/10 bg-oxford/[0.025] px-3 py-2 sm:px-4 sm:py-2.5',
        className,
      )}
    >
      <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-oxford/35">LOOKUP</span>
      <span className="h-3 w-px shrink-0 bg-oxford/10" aria-hidden />
      <span className="min-w-0 truncate font-sans text-[13px] text-oxford/65">{query}</span>
      {trailing ? (
        <span className="ml-auto shrink-0 font-mono text-[10px] uppercase tracking-[0.08em] text-oxford/30">
          {trailingLabel}
        </span>
      ) : null}
    </div>
  );
}
