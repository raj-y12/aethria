import { forwardRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
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
  QUEUE_ROW_CONTENT_TRANSITION,
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
    oneLiner,
    sectorStage,
    sortKeyValue,
  } = model;

  const { isDecided, ageDays } = queueContext;

  /* Left bar = selection only (the product-wide selection mark). Escalation is
     carried by the burgundy "Needs ruling" verdict text — with most of a busy
     queue escalated, per-row bars read as a wall of alarms, not a signal. */
  const spineVisible = isSelected;
  const spineColor = spineVisible ? '#001433' : 'transparent';
  const spineWidth = spineVisible ? 3 : 0;

  const layoutTransition = reduceMotion ? { duration: 0 } : QUEUE_ROW_LAYOUT_TRANSITION;
  const selectTransition = reduceMotion ? { duration: 0 } : QUEUE_ROW_SELECT_TRANSITION;
  const contentTransition = reduceMotion ? { duration: 0 } : QUEUE_ROW_CONTENT_TRANSITION;

  const ambientPadding =
    rowIndex % 2 === 0 ? queueRowPadding.ambient : queueRowPadding.ambientAlt;
  const selectedPadding = queueRowPadding.selected;
  // One dominant attention badge per row (stale / limited evidence / mandate
  // conflict / risk / reviewer split). Escalation/needs-ruling is already carried
  // by the burgundy spine + verdict line, so it's excluded here.
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
      className={`group relative w-full min-w-0 cursor-pointer px-phi-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-inset ${
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
        className={`grid gap-x-phi-4 ${isSelected ? 'grid-cols-[30px_minmax(0,1fr)] gap-y-phi-2' : 'grid-cols-[26px_minmax(0,1fr)]'}`}
        transition={layoutTransition}
      >
        <motion.span
          className="type-meta tabular-nums pt-px"
          initial={false}
          animate={{
            color: isSelected
              ? 'rgba(0, 20, 51, 0.68)'
              : 'rgba(0, 20, 51, 0.24)',
          }}
          transition={selectTransition}
        >
          {displayIndex}
        </motion.span>

        <div className="min-w-0">
          <div
            className={`flex min-w-0 flex-col sm:flex-row sm:items-start sm:justify-between ${
              isSelected ? 'gap-phi-3 sm:gap-phi-4' : 'gap-phi-1 sm:gap-phi-3'
            }`}
          >
            <div className="min-w-0 flex-1">
              {/* Ambient rows are one line — context belongs to the selected row. */}
              {isSelected && startup.scout.location?.trim() ? (
                <p className="mb-1.5 type-meta uppercase tracking-[0.12em] text-oxford/45">
                  {startup.scout.location.trim()}
                </p>
              ) : null}
              {/* The queue stays compressed even when selected — the Decision
                  Stage carries the subject at display scale. Selection reads
                  through weight and full ink, not size. */}
              <motion.h2
                layout={!reduceMotion}
                className={`min-w-0 break-words font-sans transition-[color,font-weight] ${
                  isSelected
                    ? 'text-[clamp(15px,1.3vw,18px)] font-semibold leading-[1.15] tracking-[-0.01em] text-oxford'
                    : 'text-[clamp(14px,1.15vw,16px)] font-normal leading-[1.15] tracking-[-0.01em] text-oxford/55'
                }`}
                style={{ transitionDuration: `${selectTransition.duration}s`, transitionTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)' }}
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
              />
            </motion.div>
          </div>

          {/* Meta row — selected only; ambient rows stay a single line. */}
          {isSelected && hasMetaRow ? (
            <motion.div
              layout={!reduceMotion}
              className="mt-phi-2 flex min-w-0 flex-wrap items-center gap-x-phi-2 gap-y-phi-1"
              initial={reduceMotion ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={selectTransition}
            >
              {sectorStage ? (
                <p className="type-meta uppercase tracking-[0.06em] text-oxford/42">{sectorStage}</p>
              ) : null}
              {showDateMeta ? (
                <>
                  {metaSep(Boolean(sectorStage))}
                  <span className="type-meta tracking-[0.06em] text-oxford/42">
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
                    className="type-meta uppercase tracking-[0.08em] text-oxford/55"
                    title="Company Resolver: identity evidence is incomplete — open the memo to see what was found and what's missing."
                  >
                    {resolutionBadge}
                  </span>
                </>
              ) : null}
            </motion.div>
          ) : null}

          <AnimatePresence initial={false} mode="popLayout">
            {/* Description lives only on the selected row — ambient rows stay calm. */}
            {isSelected && oneLiner ? (
              <motion.p
                key="oneliner-selected"
                layout
                initial={reduceMotion ? false : { opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
                transition={contentTransition}
                className="mt-phi-3 queue-row-prose text-[14px] leading-[1.55] text-oxford/72"
              >
                {oneLiner}
              </motion.p>
            ) : isSelected && attentionDriver.detail ? (
              <motion.p
                key="detail"
                layout
                initial={reduceMotion ? false : { opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
                transition={contentTransition}
                className="mt-phi-3 queue-row-prose text-[14px] leading-[1.55] text-oxford/62"
              >
                {attentionDriver.detail}
              </motion.p>
            ) : null}
          </AnimatePresence>
        </div>
      </motion.div>
    </motion.div>
  );
});

export default DocketCaseRow;
