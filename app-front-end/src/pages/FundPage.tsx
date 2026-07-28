import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import RoomHeader from '../components/RoomHeader';
import { workspaceLayout } from '../design-system/workspaceLayout';
import SystemIntelligence, { FundFacetNav, isFundFacetTab, type FundFacetTab } from '../components/SystemIntelligence';
import { useFundConfiguration, useCountUp } from '../hooks';
import type { SystemData } from '../hooks/useSystemData';

/**
 * A readout counts up when given a numeric `value` (with optional suffix like
 * "%"); pass `text` instead for values that don't count sensibly (signed drift).
 */
function HeaderReadout({ label, value, suffix, text }: { label: string; value?: number | null; suffix?: string; text?: string }) {
  const shown = useCountUp(value ?? 0);
  const display = text != null ? text : value == null ? '--' : `${shown.toLocaleString()}${suffix ?? ''}`;
  return (
    <div className="flex flex-col gap-phi-1">
      <span className="type-data text-[clamp(22px,2vw,30px)] leading-none tabular-nums text-oxford">
        {display}
      </span>
      <span className="type-label-section">{label}</span>
    </div>
  );
}

function pctNum(v: number | null | undefined): number | null {
  if (v == null || Number.isNaN(v)) return null;
  return Math.round(v <= 1 ? v * 100 : v);
}

function drift(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '--';
  const r = Math.round(v * 100) / 100;
  return r > 0 ? `+${r.toFixed(2)}` : r.toFixed(2);
}

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
  const { configuration: fundConfiguration } = useFundConfiguration(data.settings);

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

  const stats = runtime?.alignment_stats;

  return (
    <div className="page-transition-enter flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex-none bg-paper">
        <div className={`${workspaceLayout.shell} ${workspaceLayout.pageTop}`}>
          <RoomHeader
            className={`border-b border-oxford/[0.075] ${workspaceLayout.headerBottom}`}
            eyebrow="The instrument"
            title={fundName}
            readouts={
              <div className="flex flex-wrap items-end gap-x-phi-7 gap-y-phi-4">
                <HeaderReadout label="Mandate match" value={pctNum(stats?.pct_matching_thesis)} suffix="%" />
                <HeaderReadout label="Mean alignment" value={pctNum(stats?.avg_alignment_score)} suffix="%" />
                <HeaderReadout label="Drift" text={drift(stats?.drift_vs_previous)} />
                <HeaderReadout label="Reviewed" value={stats?.reviewed_with_thesis_count ?? null} />
              </div>
            }
          />
          <div className="flex flex-wrap items-center justify-between gap-x-phi-4 gap-y-phi-2 pt-phi-3">
            <FundFacetNav activeTab={activeTab} onTabChange={changeTab} showRule={false} />
            <Link
              to="/v1/settings"
              className="type-action shrink-0 border-b border-oxford/20 pb-0.5 text-oxford/65 transition-colors hover:border-oxford/40 hover:text-oxford btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
            >
              Edit mandate →
            </Link>
          </div>
        </div>
      </div>

      <div
        ref={bodyScrollRef}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain bg-paper"
      >
        <div className={`${workspaceLayout.shell} ${workspaceLayout.pageBottom} pt-phi-3`}>
          <SystemIntelligence
            activeTab={activeTab}
            onTabChange={changeTab}
            hideNav
            startups={data.startups}
            rejectionAnalytics={data.rejectionAnalytics}
            metaReports={data.metaReports}
            metaInsights={data.metaInsights}
            fundThesisRuntime={data.fundThesisRuntime}
            fundThesisRuntimeLoading={data.fundThesisRuntimeLoading}
            fundThesisRuntimeError={data.fundThesisRuntimeError}
            fundConfiguration={fundConfiguration}
          />
        </div>
      </div>
    </div>
  );
}
