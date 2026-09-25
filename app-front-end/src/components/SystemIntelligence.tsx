import { useState, useMemo } from 'react';
import SegmentedPill from './SegmentedPill';
import { motion, type Variants } from 'framer-motion';
import { tokens } from '../design-system/tokens';
import type { FundThesisRuntime } from '../api/fundThesis';
import type { FundIntelligenceData } from '../hooks/useFundIntelligence';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';

/**
 * The three Fund facets, ordered by how an investor reads the instrument:
 * what it hunts (Mandate), what the evidence says (Intelligence), and how the
 * system learns from outcomes (Learning). Portfolio owns the record; Flow owns
 * active judgement and review work.
 */
export type FundFacetTab = 'intelligence' | 'thesis' | 'learning';
type Tab = FundFacetTab;
export const FUND_FACET_TABS: readonly { key: Tab; label: string }[] = [
  { key: 'thesis', label: 'Mandate' },
  { key: 'intelligence', label: 'Intelligence' },
  { key: 'learning', label: 'Learning' },
];

export function isFundFacetTab(value: string | null): value is FundFacetTab {
  return FUND_FACET_TABS.some((tab) => tab.key === value);
}

export function FundFacetNav({
  activeTab,
  onTabChange,
  className = '',
}: {
  activeTab: FundFacetTab;
  onTabChange: (tab: FundFacetTab) => void;
  className?: string;
}) {
  return (
    <SegmentedPill
      options={FUND_FACET_TABS}
      value={activeTab}
      onChange={onTabChange}
      label="Fund facets"
      layoutId="fund-facet-active"
      className={className}
    />
  );
}

interface SystemIntelligenceProps {
  activeTab?: FundFacetTab;
  onTabChange?: (tab: FundFacetTab) => void;
  hideNav?: boolean;
  fundThesisRuntime: FundThesisRuntime | null;
  fundThesisRuntimeLoading?: boolean;
  fundThesisRuntimeError?: string | null;
  fundIntelligence: FundIntelligenceData;
}

import {
  TAB_CONTENT_CONTAINER_VARIANTS,
  InstitutionalMandateTab,
} from './system/internals';
import { FundHypothesesPanel, FundObservationsPanel } from './fund/FundIntelligenceSurface';

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
    <div className="flex w-full flex-1 flex-col font-sans bg-surface-canvas selection:bg-oxford selection:text-paper">
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
        className="flex flex-1 flex-col"
      >
          {activeTab === 'intelligence' && (
            <FundObservationsPanel data={props.fundIntelligence} />
          )}
          {activeTab === 'thesis' && (
            <InstitutionalMandateTab
              data={props.fundThesisRuntime}
              loading={props.fundThesisRuntimeLoading}
              error={props.fundThesisRuntimeError}
            />
          )}
          {activeTab === 'learning' && (
            <FundHypothesesPanel data={props.fundIntelligence} />
          )}
      </motion.div>
    </div>
  );
}
