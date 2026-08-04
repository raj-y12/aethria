import type { LookupCommandBarProps } from './types';

function cx(...parts: Array<string | false | undefined>) {
  return parts.filter(Boolean).join(' ');
}

function trailingLabel(trailing: NonNullable<LookupCommandBarProps['trailing']>): string {
  if (trailing === 'result') return 'Result';
  if (trailing === 'close') return 'Close';
  return '↵ run';
}

export default function LookupCommandBar({
  label = 'LOOKUP',
  query,
  trailing = 'run',
  className,
}: LookupCommandBarProps) {
  const showQuery = Boolean(query?.trim());

  return (
    <div
      className={cx(
        'flex items-center gap-3 border border-solid border-oxford/10 bg-oxford/[0.025] px-3 py-2 sm:px-4 sm:py-2.5',
        className,
      )}
    >
      <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-oxford/65">{label}</span>
      {showQuery ? (
        <>
          <span className="h-3 w-px shrink-0 bg-oxford/10" aria-hidden />
          <span className="min-w-0 truncate font-sans text-[13px] text-oxford/65">{query}</span>
        </>
      ) : null}
      {trailing ? (
        <span className="ml-auto shrink-0 font-mono text-[10px] uppercase tracking-[0.08em] text-oxford/65">
          {trailingLabel(trailing)}
        </span>
      ) : null}
    </div>
  );
}
