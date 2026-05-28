import QueueVerdictLine from './QueueVerdictLine';
import type { DocketRowModel } from './queueRowShared';

export default function FreshIntakeStrip({
  rows,
  totalNew,
  onSelect,
  onViewAll,
}: {
  rows: DocketRowModel[];
  totalNew: number;
  onSelect: (model: DocketRowModel) => void;
  onViewAll?: () => void;
}) {
  if (rows.length === 0) return null;

  return (
    <section className="border-b border-oxford/[0.05] bg-paper px-phi-4 py-phi-3" aria-label="Fresh intake">
      <div className="flex items-end justify-between gap-phi-3">
        <div>
          <p className="type-meta uppercase tracking-[0.12em] text-oxford/42">Fresh intake</p>
          <p className="mt-phi-1 type-meta normal-case tracking-normal text-oxford/34">
            New companies on the docket — open when ready for review.
          </p>
        </div>
        {totalNew > rows.length && onViewAll ? (
          <button
            type="button"
            onClick={onViewAll}
            className="type-meta min-h-[34px] shrink-0 text-oxford/42 hover:text-oxford/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
          >
            View all {totalNew}
          </button>
        ) : null}
      </div>
      <div className="mt-phi-3 flex flex-col gap-phi-3">
        {rows.map((model) => (
          <button
            key={model.startup.id}
            type="button"
            onClick={() => onSelect(model)}
            className="grid w-full min-h-[56px] gap-phi-1 bg-paper py-phi-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
          >
            <div className="min-w-0">
              <div className="flex min-w-0 items-center gap-phi-2">
                <span className="type-meta shrink-0 tabular-nums text-oxford/28">{model.displayIndex}</span>
                      <span className="truncate type-body font-normal text-oxford/54">{model.startup.scout.name}</span>
              </div>
              {model.oneLiner ? (
                <p className="mt-phi-1 line-clamp-1 queue-row-prose pl-[calc(28px+var(--space-4))] type-body-sm text-oxford/52">
                  {model.oneLiner}
                </p>
              ) : null}
            </div>
            <div className="flex shrink-0 sm:justify-end">
              <QueueVerdictLine ctx={model.queueContext} decisionVariant={model.decisionVariant} />
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
