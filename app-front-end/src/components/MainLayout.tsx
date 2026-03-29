import { useMemo, useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import SystemBar from './SystemBar';
import MobileHeader from './MobileHeader';
import PanelShell from './PanelShell';
import WorkGrid from './WorkGrid';
import InvestmentMemo from './InvestmentMemo';
import LiveIntelligenceFeed from './LiveIntelligenceFeed';
import GhostTransition from './GhostTransition';
import SystemIntelligence from './SystemIntelligence';
import {
  useScrollLock,
  useEscapeKey,
  useRestoreFocus,
  useFocusTrap,
  useMediaQuery,
} from '../hooks';
import type { Startup, EscalationItem } from '../types/startup';
import type { SystemData } from '../hooks/useSystemData';
import InvestmentMemoContent, { type InvestmentMemoContentHandle } from './InvestmentMemoContent';

const SYSTEM_MEMO_HEADER_PADDING = 'py-[10px]';

const PANEL_CHROME_LABEL_CLASS =
  'font-mono text-[10px] font-normal uppercase tracking-[0.1em] text-oxford/40';

const PANEL_CHROME_ACTION_BTN_CLASS =
  `${PANEL_CHROME_LABEL_CLASS} rounded-none border-0 bg-transparent p-0 cursor-pointer hover:text-oxford/80 transition-colors duration-150 ease-out btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset`;

interface MainLayoutProps {
  data: SystemData;
  startupsError?: string | null;
}

export default function MainLayout({ data, startupsError }: MainLayoutProps) {
  const {
    startups,
    escalations,
    signals,
    metaReports,
    rejectionAnalytics,
    watchlistAnalytics,
    concentrationAnalytics,
    scoutWeights,
    calibrationState,
  } = data;
  const [selectedStartup, setSelectedStartup] = useState<Startup | null>(null);
  const [rightPanel, setRightPanel] = useState<'memo' | 'feed' | 'system' | null>('system');

  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const restoreRefVerdictMemo = useRef<HTMLElement | null>(null);
  const judgementsPanelRef = useRef<HTMLDivElement | null>(null);
  const memoContentRef = useRef<InvestmentMemoContentHandle | null>(null);

  const memoOpen = !!selectedStartup;
  const verdictOrMemoOpen = memoOpen;
  const judgementsAsOverlay = rightPanel === 'feed' && !isDesktop;
  /** System replaces the work grid (left column); never an overlay. */
  const anyOverlayOpen = verdictOrMemoOpen || judgementsAsOverlay;
  const useModal = selectedStartup && !isDesktop;

  const handleStartupClick = useCallback((startup: Startup) => {
    restoreRefVerdictMemo.current = document.activeElement as HTMLElement | null;
    setRightPanel('memo');
    setSelectedStartup(startup);
  }, []);

  const handleOpenEscalationMemo = useCallback(
    (esc: EscalationItem) => {
      const id = esc.startup_id ?? esc.id;
      const startup = startups.find((s) => s.id === id);
      if (!startup) return;
      restoreRefVerdictMemo.current = document.activeElement as HTMLElement | null;
      setSelectedStartup(startup);
      /* Leave rightPanel unchanged so System stays on the left; memo uses selectedStartup on the right. */
    },
    [startups]
  );

  const handleCloseMemo = useCallback(() => {
    setSelectedStartup(null);
    setRightPanel(null);
  }, []);

  const handleCloseJudgements = useCallback(() => {
    setRightPanel((panel) => (panel === 'feed' ? null : panel));
  }, []);

  const handleEscape = useCallback(() => {
    if (memoOpen) handleCloseMemo();
    else if (rightPanel === 'feed') handleCloseJudgements();
    else if (rightPanel === 'system') setRightPanel(null);
  }, [memoOpen, rightPanel, handleCloseMemo, handleCloseJudgements]);

  useScrollLock(anyOverlayOpen);
  useEscapeKey(handleEscape, anyOverlayOpen);
  useRestoreFocus(verdictOrMemoOpen, restoreRefVerdictMemo, !judgementsAsOverlay);
  useRestoreFocus(judgementsAsOverlay, { current: null }, !verdictOrMemoOpen);
  useFocusTrap(judgementsAsOverlay, judgementsPanelRef);

  const resolvedCount = startups.filter((s) => s.partner?.decision != null).length;
  const queueDepths = data.settings?.system_health?.queue_depths;
  const unreviewed = queueDepths?.unreviewed ?? 0;
  const watchlist = queueDepths?.watchlist ?? 0;
  const pendingEscalations = data.settings?.system_health?.pending_escalations ?? 0;
  const watchlistIds = useMemo(() => {
    const ids = new Set<string>();
    for (const e of watchlistAnalytics?.entries ?? []) {
      if (e?.startup_id) ids.add(e.startup_id);
    }
    return ids;
  }, [watchlistAnalytics]);

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-paper">
      {/* Mobile / tablet top nav — desktop keeps the vertical SystemBar only */}
      {!isDesktop && (
        <>
          <MobileHeader onMenuToggle={() => setMobileMenuOpen((open) => !open)} />
          <AnimatePresence>
            {mobileMenuOpen && (
              <motion.section
                id="mobile-menu"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: tokens.motion.duration.micro, ease: tokens.motion.ease }}
                className="px-4 pb-0 border-b border-oxford/[0.06] type-label-tab bg-oxford overflow-hidden text-white/70"
                aria-label="Menu"
              >
                <div className="flex flex-col items-start gap-3 py-3">
                  {/* Mode toggles: Deals / Judgements / System — same mono scale as desktop spine */}
                  <div className="flex flex-col items-stretch gap-0.5 w-full">
                    <button
                      type="button"
                      onClick={() => {
                        setRightPanel((p) => (p === 'system' ? null : p));
                        setMobileMenuOpen(false);
                      }}
                      className={`type-meta min-h-[44px] flex items-center justify-start cursor-pointer px-0 uppercase tracking-[0.12em] btn-interaction ${
                        rightPanel !== 'system' ? 'text-white' : 'text-white/55 hover:text-white'
                      }`}
                      style={{ transitionTimingFunction: 'var(--motion-ease)' }}
                      aria-pressed={rightPanel !== 'system'}
                    >
                      <span
                        className={`inline-block pb-0.5 ${rightPanel !== 'system' ? 'border-b border-white' : ''}`}
                      >
                        Deals
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setRightPanel((panel) => (panel === 'feed' ? null : 'feed'));
                        setMobileMenuOpen(false);
                      }}
                      className={`type-meta min-h-[44px] flex items-center justify-start cursor-pointer px-0 uppercase tracking-[0.12em] btn-interaction ${
                        rightPanel === 'feed' ? 'text-white' : 'text-white/55 hover:text-white'
                      }`}
                      style={{ transitionTimingFunction: 'var(--motion-ease)' }}
                      aria-pressed={rightPanel === 'feed'}
                    >
                      <span
                        className={`inline-block pb-0.5 ${rightPanel === 'feed' ? 'border-b border-white' : ''}`}
                      >
                        Judgements
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setRightPanel((panel) => (panel === 'system' ? null : 'system'));
                        setMobileMenuOpen(false);
                      }}
                      className={`type-meta min-h-[44px] flex items-center justify-start cursor-pointer px-0 uppercase tracking-[0.12em] btn-interaction ${
                        rightPanel === 'system' ? 'text-white' : 'text-white/55 hover:text-white'
                      }`}
                      style={{ transitionTimingFunction: 'var(--motion-ease)' }}
                      aria-pressed={rightPanel === 'system'}
                    >
                      <span
                        className={`inline-block pb-0.5 ${rightPanel === 'system' ? 'border-b border-white' : ''}`}
                      >
                        System
                      </span>
                    </button>
                  </div>

                {/* Settings */}
                <div className="flex flex-col items-start gap-1 mt-3">
                  <a
                    href="/settings"
                    className="type-label-section text-white/70 hover:text-white btn-interaction"
                  >
                    Settings
                  </a>
                </div>
              </div>
              </motion.section>
            )}
          </AnimatePresence>
        </>
      )}

      <SystemBar
        scoutCount={startups.length}
        rightPanel={rightPanel}
        onShowDeals={() => setRightPanel((p) => (p === 'system' ? null : p))}
        onShowFeed={() => setRightPanel((panel) => (panel === 'feed' ? null : 'feed'))}
        onShowSystem={() => setRightPanel((panel) => (panel === 'system' ? null : 'system'))}
        onClose={() => setRightPanel(null)}
        navLink={{ href: '/settings', label: 'Settings' }}
      />
      {startupsError && (
        <div className="flex-none px-6 py-2 bg-warning border-b border-oxford/25 type-label-tab text-oxford">
          {startupsError} — Check API URL (VITE_API_URL) and backend CORS (ALLOWED_ORIGINS).
        </div>
      )}

      {/* Paper canvas. Fixed height so only WorkGrid scrolls.
          On desktop content is offset to clear vertical SystemBar; on mobile it uses standard page padding. */}
      <main className="flex-1 flex flex-col min-h-0 overflow-hidden px-4 pt-4 lg:pl-[11rem] lg:pr-6 lg:pt-6">
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        <div className="flex-1 flex flex-col lg:grid lg:grid-cols-[2fr_3fr] min-h-0 overflow-hidden pb-3 lg:pb-4 gap-4 lg:gap-4">
          <div className="flex min-w-0 min-h-0 flex-1 flex-col lg:min-h-0">
            {/* Title + pipeline summary — desktop only; escalations live here (not duplicated on SystemBar) */}
            <header className="flex-none mb-2 hidden lg:block min-w-0">
              <div>
                <h1 className="font-display font-normal text-[20px] leading-[1.4] text-oxford">
                  Aethria
                </h1>
                {data.settings?.fund_identity?.fund_name?.trim() && (
                  <p className="type-meta text-oxford/50 mt-1 tracking-[0.12em]" aria-hidden>
                    {[
                      data.settings.fund_identity.fund_name.trim(),
                      data.settings.fund_identity.stage_focus?.trim(),
                      data.settings.fund_identity.geographic_focus?.trim(),
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                )}
              </div>
              <section
                aria-label="Pipeline summary"
                className="mt-2 min-w-0 border border-oxford/[0.06] bg-paper"
              >
                <div className="min-w-0">
                  <table className="w-full table-fixed border-collapse caption-top text-left">
                    <caption className="type-meta border-b border-oxford/[0.06] px-2 py-1 text-left uppercase tracking-[0.12em] text-oxford/40">
                      Pipeline
                    </caption>
                    <colgroup>
                      <col className="w-[20%]" />
                      <col className="w-[20%]" />
                      <col className="w-[20%]" />
                      <col className="w-[20%]" />
                      <col className="w-[20%]" />
                    </colgroup>
                    <thead>
                      <tr className="bg-registerTint type-meta uppercase tracking-[0.1em] text-oxford/38">
                        <th
                          scope="col"
                          aria-label="Companies"
                          title="Companies"
                          className="border-r border-oxford/[0.06] px-1 py-1 text-center font-normal"
                        >
                          Co
                        </th>
                        <th
                          scope="col"
                          aria-label="Decided"
                          title="Decided"
                          className="border-r border-oxford/[0.06] px-1 py-1 text-center font-normal"
                        >
                          Dec
                        </th>
                        <th
                          scope="col"
                          aria-label="Unreviewed"
                          title="Unreviewed"
                          className="border-r border-oxford/[0.06] px-1 py-1 text-center font-normal"
                        >
                          Unv
                        </th>
                        <th
                          scope="col"
                          aria-label="Watchlist"
                          title="Watchlist"
                          className="border-r border-oxford/[0.06] px-1 py-1 text-center font-normal"
                        >
                          WL
                        </th>
                        <th
                          scope="col"
                          aria-label="Escalations"
                          title="Escalations"
                          className="px-1 py-1 text-center font-normal"
                        >
                          Esc
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td className="type-data border-r border-oxford/[0.06] px-1 py-1.5 text-center align-top text-oxford">
                          {startups.length}
                        </td>
                        <td className="type-data border-r border-oxford/[0.06] px-1 py-1.5 text-center align-top text-oxford">
                          {resolvedCount}
                        </td>
                        <td className="type-data border-r border-oxford/[0.06] px-1 py-1.5 text-center align-top text-oxford">
                          {unreviewed}
                        </td>
                        <td className="type-data border-r border-oxford/[0.06] px-1 py-1.5 text-center align-top text-oxford">
                          {watchlist}
                        </td>
                        <td className="px-1 py-1.5 text-center align-top">
                          <span className="type-data inline-flex items-center justify-center gap-1">
                            <span
                              className={`inline-block shrink-0 rounded-none ${
                                pendingEscalations > 0 ? 'escalation-dot-active' : ''
                              }`}
                              style={{
                                width: 5,
                                height: 5,
                                backgroundColor: '#7D2B3A',
                              }}
                              aria-hidden
                            />
                            <span
                              className={
                                pendingEscalations > 0 ? 'text-[#7D2B3A]' : 'text-oxford/40'
                              }
                            >
                              {pendingEscalations}
                            </span>
                          </span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </section>
            </header>

            {rightPanel === 'system' ? (
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden w-full min-w-0 rounded-none border border-oxford/[0.06] bg-paper">
                <PanelShell
                  className="min-h-0 flex-1"
                  title="SYSTEM"
                  titleClassName={PANEL_CHROME_LABEL_CLASS}
                  headerPaddingClass={SYSTEM_MEMO_HEADER_PADDING}
                  headerBorderClass=""
                  actions={
                    <button
                      type="button"
                      onClick={() => setRightPanel(null)}
                      className={PANEL_CHROME_ACTION_BTN_CLASS}
                      aria-label="Hide system intelligence"
                    >
                      CLOSE
                    </button>
                  }
                  contentOverflowHidden
                  contentClassName="flex-1 min-h-0 overflow-hidden"
                >
                  <SystemIntelligence
                    signals={signals}
                    escalations={escalations}
                    rejectionAnalytics={rejectionAnalytics}
                    watchlistAnalytics={watchlistAnalytics}
                    concentrationAnalytics={concentrationAnalytics}
                    metaReports={metaReports}
                    scoutWeights={scoutWeights}
                    calibrationState={calibrationState}
                    onOpenEscalationMemo={handleOpenEscalationMemo}
                  />
                </PanelShell>
              </div>
            ) : (
              <div
                className="flex-1 min-h-0 overflow-y-auto w-full min-w-0 rounded-none border border-oxford/[0.06] bg-paper"
                style={{ scrollbarGutter: 'stable both-edges' }}
              >
                <div className="px-0 pt-2 pb-6 lg:pb-8">
                  <GhostTransition disableLift>
                    <WorkGrid
                      startups={startups}
                      onStartupClick={handleStartupClick}
                      selectedId={selectedStartup?.id ?? null}
                      watchlistIds={watchlistIds}
                    />
                  </GhostTransition>
                </div>
              </div>
            )}
          </div>

          {/* Right zone: Judgements or memo only — never System. */}
          <aside
            className="hidden lg:flex flex-col min-w-0 min-h-0 border border-oxford/[0.06] bg-paper overflow-hidden"
            aria-live="polite"
            aria-label={
              rightPanel === 'feed'
                ? 'Judgements'
                : selectedStartup
                ? 'Investment memo'
                : 'Detail'
            }
          >
            {rightPanel === 'feed' ? (
              <PanelShell
                className="min-h-0 flex-1"
                title="JUDGEMENTS"
                titleClassName={PANEL_CHROME_LABEL_CLASS}
                headerPaddingClass={SYSTEM_MEMO_HEADER_PADDING}
                headerBorderClass=""
                actions={
                  <button
                    type="button"
                    onClick={handleCloseJudgements}
                    className={PANEL_CHROME_ACTION_BTN_CLASS}
                    aria-label="Hide judgements"
                  >
                    CLOSE
                  </button>
                }
                contentOverflowHidden
                contentClassName="flex-1 min-h-0 overflow-hidden"
              >
                <LiveIntelligenceFeed
                  startups={startups}
                  signals={signals}
                  metaReports={metaReports}
                />
              </PanelShell>
            ) : selectedStartup ? (
              <PanelShell
                title=""
                showTitle={false}
                headerPaddingClass={SYSTEM_MEMO_HEADER_PADDING}
                headerBorderClass=""
                headerJustifyClass="justify-end"
                actions={
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => memoContentRef.current?.downloadPDF()}
                      className={PANEL_CHROME_ACTION_BTN_CLASS}
                    >
                      DOWNLOAD PDF
                    </button>
                    <button
                      type="button"
                      onClick={handleCloseMemo}
                      className={PANEL_CHROME_ACTION_BTN_CLASS}
                      aria-label="Close memo"
                    >
                      CLOSE
                    </button>
                  </div>
                }
                contentClassName="flex-1 min-h-0 overflow-y-auto px-5 py-5 sm:px-6 sm:py-6"
              >
                <InvestmentMemoContent ref={memoContentRef} startup={selectedStartup} embedded />
              </PanelShell>
            ) : (
              <div className="flex-1 flex items-center justify-center p-8">
                <p className="type-label-tab text-oxford/25" style={{ transition: 'opacity var(--motion-micro) var(--motion-ease)' }}>
                  Click a deal to open the memo here
                </p>
              </div>
            )}
          </aside>
        </div>
        </div>
      </main>

      {/* Judgements slide-over on mobile only; System swaps into the left column above. */}
      {judgementsAsOverlay && typeof document !== 'undefined' && createPortal(
        <AnimatePresence>
          <motion.div
            key="judgements-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: tokens.motion.duration.medium, ease: tokens.motion.ease }}
            className="fixed inset-0 z-[9999]"
            style={{
              minHeight: '100dvh',
              width: '100vw',
              left: 0,
              top: 0,
              right: 0,
              bottom: 0,
              backgroundColor: '#F2F0EA',
              paddingTop: 'env(safe-area-inset-top)',
              paddingBottom: 'env(safe-area-inset-bottom)',
              paddingLeft: 'env(safe-area-inset-left)',
              paddingRight: 'env(safe-area-inset-right)',
            }}
            onClick={handleCloseJudgements}
            aria-hidden="true"
          />
          <motion.div
            ref={judgementsPanelRef}
            key="judgements-panel"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: tokens.motion.duration.medium, ease: tokens.motion.ease }}
            className="fixed top-0 right-0 w-full max-w-full sm:w-[380px] lg:w-[400px] z-[10000] flex flex-col bg-paper"
            style={{
              borderLeft: tokens.frameBorder,
              minHeight: '100dvh',
              height: '100dvh',
              paddingTop: 'env(safe-area-inset-top)',
              paddingBottom: 'env(safe-area-inset-bottom)',
              paddingRight: 'env(safe-area-inset-right)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <PanelShell
              title="JUDGEMENTS"
              titleClassName={PANEL_CHROME_LABEL_CLASS}
              headerPaddingClass={SYSTEM_MEMO_HEADER_PADDING}
              headerBorderClass=""
              actions={
                <button
                  type="button"
                  onClick={handleCloseJudgements}
                  className={`${PANEL_CHROME_ACTION_BTN_CLASS} min-w-[44px] min-h-[44px] flex items-center justify-center`}
                  aria-label="Close judgements panel"
                >
                  CLOSE
                </button>
              }
              contentOverflowHidden
              contentClassName="flex-1 min-h-0 overflow-hidden"
              className="h-full"
            >
              <LiveIntelligenceFeed
                startups={startups}
                signals={signals}
                metaReports={metaReports}
              />
            </PanelShell>
          </motion.div>
        </AnimatePresence>,
        document.body
      )}

      {/* Memo modal on small viewports; on desktop the right panel shows the memo. */}
      <AnimatePresence initial={false}>
        {useModal && selectedStartup && (
          <InvestmentMemo
            key="memo"
            startup={selectedStartup}
            onClose={handleCloseMemo}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
