import { forwardRef } from 'react';
import { motion } from 'framer-motion';
import { usePrefersReducedMotion } from '../../hooks';
import type { VerdictBadgeConfig } from '../../lib/fundConfiguration';
import DocketMarginColumn from './DocketMarginColumn';
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
 * Annotated dossier row: text block (name, one-liner · sector) on the left,
 * verdict chip + score on the right, divider between.
 */
const DocketCaseRow = forwardRef<HTMLButtonElement, DocketCaseRowProps>(function DocketCaseRow(
  { model, isSelected, rowIndex = 0, onClick, onKeyDown },
  ref
) {
  const reduceMotion = usePrefersReducedMotion();
  const { startup, decisionVariant, queueContext, attentionDriver } = model;

  const layoutTransition = reduceMotion ? { duration: 0 } : QUEUE_ROW_LAYOUT_TRANSITION;
  const selectTransition = reduceMotion ? { duration: 0 } : QUEUE_ROW_SELECT_TRANSITION;

  const ambientPadding =
    rowIndex % 2 === 0 ? queueRowPadding.ambient : queueRowPadding.ambientAlt;
  const selectedPadding = queueRowPadding.selected + 4;

  const metaLine = [model.oneLiner, model.sectorStage].filter(Boolean).join(' · ');
  const attentionLine = attentionDriver.detail ?? attentionDriver.label;

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
        backgroundColor: isSelected
          ? 'color-mix(in srgb, var(--color-paper-deep) 35%, transparent)'
          : 'rgba(0, 0, 0, 0)',
      }}
      className="group relative block w-full min-w-0 cursor-pointer rounded-none border-0 bg-transparent px-phi-0 text-left font-sans focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-inset"
    >
      <div className="flex items-start gap-phi-3">
        <div className="min-w-0 flex-1">
          <span
            className={`block min-w-0 font-sans transition-all duration-150 ${
              isSelected
                ? 'text-[22px] font-semibold leading-[1.2] tracking-[-0.015em] text-oxford'
                : 'text-[clamp(14px,1.15vw,16px)] font-normal leading-[1.3] tracking-[-0.01em] text-oxford/55 group-hover:text-oxford/80'
            }`}
          >
            {startup.scout.name}
          </span>
          {metaLine ? (
            <span
              className={`mt-1 block min-w-0 text-[12px] leading-[1.45] ${
                isSelected ? 'text-oxford/[0.62]' : 'text-oxford/50'
              }`}
            >
              {metaLine}
            </span>
          ) : null}
          {isSelected && attentionLine ? (
            <span className="mt-2 block border-t border-dotted border-oxford/15 pt-2 text-[12px] leading-[1.45] text-oxford/50">
              {attentionLine}
            </span>
          ) : null}
        </div>

        <div className="relative w-[3px] shrink-0 self-stretch" aria-hidden>
          <motion.span
            className={`absolute left-0 top-0 bottom-0 block transition-colors duration-150 ${
              isSelected ? 'bg-oxford' : 'bg-oxford/10'
            }`}
            initial={false}
            animate={{ width: isSelected ? 3 : 2 }}
            transition={selectTransition}
          />
        </div>

        <DocketMarginColumn
          variant={decisionVariant}
          score={queueContext.configuredScore}
        />
      </div>
    </motion.button>
  );
});

export default DocketCaseRow;
