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
 * Annotated dossier row: a fixed margin column (verdict chip + score) against
 * a two-line text block (name, one-liner · sector). Selection is the "open
 * file" — name and score step up in size and ink, and the attention reason
 * appears as a third line in the same muted voice as the one-liner.
 */
const DocketCaseRow = forwardRef<HTMLButtonElement, DocketCaseRowProps>(function DocketCaseRow(
  { model, isSelected, rowIndex = 0, onClick, onKeyDown },
  ref
) {
  const reduceMotion = usePrefersReducedMotion();
  const { startup, decisionVariant, queueContext, attentionDriver } = model;

  const spineVisible = isSelected;
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
          width: spineVisible ? 3 : 0,
          backgroundColor: spineVisible ? '#001433' : 'transparent',
          opacity: spineVisible ? 1 : 0,
        }}
        transition={selectTransition}
      />

      <div className="flex items-start gap-phi-3">
        <DocketMarginColumn
          variant={decisionVariant}
          score={queueContext.configuredScore}
          prominent={isSelected}
        />

        <div className="min-w-0 flex-1">
          <span
            className={`block min-w-0 truncate font-sans transition-all duration-150 ${
              isSelected
                ? 'text-[22px] font-semibold leading-[1.2] tracking-[-0.015em] text-oxford'
                : 'text-[clamp(14px,1.15vw,16px)] font-normal leading-[1.3] tracking-[-0.01em] text-oxford/55 group-hover:text-oxford/80'
            }`}
          >
            {startup.scout.name}
          </span>
          {metaLine ? (
            <span
              className={`mt-1 block min-w-0 truncate text-[12px] leading-[1.45] ${
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
      </div>
    </motion.button>
  );
});

export default DocketCaseRow;
