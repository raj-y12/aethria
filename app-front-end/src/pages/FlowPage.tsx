import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import WorkGrid from '../components/WorkGrid';
import PanelShell from '../components/PanelShell';
import LiveIntelligenceFeed from '../components/LiveIntelligenceFeed';
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
 * Flow — the judgment workspace. Queue on the left, the open memo on the
 * right. When no memo is open the right column rests on the system's live
 * judgment record: the instrument keeps reporting, the workspace is never blank.
 */
export default function FlowPage({ data }: { data: SystemData }) {
  const { startups, signals, metaReports, watchlistAnalytics } = data;
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

  // Deep link from Dispatch / Portfolio / Fund: /v1?open=<id> opens the memo.
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

  useEscapeKey(handleCloseMemo, memoOpen);
  useRestoreFocus(memoOpen, restoreRef, true);

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
    <div className="flex h-full min-h-0 flex-col px-phi-4 pb-phi-4 pt-phi-3 lg:px-phi-5 lg:pb-phi-5 lg:pt-phi-4">
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
        <section className="min-h-0 overflow-y-auto overscroll-contain" aria-label="Decision queue">
          <GhostTransition disableLift className="min-h-full w-full min-w-0">
            <WorkGrid
              startups={startups}
              onStartupClick={handleStartupClick}
              selectedId={selectedStartup?.id ?? null}
              watchlistIds={watchlistIds}
              fundConfiguration={fundConfiguration}
            />
          </GhostTransition>
        </section>

        {/* ── Memo / judgment record ────────────────────────────── */}
        <aside
          className="hidden min-h-0 min-w-0 flex-col overflow-hidden bg-paper lg:flex"
          aria-live="polite"
          aria-label={selectedStartup ? 'Memo' : 'Judgements'}
        >
          <AnimatePresence mode="wait" initial={false}>
            {selectedStartup ? (
              <motion.div
                key="flow-memo-shell"
                initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: -6 }}
                transition={transitionOrReduced(reduceMotion, {
                  duration: tokens.motion.duration.short,
                  ease: tokens.motion.ease,
                })}
                className="h-full"
              >
                <PanelShell
                  className="min-h-0 min-w-0 w-full flex-1 bg-paper"
                  title="Memo"
                  headerClassName="!items-start !py-0 !pt-phi-2 !pb-phi-2 min-h-[46px]"
                  actions={
                    <div className="flex shrink-0 items-start gap-0" role="group" aria-label="Memo controls">
                      <button
                        type="button"
                        onClick={() => memoContentRef.current?.downloadPDF()}
                        className={PANEL_ACTION_CLASS}
                        aria-label="Download IC pack as PDF"
                      >
                        IC pack (PDF)
                      </button>
                      <button
                        type="button"
                        onClick={handleCloseMemo}
                        className={PANEL_ACTION_CLASS}
                        aria-label="Close memo"
                      >
                        Close
                      </button>
                    </div>
                  }
                  contentClassName="memoShellContent memoShellContent--workspace bg-paper px-phi-4 py-phi-3 sm:px-phi-5 sm:py-phi-4"
                >
                  {/* Enter-only when swapping deals: keyed motion.div remounts instantly;
                      only the incoming memo fades in. */}
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
                      onMemoPipelineReady={handleMemoPipelineReady}
                      onDecisionResolved={handleDecisionResolved}
                      fundConfiguration={fundConfiguration}
                      peerStartups={startups}
                      portfolioSignals={signals}
                    />
                  </motion.div>
                </PanelShell>
              </motion.div>
            ) : (
              <motion.div
                key="flow-judgements-rest"
                initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: -6 }}
                transition={transitionOrReduced(reduceMotion, {
                  duration: tokens.motion.duration.short,
                  ease: tokens.motion.ease,
                })}
                className="h-full"
              >
                {/* Resting state: the system's judgment record. Selecting a
                    matter from the queue replaces this with its memo. */}
                <PanelShell
                  className="min-h-0 flex-1 bg-paper"
                  title="Judgements"
                  contentOverflowHidden
                  contentClassName="flex-1 min-h-0 overflow-hidden"
                >
                  <LiveIntelligenceFeed
                    startups={startups}
                    signals={signals}
                    metaReports={metaReports}
                  />
                </PanelShell>
              </motion.div>
            )}
          </AnimatePresence>
        </aside>
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
