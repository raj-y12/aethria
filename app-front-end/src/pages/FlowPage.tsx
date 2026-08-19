import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import WorkGrid from '../components/WorkGrid';
import type { QueueView } from '../components/queue/DecisionQueueHeader';
import InvestmentMemo from '../components/InvestmentMemo';
import InvestmentMemoContent from '../components/InvestmentMemoContent';
import AgentDispatch from '../components/AgentDispatch';
import { useAppFrame } from '../components/AppFrame';
import { productInteraction } from '../design-system/productSystem';
import { workspaceLayout } from '../design-system/workspaceLayout';
import { tokens } from '../design-system/tokens';
import {
  useEscapeKey,
  useMediaQuery,
  usePrefersReducedMotion,
  useRestoreFocus,
  useFundConfiguration,
} from '../hooks';
import { useAcknowledgeStartup } from '../hooks/useAcknowledgeStartup';
import { fetchStartupDetail } from '../api/startups';
import { fetchIdentityCases } from '../api/identity';
import { getQueryConfig } from '../lib/queryIntent';
import { isDealUnresolved } from '../lib/dealState';
import { docketHeadline } from '../lib/docketHeadline';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup } from '../types/startup';
import CsvImportDrawer from '../components/institutional/CsvImportDrawer';

/**
 * A view key — the docket's own quiet register. The headline already carries the
 * state in words, so these stay a mono line rather than a second bank of figures.
 */
function ViewKey({
  label,
  count,
  active,
  tone,
  onClick,
}: {
  label: string;
  count?: string;
  active: boolean;
  tone?: 'escalation' | 'new';
  onClick: () => void;
}) {
  const reduceMotion = usePrefersReducedMotion();
  // 'new' claims the same solid oxford/paper treatment as the app's primary
  // CTA buttons (.btn-aethria-solid) -- it's the one view that says "look at
  // this" rather than "here's where you are", so it skips the shared sliding
  // selection overlay other tabs use.
  if (tone === 'new') {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-pressed={active}
        className="type-action new-arrival-pulse inline-flex min-h-[32px] shrink-0 cursor-pointer items-center bg-oxford px-phi-4 py-phi-1 text-paper btn-interaction btn-interaction--no-press transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 hover:opacity-90"
      >
        <span className="inline-flex items-baseline gap-phi-2">
          {label}
          {count != null ? <span className="tabular-nums">{count}</span> : null}
        </span>
      </button>
    );
  }
  const idle =
    tone === 'escalation'
      ? 'text-escalation/80 hover:bg-oxford/[0.04] hover:text-escalation'
      : 'text-oxford/65 hover:bg-oxford/[0.04] hover:text-oxford/80';
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`type-action group relative min-h-[32px] shrink-0 cursor-pointer px-phi-4 py-phi-1 btn-interaction btn-interaction--no-press transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${
        active ? 'bg-surface-selected text-oxford' : idle
      }`}
      style={{ transitionTimingFunction: 'var(--motion-ease)' }}
    >
      {active ? (
        <motion.span
          layoutId="docket-view-active"
          className="absolute inset-0 bg-surface-selected"
          transition={reduceMotion ? { duration: 0 } : { duration: 0.3, ease: tokens.motion.easeInOut }}
          aria-hidden
        />
      ) : null}
      <span className="relative inline-flex items-baseline gap-phi-2">
        {label}
        {count != null ? <span className="tabular-nums">{count}</span> : null}
      </span>
    </button>
  );
}

/**
 * Flow — the judgment workspace. A framed docket on paper: the state named in a
 * mono kicker, said again in display type, then the matters themselves. Opening
 * a company raises the memo as an overlay, so the docket keeps the whole room.
 */
