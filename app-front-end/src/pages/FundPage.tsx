import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import RoomHeader from '../components/RoomHeader';
import { workspaceLayout } from '../design-system/workspaceLayout';
import SystemIntelligence, { FundFacetNav, isFundFacetTab, type FundFacetTab } from '../components/SystemIntelligence';
import { useFundIntelligence } from '../hooks';
import type { SystemData } from '../hooks/useSystemData';

/**
 * Fund — the instrument itself. Chrome (room header + facet tabs) sits in a
 * fixed top band; only the tab panels scroll beneath it.
 */
export default function FundPage({ data }: { data: SystemData }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get('tab');
  const [activeTab, setActiveTab] = useState<FundFacetTab>(() =>
    isFundFacetTab(requestedTab) ? requestedTab : 'thesis'
  );
  const bodyScrollRef = useRef<HTMLDivElement>(null);
  const fundIntelligence = useFundIntelligence(activeTab === 'intelligence' || activeTab === 'learning');

  useEffect(() => {
    bodyScrollRef.current?.scrollTo({ top: 0 });
  }, [activeTab]);
  useEffect(() => {
    if (isFundFacetTab(requestedTab)) {
      setActiveTab(requestedTab);
      return;
    }
    if (requestedTab != null) {
      setSearchParams((current) => {
        current.delete('tab');
        return current;
      }, { replace: true });
    }
  }, [requestedTab, setSearchParams]);

  const changeTab = (tab: FundFacetTab) => {
    setActiveTab(tab);
    setSearchParams((current) => {
      current.set('tab', tab);
      return current;
    }, { replace: true });
  };
  const runtime = data.fundThesisRuntime;

  const fundName =
    data.settings?.fund_identity?.fund_name?.trim() ||
    (runtime?.active_version_number != null ? `Fund Thesis v${runtime.active_version_number}` : 'Fund');


  return (
    <div className="aethria-fund paper-dot-grid page-transition-enter flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex-none bg-surface-canvas/95">
        <div className={`${workspaceLayout.shell} ${workspaceLayout.pageTop}`}>
          <RoomHeader
            className={workspaceLayout.headerBottom}
            eyebrow="The instrument"
            title={fundName}
            readouts={<FundFacetNav activeTab={activeTab} onTabChange={changeTab} />}
          />
        </div>
      </div>

      <div
        ref={bodyScrollRef}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain bg-paper"
      >
        {/* min-h-full + flex: the mandate tab stretches to the viewport and its
            terms grid takes the leftover height, so it fits without scrolling.
            Longer tabs (intelligence, learning) still scroll. */}
        <div className={`${workspaceLayout.shell} ${workspaceLayout.pageBottom} flex min-h-full flex-col pt-phi-5`}>
          <SystemIntelligence
            activeTab={activeTab}
            onTabChange={changeTab}
            hideNav
            fundThesisRuntime={data.fundThesisRuntime}
            fundThesisRuntimeLoading={data.fundThesisRuntimeLoading}
            fundThesisRuntimeError={data.fundThesisRuntimeError}
            fundIntelligence={fundIntelligence}
          />
        </div>
      </div>
    </div>
  );
}
