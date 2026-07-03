import LookupCommandBar from './LookupCommandBar';
import type { LookupResultSnapshotProps } from './types';

function cx(...parts: Array<string | false | undefined>) {
  return parts.filter(Boolean).join(' ');
}

function formatScore(score: number | null): string {
  if (score == null || !Number.isFinite(score)) return '—';
  return Number.isInteger(score) ? String(score) : score.toFixed(1);
}

export default function LookupResultSnapshot({
  companyName,
  queryLabel,
  metaLine,
  verdict,
  verdictColor,
  verdictTextColor,
  summary,
  dimensions,
  thesisLine,
  resolutionLine,
  onOpenMemo,
  openMemoLabel = 'Open full memo',
  variant = 'snapshot',
  compact = false,
  size = 'default',
  intelligenceKicker = 'Aethria intelligence · autonomous output',
  judgmentLabel = 'Investment judgment',
  dimensionsLabel = 'Dimension scores',
  className,
}: LookupResultSnapshotProps) {
  const isMemo = variant === 'memo';
  // Larger snapshot for the dispatch takeover: enlarge company name, summary, scores
  // and padding while leaving the small mono tag/labels and verdict chip unchanged.
  const lg = !isMemo && size === 'lg';
  const pad = compact ? 'p-3' : isMemo ? 'p-5 sm:p-7 md:p-9' : lg ? 'p-6 sm:p-7' : 'px-4 py-4 sm:p-5';
  const verdictSize = compact
    ? 'font-sans text-[18px] font-semibold leading-tight text-oxford'
    : isMemo
      ? 'font-sans text-[clamp(1.375rem,5vw,2rem)] font-semibold leading-tight tracking-[-0.03em] text-oxford md:text-[32px]'
      : 'font-sans text-[18px] font-semibold leading-tight text-oxford';

  const showCompanyName = true;

  return (
    <article
      className={cx('border border-solid border-oxford/10 bg-paper', className)}
      aria-label={
        isMemo
          ? `Investment memo preview for ${companyName}`
          : queryLabel
            ? `Lookup result for ${companyName}`
            : `Intelligence snapshot for ${companyName}`
      }
    >
      {isMemo ? (
        <LookupCommandBar
          label="MEMO"
          trailing="close"
          className="border-0 bg-paper"
        />
      ) : null}

      <div className={pad}>
        {isMemo ? (
          <>
            <p className="mb-4 font-mono text-[12px] uppercase tracking-[0.11em] text-oxford/40">
              {intelligenceKicker}
            </p>
            {showCompanyName ? (
              <h3 className="pc-font-sans text-xl font-semibold leading-tight tracking-tight text-oxford sm:text-2xl">
                {companyName}
              </h3>
            ) : null}
            {metaLine ? (
              <p className="mt-1.5 font-mono text-[13px] tracking-[0.08em] text-oxford/50">{metaLine}</p>
            ) : null}
            <div className="my-5 h-px bg-oxford/10" aria-hidden />
            <p className="mb-1.5 font-mono text-[12px] uppercase tracking-[0.11em] text-oxford/58">
              {judgmentLabel}
            </p>
          </>
        ) : (
          <div className="mb-3 flex items-baseline justify-between gap-3">
            <p className="font-mono text-[10px] uppercase tracking-[0.11em] text-oxford/40">Result</p>
            {metaLine ? (
              <p className="text-right font-mono text-[10px] uppercase tracking-[0.1em] text-oxford/35">{metaLine}</p>
            ) : null}
          </div>
        )}

        {!isMemo && showCompanyName && companyName ? (
          <h3
            className={cx(
              'pc-font-sans font-semibold leading-tight tracking-tight text-oxford',
              compact ? 'text-base' : lg ? 'text-2xl sm:text-3xl' : 'text-xl sm:text-2xl',
            )}
          >
            {companyName}
          </h3>
        ) : null}

        {verdictColor ? (
          <span
            className={cx(
              // Match the app-front-end decision chip (VERDICT_CHIP_CLASS) exactly.
              'inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none font-mono font-semibold uppercase leading-none min-w-[4.25rem] px-2 py-1 text-[9px] tracking-[0.1em]',
              showCompanyName && companyName ? 'mt-2' : '',
            )}
            style={{ backgroundColor: verdictColor, color: verdictTextColor ?? undefined }}
          >
            {verdict.replace(/\.$/, '')}
          </span>
        ) : (
          <p className={cx(isMemo ? '' : showCompanyName && companyName ? 'mt-2' : '', verdictSize)}>{verdict}</p>
        )}
        <p
          className={cx(
            'font-sans leading-[1.6] text-oxford/58',
            isMemo ? 'mt-3 text-[15px] font-normal' : lg ? 'mt-2.5' : 'mt-1.5',
            !isMemo && (compact ? 'text-[13px]' : lg ? 'text-base sm:text-[17px]' : 'text-[15px]'),
          )}
        >
          {summary}
        </p>
        {thesisLine ? (
          <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.08em] text-oxford/35">{thesisLine}</p>
        ) : null}
        {resolutionLine ? (
          <p className="mt-2 border border-solid border-oxford/12 bg-oxford/[0.04] px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-oxford/55">
            {resolutionLine}
          </p>
        ) : null}

        {dimensions.length > 0 ? (
          <>
            <div className={cx('bg-oxford/10', isMemo ? 'my-5 h-px' : 'my-3 h-px sm:my-4')} aria-hidden />
            {isMemo ? (
              <>
                <p className="mb-[14px] font-mono text-[12px] uppercase tracking-[0.11em] text-oxford/58">
                  {dimensionsLabel}
                </p>
                <div className="grid w-full grid-cols-5 gap-x-0.5 gap-y-1 sm:gap-x-2 sm:gap-y-2 md:gap-x-3">
                  {dimensions.map((d) => (
                    <div key={`label-${d.key}`} className="flex min-w-0 items-end justify-center text-center">
                      <p className="m-0 font-mono text-[11px] leading-[1.25] tracking-[0.03em] text-oxford/55 sm:text-[12px]">
                        {/* five full labels overlap at this column width — prefer the abbreviation */}
                        {d.labelShort ?? d.label}
                      </p>
                    </div>
                  ))}
                  {dimensions.map((d) => (
                    <p
                      key={`score-${d.key}`}
                      className="min-w-0 text-center font-mono text-base font-bold leading-tight text-oxford sm:text-xl md:text-2xl"
                    >
                      {formatScore(d.score)}
                    </p>
                  ))}
                </div>
              </>
            ) : (
              <div className="grid grid-cols-5 gap-x-1 sm:gap-x-2">
                {dimensions.map((d) => (
                  <div key={d.key} className="flex min-w-0 flex-col items-center gap-0.5 text-center">
                    <span className="font-mono text-[10px] text-oxford/35">{d.label}</span>
                    <span
                      className={cx(
                        'font-mono font-bold text-oxford/70',
                        lg ? 'text-base sm:text-lg' : 'text-[11px] sm:text-sm',
                      )}
                    >
                      {formatScore(d.score)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </>
        ) : null}

        {onOpenMemo ? (
          <button
            type="button"
            onClick={onOpenMemo}
            className="mt-4 w-full border border-solid border-oxford/12 bg-oxford px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.12em] text-paper transition-opacity hover:opacity-90"
          >
            {openMemoLabel}
          </button>
        ) : null}
      </div>
    </article>
  );
}
