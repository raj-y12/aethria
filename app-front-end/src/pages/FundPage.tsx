import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
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
            readouts={
              <div className="flex flex-wrap items-center justify-end gap-x-phi-5 gap-y-phi-2">
                <Link
                  to="/v1/settings"
                  className="type-action shrink-0 text-oxford/55 transition-colors hover:text-oxford btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
                >
                  Edit mandate →
                </Link>
                <FundFacetNav activeTab={activeTab} onTabChange={changeTab} />
              </div>
            }
          />
        </div>
      </div>

      <div
        ref={bodyScrollRef}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain bg-paper"
      >
        <div className={`${workspaceLayout.shell} ${workspaceLayout.pageBottom} pt-phi-6`}>
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
