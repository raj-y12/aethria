import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import WorkGrid from '../components/WorkGrid';
import PanelShell from '../components/PanelShell';
import DecisionStage from '../components/DecisionStage';
import EmptyState from '../components/EmptyState';
import InvestmentMemo from '../components/InvestmentMemo';
import InvestmentMemoContent, { type InvestmentMemoContentHandle } from '../components/InvestmentMemoContent';
import AgentDispatch from '../components/AgentDispatch';
import GhostTransition from '../components/GhostTransition';
import { useAppFrame } from '../components/AppFrame';
import { tokens } from '../design-system/tokens';
import { transitionOrReduced } from '../design-system/motion';
import { productInteraction } from '../design-system/productSystem';
import {
  useEscapeKey,
  useMediaQuery,
  usePrefersReducedMotion,
  useRestoreFocus,
  useFundConfiguration,
} from '../hooks';
import { useAcknowledgeStartup } from '../hooks/useAcknowledgeStartup';
import { fetchStartupDetail } from '../api/startups';
import { getQueryConfig } from '../lib/queryIntent';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup } from '../types/startup';

const PANEL_ACTION_CLASS = productInteraction.panelActionInline;

/**
 * Flow — the judgment workspace: queue | active decision. The queue is
 * compressed utility; the right column is the Decision Stage, where the
 * active company dominates the canvas (huge conviction, the state of the
 * call, the name at display scale) with the full memo flowing beneath it.
 * The stage always has a subject — the top of the queue takes the canvas
 * until the principal chooses otherwise.
 */
export default function FlowPage({ data }: { data: SystemData }) {
  const { startups, signals, watchlistAnalytics } = data;
  const { inlineDispatch, setPageOverlayOpen } = useAppFrame();
  const { configuration: fundConfiguration } = useFundConfiguration(data.settings);
  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const reduceMotion = usePrefersReducedMotion();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const [selectedStartup, setSelectedStartup] = useState<Startup | null>(null);
  const restoreRef = useRef<HTMLElement | null>(null);
  const memoContentRef = useRef<InvestmentMemoContentHandle | null>(null);

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

  // Deep link from Today / Dispatch / Portfolio / Fund: /v1/flow?open=<id> opens the memo.
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
    queryFn: () => fetchStartupDetail(selectedStartup!.id),
    enabled: Boolean(selectedStartup?.id && memoOpen),
    ...getQueryConfig('STATIC'),
  });
  /** Full payload for memo (list row is thin; detail fetched on demand). */
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

  // The stage holds its subject: a queued row replaces it, nothing closes it.
  // Escape applies only to the mobile modal.
  useEscapeKey(handleCloseMemo, memoOpen && !isDesktop);
  useRestoreFocus(memoOpen, restoreRef, true);

  // Auto-selection (desktop): the top of the queue takes the canvas without
  // being acknowledged — only a deliberate click marks a row as seen.
  const handleAutoSelect = useCallback((startup: Startup) => {
    setSelectedStartup(startup);
  }, []);

  // Small viewports show the memo as a modal; the frame owns body scroll locking.
  const useModal = Boolean(selectedStartup && !isDesktop);
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
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <div className="mx-auto flex h-full min-h-0 w-full max-w-[1180px] flex-col px-phi-5 pb-phi-8 pt-phi-5">
        {/* Mobile dispatch — desktop research goes through ⌘K */}
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

        <div className="aethria-flow-grid flex min-h-0 flex-1 flex-col overflow-hidden lg:grid">
          {/* ── Queue ─────────────────────────────────────────────── */}
          <section
            className="min-h-0 overflow-y-auto overscroll-contain lg:border-r lg:border-oxford/[0.06] lg:pr-phi-4"
            aria-label="Decision queue"
          >
            <GhostTransition disableLift className="min-h-full w-full min-w-0">
              <WorkGrid
                startups={startups}
                onStartupClick={handleStartupClick}
                selectedId={selectedStartup?.id ?? null}
                watchlistIds={watchlistIds}
                fundConfiguration={fundConfiguration}
                autoSelectFirst={isDesktop}
                onAutoSelect={handleAutoSelect}
              />
            </GhostTransition>
          </section>

          {/* ── Active decision ───────────────────────────────────── */}
          <aside
            className="hidden min-h-0 min-w-0 flex-col overflow-hidden bg-paper lg:flex lg:pl-phi-4"
            aria-live="polite"
            aria-label="Active decision"
          >
            {selectedStartup ? (
              <PanelShell
                className="min-h-0 min-w-0 w-full flex-1 bg-paper"
                title="Active decision"
                headerClassName="!items-start !px-phi-0 !py-phi-2 min-h-[44px]"
                actions={
                  <button
                    type="button"
                    onClick={() => memoContentRef.current?.downloadPDF()}
                    className={PANEL_ACTION_CLASS}
                    aria-label="Download IC pack as PDF"
                  >
                    IC pack (PDF)
                  </button>
                }
                contentClassName="memoShellContent memoShellContent--workspace bg-paper px-phi-0 pt-phi-1 pb-phi-6"
              >
                {/* Enter-only when swapping deals: keyed motion.div remounts instantly;
                    only the incoming decision fades in. */}
                <motion.div
                  key={memoStartup!.id}
                  initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={transitionOrReduced(reduceMotion, {
                    duration: tokens.motion.duration.micro,
                    ease: tokens.motion.ease,
                  })}
                  className="h-full min-h-full bg-paper"
                >
                  <InvestmentMemoContent
                    ref={memoContentRef}
                    startup={memoStartup!}
                    embedded
                    coverOverride={
                      <DecisionStage startup={memoStartup!} fundConfiguration={fundConfiguration} />
                    }
                    onMemoPipelineReady={handleMemoPipelineReady}
                    onDecisionResolved={handleDecisionResolved}
                    fundConfiguration={fundConfiguration}
                    peerStartups={startups}
                    portfolioSignals={signals}
                  />
                </motion.div>
              </PanelShell>
            ) : startups.length === 0 ? (
              <div className="flex h-full items-center justify-center px-phi-0">
                <EmptyState
                  label="Decision stage"
                  body="Scouts are filling the workspace against the active mandate. The first matter takes the stage as soon as it lands."
                />
              </div>
            ) : null}
          </aside>
        </div>
      </div>

      {/* Memo modal on small viewports; on desktop the right column shows the memo. */}
      <AnimatePresence initial={false}>
        {useModal && memoStartup && (
          <InvestmentMemo
            key={`memo-${memoStartup.id}`}
            startup={memoStartup}
            onClose={handleCloseMemo}
            onMemoPipelineReady={handleMemoPipelineReady}
            onDecisionResolved={handleDecisionResolved}
            fundConfiguration={fundConfiguration}
            peerStartups={startups}
            portfolioSignals={signals}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
