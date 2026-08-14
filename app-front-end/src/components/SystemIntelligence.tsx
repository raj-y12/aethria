import { useState, useMemo } from 'react';
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
  showRule = true,
}: {
  activeTab: FundFacetTab;
  onTabChange: (tab: FundFacetTab) => void;
  className?: string;
  /** Full-width rule under the tab row (off when chrome sits flush above scroll body). */
  showRule?: boolean;
}) {
  const reduceMotion = usePrefersReducedMotion();

  return (
    <nav
      role="tablist"
      aria-label="Fund facets"
      className={`flex items-center gap-0.5 overflow-x-auto no-scrollbar ${showRule ? 'border-b border-oxford/[0.08]' : ''} ${className}`.trim()}
    >
      {FUND_FACET_TABS.map((tab) => {
        const isActive = activeTab === tab.key;
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onTabChange(tab.key)}
            className={`type-action group relative min-h-[32px] shrink-0 px-phi-4 py-phi-1 cursor-pointer btn-interaction btn-interaction--no-press transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 ${
              isActive ? 'bg-surface-selected text-oxford' : 'text-oxford/65 hover:bg-oxford/[0.04] hover:text-oxford/80'
            }`}
            style={{ transitionTimingFunction: 'var(--motion-ease)' }}
          >
            {isActive ? (
              <motion.span
                layoutId="fund-facet-active"
                className="absolute inset-0 bg-surface-selected"
                transition={reduceMotion ? { duration: 0 } : { duration: 0.3, ease: [0.77, 0, 0.175, 1] }}
                aria-hidden
              />
            ) : null}
            <span className="relative">{tab.label}</span>
          </button>
        );
      })}
    </nav>
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
