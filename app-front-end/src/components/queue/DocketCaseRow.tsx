import { forwardRef } from 'react';
import { motion } from 'framer-motion';
import { usePrefersReducedMotion } from '../../hooks';
import type { VerdictBadgeConfig } from '../../lib/fundConfiguration';
import QueueVerdictLine from './QueueVerdictLine';
import QueueAttentionBadge from './QueueAttentionBadge';
import { shouldRenderAttentionBadge } from '../../lib/queueAttentionDriver';
import {
  buildRowAriaLabel,
  formatRowDate,
  resolutionBadgeLabel,
  type DocketRowModel,
} from './queueRowShared';
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

const DocketCaseRow = forwardRef<HTMLDivElement, DocketCaseRowProps>(function DocketCaseRow(
  { model, isSelected, rowIndex = 0, onClick, onKeyDown },
  ref
) {
  const reduceMotion = usePrefersReducedMotion();
  const {
    startup,
    displayIndex,
    decisionVariant,
    queueContext,
    attentionDriver,
    sectorStage,
    sortKeyValue,
  } = model;

  const { isDecided, ageDays } = queueContext;

  const spineVisible = isSelected;
  const spineColor = spineVisible ? '#001433' : 'transparent';
  const spineWidth = spineVisible ? 3 : 0;

  const layoutTransition = reduceMotion ? { duration: 0 } : QUEUE_ROW_LAYOUT_TRANSITION;
  const selectTransition = reduceMotion ? { duration: 0 } : QUEUE_ROW_SELECT_TRANSITION;
  const ambientPadding =
    rowIndex % 2 === 0 ? queueRowPadding.ambient : queueRowPadding.ambientAlt;
  const selectedPadding = queueRowPadding.selected;
  const showAttentionBadge =
    !isDecided && shouldRenderAttentionBadge(attentionDriver) && attentionDriver.key !== 'needs_ruling';
  const showDateMeta = isSelected && Boolean(sortKeyValue);
  const resolutionBadge = resolutionBadgeLabel(startup);
  const hasMetaRow = Boolean(sectorStage) || showDateMeta || showAttentionBadge || Boolean(resolutionBadge);

  const metaSep = (needsSep: boolean) =>
    needsSep ? (
      <span className="type-meta text-oxford/20" aria-hidden>
        ·
      </span>
    ) : null;

  return (
    <motion.div
      ref={ref}
      layout={!reduceMotion}
      transition={layoutTransition}
      role="button"
      tabIndex={0}
      aria-pressed={isSelected}
      aria-label={buildRowAriaLabel(model, isSelected)}
      onClick={onClick}
      onKeyDown={onKeyDown}
      initial={false}
      animate={{
        paddingTop: isSelected ? selectedPadding : ambientPadding,
        paddingBottom: isSelected ? selectedPadding : ambientPadding,
      }}
      className={`group relative w-full min-w-0 cursor-pointer pl-1.5 pr-phi-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-inset ${
        isSelected ? 'bg-paperDeep/35' : ''
      }`}
    >
      <motion.span
        className="absolute left-0 top-0 bottom-0 block"
        aria-hidden
        initial={false}
        animate={{
          top: isSelected ? 18 : 9,
          bottom: isSelected ? 18 : 9,
          width: spineWidth,
          backgroundColor: spineColor,
          opacity: spineWidth === 0 ? 0 : 1,
        }}
        transition={selectTransition}
      />

      <motion.div
        layout={!reduceMotion}
        className="grid grid-cols-[auto_minmax(0,1fr)] items-start gap-x-phi-3"
        transition={layoutTransition}
      >
        <motion.span
          className="type-meta tabular-nums self-start shrink-0 min-w-[2.75rem] pr-0.5 leading-none"
          initial={false}
          animate={{
            color: isSelected ? 'rgba(0, 20, 51, 0.68)' : 'rgba(0, 20, 51, 0.24)',
          }}
          transition={selectTransition}
        >
          {displayIndex}
        </motion.span>

        <div className="min-w-0">
          <div
            className={`flex min-w-0 flex-col sm:flex-row sm:items-start sm:justify-between ${
              isSelected ? 'gap-phi-5 sm:gap-phi-6' : 'gap-phi-1 sm:gap-phi-3'
            }`}
          >
            <div className="min-w-0 flex-1">
              {isSelected && startup.scout.location?.trim() ? (
                <p className="mb-1.5 type-meta uppercase tracking-[0.12em] text-oxford/60">
                  {startup.scout.location.trim()}
                </p>
              ) : null}
              <motion.h2
                layout={!reduceMotion}
                className={`min-w-0 break-words transition-[color,font-weight] ${
                  isSelected
                    ? 'font-display text-[clamp(28px,2.6vw,36px)] font-medium leading-[1.1] tracking-[-0.02em] text-oxford'
                    : 'font-sans text-[clamp(14px,1.15vw,16px)] font-normal leading-[1.15] tracking-[-0.01em] text-oxford/60'
                }`}
                style={{
                  transitionDuration: `${selectTransition.duration}s`,
                  transitionTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)',
                }}
                transition={selectTransition}
              >
                {startup.scout.name}
              </motion.h2>
            </div>
            <motion.div layout={!reduceMotion} className="shrink-0 sm:text-right sm:pt-px" transition={layoutTransition}>
              <QueueVerdictLine
                ctx={queueContext}
                decisionVariant={decisionVariant}
                prominent={isSelected}
                attentionDriver={attentionDriver}
              />
            </motion.div>
          </div>

          {isSelected && hasMetaRow ? (
            <motion.div
              layout={!reduceMotion}
              className="mt-phi-2 flex min-w-0 flex-wrap items-center gap-x-phi-2 gap-y-phi-1"
              initial={reduceMotion ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={selectTransition}
            >
              {sectorStage ? (
                <p className="type-meta uppercase tracking-[0.06em] text-oxford/60">{sectorStage}</p>
              ) : null}
              {showDateMeta ? (
                <>
                  {metaSep(Boolean(sectorStage))}
                  <span className="type-meta tracking-[0.06em] text-oxford/60">
                    {formatRowDate(sortKeyValue)}
                  </span>
                </>
              ) : null}
              {showAttentionBadge ? (
                <>
                  {metaSep(Boolean(sectorStage || showDateMeta))}
                  <QueueAttentionBadge driver={attentionDriver} ctx={{ ageDays }} prominent={isSelected} />
                </>
              ) : null}
              {resolutionBadge ? (
                <>
                  {metaSep(Boolean(sectorStage || showDateMeta || showAttentionBadge))}
                  <span
                    className="type-meta uppercase tracking-[0.08em] text-oxford/60"
                    title="Company Resolver: identity evidence is incomplete — open the memo to see what was found and what's missing."
                  >
                    {resolutionBadge}
                  </span>
                </>
              ) : null}
            </motion.div>
          ) : null}

        </div>
      </motion.div>
    </motion.div>
  );
});

export default DocketCaseRow;
