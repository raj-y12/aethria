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
import { QUEUE_ROW_SELECT_TRANSITION } from './queueRowMotion';
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
 * One matter on the docket. Selection reads through ink and space alone — the
 * row opens out, the name takes its display face, and the record follows. The
 * tint and text share the same horizontal gutter as the system-rail buttons.
 */
const DocketCaseRow = forwardRef<HTMLDivElement, DocketCaseRowProps>(function DocketCaseRow(
  { model, isSelected, rowIndex = 0, onClick, onKeyDown },
  ref
) {
  const reduceMotion = usePrefersReducedMotion();
  const {
    startup,
    decisionVariant,
    queueContext,
    attentionDriver,
    sectorStage,
    sortKeyValue,
  } = model;

  const { isDecided, ageDays } = queueContext;

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
      className={`group relative w-full min-w-0 cursor-pointer px-phi-4 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-inset ${
        isSelected ? 'bg-surface-selected' : 'hover:bg-oxford/[0.04]'
      }`}
      style={{ transitionTimingFunction: 'var(--motion-ease)' }}
    >
      <div className="min-w-0">
        {/* Selected rows stack like a mini masthead — the title owns the full
            column width so it never fights the verdict chip for space. Ambient
            rows keep the one-line name + quiet status ledger layout. */}
        <div
          className={`flex min-w-0 ${
            isSelected
              ? 'flex-col gap-phi-3'
              : 'flex-col gap-phi-1 sm:flex-row sm:items-start sm:justify-between sm:gap-phi-3'
          }`}
        >
          <div className="min-w-0 flex-1">
            {isSelected && startup.scout.location?.trim() ? (
              <p className="mb-1.5 type-meta uppercase tracking-[0.12em] text-oxford/60">
                {startup.scout.location.trim()}
              </p>
            ) : null}
            {/* Keyed on selection: the title fades in already set in its final
                face — tweening font-weight steps across Playfair's static files. */}
            <motion.h2
              key={isSelected ? 'selected' : 'ambient'}
              initial={reduceMotion ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              className={`min-w-0 break-words ${
                isSelected
                  ? 'text-balance font-display text-[clamp(28px,2.6vw,36px)] font-medium leading-[1.1] tracking-[-0.02em] text-oxford'
                  : 'font-sans text-[clamp(16px,1.3vw,19px)] font-medium leading-[1.2] tracking-[-0.01em] text-oxford/[0.72] transition-colors group-hover:text-oxford'
              }`}
              transition={selectTransition}
            >
              {startup.scout.name}
            </motion.h2>
          </div>
          <div className={isSelected ? 'shrink-0' : 'shrink-0 sm:text-right sm:pt-px'}>
            <QueueVerdictLine
              ctx={queueContext}
              decisionVariant={decisionVariant}
              prominent={isSelected}
              attentionDriver={attentionDriver}
            />
          </div>
        </div>

        {isSelected && hasMetaRow ? (
          <motion.div
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
  );
});

export default DocketCaseRow;
