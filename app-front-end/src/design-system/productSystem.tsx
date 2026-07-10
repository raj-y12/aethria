import type { ReactNode } from 'react';

export const productText = {
  sectionLabel: 'type-label-section',
  mutedLabel: 'type-label-section',
  micro: 'type-meta',
  body: 'type-body-sm leading-relaxed text-oxford/60',
  bodyStrong: 'type-body-emphasis text-oxford',
  numeric: 'type-data',
};

export const productInteraction = {
  action:
    'type-action min-h-[44px] rounded-none border-0 bg-transparent p-0 transition-colors hover:text-oxford disabled:cursor-not-allowed disabled:opacity-30 focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 focus-visible:ring-offset-0',
  /** Panel header actions (memo exports, close) — same scale as WorkGrid queue tabs. */
  panelAction:
    'type-action min-h-[36px] rounded-none border-0 bg-transparent px-phi-3 transition-colors hover:text-oxford disabled:cursor-not-allowed disabled:opacity-30 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-inset',
  /** Inline kicker row — matches DecisionStage sector line (10px mono, 0.12em tracking). */
  panelActionInline:
    'type-action inline-flex min-h-0 items-center rounded-none border-0 bg-transparent p-0 transition-colors hover:text-oxford disabled:cursor-not-allowed disabled:opacity-30 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-inset',
  /** Subtle hover-fill interaction (panel tabs) — no text-color shift. */
  quiet:
    'transition-colors duration-150 hover:bg-oxford/[0.035] focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 focus-visible:ring-inset',
  /** Unselected memo ruling chip — Invest / Monitor / Pass at rest. */
  rulingChoiceIdle:
    'type-status inline-flex h-10 min-h-[40px] items-center justify-center rounded-none border-0 bg-oxford/[0.025] px-2.5 transition-colors hover:bg-oxford/[0.04] hover:text-oxford disabled:cursor-not-allowed disabled:opacity-30 btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-inset',
  selected: 'bg-surface-selected text-oxford',
  idle: 'text-oxford/60 hover:text-oxford/[0.72]',
};

export const productPanel = {
  shell: 'bg-paper text-oxford',
  /** Matches WorkGrid sticky toolbar — shared rhythm across center + right columns. */
  header:
    'flex-none flex items-center bg-paper px-phi-3 py-phi-2',
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
