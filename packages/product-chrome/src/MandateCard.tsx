import type { MandateCardProps } from './types';

function cx(...parts: Array<string | false | undefined>) {
  return parts.filter(Boolean).join(' ');
}

export default function MandateCard({
  variant,
  title,
  tags = [],
  excerpt,
  live = false,
  compact = false,
  className,
}: MandateCardProps) {
  const isDark = variant === 'dark';
  const pad = compact ? 'p-3' : 'p-4 sm:p-5';

  const border = isDark ? 'border-[rgba(244,241,234,0.12)]' : 'border-oxford/10';
  const labelCls = isDark
    ? 'font-mono text-[10px] uppercase tracking-[0.11em] text-[rgba(244,241,234,0.35)]'
    : 'font-mono text-[11px] uppercase tracking-[0.11em] text-oxford/40';
  const titleCls = isDark
    ? 'font-sans text-[15px] font-semibold text-[#f4f1ea]'
    : 'font-sans text-[15px] font-semibold leading-tight tracking-tight text-oxford';
  const tagLineCls = 'font-sans text-[13px] leading-[1.6] text-[rgba(244,241,234,0.5)]';
  const tagChipCls =
    'border border-solid border-oxford/10 px-2 py-0.5 font-mono text-[10px] tracking-[0.06em] text-oxford/58';
  const liveCls = isDark
    ? 'font-mono text-[10px] uppercase tracking-[0.1em] text-[rgba(244,241,234,0.45)]'
    : 'font-mono text-[10px] uppercase tracking-[0.1em] text-oxford/50';
  const dotCls = isDark ? 'bg-[#f4f1ea]' : 'bg-oxford';
  const excerptCls = isDark
    ? 'font-sans text-[13px] italic leading-[1.65] text-[rgba(244,241,234,0.4)]'
    : 'font-sans text-[13px] leading-[1.6] text-oxford/58';
  const ruleCls = isDark ? 'bg-[rgba(244,241,234,0.1)]' : 'bg-oxford/10';

  return (
    <div
      className={cx(
        'border border-solid',
        border,
        pad,
        isDark ? 'bg-transparent' : 'bg-paper',
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <p className={labelCls}>Active Mandate{isDark ? '' : ' · Fund Thesis'}</p>
        {live ? (
          <span className="inline-flex shrink-0 items-center gap-1.5">
            <span className={cx('h-1.5 w-1.5 shrink-0 rounded-none', dotCls, 'pc-live-dot')} aria-hidden />
            <span className={liveCls}>Live</span>
          </span>
        ) : null}
      </div>

      <p className={cx('mt-2.5', titleCls)}>{title}</p>

      {tags.length > 0 ? (
        isDark ? (
          <p className={cx('mt-1', tagLineCls)}>{tags.join(' · ')}</p>
        ) : (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {tags.map((tag) => (
              <span key={tag} className={tagChipCls}>
                {tag}
              </span>
            ))}
          </div>
        )
      ) : null}

      {excerpt ? (
        <>
          <div className={cx('mt-3 h-px', ruleCls)} aria-hidden />
          <p className={cx('mt-3', excerptCls)}>{isDark ? `"${excerpt}"` : excerpt}</p>
        </>
      ) : null}
    </div>
  );
}
