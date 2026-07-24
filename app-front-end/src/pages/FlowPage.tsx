import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import WorkGrid from '../components/WorkGrid';
import type { QueueView } from '../components/queue/DecisionQueueHeader';
import InvestmentMemo from '../components/InvestmentMemo';
import InvestmentMemoContent, { type InvestmentMemoContentHandle } from '../components/InvestmentMemoContent';
import AgentDispatch from '../components/AgentDispatch';
import RoomHeader from '../components/RoomHeader';
import { workspaceLayout } from '../design-system/workspaceLayout';
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
import { isDealUnresolved } from '../lib/dealState';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup } from '../types/startup';
import CsvImportDrawer from '../components/institutional/CsvImportDrawer';

/**
 * A readout that is also the instrument's control: the numeral reads the queue
 * and clicking it sets the view. One chrome band — no second tab strip below.
 */
function ReadoutKey({
  label,
  value,
  tone,
  active,
  onClick,
}: {
  label: string;
  value: string;
  tone?: 'escalation';
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className="group flex flex-col items-start gap-phi-1 border-0 bg-transparent p-0 text-left btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35"
    >
      <span
        className={`type-data text-[clamp(22px,2vw,30px)] leading-none transition-colors ${
          tone === 'escalation'
            ? 'text-escalation'
            : active
              ? 'text-oxford'
              : 'text-oxford/60 group-hover:text-oxford/70'
        }`}
      >
        {value}
      </span>
      <span className="type-label-section relative transition-colors group-hover:text-oxford">
        {label}
        <span
          aria-hidden
          className={`absolute -bottom-[5px] left-0 right-0 h-[2px] bg-oxford transition-opacity ${
            active ? 'underline-draw opacity-100' : 'opacity-0'
          }`}
        />
      </span>
    </button>
  );
}

/**
 * Flow — the judgment workspace. One room header (like Portfolio and Fund), a
 * compressed docket on the left, and the active memo on the right. No nested
 * panel titles — the stage speaks through the company name and conviction.
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

  const [selectedStartup, setSelectedStartup] = useState<Startup | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const restoreRef = useRef<HTMLElement | null>(null);
  const memoContentRef = useRef<InvestmentMemoContentHandle | null>(null);
  const initialMemoRevealHandledRef = useRef(false);

  // The room header readouts are the queue views — state lives here, the
  // docket (WorkGrid) is controlled and reports its per-view counts back.
  const [queueView, setQueueView] = useState<QueueView>('PRIORITY');
  const [viewCounts, setViewCounts] = useState<Record<QueueView, number> | null>(null);
  const selectView = useCallback(
    (view: QueueView) => setQueueView((current) => (current === view && view !== 'PRIORITY' ? 'PRIORITY' : view)),
    [],
  );

  const openCount = useMemo(() => startups.filter(isDealUnresolved).length, [startups]);
  const newCount = useMemo(() => startups.filter((s) => s.is_new_to_user).length, [startups]);
  const needRuling = data.pendingEscalationCount ?? 0;

  const acknowledge = useAcknowledgeStartup(
    useCallback((updated: Startup) => {
      setSelectedStartup((current) => (current?.id === updated.id ? updated : current));
    }, []),
  );

  const handleStartupClick = useCallback(
    (startup: Startup) => {
      initialMemoRevealHandledRef.current = true;
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
      initialMemoRevealHandledRef.current = true;
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

  useEscapeKey(handleCloseMemo, memoOpen && !isDesktop);
  useRestoreFocus(memoOpen, restoreRef, true);

  const handleGridEntranceComplete = useCallback((startup: Startup) => {
    if (initialMemoRevealHandledRef.current) return;
    initialMemoRevealHandledRef.current = true;
    setSelectedStartup((current) => current ?? startup);
  }, []);

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
      <div className={`${workspaceLayout.shell} ${workspaceLayout.pageTop} ${workspaceLayout.pageBottom} flex h-full min-h-0 flex-col`}>
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

        <RoomHeader
          className={`border-b border-oxford/[0.075] ${workspaceLayout.headerBottom}`}
          eyebrow="Judgment"
          title="Flow"
          plateIndex="02 — 04"
          readouts={
            <div
              className="flex flex-wrap items-end gap-x-phi-7 gap-y-phi-4"
              role="group"
              aria-label="Queue views"
            >
              <ReadoutKey
                label="Open"
                value={openCount.toLocaleString()}
                active={queueView === 'PRIORITY'}
                onClick={() => selectView('PRIORITY')}
              />
              <ReadoutKey
                label="Need ruling"
                value={(viewCounts?.ESCALATED ?? needRuling).toLocaleString()}
                tone={(viewCounts?.ESCALATED ?? needRuling) > 0 ? 'escalation' : undefined}
                active={queueView === 'ESCALATED'}
                onClick={() => selectView('ESCALATED')}
              />
              <ReadoutKey
                label="New"
                value={(viewCounts?.NEW ?? newCount).toLocaleString()}
                active={queueView === 'NEW'}
                onClick={() => selectView('NEW')}
              />
              <ReadoutKey
                label="Stale"
                value={(viewCounts?.STALE ?? 0).toLocaleString()}
                active={queueView === 'STALE'}
                onClick={() => selectView('STALE')}
              />
              <button
                type="button"
                onClick={() => setImportOpen(true)}
                className="type-action border border-oxford/15 px-3 py-2 text-oxford transition-colors hover:border-oxford/35"
              >
                Import CSV
              </button>
            </div>
          }
        />

        {startups.length === 0 ? (
          <div className="flex min-h-0 flex-1 flex-col items-center justify-center text-center">
            <span className="block h-2 w-2 rounded-none bg-brand-mark" aria-hidden />
            <h2 className="type-display mt-phi-5 text-[clamp(26px,3vw,40px)] leading-[1.1] text-oxford">
              The pipeline is filling.
            </h2>
            <p className="type-note mt-phi-3 max-w-[36ch] text-oxford/60">
              Scouts are searching against your mandate. New matters appear here as they land.
            </p>
            <button
              type="button"
              onClick={openDispatch}
              className={`mt-phi-6 gap-phi-2 ${productInteraction.rulingChoiceIdle}`}
            >
              Dispatch a lookup
              <span className="font-normal text-oxford/60" aria-hidden>⌘K</span>
            </button>
          </div>
        ) : (
          <div className="aethria-flow-grid flex min-h-0 flex-1 flex-col overflow-hidden pt-phi-4 lg:grid">
            <section className="min-h-0 overflow-y-auto overscroll-contain lg:pr-phi-4">
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
                onEntranceComplete={isDesktop ? handleGridEntranceComplete : undefined}
              />
            </section>

            <aside className="hidden min-h-0 min-w-0 flex-col overflow-hidden bg-paper lg:flex lg:pl-phi-4" aria-live="polite">
              {selectedStartup && memoStartup ? (
                <div className="memoShellContent memoShellContent--workspace min-h-0 min-w-0 w-full flex-1 overflow-y-auto overflow-x-hidden bg-paper px-phi-0 pt-phi-3 pb-phi-6">
                  <motion.div
                    key={memoStartup.id}
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
                      startup={memoStartup}
                      embedded
                      onAddContext={() => openRerun(memoStartup)}
                      onMemoPipelineReady={handleMemoPipelineReady}
                      onDecisionResolved={handleDecisionResolved}
                      fundConfiguration={fundConfiguration}
                      peerStartups={startups}
                      portfolioSignals={signals}
                    />
                  </motion.div>
                </div>
              ) : null}
            </aside>
          </div>
        )}
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
