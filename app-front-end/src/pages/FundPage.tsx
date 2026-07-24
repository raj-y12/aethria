import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import RoomHeader from '../components/RoomHeader';
import { workspaceLayout } from '../design-system/workspaceLayout';
import SystemIntelligence, { FundFacetNav, type FundFacetTab } from '../components/SystemIntelligence';
import { useFundConfiguration, useCountUp } from '../hooks';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup } from '../types/startup';

/**
 * A readout counts up when given a numeric `value` (with optional suffix like
 * "%"); pass `text` instead for values that don't count sensibly (signed drift).
 */
function HeaderReadout({ label, value, suffix, text }: { label: string; value?: number | null; suffix?: string; text?: string }) {
  const shown = useCountUp(value ?? 0);
  const display = text != null ? text : value == null ? '--' : `${shown.toLocaleString()}${suffix ?? ''}`;
  return (
    <div className="flex flex-col gap-phi-1 bg-paper px-phi-4 py-phi-3">
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
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<FundFacetTab>('thesis');
  const bodyScrollRef = useRef<HTMLDivElement>(null);
  const { configuration: fundConfiguration } = useFundConfiguration(data.settings);

  useEffect(() => {
    bodyScrollRef.current?.scrollTo({ top: 0 });
  }, [activeTab]);
  const runtime = data.fundThesisRuntime;

  const fundName =
    data.settings?.fund_identity?.fund_name?.trim() ||
    (runtime?.active_version_number != null ? `Fund Thesis v${runtime.active_version_number}` : 'Fund');

  const openDeal = (startup: Startup) => navigate(`/v1/flow?open=${startup.id}`);
  const stats = runtime?.alignment_stats;

  return (
    <div className="page-transition-enter flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex-none bg-paper">
        <div className={`${workspaceLayout.shell} ${workspaceLayout.pageTop}`}>
          <RoomHeader
            className={workspaceLayout.headerBottom}
            eyebrow={`The instrument${
              runtime?.active_version_number != null ? ` · Mandate v${runtime.active_version_number}` : ''
            }`}
            title={fundName}
            plateIndex="04 — 04"
            sub={
              <Link
                to="/v1/settings"
                className="type-action inline-block transition-colors hover:text-oxford btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
              >
                Edit mandate →
              </Link>
            }
            readouts={
              // Record-plate dims cells — 1px section-divider grid lines via the
              // gap+background trick (marketing `.dims` pattern), cells on bg-paper.
              <div className="grid grid-cols-2 gap-px border border-[var(--section-divider)] bg-[var(--section-divider)] sm:grid-cols-4">
                <HeaderReadout label="Mandate match" value={pctNum(stats?.pct_matching_thesis)} suffix="%" />
                <HeaderReadout label="Mean alignment" value={pctNum(stats?.avg_alignment_score)} suffix="%" />
                <HeaderReadout label="Drift" text={drift(stats?.drift_vs_previous)} />
                <HeaderReadout label="Reviewed" value={stats?.reviewed_with_thesis_count ?? null} />
              </div>
            }
          />
          <FundFacetNav activeTab={activeTab} onTabChange={setActiveTab} showRule={false} className="pt-phi-3" />
        </div>
      </div>

      <div
        ref={bodyScrollRef}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain bg-paper"
      >
        <div className={`${workspaceLayout.shell} ${workspaceLayout.pageBottom} pt-phi-3`}>
          <SystemIntelligence
            activeTab={activeTab}
            onTabChange={setActiveTab}
            hideNav
            startups={data.startups}
            onStartupClick={openDeal}
            selectedStartupId={null}
            rejectionAnalytics={data.rejectionAnalytics}
            watchlistAnalytics={data.watchlistAnalytics}
            concentrationAnalytics={data.concentrationAnalytics}
            systemHealth={data.systemHealth}
            systemStatus={data.systemStatus}
            metaReports={data.metaReports}
            scoutWeights={data.scoutWeights}
            calibrationState={data.calibrationState}
            metaPromptState={data.metaPromptState}
            metaEvalSet={data.metaEvalSet}
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
