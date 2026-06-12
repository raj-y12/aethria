import { forwardRef } from 'react';
import { motion } from 'framer-motion';
import { usePrefersReducedMotion } from '../../hooks';
import type { VerdictBadgeConfig } from '../../lib/fundConfiguration';
import QueueVerdictLine from './QueueVerdictLine';
import { buildRowAriaLabel, type DocketRowModel } from './queueRowShared';
import {
  QUEUE_ROW_LAYOUT_TRANSITION,
  QUEUE_ROW_SELECT_TRANSITION,
} from './queueRowMotion';
import { queueRowPadding } from '../../design-system/density';

interface DocketCaseRowProps {
  model: DocketRowModel;
  isSelected: boolean;
  rowIndex?: number;
  onClick: () => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  /** @deprecated Queue uses monochrome type; kept for call-site compatibility. */
  badges?: VerdictBadgeConfig[];
}

/**
 * The docket row — a pure index line: number, name, verdict. All context
 * (location, sector, standfirst, attention detail) belongs to the Decision
 * Stage; repeating it here put the same sentence on screen three times.
 * Selection reads through the left bar, full ink, and weight — never size.
 */
const DocketCaseRow = forwardRef<HTMLButtonElement, DocketCaseRowProps>(function DocketCaseRow(
  { model, isSelected, rowIndex = 0, onClick, onKeyDown },
  ref
) {
  const reduceMotion = usePrefersReducedMotion();
  const { startup, displayIndex, decisionVariant, queueContext } = model;

  /* Left bar = selection only (the product-wide selection mark). Escalation is
     carried by the burgundy "Needs ruling" verdict text — with most of a busy
     queue escalated, per-row bars read as a wall of alarms, not a signal. */
  const spineVisible = isSelected;
  const spineColor = spineVisible ? '#001433' : 'transparent';
  const spineWidth = spineVisible ? 3 : 0;

  const layoutTransition = reduceMotion ? { duration: 0 } : QUEUE_ROW_LAYOUT_TRANSITION;
  const selectTransition = reduceMotion ? { duration: 0 } : QUEUE_ROW_SELECT_TRANSITION;

  const ambientPadding =
    rowIndex % 2 === 0 ? queueRowPadding.ambient : queueRowPadding.ambientAlt;
  const selectedPadding = queueRowPadding.selected;

  return (
    <motion.button
      ref={ref}
      type="button"
      layout={!reduceMotion}
      transition={layoutTransition}
      aria-pressed={isSelected}
      aria-label={buildRowAriaLabel(model, isSelected)}
      onClick={onClick}
      onKeyDown={onKeyDown}
      initial={false}
      animate={{
        paddingTop: isSelected ? selectedPadding : ambientPadding,
        paddingBottom: isSelected ? selectedPadding : ambientPadding,
      }}
      className={`group relative block w-full min-w-0 cursor-pointer border-0 bg-transparent px-phi-0 text-left font-sans focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-inset ${
        isSelected ? 'bg-paperDeep/35' : ''
      }`}
    >
      <motion.span
        className="absolute left-0 top-0 bottom-0 block"
        aria-hidden
        initial={false}
        animate={{
          top: isSelected ? 10 : 9,
          bottom: isSelected ? 10 : 9,
          width: spineWidth,
          backgroundColor: spineColor,
          opacity: spineWidth === 0 ? 0 : 1,
        }}
        transition={selectTransition}
      />

      <div className="grid grid-cols-[26px_minmax(0,1fr)] items-baseline gap-x-phi-4">
        <motion.span
          className="type-meta tabular-nums"
          initial={false}
          animate={{
            color: isSelected ? 'rgba(0, 20, 51, 0.68)' : 'rgba(0, 20, 51, 0.24)',
          }}
          transition={selectTransition}
        >
          {displayIndex}
        </motion.span>

        <div className="flex min-w-0 items-baseline justify-between gap-phi-3">
          {/* span, not h2 — heading content is invalid inside a button, and a
              docket of rows is an index, not a document outline. */}
          <span
            className={`min-w-0 truncate font-sans text-[clamp(14px,1.15vw,16px)] leading-[1.3] tracking-[-0.01em] transition-[color,font-weight] duration-150 ${
              isSelected ? 'font-semibold text-oxford' : 'font-normal text-oxford/55 group-hover:text-oxford/80'
            }`}
          >
            {startup.scout.name}
          </span>
          <div className="shrink-0 text-right">
            <QueueVerdictLine
              ctx={queueContext}
              decisionVariant={decisionVariant}
              prominent={isSelected}
            />
          </div>
        </div>
      </div>
    </motion.button>
  );
});

export default DocketCaseRow;
