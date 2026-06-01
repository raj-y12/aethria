import { forwardRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { usePrefersReducedMotion } from '../../hooks';
import type { VerdictBadgeConfig } from '../../lib/fundConfiguration';
import QueueVerdictLine from './QueueVerdictLine';
import {
  buildRowAriaLabel,
  formatRowDate,
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

  const { isStale, isEscalated, isDecided, ageDays } = queueContext;
  const isEscalationState =
    isEscalated || decisionVariant === 'escalation' || attentionDriver.key === 'needs_ruling';

  /** Coloured spine: selected row (oxford) or escalation (burgundy) only. */
  const spineVisible = isSelected || isEscalationState;
  const spineColor = !spineVisible
    ? 'transparent'
    : isEscalationState
      ? isSelected
        ? '#7D2B3A'
        : 'rgba(125, 43, 58, 0.38)'
      : '#001433';
  const spineWidth = spineVisible ? (isSelected ? 3 : 2) : 0;

  const layoutTransition = reduceMotion ? { duration: 0 } : QUEUE_ROW_LAYOUT_TRANSITION;
  const selectTransition = reduceMotion ? { duration: 0 } : QUEUE_ROW_SELECT_TRANSITION;
  const contentTransition = reduceMotion ? { duration: 0 } : QUEUE_ROW_CONTENT_TRANSITION;

  const ambientPadding =
    rowIndex % 2 === 0 ? queueRowPadding.ambient : queueRowPadding.ambientAlt;
  const selectedPadding = queueRowPadding.selected;
  const showReviewerSplitMeta =
    attentionDriver.key === 'reviewer_split' && !isEscalationState;
  const showStaleMeta = isStale && ageDays != null && !isDecided;
  const showDateMeta = isSelected && Boolean(sortKeyValue);
  const hasMetaRow =
    Boolean(sectorStage) || showStaleMeta || showReviewerSplitMeta || showDateMeta;

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
      className={`group relative w-full min-w-0 cursor-pointer px-phi-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-inset ${
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
            <motion.h2
              layout={!reduceMotion}
              className={`min-w-0 flex-1 break-words font-sans transition-[color,font-weight] ${
                isSelected
                  ? 'font-semibold text-oxford text-[length:var(--case-title-size)] leading-[var(--case-title-leading)] tracking-[var(--case-title-tracking)]'
                  : 'text-[clamp(15px,1.4vw,20px)] font-normal leading-[1.08] tracking-[-0.02em] text-oxford/52'
              }`}
              style={{ transitionDuration: `${selectTransition.duration}s`, transitionTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)' }}
              transition={selectTransition}
            >
              {startup.scout.name}
            </motion.h2>
            <motion.div layout={!reduceMotion} className="shrink-0 sm:text-right sm:pt-px" transition={layoutTransition}>
              <QueueVerdictLine
                ctx={queueContext}
                decisionVariant={decisionVariant}
                prominent={isSelected}
              />
            </motion.div>
          </div>

          <motion.div
            layout={!reduceMotion}
            className="flex min-w-0 flex-wrap items-center gap-x-phi-2 gap-y-phi-1"
            initial={false}
            animate={{ marginTop: isSelected ? 6 : hasMetaRow ? 3 : 2 }}
            transition={selectTransition}
          >
            {sectorStage ? (
              <p className={`type-meta tracking-[0.06em] ${isSelected ? 'text-oxford/42' : 'text-oxford/30'}`}>
                {sectorStage}
              </p>
            ) : null}
            {showDateMeta ? (
              <>
                {metaSep(Boolean(sectorStage))}
                <span className={`type-meta tracking-[0.06em] ${isSelected ? 'text-oxford/42' : 'text-oxford/30'}`}>
                  {formatRowDate(sortKeyValue)}
                </span>
              </>
            ) : null}
            {showStaleMeta ? (
              <>
                {metaSep(Boolean(sectorStage || showDateMeta))}
                <span
                  className={`font-mono tracking-[0.06em] ${
                    isSelected ? 'text-[10px] text-brass' : 'text-[9px] text-brass/90'
                  }`}
                >
                  Stale · {ageDays}d
                </span>
              </>
            ) : null}
            {showReviewerSplitMeta ? (
              <>
                {metaSep(Boolean(sectorStage || showDateMeta || showStaleMeta))}
                <span
                  className={`font-mono normal-case tracking-[0.04em] ${
                    isSelected ? 'text-[10px] text-escalation' : 'text-[9px] text-escalation/75'
                  }`}
                >
                  Reviewer split
                </span>
              </>
            ) : null}
          </motion.div>

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
