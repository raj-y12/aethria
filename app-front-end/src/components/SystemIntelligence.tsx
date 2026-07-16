import { useState, useMemo } from 'react';
import { motion, type Variants } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import type {
  Startup, RejectionAnalytics, WatchlistAnalytics,
  ConcentrationAnalytics, MetaCycleReport, MetaPromptState, MetaEvalSet, ScoutWeights, CalibrationState,
  SystemHealthSnapshot, MetaInsightsPayload,
} from '../types/startup';
import type { FundThesisRuntime } from '../api/fundThesis';
import type { SystemStatus } from '../api/system';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';
import { type FundConfiguration } from '../lib/fundConfiguration';
import IdentityReviewQueue from './identity/IdentityReviewQueue';

/**
 * The five facets of the instrument, ordered by how an investor reads it:
 * what it hunts (Mandate), what the human ruled (Record), what its decisions
 * show (Patterns), how tightly it is tuned (Calibration), how it rewrites
 * itself (Evolution). Signals live in Portfolio, where they act on conviction.
 */
export type FundFacetTab = 'analytics' | 'decisions' | 'calibration' | 'thesis' | 'meta';
type Tab = FundFacetTab;
const TABS: { key: Tab; label: string }[] = [
  { key: 'thesis', label: 'Mandate' },
  { key: 'decisions', label: 'Record' },
  { key: 'analytics', label: 'Patterns' },
  { key: 'calibration', label: 'Calibration' },
  { key: 'meta', label: 'Evolution' },
];

export function FundFacetNav({
  activeTab,
  onTabChange,
  className = '',
  showRule = true,
}: {
  activeTab: FundFacetTab;
  onTabChange: (tab: FundFacetTab) => void;
  className?: string;
  /** Full-width rule under the tab row (off when chrome sits flush above scroll body). */
  showRule?: boolean;
}) {
  return (
    <nav
      role="tablist"
      aria-label="Fund facets"
      className={`flex items-center gap-phi-5 overflow-x-auto no-scrollbar ${showRule ? 'border-b border-oxford/[0.08]' : ''} ${className}`.trim()}
    >
      {TABS.map((tab) => {
        const isActive = activeTab === tab.key;
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onTabChange(tab.key)}
            className={`relative -mb-px shrink-0 border-b pb-phi-3 pt-phi-1 type-label-tab transition-colors btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${
              isActive
                ? 'border-oxford font-semibold text-oxford'
                : 'border-transparent font-normal text-oxford/60 hover:text-oxford/70'
            }`}
          >
            {tab.label}
          </button>
        );
      })}
    </nav>
  );
}

interface SystemIntelligenceProps {
  startups: Startup[];
  onStartupClick?: (startup: Startup) => void;
  selectedStartupId?: string | null;
  activeTab?: FundFacetTab;
  onTabChange?: (tab: FundFacetTab) => void;
  hideNav?: boolean;
  rejectionAnalytics: RejectionAnalytics;
  watchlistAnalytics: WatchlistAnalytics;
  concentrationAnalytics: ConcentrationAnalytics;
  systemHealth: SystemHealthSnapshot | null;
  systemStatus?: SystemStatus | null;
  metaReports: MetaCycleReport[];
  scoutWeights: ScoutWeights;
  calibrationState: CalibrationState;
  metaPromptState: MetaPromptState;
  metaEvalSet: MetaEvalSet;
  metaInsights: MetaInsightsPayload | null;
  fundThesisRuntime: FundThesisRuntime | null;
  fundThesisRuntimeLoading?: boolean;
  fundThesisRuntimeError?: string | null;
  fundConfiguration?: FundConfiguration;
}

import {
  TAB_CONTENT_CONTAINER_VARIANTS,
  DecisionsTab,
  CalibrationTab,
  AnalyticsTab,
  InstitutionalMandateTab,
  MetaCommandTab,
} from './system/internals';

export default function SystemIntelligence(props: SystemIntelligenceProps) {
  const [internalTab, setInternalTab] = useState<Tab>('thesis');
  const activeTab = props.activeTab ?? internalTab;
  const setActiveTab = props.onTabChange ?? setInternalTab;
  const reduceMotion = usePrefersReducedMotion();
  const tabContentContainerVariants = useMemo(
    (): Variants | undefined => (reduceMotion ? undefined : TAB_CONTENT_CONTAINER_VARIANTS),
    [reduceMotion]
  );

  return (
    <div className="w-full font-sans bg-surface-canvas selection:bg-oxford selection:text-paper min-h-full">
      {!props.hideNav ? (
        <div className="sticky top-0 z-20 bg-surface-canvas pt-phi-3">
          <FundFacetNav activeTab={activeTab} onTabChange={setActiveTab} />
        </div>
      ) : null}

      <motion.div
        key={activeTab}
        initial={reduceMotion ? false : 'hidden'}
        animate="visible"
        transition={transitionOrReduced(reduceMotion, { duration: 0.2, ease: tokens.motion.ease })}
        variants={tabContentContainerVariants}
      >
          {activeTab === 'analytics' && (
            <AnalyticsTab
              rejection={props.rejectionAnalytics}
              watchlist={props.watchlistAnalytics}
              concentration={props.concentrationAnalytics}
              systemHealth={props.systemHealth}
              systemStatus={props.systemStatus}
            />
          )}
          {activeTab === 'decisions' && (
            <DecisionsTab
              startups={props.startups}
              onStartupClick={props.onStartupClick}
              selectedStartupId={props.selectedStartupId}
            />
          )}
          {activeTab === 'calibration' && (
            <div className="space-y-phi-6">
              <IdentityReviewQueue compact />
              <CalibrationTab startups={props.startups} fundConfiguration={props.fundConfiguration} />
            </div>
          )}
          {activeTab === 'thesis' && (
            <InstitutionalMandateTab
              data={props.fundThesisRuntime}
              loading={props.fundThesisRuntimeLoading}
              error={props.fundThesisRuntimeError}
            />
          )}
          {activeTab === 'meta' && (
            <MetaCommandTab
              reports={props.metaReports}
              weights={props.scoutWeights}
              calibration={props.calibrationState}
              promptState={props.metaPromptState}
              metaEvalSet={props.metaEvalSet}
              insights={props.metaInsights}
              fundConfiguration={props.fundConfiguration}
            />
          )}
      </motion.div>
    </div>
  );
}
