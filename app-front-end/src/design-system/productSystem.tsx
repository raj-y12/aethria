import type { ReactNode } from 'react';

export const productText = {
  sectionLabel: 'type-label-section text-oxford/72',
  mutedLabel: 'type-label-section text-oxford/45',
  micro: 'type-meta text-oxford/42',
  body: 'type-body-sm leading-relaxed text-oxford/55',
  bodyStrong: 'type-body-emphasis text-oxford',
  numeric: 'font-mono tabular-nums text-oxford',
};

export const productInteraction = {
  action:
    'type-label-section min-h-[44px] rounded-none border-0 bg-transparent p-0 text-oxford/55 transition-colors hover:text-oxford disabled:cursor-not-allowed disabled:opacity-30 focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 focus-visible:ring-offset-0',
  /** Panel header actions (memo exports, close) — same scale as WorkGrid queue tabs. */
  panelAction:
    'type-label-section min-h-[36px] rounded-none border-0 bg-transparent px-phi-3 text-oxford/45 transition-colors hover:text-oxford/72 disabled:cursor-not-allowed disabled:opacity-30 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-inset',
  /** Inline header row — matches mutedLabel / queue kicker cap height (no 36px block). */
  panelActionInline:
    'type-label-section inline-flex min-h-0 items-center rounded-none border-0 bg-transparent px-phi-3 py-0 text-oxford/45 transition-colors hover:text-oxford/72 disabled:cursor-not-allowed disabled:opacity-30 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-inset',
  quiet:
    'transition-colors duration-150 hover:bg-oxford/[0.035] focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 focus-visible:ring-inset',
  selected: 'bg-surface-selected text-oxford',
  idle: 'text-oxford/42 hover:text-oxford/72',
};

export const productPanel = {
  shell: 'bg-paper text-oxford',
  /** Matches WorkGrid sticky toolbar — shared rhythm across center + right columns. */
  header:
    'flex-none flex items-center bg-paper px-phi-3 py-phi-2 uppercase tracking-[0.06em]',
  section: 'border-t border-oxford/[0.075] py-phi-5 first:border-t-0 first:pt-0',
  rule: 'border-t border-oxford/[0.075]',
  inset: 'bg-oxford/[0.025]',
};

export function ProductSection({
  title,
  kicker,
  children,
  className = '',
}: {
  title: string;
  kicker?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`${productPanel.section} ${className}`.trim()}>
      <div className="grid gap-phi-5 xl:grid-cols-[minmax(150px,22%)_minmax(0,1fr)]">
        <div>
          <p className={productText.sectionLabel}>{title}</p>
          {kicker ? <div className={`mt-phi-3 max-w-[18rem] ${productText.body}`}>{kicker}</div> : null}
        </div>
        <div className="min-w-0">{children}</div>
      </div>
    </section>
  );
}