export default function FlowPage({ data }: { data: SystemData }) {
  const { startups, signals, watchlistAnalytics } = data;
  const {
    inlineDispatch,
    setPageOverlayOpen,
    openDispatch,
    openRerun,
    workspaceChromeReady,
  } = useAppFrame();
  const { configuration: fundConfiguration } = useFundConfiguration(data.settings);
  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const reduceMotion = usePrefersReducedMotion();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const identityCasesQuery = useQuery({
    queryKey: ['identity', 'cases', 'open'],
    queryFn: () => fetchIdentityCases('open', 100),
    ...getQueryConfig('SEMI_DYNAMIC', { pollIntervalMs: 30_000 }),
    refetchInterval: 30_000,
  });
  const identityReviewCount = identityCasesQuery.data?.length ?? 0;

  const [selectedStartup, setSelectedStartup] = useState<Startup | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const restoreRef = useRef<HTMLElement | null>(null);

  // The view keys are state, the docket (WorkGrid) is controlled and reports its
  // per-view counts back so the kicker and headline can never disagree with it.
  const [queueView, setQueueView] = useState<QueueView>('PRIORITY');
  const [viewCounts, setViewCounts] = useState<Record<QueueView, number> | null>(null);
  const selectView = useCallback(
    (view: QueueView) => setQueueView((current) => (current === view && view !== 'PRIORITY' ? 'PRIORITY' : view)),
    [],
  );
  const openIdentityReview = useCallback(() => {
    window.dispatchEvent(new CustomEvent('aethria:open-identity-review'));
  }, []);

  const openCount = useMemo(() => startups.filter(isDealUnresolved).length, [startups]);
  const newCount = useMemo(() => startups.filter((s) => s.is_new_to_user).length, [startups]);
  const needRuling = data.pendingEscalationCount ?? 0;

  const escalatedCount = viewCounts?.ESCALATED ?? needRuling;
  const staleCount = viewCounts?.STALE ?? 0;
  const shownCount =
    queueView === 'ESCALATED'
      ? escalatedCount
      : queueView === 'NEW'
        ? (viewCounts?.NEW ?? newCount)
        : queueView === 'STALE'
          ? staleCount
          : openCount;

  const { eyebrow, urgent } = docketHeadline(queueView, { shown: shownCount, needRuling });

  // What the docket is not showing, and is handling on its own.
  const restOpen = Math.max(0, openCount - shownCount);
  const monitored = watchlistAnalytics.total;

  const acknowledge = useAcknowledgeStartup(
    useCallback((updated: Startup) => {
      setSelectedStartup((current) => (current?.id === updated.id ? updated : current));
    }, []),
  );

  const handleStartupClick = useCallback(
    (startup: Startup) => {
      restoreRef.current = document.activeElement as HTMLElement | null;
      setSelectedStartup(startup.is_new_to_user ? acknowledge(startup) : startup);
    },
    [acknowledge],
  );

  useEffect(() => {
    const openId = searchParams.get('open');
    if (!openId || startups.length === 0) return;
    const match = startups.find((s) => s.id === openId);
    if (match) {
      setSelectedStartup(match.is_new_to_user ? acknowledge(match) : match);
    }
    const params = new URLSearchParams(searchParams);
    params.delete('open');
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams, startups, acknowledge]);

  const memoOpen = !!selectedStartup;
  const startupDetailQuery = useQuery({
    queryKey: ['startup', 'detail', selectedStartup?.id],
    queryFn: () => fetchStartupDetail(selectedStartup!.id, selectedStartup!.canonical_opportunity_id),
    enabled: Boolean(selectedStartup?.id && memoOpen),
    ...getQueryConfig('STATIC'),
  });
  const memoStartup = startupDetailQuery.data ?? selectedStartup;

  const handleMemoPipelineReady = useCallback(() => {
    const id = selectedStartup?.id;
    if (id) void queryClient.invalidateQueries({ queryKey: ['startup', 'detail', id] });
  }, [queryClient, selectedStartup?.id]);

  const handleDecisionResolved = useCallback(
    (nextStartup: Startup) => {
      queryClient.setQueryData<Startup[]>(['startups', 'list'], (prev) =>
        prev?.map((s) => (s.id === nextStartup.id ? nextStartup : s)) ?? prev,
      );
      queryClient.setQueryData<Startup | null>(['startup', 'detail', nextStartup.id], nextStartup);
      setSelectedStartup((current) => (current?.id === nextStartup.id ? nextStartup : current));
      void queryClient.invalidateQueries({ queryKey: ['escalations'] });
      void queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
    [queryClient],
  );

  const handleCloseMemo = useCallback(() => setSelectedStartup(null), []);

  useEscapeKey(handleCloseMemo, memoOpen);
  useRestoreFocus(memoOpen, restoreRef, true);

  // Desktop opens the memo beside the docket: the docket gives up the room it
  // was centred in and settles left, the memo rises on the right. Below lg there
  // is no room for two columns, so the memo takes the screen as a modal instead.
  const splitOpen = isDesktop && Boolean(selectedStartup);
  const useModal = Boolean(selectedStartup) && !isDesktop;
  useEffect(() => {
    setPageOverlayOpen(useModal);
    return () => setPageOverlayOpen(false);
  }, [useModal, setPageOverlayOpen]);

  const watchlistIds = useMemo(() => {
    const ids = new Set<string>();
    for (const e of watchlistAnalytics?.entries ?? []) {
      if (e?.startup_id) ids.add(e.startup_id);
    }
    return ids;
  }, [watchlistAnalytics]);

  return (
    <div className="paper-dot-grid flex h-full min-h-0 flex-1 overflow-hidden">
      {/* The room measure — the same shell (--room-max) the workspace has always
          used, so Flow lines up with Portfolio and Fund. The split happens inside
          it rather than across the whole viewport. */}
      <div
        className={`${workspaceLayout.shell} ${workspaceLayout.pageTop} ${workspaceLayout.pageBottom} flex h-full min-h-0 flex-col gap-phi-5`}
      >
        <motion.div
          initial={false}
          animate={{ width: splitOpen ? '100%' : 'min(100%, 920px)' }}
          transition={reduceMotion ? { duration: 0 } : { duration: 0.5, ease: tokens.motion.ease }}
          className="mx-auto flex min-h-[32px] flex-none items-center gap-x-phi-5 bg-surface-canvas/95 backdrop-blur-[2px]"
        >
          <p className="type-action flex min-w-0 flex-1 items-center gap-phi-2 text-oxford/65">
            <span
              aria-hidden
              className={`h-[6px] w-[6px] shrink-0 ${urgent ? 'bg-escalation' : 'bg-oxford/25'}`}
            />
            <span className="truncate">{eyebrow}</span>
          </p>

          <div className="ml-auto flex shrink-0 items-center justify-end gap-x-phi-2">
            {identityReviewCount > 0 ? (
              <ViewKey
                label="Identity"
                count={identityReviewCount.toLocaleString()}
                tone="escalation"
                active={false}
                onClick={openIdentityReview}
              />
            ) : null}
            <ViewKey label="Import CSV" active={false} onClick={() => setImportOpen(true)} />
          </div>

        </motion.div>

        <div className="flex min-h-0 flex-1 gap-phi-5">
        {/* The docket column. Closed, it takes the room, centred on a 920px
            measure. Open, it yields to 38 / 62 — the workspace's original φ split
            (38.2 : 61.8) — and settles left while the memo rises beside it. One
            motion, driven by flex-basis so the type never scales. */}
        <motion.div
          initial={false}
          animate={{ flexBasis: splitOpen ? '38%' : '100%' }}
          transition={reduceMotion ? { duration: 0 } : { duration: 0.5, ease: tokens.motion.ease }}
          className="flex min-h-0 min-w-0 shrink-0 grow-0 flex-col overflow-hidden px-phi-6"
        >
        <div className="mx-auto flex min-h-0 w-full max-w-[920px] flex-1 flex-col">
        <div className="flex-none pb-phi-4 lg:hidden">
          <AgentDispatch
            input={inlineDispatch.input}
            setInput={inlineDispatch.setInput}
            onSubmit={inlineDispatch.onSubmit}
            onCancel={inlineDispatch.onCancel}
            isBusy={inlineDispatch.isBusy}
            message={inlineDispatch.message}
            onClearMessage={inlineDispatch.onClearMessage}
            lookupPhase={inlineDispatch.lookupPhase}
          />
        </div>

        {startups.length === 0 ? (
          <div className="flex min-h-[50vh] flex-col items-center justify-center text-center">
            <span className="block h-2 w-2 rounded-none bg-brand-mark" aria-hidden />
            <h2 className="type-display mt-phi-5 text-[clamp(26px,3vw,40px)] leading-[1.1] text-oxford">
              The pipeline is filling.
            </h2>
            <p className="type-note mt-phi-3 max-w-[36ch] text-oxford/65">
              Scouts are searching against your mandate. New matters appear here as they land.
            </p>
            <button
              type="button"
              onClick={openDispatch}
              className={`mt-phi-6 gap-phi-2 ${productInteraction.rulingChoiceIdle}`}
            >
              Dispatch a lookup
              <span className="font-normal text-oxford/65" aria-hidden>⌘K</span>
            </button>
          </div>
        ) : (
          /* ── The docket, framed in both states. The frame is fixed to the
                column and the matters scroll inside it, so the brackets stay
                put and the headline and tally never leave the screen. ── */
          <div className="focus-frame focus-frame--docket mt-phi-5 mb-phi-5 flex min-h-0 flex-1 flex-col">
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
              <WorkGrid
                startups={startups}
                onStartupClick={handleStartupClick}
                selectedId={selectedStartup?.id ?? null}
                watchlistIds={watchlistIds}
                fundConfiguration={fundConfiguration}
                queueView={queueView}
                onQueueViewChange={setQueueView}
                onViewCounts={setViewCounts}
                entranceReady={workspaceChromeReady}
                viewsSlot={
                  <>
                    {/* Never wraps: at the docket's 38% basis a wrapping row breaks
                        onto three lines and shoves the list down. It scrolls
                        sideways instead, like the fund facets. */}
                    <nav
                      className="no-scrollbar flex min-w-0 flex-nowrap items-center gap-x-phi-1 overflow-x-auto"
                      aria-label="Queue views"
                    >
                      <ViewKey
                        label="Open"
                        count={openCount.toLocaleString()}
                        active={queueView === 'PRIORITY'}
                        onClick={() => selectView('PRIORITY')}
                      />
                      <ViewKey
                        label="Need ruling"
                        count={escalatedCount.toLocaleString()}
                        tone={escalatedCount > 0 ? 'escalation' : undefined}
                        active={queueView === 'ESCALATED'}
                        onClick={() => selectView('ESCALATED')}
                      />
                      <ViewKey
                        label="New"
                        count={(viewCounts?.NEW ?? newCount).toLocaleString()}
                        tone={(viewCounts?.NEW ?? newCount) > 0 ? 'new' : undefined}
                        active={queueView === 'NEW'}
                        onClick={() => selectView('NEW')}
                      />
                      <ViewKey
                        label="Stale"
                        count={staleCount.toLocaleString()}
                        active={queueView === 'STALE'}
                        onClick={() => selectView('STALE')}
                      />
                    </nav>
                  </>
                }
              />
            </div>

            {restOpen > 0 || monitored > 0 ? (
              <p className="type-meta mt-phi-4 flex-none border-t border-oxford/[0.08] pt-phi-4 text-oxford/[0.42]">
                Everything else — {restOpen.toLocaleString()} open, {monitored.toLocaleString()} monitored — is
                still moving on its own.
              </p>
            ) : null}
          </div>
        )}
        </div>
      </motion.div>

      {/* ── The memo, risen beside the docket. Mounted plainly rather than
            through AnimatePresence: an exiting flex child collapses to a zero
            basis as the docket reclaims the row, which squashes the memo's
            columns mid-fade. It leaves at once and the docket glides back. ── */}
      {splitOpen && memoStartup ? (
        <motion.aside
          key={memoStartup.id}
          initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: 26 }}
          animate={{ opacity: 1, y: 0 }}
          transition={reduceMotion ? { duration: 0 } : { duration: 0.42, ease: tokens.motion.ease }}
          aria-live="polite"
          className="min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-contain bg-paper"
        >
          <InvestmentMemoContent
            startup={memoStartup}
            embedded
            onClose={handleCloseMemo}
            onAddContext={() => openRerun(memoStartup)}
            onMemoPipelineReady={handleMemoPipelineReady}
            onDecisionResolved={handleDecisionResolved}
            fundConfiguration={fundConfiguration}
            peerStartups={startups}
            portfolioSignals={signals}
          />
        </motion.aside>
      ) : null}
      </div>
      </div>

      <AnimatePresence initial={false}>
        {useModal && memoStartup && (
          <InvestmentMemo
            key={`memo-${memoStartup.id}`}
            startup={memoStartup}
            onClose={handleCloseMemo}
            onAddContext={() => {
              // Takeover lives inside AppFrame (z-20) below this body portal — close first.
              handleCloseMemo();
              openRerun(memoStartup);
            }}
            onMemoPipelineReady={handleMemoPipelineReady}
            onDecisionResolved={handleDecisionResolved}
            fundConfiguration={fundConfiguration}
            peerStartups={startups}
            portfolioSignals={signals}
          />
        )}
      </AnimatePresence>
      <CsvImportDrawer open={importOpen} onClose={() => setImportOpen(false)} />
    </div>
  );
}
